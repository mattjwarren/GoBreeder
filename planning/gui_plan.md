# GoBreeder PySide6 GUI — Implementation Plan

**Date:** 2026-02-22  
**Status:** Planning

---

## Overview

This document describes a phased plan for adding a PySide6 desktop GUI to the GoBreeder application. The GUI covers four functional areas:

1. **Deployment management** — create/delete/configure breeding deployment instances.
2. **Breeding run management** — start/stop concurrent breeding runs, monitor progress.
3. **VM inspector / debugger** — load a genome, view and step through VM execution.
4. **Archive & population library** — browse run archives, extract genomes, compose new populations, inject them into deployments.

The implementation is split into six phases. Each phase produces working, tested code before the next begins.

---

## Background: key implementation facts

### Deployments

A "deployment" is a directory tree that mirrors the `GoBreeder/breed/` directory. Each deployment has:

- Its own `breed/config.py` where `basepath` is set to the deployment's absolute path.
- Its own `current_population.py` (active population being evolved).
- Its own `current_population.py_save` + `current_population.py_save_stats` (previous generation snapshots).
- A `runlog.txt` that breeding runs append to.
- Optionally a `histories/` subtree for per-move recording.

The deployment does **not** carry copies of binaries; binaries are located relative to the installed repo. Only the Python source files and population data files are per-deployment.

### Breeding runs

A breeding run is: `uv run python3 <basepath>/mediator.py -gtp_breed -genome_file <basepath>/current_population.py`

This is a long-lived subprocess. It writes to `runlog.txt` and evolves `current_population.py` generation by generation.

Multiple deployments can run concurrently; each is a separate subprocess.

### Population file format

One genome per line. Each line is a Python literal: `repr(dna)` where `dna` is a list of `(opcode, [operand1, operand2])` tuples.

Stats-save format appends `<<<>>>repr(stats)<<<>>>fitness` to the DNA repr on each line.

### VM state (full register set to expose)

The VM's `GoVM` instance exposes (after `boot()` is called):

- **Control registers** (internal, not program-accessible): `reg_pc`, `reg_clock`, `reg_HALT`, `PC_INTERRUPT`, `PC_INTERRUPT_A`
- **Move output registers**: `reg_X`, `reg_Y`
- **Arithmetic/flag registers**: `reg_RES`, `reg_CRY`, `reg_SGN`, `reg_LOG`
- **Board cursor**: `reg_STN` (tuple `(x, y)`)
- **General-purpose X working registers**: `reg_X0` … `reg_X7`
- **General-purpose Y working registers**: `reg_Y0` … `reg_Y7`
- **General-purpose registers**: `reg_GP0` … `reg_GP7`
- **Board modulated registers**: `reg_WXY`, `reg_PLAYER`
- **Memory**: `self.memory` (array of 640×1024 8-byte ints; show first N slots)
- **Stack**: `self.stack_memory` (list)
- **Board info iterators** (CircularList state): `bi_blacks`, `bi_whites`, `bi_spaces`, `bi_white_freedoms`, `bi_black_freedoms`, `bi_all_stones` — each has `.values` and `._ptr`
- **Board**: `self.board` (dict `{(x,y): -1|0|1}`)
- **Program** (genome): `self.program` (the list of instructions)

The current instruction is `self.program[self.reg_pc]` (if `reg_pc < len(self.program)`).

### VM stepping challenge

`GoVM.execute_program()` is currently a synchronous blocking loop. To enable step-by-step GUI inspection, we must replace it with a generator-based implementation that yields after every clock tick. A new `SteppableGoVM` subclass (or a debug wrapper) will provide:

- `step()` — execute one instruction, update state, return snapshot.
- `run_to_completion()` — run all remaining instructions (calls `step()` in a loop).

---

## Phase 1: Foundation — project structure and core framework

### Goals

- Add PySide6 to the project dependencies.
- Create the `GoBreeder/gui/` package with a skeleton main window.
- Set up an application model layer (non-UI state and business logic the GUI drives).
- Establish the pattern for separating UI code from application logic.
- Unit-test the model layer.

