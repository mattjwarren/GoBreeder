# GoBreeder codebase analysis (Jan 2026)

## What this project is

GoBreeder is a genetic-programming / evolutionary "breeder" that evolves small programs (called *genomes*) that act as a Go-playing engine.

- The evolved agent is **not** a traditional search engine.
- Instead, each genome is a list of VM instructions executed by a custom virtual machine (`GoVM`).
- On each `genmove` request (GTP), the VM runs for a fixed number of instructions (“clocks”) and outputs a move using its `X` and `Y` registers.

The project is tightly coupled to:

- **GTP** (Go Text Protocol) for engine I/O.
- **GoGui’s** `gogui-twogtp.exe` for match orchestration.
- An external **referee executable** (`ref_v0.1_exe`) to adjudicate games.
- A Java opponent bot (default: `gosumi_2013.jar`).

The code is largely **Python 2-era** style (e.g., `print message`), and configuration assumes a Windows + Cygwin setup.


## Repository layout (high level)

- `breed/`: all Python code and most runtime artifacts/tools.
  - Core modules: `mediator.py`, `breeder.py`, `vm.py`, `go_engine.py`, `data_structures.py`, `board_info.py`.
  - Bundled executables/JARs: `gogui-twogtp.exe`, `ref_v0.1_exe`, `gosumi_2013.jar`, etc.
- `breed_pop.sh`: launches a breeding run for a deployed instance.
- `deploy_breeder_instance.sh`: deploys per-instance copies and rewrites `breed/config.py`.
- `redeploy_breeder.sh`: attempts to preserve histories/config/current files across redeploy.
- `planning/`: documentation and notes (this file lives here).


## The two main run modes

There are two distinct ways `breed/mediator.py` runs.

### 1) Breeding mode (population evolution)

Triggered by `mediator.py -gtp_breed -genome_file <population_file>`.

- `Mediator` creates a `Breeder` instance with `population_file`.
- The `Breeder` repeatedly:
  1. Writes a single genome out to `breed/breeding_genome.py`.
  2. Invokes `gogui-twogtp.exe` to run a match:
     - “player” program: the GoBreeder GTP engine (`mediator.py -genome_file breeding_genome.py`)
     - “enemy” program: default Gosumi jar
     - “referee”: `ref_v0.1_exe`
  3. Parses twogtp output to determine winner and approximate move count.
  4. Records stats for that genome.
- After all genomes in the population are evaluated, `breed()` selects and breeds a new generation, writing it to `current_population.py`.

This is the mode used by `breed_pop.sh`.

### 2) Single-genome GTP engine mode (play one genome)

Triggered by `mediator.py -genome_file <genome_file>` (without `-gtp_breed`).

- The file is read and evaluated as a Python literal DNA list.
- A `GoGenome` is built and used as the playing program.
- `Mediator.go_gtp()` performs a GTP handshake (via `GoEngine.initialise()`), then loops:
  - On `genmove <b|w>` it calls `GoVM.get_move(...)` and responds with `= <coord>`.

This is how GoGui / twogtp interacts with the evolved agent during breeding.


## Runtime architecture (data + control flow)

A simplified view:

```
+---------------------------+
| breeder.py (Breeder)      |
| - loads population        |
| - writes breeding_genome  |
| - calls gogui-twogtp      |
| - parses win/move count   |
| - breeds new generation   |
+-------------+-------------+
              |
              v
+---------------------------+     stdin/stdout (GTP)
| mediator.py (Mediator)    | <-------------------------- GoGui twogtp
| - single genome engine    |
| - calls GoVM for genmove  |
+-------------+-------------+
              |
              v
+---------------------------+
| vm.py (GoVM)              |
| - boots registers/memory  |
| - loads board features    |
| - executes genome         |
| - outputs X,Y as move     |
+-------------+-------------+
              |
              v
+---------------------------+
| go_engine.py (GoEngine)   |
| - maintains board dict    |
| - translates coords       |
| - handles minimal GTP     |
+---------------------------+
```


