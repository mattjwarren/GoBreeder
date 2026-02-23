# go_vm_rs

Rust/PyO3 re-implementation of the GoBreeder VM (`vm.py`), providing a
`get_move` function that is a drop-in replacement for `GoVM.get_move()`.

## Measured speedup

~127× faster than the pure-Python VM on a 1024-instruction genome with 4000 clock cycles
(0.18 ms vs 23 ms per call on a typical x86-64 desktop).

## Exposed API

```python
import go_vm_rs

move, pc_history = go_vm_rs.get_move(board, player, program)
```

| Argument  | Type | Description |
|-----------|------|-------------|
| `board`   | `dict[(x,y), int]` | Board state: -1 black, 0 empty, 1 white |
| `player`  | `str` | `"black"` or `"white"` |
| `program` | `GoGenome` or `list` | Genome object (`.dna` extracted) or raw DNA list |

Returns `((x, y), pc_history_list)` — identical to the Python `GoVM.get_move` signature.

## Building

Requires the Rust toolchain (install via [rustup](https://rustup.rs)) and `maturin`.

```bash
# Install maturin into the project venv
uv pip install maturin

# Development build (fast compile, debug symbols)
cd go_vm_rs && maturin develop

# Release build (full opt-level 3 + LTO — use for production)
cd go_vm_rs && maturin develop --release
```

The wheel is installed directly into the project venv so `import go_vm_rs` works
from anywhere in the project.

## Integration

`GoBreeder/breed/vm.py` automatically uses the Rust extension when available:

```python
try:
    import go_vm_rs as _go_vm_rs
    _RUST_VM_AVAILABLE = True
except ImportError:
    _go_vm_rs = None
    _RUST_VM_AVAILABLE = False
```

If `go_vm_rs` is not importable (e.g. on a fresh checkout before building),
`GoVM.get_move` falls back transparently to the pure-Python implementation.