### Deliverables

#### 1.1 Dependency addition (`pyproject.toml`)

Add to `[project] dependencies`:
```
"pyside6>=6.6",
```

#### 1.2 Package layout

```
GoBreeder/gui/
    __init__.py
    app.py            # entry point: creates QApplication and MainWindow
    main_window.py    # MainWindow(QMainWindow) — tab container
    models/
        __init__.py
        deployment.py       # DeploymentModel — dataclass + persistence helpers
        run_state.py        # RunState — enum: IDLE, RUNNING, STOPPING
        app_state.py        # AppState — top-level observable state (QObject signals)
    utils/
        __init__.py
        paths.py            # workspace/repo path resolution helpers
        population_io.py    # read/write population files (wraps existing breeder logic)
```

#### 1.3 `DeploymentModel` (Pydantic model)

Fields:
- `name: str` — user-chosen label
- `deployment_dir: Path` — absolute path to the deployment's root
- `breed_dir: Path` — computed as `deployment_dir / "breed"`
- `created_at: datetime`
- `run_state: RunState` — persisted as a JSON sidecar file

Methods:
- `population_file_path() -> Path`
- `previous_population_file_path() -> Path`
- `stats_file_path() -> Path`
- `runlog_path() -> Path`
- `is_running() -> bool`

#### 1.4 `AppState` (`QObject` with signals)

Manages a list of `DeploymentModel` instances. Persists deployment registry to a JSON file in the user data directory. Emits `deployments_changed` signal on mutation.

#### 1.5 `MainWindow`

`QMainWindow` with a `QTabWidget` containing placeholder tabs:
- "Deployments"
- "Breeding Runs"
- "VM Inspector"
- "Archive Manager"

A status bar shows summary of active runs.

#### 1.6 Entry point

`GoBreeder/gui/app.py` contains `main()` which creates a `QApplication`, instantiates `AppState`, creates `MainWindow`, and calls `app.exec()`.

Add to `pyproject.toml`:
```toml
[project.scripts]
gobreeder-gui = "GoBreeder.gui.app:main"
```

#### 1.7 Tests

`tests/gui/test_deployment_model.py` — test `DeploymentModel` creation, serialisation, and path helpers.  
`tests/gui/test_app_state.py` — test deployment registry add/remove/persistence.

### Acceptance criteria

- `uv run gobreeder-gui` opens the main window with the four tabs.
- `AppState` persists/restores deployment list across restarts.
- All new unit tests pass; ruff and mypy clean.

---

## Phase 2: Deployment management panel

### Goals

- Implement the "Deployments" tab as a full CRUD UI.
- Creating a deployment copies the Python source files from the repo `breed/` directory into a new directory, generates a valid `config.py` for that path, and registers it in `AppState`.
- Deleting a deployment removes the directory (only if not currently running) and removes it from the registry.
- Editing a deployment allows renaming (the display label only).

### Deliverables

#### 2.1 Deployment creation logic (`models/deployment_factory.py`)

```python
class DeploymentFactory:
    def create(self, name: str, parent_dir: Path, repo_root: Path) -> DeploymentModel:
        ...
```

Steps:
1. Create `parent_dir / name / breed/` directory.
2. Copy all `.py` source files from `repo_root / GoBreeder / breed /` to `deployment_dir / breed/`.
3. Copy the required binaries/JARs (`ref_v0.1_exe`, `java/gosumi_2013.jar`, `java/gosumi_dks.jar`, `windows/gogui-twogtp.exe` if present).
4. Generate a `config.py` in the deployment with `basepath` pre-set to the deployment's `breed/` directory (absolute Windows path, using `os.path.abspath`).
5. Create an empty `current_population.py` with a comment noting the population is unset.
6. Return a `DeploymentModel` with `run_state = RunState.IDLE`.

#### 2.2 Deployment deletion logic (`models/deployment_manager.py`)

```python
class DeploymentManager:
    def delete(self, deployment: DeploymentModel) -> None:
        ...  # raises if is_running(); recursively removes deployment_dir
```