## Configuration and environment assumptions

`breed/config.py` is the central configuration.

Key fields:

- `basepath`: absolute path to the `breed/` directory. Deployment scripts rewrite this per instance.
- `pythonpath`: explicit Python 2.7 interpreter path.
- `two_gtp_command`: path to `gogui-twogtp.exe`.
- `referee_program_command`: path to `ref_v0.1_exe`.
- `enemy_program`: Java invocation for Gosumi.
- Population files:
  - `current_population_file`: `current_population.py`
  - `previous_population_file`: `current_population.py_save`
  - `previous_population_stats_file`: `current_population.py_save_stats`
- Logging:
  - `runlog`: `runlog.txt`
- Optional detailed run recording:
  - `history_stats_base`: `histories/`
  - `record_stats`: when `True`, writes per-move data

Note: `config.board_size` is set to 9 and many parts of the VM/board code assume 9x9.


## Data formats

### Genome DNA (instruction list)

A genome is a Python list of instructions. Each instruction is:

- `(opcode, [operandA, operandB])` for opcodes with operands
- `(opcode, [None, None])` for operand-less ops (most code passes a 2-slot list)

Operands are usually strings, later resolved (“canonicalised”) by the VM.

Examples of operand encodings:

- `'123'` / `'-4'` : immediate integer
- `'X'`, `'RES'`, `'GP4'` : register name
- `'m123'` : memory at address 123
- `'mX'` : memory at address stored in register X
- `'*123'` or `'*X'` : dereference once (use memory value as a pointer)
- `'STN_C_STATS'`, `'STN_TL_XCOORD'` : special STN-derived values (see VM section)

### Genome file format

A *single genome file* is just one line:

- `repr(dna) + '\n'`

This is what `mediator.py` reads with `dna = eval(genome_file.readline())`.

### Population file format

A *population file* contains one genome DNA per line.

`Breeder.initialise_population()` reads each non-empty line and uses `eval(line)`.

A special stats-save format is also supported:

- `repr(dna) + '<<<>>>' + repr(stats_dict) + '<<<>>>' + str(fitness) + '\n'`

When `Breeder` sees `'<<<>>>'`, it splits the DNA off and ignores the rest for resurrection.


## The breeder (evolutionary loop)

Implemented in `breed/breeder.py`.

### Match simulation

`simulate_gtp_game()`:

- Picks the current genome from the population.
- Writes it into `breed/breeding_genome.py` (one line, `repr(dna)`).
- Builds a `gogui-twogtp.exe` command roughly like:

  - `gogui-twogtp.exe -black <player_program> -white <enemy_program> -size 9 -referee <ref> -auto -verbose`

- Launches the process and parses stdout/stderr:
  - counts lines containing `genmove` (divided by 2 as a heuristic)
  - considers a win if a line contains `has won` and the reported color matches the program’s color

### Fitness and breeding

`breed()`:

- Fitness for a **loss** is `moves_made`.
- Fitness for a **win** is `(45 - moves_made) + 46`.
  - This makes any winner outrank any loser.
  - Among winners, fewer moves are better.
- Selection:
  - computes `threshold_fitness` midway between min and max fitness.
  - seed population = genomes with fitness >= threshold.
- Reproduction:
  - new population starts as the seed set.
  - it repeatedly creates children via one-point crossover with a random genome.
  - mutation is applied per-instruction with a computed `mutation_rate`.
- Persistence:
  - copies `current_population.py` to `current_population.py_save`.
  - writes a stats file to `current_population.py_save_stats`.
  - writes the newly bred population back to `current_population.py`.


## The VM (how genomes execute)

Implemented in `breed/vm.py`.

### VM lifecycle per move

`GoVM.get_move(board, player, program)`:

1. `boot(board, program)` initializes:
   - registers (`reg_*`)
   - memory (`self.memory`, `self.stack_memory`)
   - board-info iterators (`self.bi_*`) from `board_info.get_board_info()`
2. Sets `reg_PLAYER`:
   - black => `-1`
   - white => `1`
