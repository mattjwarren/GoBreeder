# GoBreeder GUI Progress

## Last Updated: 2026-06-08

## Current Branch: GUI

## Overall Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1-4   | Core GUI (deployments, breeding runs, VM inspector) | Complete |
| 5     | Archive Management UI | Complete |
| 6     | Population Library | Complete |
| Bug   | Breeding run correctness + log verbosity fixes | Complete |

## Recent Work (2026-06-08)

Three breeding-run bugfixes made in this session (all 277 tests pass):

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