#### 2.3 UI: `DeploymentPanel` (`QWidget`)

Layout:
- Left: `QListWidget` of deployments (name + status badge: IDLE / RUNNING).
- Right: detail pane showing:
  - Name (editable `QLineEdit`)
  - Directory path (read-only)
  - Population file status (exists / line count / last modified)
  - Run state
  - **"Go to run" button** (switches to Breeding Runs tab, pre-selects this deployment)

Toolbar buttons above list:
- **New Deployment** → opens `NewDeploymentDialog`
- **Delete Deployment** (disabled if running)
- **Open Directory** (opens OS file explorer)

#### 2.4 `NewDeploymentDialog`

- Input: deployment name, parent directory (browse button)
- Validation: name is a valid directory name, parent dir exists and is writable
- On OK: calls `DeploymentFactory.create()`, adds to `AppState`

#### 2.5 Tests

- `tests/gui/test_deployment_factory.py` — create a deployment in a temp directory, verify file layout and `config.py` content.
- `tests/gui/test_deployment_manager.py` — delete a deployment, verify directory removed and IDLE check.

### Acceptance criteria

- Can create a new deployment via the UI; directory is created with correct layout.
- Can delete a deployment; directory is removed.
- Config.py in newly created deployment has correct `basepath`.
- Cannot delete a running deployment (button disabled, error on attempt).

---

## Phase 3: Breeding run management

### Goals

- Start/stop breeding runs for any IDLE deployment.
- Multiple deployments can run concurrently.
- Each run executes in a background thread (drives a subprocess).
- The UI shows real-time log output and generation count for each active run.

### Deliverables

#### 3.1 `BreedingRunController` (`QObject`)