3. Executes the program with `execute_program(max_clocks=4000)`.
4. Returns `(reg_X % 9, reg_Y % 9)` and the PC history.

### Operand canonicalization

`canonicalise(opcode, opdata)` converts the string-encoded operands into concrete values.

- immediate digits: `int(opdatum)`
- memory addressing:
  - `m<digits>` or `m<REG>` reads `self.memory[address % max_memoryons]`
  - `*<digits>` or `*<REG>` dereferences one level (reads `self.memory[self.memory[address] % max_memoryons]`)
- registers:
  - `REG` reads `self.reg_REG`
- special case for `mov` destination:
  - for the second operand of `mov`, the VM keeps the operand as a *name* (register or memory token), because it represents the destination.
- STN-derived values:
  - operands like `STN_C_STATS`, `STN_TL_XCOORD` are resolved through `process_STN_op()`.

### Board-info access: STN, neighbors, and iterators

The VM exposes the board through lists and a single “cursor” register:

- `reg_STN` is a coordinate tuple `(x, y)`.
- The VM maintains CircularList iterators:
  - stones: blacks, whites, spaces
  - “freedoms”: empty points adjacent (orthogonally) to at least one stone of a given color

Board-info opcodes set or move the STN cursor:

- `sstn A B`: set `reg_STN = (A, B)`
- `nstn` / `rstn`: iterate through all stones
- `nblk` / `rblk`: iterate blacks
- `nwht` / `rwht`: iterate whites
- `nfrn` / `rfrn`: iterate friendly stones (based on `reg_PLAYER`)
- `nnme` / `rnme`: iterate enemy stones
- `nspc` / `rspc`: iterate empty spaces
- `nblkf` / `rblkf`, `nwhtf` / `rwhtf`, `nfrnf` / `rfrnf`, `nnmef` / `rnmef`: iterate freedoms

STN-derived operands allow inspecting the current STN coordinate and its neighbors.

A board-pointer is one of: `TL, TT, TR, ML, C, MR, BL, BB, BR`.

- `STN_<BP>_XCOORD` / `STN_<BP>_YCOORD`:
  - returns the x or y coordinate of the STN neighbor at that board pointer offset.
- `STN_<BP>_STATS`:
  - returns a coded state value for that STN neighbor:
    - `-1`: black stone
    - `0`: empty
    - `1`: white stone
    - `2`: black freedom
    - `3`: white freedom
    - `4`: both freedoms
    - `9999`: off-board

This is the primary way genomes “sense” the board.

### Execution loop

`execute_program(max_clocks)`:

- Writes the currently running genome DNA to `config.vm_running_genome_file` (debug aid).
- Repeats until clock limit or PC reaches end of program:
  - records PC into `pc_history`
  - loads `(opcode, opdata)` from `self.program[self.reg_pc]`
  - canonicalises operands
  - dispatches the opcode via `self.opcodes[opcode](self, opdata)`
  - applies pending `PC_INTERRUPT` (for jumps)
  - otherwise increments PC
  - increments clock

### Key registers

The VM uses (at minimum):

- `X`, `Y`: move output registers
- `RES`: arithmetic result register
- `CRY`: remainder/carry register (set by `div`)
- `SGN`: sign of RES (-1/0/1)
- `LOG`: boolean-ish flag used for conditional branches (`jmpl`, `calll`, etc.)
- `PLAYER`: -1 black, +1 white
- `STN`: board cursor coordinate

### Instruction set summary

Arithmetic / bitwise:

- `add`, `sub`, `mul`, `div`, `incr`, `decr`
- `and`, `or`, `xor`, `not`
- `rnd` sets `RES` to a random value in roughly `[-rand_max/2, +rand_max/2]`

Comparisons (set `LOG`):

- `cmpe`, `cmpne`, `cmp0`, `cmplt`, `cmpgt`

Control flow:

- absolute and relative jumps: `jmp`, `jmpr`, `jmp0`, `jmpl`, `jmprl`, `jmpr0`
- call/return: `call`, `callr`, `call0`, `callr0`, `calll`, `callrl`, `ret`, `ret0`, `retl`

