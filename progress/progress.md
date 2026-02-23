# GoBreeder GUI Progress

## Last Updated: 2026-02-23

## Current Branch: recode

## Overall Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1-4   | Core GUI (deployments, breeding runs, VM inspector) | Complete |
| 5     | Archive Management UI | Complete |
| 6     | Population Library | Complete |
| Bug   | Breeding run correctness + log verbosity fixes | Complete |
| Recode | Rust VM acceleration (`go_vm_rs`) | **Complete** |
| GoSumi  | Bytecode-patch for 10× faster games | **Complete** |

## Recent Work (2026-02-23)

### GoSumi fast JAR (`gosumi_2013_fast.jar`)

Bytecode-patched `gosumi_2013.jar` for ~10× faster per-move search, enabling shorter
timeouts per game and dramatically faster training throughput.

**Benchmark result: 600 ms/move → 56 ms/move (10.6× speedup)**

Key changes:
- `adhoc_scripts/patch_gosumi_jar.py` — Python script that patches `GoSumi.class` in-place
  using pure bytecode manipulation (no Java source needed).
- Three patches applied:
  1. Timeout multiplier `sipush 1000 → sipush 100` — `-timeout 1` now means 100 ms/move
     instead of 1000 ms/move.
  2. Default max_time `sipush 28000 → sipush 2000` — fallback (no `-timeout`) is 2 s not 28 s.
  3. `GOSUMI_9x9_DEF_DEPTH {8,12,16} → {4,6,8}` — shallower search terminates by depth
     sooner, complementing the smaller time budget.
- `GoBreeder/breed/java/gosumi_2013_fast.jar` added.
- `GoBreeder/breed/config.py` updated: `enemy_program` now points to `gosumi_2013_fast.jar`
  (both module-level and inside `set_basepath()`); original jar retained for reference.
- Move quality impact minimal for the opening/mid-game (first 8–9 moves identical in
  benchmark runs); diverges slightly in the endgame, which is acceptable for training.

### Rust VM acceleration (`go_vm_rs`)

Re-implemented the VM execution engine in Rust + PyO3 as `go_vm_rs/`.

**Result: ~127× faster `get_move` calls** (0.18 ms vs 23 ms on a 1024-instruction genome,
4000 clock cycles, release build, x86-64).

Key changes:
- New Rust crate at `go_vm_rs/` — build with `maturin develop --release` from that directory.
- `GoBreeder/breed/vm.py` delegates `get_move` to `go_vm_rs.get_move()` when available; falls
  back silently to the pure-Python engine if the wheel is not installed.
- Fixed pre-existing Python 3 port bug in `opcode_div`: `A / B` (float) → `A // B` (integer),
  matching the original Python 2 semantics and the Rust implementation.
- All 277 tests pass (branch `recode`).



1. **`vm.logging=False` crash** (`bb04159`) — `mediator.py` line 46 was setting
   `vm.logging = False` (an attribute on the *module* object), replacing `vm`'s
   `import logging` binding with `False`.  Any subsequent `logging.getLogger()`
   call inside `vm.py` then crashed with `AttributeError: 'bool' object has no
   attribute 'getLogger'`.  Fix: deleted the line entirely.

2. **Result always `?` when player dies mid-game** (`dde651d`) — `ref_v0.1_exe`
   emits `R<< ? Black move failed - White has won` as a GTP error body.  The
   primary parser only accepts non-empty `<< = <score>` responses, so
   `result_str` stayed `?`.  Fix: added a secondary scan of `serr_lines` for
   `"white has won"` / `"black has won"` (case-insensitive) that synthesises
   `"W+R"` or `"B+R"`.

3. **Log verbosity** (`4c17d73`) — all messages previously went to `_logger.debug()`
   meaning every game dumped MB of GTP dialogue to `gobreeder.log`.  Fix:
   - `setup_logging` default changed to `logging.INFO`
   - Resurrections, pop size, final board, game result, evaluation summary
     promoted to `_logger.info()` — always visible
   - subprocess stderr dump + result-parsing context list-comprehension gated
     on `_logger.isEnabledFor(logging.DEBUG)` so the multi-MB work is never
     even started at INFO level

See [phase5_6_progress.md](phase5_6_progress.md) for earlier phase details.

## Key Files

- `GoBreeder/breed/mediator.py` — `final_score` handler now renders board
- `GoBreeder/breed/breeder.py` — full serr DEBUG logging restored; imports sorted
- `GoBreeder/gui/models/population_library.py` — Phase 6 model
- `GoBreeder/gui/panels/archive_manager_panel.py` — Phase 5+6 panel
- `GoBreeder/gui/panels/population_library_panel.py` — Phase 6 panel
- `tests/gui/test_population_library.py` — 20 tests, all passing

## Test Status

277 tests, all passing. ruff clean, mypy clean.