Manages one breeding run. Uses `QProcess` (PySide6's managed process, integrates with Qt event loop) rather than `subprocess.Popen` to avoid threading complexity.

```python
class BreedingRunController(QObject):
    log_line_received = Signal(str)
    generation_advanced = Signal(int)
    run_finished = Signal()
    run_failed = Signal(str)

    def start(self, deployment: DeploymentModel) -> None: ...
    def stop(self) -> None: ...  # sends SIGTERM, waits up to 5 s then SIGKILL
```

Implementation:
- Command: `uv run python3 <breed_dir>/mediator.py -gtp_breed -genome_file <breed_dir>/current_population.py`
- `QProcess.setWorkingDirectory(str(deployment.breed_dir))`
- Connect `QProcess.readyReadStandardOutput` + `readyReadStandardError` to a line parser that:
  - Emits `log_line_received` for each line.
  - Detects lines containing `breeding generation` (from `Breeder.breed()` log) and updates generation counter, emitting `generation_advanced`.

#### 3.2 `RunRegistry` (`QObject`)

Maps `DeploymentModel -> BreedingRunController`. Owned by `AppState`. Manages start/stop lifecycle and updates `RunState` on each deployment.

#### 3.3 UI: `BreedingRunsPanel` (`QWidget`)

Layout:
- `QSplitter` (horizontal):
  - Left: `QListWidget` of all deployments, each showing name + run state badge + generation counter.
  - Right: per-run detail pane:
    - **Start / Stop** toggle button
    - Generation counter label
    - `QPlainTextEdit` log viewer (auto-scrolls, last 5000 lines retained)
    - Population stats bar: population size, last breed time

#### 3.4 `RunLogBuffer`

A thread-safe ring buffer (max lines configurable, default 5000). The `QPlainTextEdit` is updated via `QMetaObject.invokeMethod` from the `log_line_received` signal (signal/slot ensures GUI thread safety).

#### 3.5 Tests

- `tests/gui/test_breeding_run_controller.py` — mock `QProcess`, verify start/stop/command construction.
- `tests/gui/test_run_registry.py` — verify state transitions, concurrent run tracking.

### Acceptance criteria

- Can start a breeding run on a deployment with a valid population.
- Log lines appear in the UI within 1 s of being written by the subprocess.
- Generation count increments as breeding progresses.
- Can stop a run; the process terminates gracefully.
- Multiple runs can be active simultaneously; each shows its own log.
- Starting a run changes deployment state to RUNNING; stopping returns to IDLE.

---

## Phase 4: VM inspector and step debugger

### Goals

- Select any deployment's `current_population.py` (or any population file) and pick a specific genome.
- Set up an initial board state (empty or custom).
- Execute VM step-by-step or in one shot, with the ability to pause at any point.
- Display the full VM state (all registers, memory slice, board info iterators, stack, current instruction) at every step.
- Show the genome as a formatted instruction listing with the current PC highlighted.
- Show the board graphically.

### Deliverables

#### 4.1 `SteppableGoVM` (`GoBreeder/breed/steppable_vm.py`)

A subclass of `GoVM` that replaces `execute_program()` with a generator-based version:

```python
class VMStepSnapshot(BaseModel):
    clock: int
    pc: int
    current_instruction: tuple[str, list]
    canonical_opdata: list
    registers: dict[str, Any]
    stack_top_10: list
    memory_0_to_50: list[int]
    board_info: dict  # pointer + values for each CircularList
    board: dict       # the board dict {(x,y): int}
    halt: bool

class SteppableGoVM(GoVM):
    def step_generator(self, max_clocks: int = 4000) -> Generator[VMStepSnapshot, None, None]:
        """Yields a snapshot after each instruction execution."""
        ...
```

The generator runs one iteration of the existing `execute_program` while-loop body per `next()` call, yielding the snapshot before PC advance. The caller drives execution by calling `next()`.

#### 4.2 `VMDebugSession` (`QObject`)

Wraps a `SteppableGoVM` and its generator. Runs in a background `QThread` worker. The GUI communicates with the worker via signals/slots.

```python
class VMDebugSession(QObject):
    snapshot_ready = Signal(VMStepSnapshot)
    execution_finished = Signal(VMStepSnapshot)  # final state
    paused = Signal(VMStepSnapshot)

    def load(self, genome_dna: list, board: dict, player: str) -> None: ...
    def step(self) -> None: ...       # advance one instruction
    def run(self) -> None: ...        # run until pause/finish
    def pause(self) -> None: ...      # request pause after current step
    def reset(self) -> None: ...      # reload to initial state
```

`run()` uses a `QTimer` with a short interval (e.g., 5 ms per step minimum) so the Qt event loop stays responsive.

#### 4.3 UI: `VMInspectorPanel` (`QWidget`)

Top toolbar:
- Population file selector (browse button or deployment dropdown)
- Genome index selector (`QSpinBox` with range 0 to population size − 1) + "Load Genome" button
- Player selector (`QComboBox`: black / white)
- Board state selector: "Empty" or "Custom" (opens a simple board editor)

Center area (`QSplitter`, three panes):

**Left pane: Genome listing** (`QTableWidget`, read-only)
- Columns: Index | Opcode | Operand A | Operand B
- Row of `reg_pc` is highlighted in yellow.
- Scrolls to keep current instruction visible.
- Genome is shown as the raw DNA, one instruction per row.

**Middle pane: VM state** (scrollable `QFormLayout` or `QTreeView`)

Register groups (collapsible sections using `QGroupBox`):
- **Control**: `pc`, `clock`, `HALT`, `PC_INTERRUPT`, `PC_INTERRUPT_A`
- **Output**: `X`, `Y` (move registers)
- **Arithmetic/flags**: `RES`, `CRY`, `SGN`, `LOG`
- **Board**: `PLAYER`, `STN`
- **WXY**: `WXY`
- **X working registers**: `X0` … `X7`
- **Y working registers**: `Y0` … `Y7`
- **GP registers**: `GP0` … `GP7`

Memory section:
- Label: "Memory[0:50]"
- `QTableWidget` showing first 50 memory slots (address | value), updated each step.
- Optional: a second mini-table for the stack (top 10 entries).

Board info section:
- One row per CircularList: blacks, whites, spaces, black_freedoms, white_freedoms, all_stones.
- Shows: current pointer index, number of values, current value.

**Right pane: Board display** (custom `QWidget: BoardWidget`)
- Draws a 9×9 Go board.
- Black and white stones filled/outlined circles.
- Highlights the cell at `(reg_X % 9, reg_Y % 9)` as the current move candidate.
- Highlights `reg_STN` coordinates with a cursor marker.
- Board pointer offset cells relative to STN are shown faintly.

Bottom control bar:
- **Step** button (advance one instruction) — shortcut: `Space`
- **Run** button (run continuously until pause/end) — shortcut: `F5`
- **Pause** button (interrupt continuous run)
- **Reset** button (reload genome to initial state)
- Speed slider (controls delay between steps during continuous run: 0 ms to 500 ms)
- Step counter: "Step: N / 4000"

#### 4.4 `GenomeCodeView` (`QWidget`)

Formats a genome DNA list as human-readable pseudo-assembly. Shows the instruction index prominently. Scrolls to current PC line during stepping. Uses a monospace font. Changed registers since last step are highlighted in the register panel.

#### 4.5 Tests

- `tests/test_steppable_vm.py` — verify `SteppableGoVM.step_generator()` produces the correct number of snapshots and final state matches `GoVM.get_move()` for the same inputs.
- `tests/gui/test_vm_debug_session.py` — mock session, verify signal emissions.

### Acceptance criteria

- Loading a genome from a population file displays its instruction listing.
- Clicking "Step" advances one instruction; all registers update in the UI.
- "Run" executes continuously; "Pause" halts at the current instruction.
- Board display shows the current stones and highlights `STN` and move candidate.
- After execution completes, the final `X`, `Y` values shown are the move that would be played.
- All registers listed in §4.3 are visible and update correctly.

---

## Phase 5: Archive management

### Goals

- Browse tar archives (`.tar`, `.tar.gz`, `.tar.bz2`) of run data.
- Navigate the archive tree structure.
- Extract population files (`current_population.py`, `*.py_save`, etc.) from an archive.
- Read and display individual genome entries from an extracted population.
- Select genomes from one or more archives (or population files) and save them to a new population file.

### Background: expected archive structure

Archives produced by wrapping a deployment directory will typically contain:
```
GoBreeder_<n>/
    breed/
        current_population.py
        current_population.py_save
        current_population.py_save_stats
        runlog.txt
        histories/
            <genome_hash>/
                full_genome.py
                game_<k>/
                    player_color
                    VM_version
```

The GUI needs to find and read any file matching `*population*.py` or containing genome DNA lines.

### Deliverables

#### 5.1 `ArchiveReader` (`GoBreeder/gui/archive/archive_reader.py`)

```python
class ArchiveEntry(BaseModel):
    archive_path: Path
    internal_path: str   # path within the archive
    size: int

class ArchiveReader:
    def list_files(self, archive_path: Path) -> list[ArchiveEntry]: ...
    def find_population_files(self, archive_path: Path) -> list[ArchiveEntry]: ...
    def read_population_file(self, entry: ArchiveEntry) -> list[str]: ...
        # returns list of raw genome repr strings (one per line)
```

Uses Python's `tarfile` module. Supports `.tar`, `.tar.gz`, `.tar.bz2`.

#### 5.2 `GenomeEntry` (Pydantic model)

```python
class GenomeEntry(BaseModel):
    source_archive: Path | None
    source_file: str           # archive internal path or filesystem path
    line_index: int
    dna_repr: str              # raw repr string
    stats: str | None          # parsed stats portion if present
    fitness: float | None
```

`GenomeEntry.dna` property: parses `dna_repr` via `ast.literal_eval`.

#### 5.3 `PopulationFileReader` (`GoBreeder/gui/archive/population_file_reader.py`)

Wraps the existing `Breeder.initialise_population()` logic as a standalone function that returns `list[GenomeEntry]` from a path (filesystem or archive entry). Handles both plain DNA lines and stats-save format lines.

#### 5.4 UI: `ArchiveManagerPanel` (`QWidget`)

Layout (`QSplitter`, three panes left to right):

**Archive browser pane:**
- `QListWidget` of loaded archives (with "Add Archive…" / "Remove" buttons)
- Below: `QTreeWidget` showing the directory tree of the selected archive
- Quick filter button: "Show population files only"

**Population view pane:**
- Label: current population file path in archive
- `QTableWidget` of genomes: columns `Index | Length | Fitness | Stats | Preview (first 3 opcodes)`
- Select one or more rows (supports multi-select with `Ctrl`/`Shift`)
- "View Genome" button → opens genome in VM Inspector
- "Add to Selection" button → adds selected to the export selection list

**Export selection pane:**
- `QListWidget` of genomes collected for export (from any open archive)
- "Remove Selected" button
- "Clear All" button
- "Save as Population File…" button → opens save dialog, writes one `repr(dna)+'\n'` per genome

#### 5.5 Tests

- `tests/gui/test_archive_reader.py` — create a temp tar archive with a mock population file; verify `find_population_files` and `read_population_file`.
- `tests/gui/test_population_file_reader.py` — parse a stats-save format and plain DNA format population file.
- `tests/gui/test_genome_entry.py` — verify `dna` parsing from repr string.

### Acceptance criteria

- Can open a `.tar.gz` archive and browse its tree.
- Population files are detected and their genomes listed.
- Genome fitness values are displayed where the stats-save format is present.
- Can select genomes from multiple archive/population sources.
- Saving the selection writes a valid population file that the existing `Breeder` can load.

---

## Phase 6: Population library and deployment injection

### Goals

- Maintain a persistent library of named population files.
- Create new populations (empty or by cloning an existing one).
- Rename and delete populations in the library.
- Inject a population from the library into any IDLE deployment (replacing its `current_population.py`).
- The VM Inspector can load from any library population.

### Deliverables

#### 6.1 `PopulationLibrary` (`QObject`)

Manages a user data directory (e.g., `~/.gobreeder/populations/`). Stores each population as a `.pop` file (identical format to `current_population.py` — one genome repr per line).

```python
class PopulationRecord(BaseModel):
    name: str
    file_path: Path
    genome_count: int
    created_at: datetime
    modified_at: datetime
    notes: str

class PopulationLibrary(QObject):
    library_changed = Signal()

    def add(self, name: str, source_path: Path | None = None) -> PopulationRecord: ...
    def delete(self, record: PopulationRecord) -> None: ...
    def rename(self, record: PopulationRecord, new_name: str) -> None: ...
    def inject_into_deployment(self, record: PopulationRecord, deployment: DeploymentModel) -> None:
        # raises if deployment.is_running()
        # copies record.file_path to deployment.population_file_path()
        ...
    def list_all(self) -> list[PopulationRecord]: ...
```

The library registry is persisted as `~/.gobreeder/library.json`.

#### 6.2 UI: `PopulationLibraryPanel` (integrated into `ArchiveManagerPanel` or as a sub-tab)

Layout (`QSplitter`, two panes):

**Library list pane:**
- `QListWidget` of population records (name + genome count + modified date)
- Toolbar: **New Population**, **Import from File…**, **Delete**, **Rename**
- **"Import from Archive Selection"** button — takes the current export selection from the Archive Manager and saves it as a new library entry (prompts for name)

**Population detail pane:**
- Name (editable inline)
- File path
- Genome count
- Notes (`QPlainTextEdit`, editable)
- `QTableWidget` preview of first 20 genomes (Index | Length columns)
- **"Inject into Deployment"** button (disabled if no IDLE deployment selected)
  - Opens a dialog to choose the target IDLE deployment
  - Shows a warning: "This will overwrite the current population for `<deployment_name>`. Continue?"
- **"Open in VM Inspector"** button

#### 6.3 Deployment panel integration

In the `DeploymentPanel` detail pane (Phase 2), add a section:

- **Current Population** status: file exists (yes/no), genome count, last modified timestamp.
- **"Inject Population from Library…"** button (disabled if running) → opens a picker dialog listing the population library.

#### 6.4 Tests

- `tests/gui/test_population_library.py` — add/delete/rename/inject operations.
- Test that injection raises when the deployment is running.
- Test that injecting a population produces a readable population file in the deployment directory.

### Acceptance criteria

- Population library persists across application restarts.
- Can import any `.pop` or `current_population.py` file into the library.
- Can inject a library population into an IDLE deployment.
- Cannot inject into a RUNNING deployment (button disabled + error on attempt).
- "Open in VM Inspector" loads the population from library into the VM Inspector tab.

---

## Cross-cutting concerns

### Threading model

| Concern | Mechanism |
|---|---|
| GUI thread | Main Qt event loop only. All UI updates here. |
| Breeding run subprocess | `QProcess` — integrated with Qt event loop; callbacks on main thread. |
| VM stepping (continuous run) | `QThread` worker + signals back to GUI thread via queued connections. |
| File I/O (archive reading, large populations) | `QRunnable` + `QThreadPool` for one-shot ops; emit signal on completion. |

No direct mutation of Qt widgets from worker threads.

### Code structure

```
GoBreeder/
    gui/
        __init__.py
        app.py
        main_window.py
        panels/
            deployment_panel.py
            breeding_runs_panel.py
            vm_inspector_panel.py
            archive_manager_panel.py
            population_library_panel.py
        models/
            deployment.py
            run_state.py
            app_state.py
            run_registry.py
            population_library.py
        archive/
            archive_reader.py
            population_file_reader.py
        vm_debug/
            steppable_vm.py
            vm_debug_session.py
        widgets/
            board_widget.py
            genome_code_view.py
            run_log_view.py
            status_badge.py
        dialogs/
            new_deployment_dialog.py
            inject_population_dialog.py
    breed/              # existing — not modified in early phases
        ...
```

### Style and quality

- All new code must pass `ruff` linting and `mypy` type checking.
- PySide6 objects used in type annotations: use `from __future__ import annotations` and string literals for complex PySide6 generics.
- The `breed/` package's modules (`vm.py`, `breeder.py`, etc.) are imported by the GUI but **not modified** until Phase 4 introduces `SteppableGoVM` as a new file.
- The `SteppableGoVM` must produce identical results to `GoVM.execute_program()` — verified by unit tests in Phase 4.
- 80%+ test coverage target for all new `models/` and `archive/` code.
- GUI widget tests use `pytest-qt` (add to dev dependencies).

### Known constraints and risks

| Risk | Mitigation |
|---|---|
| VM stepping introduces drift from the original VM | Unit tests compare step-by-step vs one-shot results |
| `QProcess` on Windows needs the correct Python interpreter from uv | Construct command using `sys.executable` or `uv run` prefix; test on Windows |
| Population files can be large (1000+ genomes, each 500–1000 instructions) | Load population in a background `QRunnable`; show progress indicator |
| Tar archives may be very large | Stream archive listing; only extract population files on demand |
| Multiple concurrent `QProcess` instances on Windows | Test with 3+ simultaneous runs; monitor handle limits |

---

## Phase summary

| Phase | Focus | Key new modules | Tests |
|---|---|---|---|
| 1 | Foundation + project skeleton | `app.py`, `main_window.py`, `models/` | deployment model, app state |
| 2 | Deployment CRUD | `deployment_factory.py`, `deployment_panel.py` | factory, manager |
| 3 | Breeding run management | `run_registry.py`, `breeding_runs_panel.py` | controller, registry |
| 4 | VM inspector / debugger | `steppable_vm.py`, `vm_inspector_panel.py`, `board_widget.py` | steppable VM, debug session |
| 5 | Archive management | `archive_reader.py`, `population_file_reader.py`, `archive_manager_panel.py` | reader, parser |
| 6 | Population library + injection | `population_library.py`, `population_library_panel.py` | library ops, injection |

Each phase produces a fully working (not prototype) implementation of its features before the next phase begins.
