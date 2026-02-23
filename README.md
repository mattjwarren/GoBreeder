# GoBreeder

A genetic-programming system that evolves Go-playing programs. Genomes are lists of custom VM instructions that are evaluated by playing games against an opponent engine, then bred across generations to improve their playing ability.

---

## How it works

Each **genome** is a program for a custom stack-based virtual machine (`GoVM`). On every `genmove` GTP request, the VM runs for a fixed number of clock cycles and outputs a board move via its `X` and `Y` output registers. The VM reads board state through a set of circular-iterator "board info" registers that expose stone positions, liberties, and spaces.

Evolution proceeds as follows:

1. Each genome in the current population is written to a temporary file and played as a GTP engine against an opponent (default: `gosumi_2013_fast.jar`) using `gogui-twogtp` for match orchestration.
2. Win/loss results and move counts are recorded as fitness metrics.
3. After the whole population is evaluated, `Breeder.breed()` selects survivors and produces a new generation via mutation and crossover.
4. The new generation is saved to `current_population.py` and the cycle repeats.

---

## Performance configuration

Breeding speed is determined by two independent axes. Both are set in `GoBreeder/breed/config.py` (or per-deployment `config.py`):

### 1 — VM backend (`use_rust_vm`)

The GoVM execution engine has two backends:

| Backend | Setting | Speed | Notes |
|---------|---------|-------|-------|
| **Rust (PyO3)** | `use_rust_vm = True` *(default)* | ~127× faster per `get_move` call | Requires Rust toolchain; built automatically on deploy |
| **Pure Python** | `use_rust_vm = False` | baseline | Always available; useful for debugging |

Raw micro-benchmark on a 1 024-instruction genome, 4 000 clock cycles:

| Backend | Per-call latency |
|---------|-----------------|
| Rust (release build) | **0.18 ms** |
| Pure Python | 23 ms |

### 2 — Opponent engine (`enemy_program`)

Three opponent JAR variants are bundled in `GoBreeder/breed/java/`:

| JAR | Setting | Per-move time | Notes |
|-----|---------|---------------|-------|
| `gosumi_2013_fast.jar` | `enemy_program = gosumi_2013_fast` *(default)* | ~fast | Bytecode-patched: timeout multiplier 1 000→100 ms, default 28 000→2 000 ms, search depths {8,12,16}→{4,6,8} |
| `gosumi_2013.jar` | `enemy_program = gosumi_2013` | ~slow | Original unpatched opponent |
| `gosumi_dks.jar` | `enemy_program = gosumi` | varies | Alternative engine |

### Combined real-world impact

With both defaults active (Rust VM + fast gosumi opponent) a complete 9×9 game between two engines takes approximately **5 seconds**. Using the Python VM and the original gosumi_2013 opponent the same game takes approximately **30 seconds** — a **~6× end-to-end speedup** on a full breeding game.

### Changing the configuration

Edit `enemy_program` and `use_rust_vm` in a deployment's `config.py`:

```python
# config.py in your deployment directory

# VM backend: True = Rust (~127× faster per move), False = pure Python
use_rust_vm = True

# Opponent JAR (choose one):
enemy_program = gosumi_2013_fast  # default — fastest training games
# enemy_program = gosumi_2013     # original, slower opponent
# enemy_program = gosumi          # gosumi_dks alternative
```

> **Note:** `use_rust_vm` is silently ignored if the Rust extension is not installed — the Python VM is used automatically as a fallback.

---

## Architecture

```
GoBreeder/
├── breed/              # Core evolutionary engine
│   ├── vm.py           # GoVM — custom register/stack machine (Rust or Python backend)
│   ├── breeder.py      # Population management and evolutionary operators
│   ├── mediator.py     # Orchestrates Breeder ↔ GoEngine; GTP server mode
│   ├── go_engine.py    # GTP client/server wrapper
│   ├── data_structures.py  # GoGenome, CircularList
│   ├── board_info.py   # Board-state query helpers
│   └── config.py       # Per-deployment path and performance configuration
├── gui/                # PySide6 desktop GUI
│   ├── app.py          # Entry point (gobreeder-gui)
│   ├── main_window.py  # Four-tab main window
│   ├── models/         # Pydantic app-state models
│   ├── panels/         # Tab panel widgets
│   ├── widgets/        # Reusable widgets (BoardWidget, GenomeCodeView, …)
│   └── vm_debug/       # VM step-debugger backend (QThread)
└── go_vm_rs/           # Rust/PyO3 VM extension source (built by deploy script)
```

### Run modes

| Mode | Command |
|------|---------|
| Breeding run (evolve a population) | `uv run python mediator.py -gtp_breed -genome_file current_population.py` |
| Single-genome GTP engine | `uv run python mediator.py -genome_file breeding_genome.py` |
| Desktop GUI | `uv run gobreeder-gui` |

---

## GUI

A full PySide6 desktop application manages the entire workflow without needing the command line.

