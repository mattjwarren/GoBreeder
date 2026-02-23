# GoBreeder

A genetic-programming system that evolves Go-playing programs. Genomes are lists of custom VM instructions that are evaluated by playing games against an opponent engine, then bred across generations to improve their playing ability.

---

## How it works

Each **genome** is a program for a custom stack-based virtual machine (`GoVM`). On every `genmove` GTP request, the VM runs for a fixed number of clock cycles and outputs a board move via its `X` and `Y` output registers. The VM reads board state through a set of circular-iterator "board info" registers that expose stone positions, liberties, and spaces.

Evolution proceeds as follows:

1. Each genome in the current population is written to a temporary file and played as a GTP engine against an opponent (default: `gosumi_2013.jar`) using `gogui-twogtp` for match orchestration.
2. Win/loss results and move counts are recorded as fitness metrics.
3. After the whole population is evaluated, `Breeder.breed()` selects survivors and produces a new generation via mutation and crossover.
4. The new generation is saved to `current_population.py` and the cycle repeats.

---

## Architecture

```
GoBreeder/
├── breed/              # Core evolutionary engine
│   ├── vm.py           # GoVM — custom register/stack machine
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
