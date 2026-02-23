"""Benchmark: Rust VM vs pure-Python VM for a single get_move call.

Run from the project root:
    uv run python adhoc_scripts/bench_vm.py
"""

import sys
import time

sys.path.insert(0, "GoBreeder/breed")

import config  # noqa: E402
import go_vm_rs  # noqa: E402
import vm as vm_module  # noqa: E402
from data_structures import GoGenome  # noqa: E402

ITERATIONS = 500


def _empty_board():
    return {(x, y): 0 for x in range(config.board_size) for y in range(config.board_size)}


def main():
    board = _empty_board()
    genome = GoGenome()  # random 1024-instruction genome

    # --- Rust ---
    t0 = time.perf_counter()
    for _ in range(ITERATIONS):
        go_vm_rs.get_move(board, "black", genome)
    rust_elapsed = time.perf_counter() - t0

    # --- Pure Python ---
    # Temporarily disable Rust path
    orig = vm_module._RUST_VM_AVAILABLE
    vm_module._RUST_VM_AVAILABLE = False
    python_vm = vm_module.GoVM()
    t0 = time.perf_counter()
    for _ in range(ITERATIONS):
        python_vm.get_move(board=board, player="black", program=genome)
    python_elapsed = time.perf_counter() - t0
    vm_module._RUST_VM_AVAILABLE = orig

    print(f"Iterations       : {ITERATIONS}")
    print(f"Rust total        : {rust_elapsed*1000:.1f} ms  "
          f"({rust_elapsed/ITERATIONS*1000:.3f} ms/call)")
    print(f"Pure Python total : {python_elapsed*1000:.1f} ms  "
          f"({python_elapsed/ITERATIONS*1000:.3f} ms/call)")
    print(f"Speedup           : {python_elapsed/rust_elapsed:.1f}×")


if __name__ == "__main__":
    main()