| Tab | Function |
|-----|----------|
| **Deployments** | Create, configure, and delete deployment directories. Each deployment is an independent copy of the breed directory with its own population and config. |
| **Breeding Runs** | Start/stop breeding runs (QProcess-based), monitor per-generation progress, and tail the run log in real time. Multiple deployments can run concurrently. |
| **VM Inspector** | Load any genome, step through its execution instruction by instruction, and inspect all registers, memory, stack, and the live 9×9 board state. |
| **Archive & Library** | Browse per-run archives, select individual genomes, export them, and compose new population files to inject into any deployment. |

### Screenshot

> *(No screenshot yet — run `uv run gobreeder-gui` to see the GUI.)*

---

## Virtual Machine

`GoVM` is a custom register-and-stack machine with:

- **Output registers** `X`, `Y` — the move coordinates emitted each `genmove`.
- **Arithmetic registers** `RES`, `CRY`, `SGN`, `LOG`.
- **Working registers** `X0`–`X7`, `Y0`–`Y7`, `GP0`–`GP7`.
- **Board pointer** `STN` — a 3×3 cursor over the board.
- **Board info iterators** (`bi_blacks`, `bi_whites`, `bi_spaces`, `bi_white_freedoms`, `bi_black_freedoms`, `bi_all_stones`) — circular lists that expose stone coordinates to the program.
- **Memory** — 640 × 1 024 addressable 8-byte integer slots.
- **Stack** — unbounded push/pop stack.

The `SteppableGoVM` subclass exposes a generator-based `step()` interface used by the GUI debugger.

The hot execution engine is implemented in Rust (`go_vm_rs/`) and exposed via PyO3. The pure-Python engine in `vm.py` is retained as a fallback and for use by the step-debugger.

---

## Requirements