Memory / stack:

- `mov A B` (writes value A into destination B)
- `push`, `pop`

Board iteration:

- `sstn`, `nstn`, `rstn` and the `n*/r*` iterators for stones/spaces/freedoms


## The Go engine shim (GTP integration)

Implemented in `breed/go_engine.py`.

Important characteristics:

- Maintains `board[(x,y)]` with values:
  - `-1` black, `0` empty, `1` white
- Provides a scripted GTP handshake in `initialise()`.
- Translates between internal (x,y) and Go coordinates (A..J skipping I; rows 9..1).
- Does not implement full Go legality/capture rules; it primarily mirrors moves.
  - The external referee and opponent determine the “real” rules outcome.


## Board feature extraction

Implemented in `breed/board_info.py`.

- Iterates the 9x9 board and builds CircularLists of:
  - black stones
  - white stones
  - spaces
  - black freedoms / white freedoms (spaces adjacent orthogonally to stones)
- Returns these lists to the VM.


## Logging, outputs, and history

### Run log

- Most components append to `runlog.txt` (path from `config.runlog`).

### Optional per-move recording

When `config.record_stats` is `True`, `Mediator` will write to:

- `histories/<genome_hash>/game_<n>/move_<k>/`
  - `rundata_pc_history` (PC trace)
  - `rundata_board` (board render)
  - plus per-game metadata like player color and VM version


## Shell scripts and deployment

### Running a breeder instance

`breed_pop.sh` expects a deployed instance directory named `GoBreeder_<n>` and then runs:

- `python.exe mediator.py -gtp_breed -genome_file current_population.py`

and tails `runlog.txt`.

### Deploying per-instance copies

`deploy_breeder_instance.sh <n>`:

- copies the base tree into `/home/matth/breeders/GoBreeder_<n>`
- rewrites `breed/config.py` so `basepath` points at that instance’s `breed/` directory (as a Windows/Cygwin path string)

### Redeploying

`redeploy_breeder.sh` attempts to preserve histories/config/current files.

Note: as written it contains a likely typo (`saved__histories` vs `saved_histories`).


## Notable quirks / sharp edges

These are not necessarily “bugs” in the sense of breaking the original author’s workflow, but they are worth knowing when working on the code:

- `threaded_fileops.threaded_writelines()` appears to call the write function immediately instead of passing it as the thread target.
- The VM’s `general_purpose_registers` list is extended without extending weights (a comment in `vm.py` calls this out).
- `GoEngine.initialise()` expects an exact scripted GTP conversation; if the harness differs, init fails.
- Many constants assume board size 9.
- `GoVM.execute_program()` will `sys.exit(0)` if `reg_HALT` is set, which would terminate the engine process.


## How to run (practical checklist)

1. Ensure you have:
   - a Python 2.7 interpreter (or adjust code to Python 3)
   - Java installed (for Gosumi)
   - GoGui twogtp available at the configured path
   - the referee executable present
2. Update `breed/config.py` (or use `deploy_breeder_instance.sh`) so `basepath`, `pythonpath`, `two_gtp_command`, `enemy_program`, and `referee_program_command` are valid on your machine.
3. For a breeding run:
   - run from a deployed instance’s `breed/` directory:
     - `python.exe mediator.py -gtp_breed -genome_file current_population.py`
4. To pit a genome against an opponent via GoGui:
   - use `gogui-twogtp.exe` with the “player” program set to run `mediator.py -genome_file <that_genome_file>`.


## “What is it used for?” (conceptually)

- Experimenting with genetic programming of Go move selection.
- Studying how an instruction-based genome with very limited perception (STN cursor + neighbor stats + iterators) can evolve heuristics.
- Running many automated matches against a fixed opponent to drive selection pressure.

If you want, I can also add a short “glossary” section (GTP, STN, freedoms, PC history) or produce a minimal “getting started on a fresh machine” doc tailored to your current Windows environment.
