"""
Bytecode-patch gosumi_2013.jar to produce a faster variant:

Patches applied to GoSumi.class:
  1. Timeout multiplier: sipush 1000 → sipush <new_multiplier>
     - genmove uses: max_time = timeout_arg * multiplier (ms)
     - Default timeout_arg = 1 (via -timeout 1 in config)
     - With multiplier=100:  -timeout 1 → 100ms/move  (10× faster)
     - With multiplier=200:  -timeout 1 → 200ms/move  (5× faster)
     - With multiplier=500:  -timeout 1 → 500ms/move  (2× faster)

  2. Default max_time: sipush 28000 → sipush <new_default>
     - Used when -timeout not specified (or -timeout 0)
     - Changed to 2000 (2 seconds) to prevent runaway search

  3. GOSUMI_9x9_DEF_DEPTH: {8, 12, 16} → {4, 6, 8}
     - Minimax search depths for early/mid/late game phases
     - Shallower depth means faster termination even within the time limit
     - For training purposes a weaker-but-faster opponent is preferred

Usage:
    python3 patch_gosumi_jar.py [--multiplier N] [--default-ms N] [--reduce-depth] [--output FILE]
"""

import argparse
import io
import struct
import zipfile
from pathlib import Path


JAR_DIR = Path(__file__).parent.parent / "GoBreeder" / "breed" / "java"
SOURCE_JAR = JAR_DIR / "gosumi_2013.jar"


def find_unique(data: bytes, pattern: bytes, label: str) -> int:
    """Find a pattern that must appear exactly once; raise if not."""
    positions = []
    pos = 0
    while True:
        idx = data.find(pattern, pos)
        if idx == -1:
            break
        positions.append(idx)
        pos = idx + 1
    if len(positions) == 0:
        raise ValueError(f"Pattern {pattern.hex()} not found for {label}")
    if len(positions) > 1:
        raise ValueError(
            f"Pattern {pattern.hex()} found {len(positions)} times for {label}; "
            "expected 1. Offsets: " + ", ".join(hex(p) for p in positions)
        )
    return positions[0]


def sipush(value: int) -> bytes:
    """Encode a sipush instruction for the given value (−32768..32767)."""
    if not (-32768 <= value <= 32767):
        raise ValueError(f"Value {value} out of range for sipush")
    return bytes([0x11]) + struct.pack(">h", value)


def bipush(value: int) -> bytes:
    """Encode a bipush instruction for the given value (−128..127)."""
    if not (-128 <= value <= 127):
        raise ValueError(f"Value {value} out of range for bipush")
    return bytes([0x10, value & 0xFF])