- Python ≥ 3.10
- [uv](https://github.com/astral-sh/uv) (package/env manager)
- Java (for gosumi opponent JARs) on `PATH`
- `gogui-twogtp` binary (bundled in `gogui-v1.6.0-bin/`)
- `ref_v0.1_exe` referee (bundled in `GoBreeder/breed/`)
- Rust toolchain (for the native VM extension — installed automatically by the deploy script if absent)

---

## Installation

```bash
git clone https://github.com/<your-org>/GoBreeder.git
cd GoBreeder
uv sync
```

### Building the Rust VM extension (recommended)

```bash
# Install maturin (build tool) and build the release extension:
uv pip install maturin
cd go_vm_rs && maturin develop --release
```

Once built, `import go_vm_rs` works inside the project venv and `vm.py` switches to the Rust backend automatically. The deploy script (`deploy_breeder_instance.sh`) handles this automatically for each deployment instance.

To include development dependencies (tests, linting):

```bash
uv sync --group dev
```

---

## Running the GUI

```bash
uv run gobreeder-gui
```

---

## Running a breeding session (command line)

```bash
# From a deployment directory that has current_population.py
uv run python GoBreeder/breed/mediator.py \
    -gtp_breed \
    -genome_file /path/to/deployment/current_population.py
```

Or use the helper script:

```bash
bash GoBreeder/scripts/breed_pop.sh /path/to/deployment
```

---

## Development

```bash
# Run all tests
uv run pytest

# Linting / formatting check
uv run ruff check .

# Type checking
uv run mypy GoBreeder
```

**277 tests, ruff clean, mypy clean.**

---

## Deployment management

A *deployment* is a directory that mirrors `GoBreeder/breed/` with:

- Its own `config.py` (`basepath` set to the deployment path).
- Its own `current_population.py` (active population).
- A `runlog.txt` appended to by breeding runs.
- Optionally a `histories/` subtree for per-move game recording.
- The `go_vm_rs/` Rust source and a compiled `.so` installed into the instance's `.venv`.

Deployments can be created and managed via the GUI's **Deployments** tab, or manually using `GoBreeder/scripts/deploy_breeder_instance.sh`.

---

## Project structure (key files)

| File | Purpose |
|------|---------|
| `GoBreeder/breed/vm.py` | GoVM — dispatches to Rust or Python backend |
| `go_vm_rs/src/lib.rs` | Rust VM implementation (PyO3 extension) |
| `GoBreeder/breed/config.py` | Paths, performance flags (`use_rust_vm`, `enemy_program`) |
| `GoBreeder/breed/breeder.py` | Genetic operators and population management |
| `GoBreeder/breed/mediator.py` | GTP server / breeding orchestrator |
| `GoBreeder/breed/go_engine.py` | GTP engine wrapper |
| `GoBreeder/breed/data_structures.py` | `GoGenome`, `CircularList` |
| `GoBreeder/gui/app.py` | GUI entry point |
| `GoBreeder/gui/models/app_state.py` | Application-level Pydantic state |
| `GoBreeder/gui/vm_debug/` | Step-debugger thread and session model |
| `tests/` | 277 pytest tests |

---

## License

See [`GoBreeder/extras/external_go_docs/License.txt`](GoBreeder/extras/external_go_docs/License.txt) for third-party component licences.

│   ├── breeder.py      # Population management and evolutionary operators
│   ├── mediator.py     # Orchestrates Breeder ↔ GoEngine; GTP server mode
│   ├── go_engine.py    # GTP client/server wrapper
│   ├── data_structures.py  # GoGenome, CircularList
│   ├── board_info.py   # Board-state query helpers
│   └── config.py       # Per-deployment path configuration
└── gui/                # PySide6 desktop GUI
    ├── app.py          # Entry point (gobreeder-gui)
    ├── main_window.py  # Four-tab main window
    ├── models/         # Pydantic app-state models
    ├── panels/         # Tab panel widgets
    ├── widgets/        # Reusable widgets (BoardWidget, GenomeCodeView, …)
    └── vm_debug/       # VM step-debugger backend (QThread)
```

### Run modes

| Mode | Command |
|------|---------|
| Breeding run (evolve a population) | `uv run python mediator.py -gtp_breed -genome_file current_population.py` |
| Single-genome GTP engine | `uv run python mediator.py -genome_file breeding_genome.py` |
| Desktop GUI | `uv run gobreeder-gui` |

---

## GUI

A full PySide6 desktop application manages the entire workflow without needing the command line.

| Tab | Function |
|-----|----------|
| **Deployments** | Create, configure, and delete deployment directories. Each deployment is an independent copy of the breed directory with its own population and config. |
| **Breeding Runs** | Start/stop breeding runs (QProcess-based), monitor per-generation progress, and tail the run log in real time. Multiple deployments can run concurrently. |
| **VM Inspector** | Load any genome, step through its execution instruction by instruction, and inspect all registers, memory, stack, and the live 9×9 board state. |
| **Archive & Library** | Browse per-run archives, select individual genomes, export them, and compose new population files to inject into any deployment. |

### Screenshot

> *(No screenshot yet — run `uv run gobreeder-gui` to see the GUI.)*

---

## Virtual Machine

`GoVM` is a custom register-and-stack machine with:

- **Output registers** `X`, `Y` — the move coordinates emitted each `genmove`.
- **Arithmetic registers** `RES`, `CRY`, `SGN`, `LOG`.
- **Working registers** `X0`–`X7`, `Y0`–`Y7`, `GP0`–`GP7`.
- **Board pointer** `STN` — a 3×3 cursor over the board.
- **Board info iterators** (`bi_blacks`, `bi_whites`, `bi_spaces`, `bi_white_freedoms`, `bi_black_freedoms`, `bi_all_stones`) — circular lists that expose stone coordinates to the program.
- **Memory** — 640 × 1 024 addressable 8-byte integer slots.
- **Stack** — unbounded push/pop stack.

The `SteppableGoVM` subclass exposes a generator-based `step()` interface used by the GUI debugger.

---

## Requirements

- Python ≥ 3.10
- [uv](https://github.com/astral-sh/uv) (package/env manager)
- Java (for `gosumi_2013.jar` opponent) on `PATH`
- `gogui-twogtp` binary (bundled in `gogui-v1.6.0-bin/`)
- `ref_v0.1_exe` referee (bundled in `GoBreeder/breed/`)

---

## Installation

```bash
git clone https://github.com/<your-org>/GoBreeder.git
cd GoBreeder
uv sync
```

To include development dependencies (tests, linting):

```bash
uv sync --group dev
```

---

## Running the GUI

```bash
uv run gobreeder-gui
```

---

## Running a breeding session (command line)

```bash
# From a deployment directory that has current_population.py
uv run python GoBreeder/breed/mediator.py \
    -gtp_breed \
    -genome_file /path/to/deployment/current_population.py
```

Or use the helper script:

```bash
bash GoBreeder/scripts/breed_pop.sh /path/to/deployment
```

---

## Development

```bash
# Run all tests
uv run pytest

# Linting / formatting check
uv run ruff check .

# Type checking
uv run mypy GoBreeder
```

**277 tests, ruff clean, mypy clean.**

---

## Deployment management

A *deployment* is a directory that mirrors `GoBreeder/breed/` with:

- Its own `config.py` (`basepath` set to the deployment path).
- Its own `current_population.py` (active population).
- A `runlog.txt` appended to by breeding runs.
- Optionally a `histories/` subtree for per-move game recording.

Deployments can be created and managed via the GUI's **Deployments** tab, or manually using `GoBreeder/scripts/deploy_breeder_instance.sh`.

---

## Project structure (key files)

| File | Purpose |
|------|---------|
| `GoBreeder/breed/vm.py` | Core VM implementation |
| `GoBreeder/breed/breeder.py` | Genetic operators and population management |
| `GoBreeder/breed/mediator.py` | GTP server / breeding orchestrator |
| `GoBreeder/breed/go_engine.py` | GTP engine wrapper |
| `GoBreeder/breed/data_structures.py` | `GoGenome`, `CircularList` |
| `GoBreeder/gui/app.py` | GUI entry point |
| `GoBreeder/gui/models/app_state.py` | Application-level Pydantic state |
| `GoBreeder/gui/vm_debug/` | Step-debugger thread and session model |
| `tests/` | 277 pytest tests |

---

## License

See [`GoBreeder/extras/external_go_docs/License.txt`](GoBreeder/extras/external_go_docs/License.txt) for third-party component licences.