def patch_gosumi_class(
    data: bytes,
    multiplier: int,
    default_ms: int,
    reduce_depth: bool,
) -> bytes:
    data = bytearray(data)

    # ------------------------------------------------------------------
    # Patch 1: timeout multiplier  sipush 1000 → sipush <multiplier>
    # Context (from genmove bytecode):
    #   ifle +13                    (skip if timeout arg <= 0)
    #   sipush 1000                 ← patch THIS
    #   aload_0
    #   getfield #160 (timeout)
    #   imul
    #   istore 4
    # Unique discriminator: ifle(9e 00 0d) + sipush 1000(11 03 e8) + aload_0(2a)
    # ------------------------------------------------------------------
    ctx_pattern = bytes([0x9E, 0x00, 0x0D]) + sipush(1000) + bytes([0x2A])
    ctx_idx = find_unique(bytes(data), ctx_pattern, "timeout multiplier context")
    mult_offset = ctx_idx + 3  # skip the ifle(3 bytes) to reach sipush bytes
    old_sipush = sipush(1000)
    new_sipush = sipush(multiplier)
    assert data[mult_offset: mult_offset + 3] == bytearray(old_sipush), (
        f"Expected {old_sipush.hex()} at {mult_offset:#x}, "
        f"got {bytes(data[mult_offset:mult_offset+3]).hex()}"
    )
    data[mult_offset: mult_offset + 3] = new_sipush
    print(f"  [OK] Timeout multiplier: sipush 1000 → sipush {multiplier} at offset {mult_offset:#x}")

    # ------------------------------------------------------------------
    # Patch 2: default max_time  sipush 28000 → sipush <default_ms>
    # Context: goto(a7 00 45) + sipush 28000(11 6d 60)
    # ------------------------------------------------------------------
    ctx2_pattern = bytes([0xA7, 0x00, 0x45]) + sipush(28000)
    ctx2_idx = find_unique(bytes(data), ctx2_pattern, "default max_time context")
    def2_offset = ctx2_idx + 3
    old_def = sipush(28000)
    new_def = sipush(default_ms)
    assert data[def2_offset: def2_offset + 3] == bytearray(old_def), (
        f"Expected {old_def.hex()} at {def2_offset:#x}, "
        f"got {bytes(data[def2_offset:def2_offset+3]).hex()}"
    )
    data[def2_offset: def2_offset + 3] = new_def
    print(f"  [OK] Default max_time: sipush 28000 → sipush {default_ms} at offset {def2_offset:#x}")

    # ------------------------------------------------------------------
    # Patch 3: GOSUMI_9x9_DEF_DEPTH {8, 12, 16} → {4, 6, 8}
    # Constructor bytecode sequence:
    #   newarray int (bc 0a)
    #   dup + iconst_0 + bipush 8  + iastore (59 03 10 08 4f)
    #   dup + iconst_1 + bipush 12 + iastore (59 04 10 0c 4f)
    #   dup + iconst_2 + bipush 16 + iastore (59 05 10 10 4f)
    # ------------------------------------------------------------------
    if reduce_depth:
        depth_pattern = (
            bytes([0xBC, 0x0A])          # newarray int
            + bytes([0x59, 0x03])        # dup, iconst_0
            + bipush(8)                  # bipush 8
            + bytes([0x4F])              # iastore
            + bytes([0x59, 0x04])        # dup, iconst_1
            + bipush(12)                 # bipush 12
            + bytes([0x4F])              # iastore
            + bytes([0x59, 0x05])        # dup, iconst_2
            + bipush(16)                 # bipush 16
            + bytes([0x4F])              # iastore
        )
        depth_idx = find_unique(bytes(data), depth_pattern, "GOSUMI_9x9_DEF_DEPTH init")
        # Offsets of the three depth value bytes within the pattern:
        #   bytes: bc 0a  59 03  10 08  4f  59 04  10 0c  4f  59 05  10 10  4f
        #   index:  0  1   2  3   4  5   6   7  8   9 10  11  12 13  14 15  16
        d0_off = depth_idx + 5   # byte 5 = value byte of bipush 8
        d1_off = depth_idx + 10  # byte 10 = value byte of bipush 12
        d2_off = depth_idx + 15  # byte 15 = value byte of bipush 16
        assert data[d0_off] == 8,  f"Expected depth 8 at {d0_off:#x}, got {data[d0_off]}"
        assert data[d1_off] == 12, f"Expected depth 12 at {d1_off:#x}, got {data[d1_off]}"
        assert data[d2_off] == 16, f"Expected depth 16 at {d2_off:#x}, got {data[d2_off]}"
        data[d0_off] = 4
        data[d1_off] = 6
        data[d2_off] = 8
        print(f"  [OK] GOSUMI_9x9_DEF_DEPTH: {{8,12,16}} → {{4,6,8}} at offsets "
              f"{d0_off:#x}, {d1_off:#x}, {d2_off:#x}")
    else:
        print("  [--] GOSUMI_9x9_DEF_DEPTH: unchanged (use --reduce-depth to enable)")

    return bytes(data)


def patch_jar(
    source_jar: Path,
    output_jar: Path,
    multiplier: int,
    default_ms: int,
    reduce_depth: bool,
) -> None:
    print(f"\nPatching {source_jar.name} → {output_jar.name}")
    print(f"  multiplier={multiplier}  default_ms={default_ms}  reduce_depth={reduce_depth}")

    buf = io.BytesIO()
    with zipfile.ZipFile(source_jar, "r") as src, zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            raw = src.read(item.filename)
            if item.filename == "GoSumi.class":
                print(f"\nPatching GoSumi.class ({len(raw)} bytes):")
                raw = patch_gosumi_class(raw, multiplier, default_ms, reduce_depth)
                print(f"  Patched size: {len(raw)} bytes")
            dst.writestr(item, raw)

    output_jar.write_bytes(buf.getvalue())
    print(f"\nWrote {output_jar} ({output_jar.stat().st_size} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bytecode-patch gosumi_2013.jar to create a faster variant."
    )
    parser.add_argument(
        "--multiplier", type=int, default=100,
        help="Timeout multiplier in ms (default 100; original=1000). "
             "-timeout 1 → multiplier ms/move."
    )
    parser.add_argument(
        "--default-ms", type=int, default=2000,
        help="Default max_time ms when -timeout not given (default 2000; original=28000)."
    )
    parser.add_argument(
        "--reduce-depth", action="store_true", default=True,
        help="Reduce GOSUMI_9x9_DEF_DEPTH from {8,12,16} to {4,6,8} (default: enabled)."
    )
    parser.add_argument(
        "--no-reduce-depth", action="store_false", dest="reduce_depth",
        help="Don't change the search depths."
    )
    parser.add_argument(
        "--output", type=Path,
        default=JAR_DIR / "gosumi_2013_fast.jar",
        help="Output jar path."
    )
    args = parser.parse_args()

    patch_jar(
        source_jar=SOURCE_JAR,
        output_jar=args.output,
        multiplier=args.multiplier,
        default_ms=args.default_ms,
        reduce_depth=args.reduce_depth,
    )


if __name__ == "__main__":
    main()
