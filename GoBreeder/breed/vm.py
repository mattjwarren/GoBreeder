"""
Created on 4 Sep 2013

@author: GB108544

Fast path: `get_move` delegates to the Rust/PyO3 extension `go_vm_rs` when
available.  All class-level constants (register lists, opcode tables, etc.)
are kept here because ``data_structures.py`` imports them to generate genomes.
The pure-Python execution engine is preserved and used automatically when the
native extension is absent (e.g. on a fresh checkout without the wheel built).
"""

import array
import datetime
import logging
import random
import sys

import board_info
import config

# Attempt to load the Rust-accelerated VM.  Importing at module level means
# the cost is paid once per process, not once per move.
try:
    import go_vm_rs as _go_vm_rs  # type: ignore[import]

    _RUST_VM_AVAILABLE = True
except ImportError:
    _go_vm_rs = None  # type: ignore[assignment]
    _RUST_VM_AVAILABLE = False

logger = logging.getLogger(__name__)


def log(message: str) -> None:
    """Legacy shim: forward to module logger at DEBUG level."""
    logger.debug(message)


# ---------------------------------------------------------------------------
# Operand-kind constants used by the genome pre-compiler.
# Pre-compiling each instruction's operands once in boot() eliminates all
# string-parsing from the hot execution loop.
# ---------------------------------------------------------------------------
_OP_CONST = 0         # literal integer constant
_OP_REG = 1           # read register: getattr(self, attr_name)
_OP_MEM_CONST = 2     # read self.memory[const_addr]
_OP_MEM_REG = 3       # read self.memory[getattr(self, attr) % max]
_OP_DEREF_CONST = 4   # read self.memory[self.memory[const_addr] % max]
_OP_DEREF_REG = 5     # read self.memory[self.memory[getattr(self, attr) % max] % max]
_OP_MOV_REG = 6       # mov destination: plain register name kept as string
_OP_STN = 7           # STN_bp_op board-pointer operation: val = (bp_str, op_str)

# Frozenset of all program-accessible register names (without the "reg_" prefix).
# Used by __getattr__ / __setattr__ to forward legacy reg_* attribute access to
# self.regs dict.
_ACCESSIBLE_REGS: frozenset[str] = frozenset(
    ["X", "Y", "WXY", "RES", "CRY", "SGN", "LOG", "STN", "PLAYER"]
    + [f"X{n}" for n in range(8)]
    + [f"Y{n}" for n in range(8)]
    + [f"GP{n}" for n in range(8)]
)


class GoVM:
    working_X_registers = ["X" + str(N) for N in range(0, 8)]  # change in gogenmoe to
    working_Y_registers = ["Y" + str(N) for N in range(0, 8)]
    general_working_registers = ["GP" + str(N) for N in range(0, 8)]  # change in gogenmoe to

    board_pointers = ["TL", "TT", "TR", "ML", "C", "MR", "BL", "BB", "BR"]
    board_pointer_offsets = {
        "TL": (-1, -1),
        "TT": (0, -1),
        "TR": (1, -1),
        "ML": (-1, 0),
        "C": (0, 0),
        "MR": (1, 0),
        "BL": (-1, 1),
        "BB": (0, 1),
        "BR": (1, 1),
    }

    ####
    # can accept arbitrary values
    general_purpose_registers = working_X_registers + working_Y_registers
    general_purpose_weights = [1] * len(general_purpose_registers)

    general_purpose_registers += ["RES", "X", "Y", "WXY"]
    general_purpose_weights += [
        1,
        1,
        1,
        1,
    ]  # are the wieght definitions in the right place? breeder maybe? the VM shouldn't care about it.

    # BUG: TODO: is extending general_purpose_registers but not the weights a bug?
    general_purpose_registers += general_working_registers

    branching_instructions = [
        "jmp",
        "jmpr",
        "jmp0",
        "jmpl",
        "jmprl",
        "jmpr0",
        "call",
        "callr",
        "call0",
        "callr0",
        "calll",
        "callrl",
    ]

    # only set by result of instructions
    special_info_registers = ["CRY", "SGN", "LOG", "PLAYER"]
    special_info_weights = [1, 1, 1, 1]

    # only set by internal board_info
    stn_registers = ["STN"]
    stn_weights = [50]

    all_registers = special_info_registers + general_purpose_registers + stn_registers

    modulated_registers = {
        "WXY": config.board_size,
        "X": config.board_size,  # board_size: coords wrap at board boundary
        "Y": config.board_size,
    }

    for working_reg in working_X_registers + working_Y_registers:
        modulated_registers[working_reg] = config.board_size

    # note, all_registers does not include *all* the registers.
    # it only includes the registers that are available to program space
    # (which is generally what people really mean when they say all_registers)

    player_reg_lookup = {"black": -1, "white": 1}

    # ------------------------------------------------------------------
    # __slots__: removes per-instance __dict__, making every attribute
    # access a C-level slot lookup – faster writes in opcode methods and
    # reduced memory footprint per VM instance.
    # Program-accessible registers are stored in self.regs (a slotted dict);
    # control variables (reg_pc, reg_clock, reg_HALT, …) are separate slots.
    # ------------------------------------------------------------------
    __slots__ = (
        "regs",            # program-accessible register dict
        "max_memoryons", "version",
        "board", "program", "_compiled_program",
        "reg_pc", "reg_clock", "reg_HALT",
        "PC_INTERRUPT", "PC_INTERRUPT_A",
        "SPECIAL_VAL_INTERRUPT", "SPECIAL_VAL_INTERRUPT_A",
        "old_pc",
        "memory", "stack_memory",
        "bi_blacks", "bi_whites", "bi_spaces",
        "bi_white_freedoms", "bi_black_freedoms",
        "bi_legal_moves", "bi_illegal_moves", "bi_all_stones",
    )

    def __init__(self, memoryons=640 * 1024):  # ought to be enough for anyone
        self.max_memoryons = memoryons
        self.version = "1.0"

    # ------------------------------------------------------------------
    # Backward-compat attribute forwarding for tests / external callers.
    # Opcode methods and _resolve_operands use self.regs[name] directly
    # (no __getattr__/__setattr__ overhead on the hot path).
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> object:
        """Forward reg_* reads to self.regs for program-accessible registers."""
        if name.startswith("reg_"):
            reg_name = name[4:]
            if reg_name in _ACCESSIBLE_REGS:
                try:
                    return object.__getattribute__(self, "regs")[reg_name]
                except (AttributeError, KeyError):
                    pass
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: object) -> None:
        """Forward reg_* writes to self.regs for program-accessible registers."""
        if name.startswith("reg_"):
            reg_name = name[4:]
            if reg_name in _ACCESSIBLE_REGS:
                self.regs[reg_name] = value
                return
        super().__setattr__(name, value)

    # Run the genome, with the board info (should metadata the board stuff out as is Go sepcific)
    def get_move(self, board=dict(), player=None, program=list()):
        if _RUST_VM_AVAILABLE:
            return self._get_move_rust(board=board, player=player, program=program)
        return self._get_move_python(board=board, player=player, program=program)

    def _get_move_rust(self, board=dict(), player=None, program=list()):
        """Delegate execution to the Rust/PyO3 go_vm_rs extension.

        ``boot()`` is called on the Python instance so that register attributes
        (e.g. ``reg_X``, ``reg_Y``) remain accessible after the call, preserving
        the same post-execution interface as the pure-Python path.
        """
        self.boot(board=board, program=program)
        self.regs["PLAYER"] = GoVM.player_reg_lookup[player]
        move, pc_history = _go_vm_rs.get_move(board, player, program)
        # Sync the result coordinates back so callers can read reg_X / reg_Y.
        self.regs["X"] = move[0]
        self.regs["Y"] = move[1]
        return move, pc_history

    def _get_move_python(self, board=dict(), player=None, program=list()):
        self.boot(board=board, program=program)

        self.regs["PLAYER"] = GoVM.player_reg_lookup[player]
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("exec starts: %s", datetime.datetime.now())
        pc_history = self.execute_program(
            max_clocks=4000
        )  # up max clocks to twice. (5->10 hundred) what effect on current pop?
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("exec ends: %s", datetime.datetime.now())

        regs = self.regs
        move = (regs["X"] % config.board_size, regs["Y"] % config.board_size)
        self.set_board_info_memory()  # TODO: FAST!
        return move, pc_history

    def initialise_memories(self):
        self.initialise_registers()
        self.initialise_memory()

    def initialise_registers(self):
        # Build the register dict first so that subsequent assignments below
        # (via __setattr__) can route into it correctly.
        self.regs: dict = {
            "X": 0, "Y": 0, "RES": 0, "CRY": 0, "SGN": 0, "LOG": 1,
            "STN": (0, 0), "WXY": 0, "PLAYER": 0,
            **{f"X{n}": 0 for n in range(8)},
            **{f"Y{n}": 0 for n in range(8)},
            **{f"GP{n}": 0 for n in range(8)},
        }
        # internal control (kept as plain slots, not in regs)
        self.reg_pc = 0
        self.PC_INTERRUPT = False
        self.PC_INTERRUPT_A = 0
        self.SPECIAL_VAL_INTERRUPT = False
        self.SPECIAL_VAL_INTERRUPT_A = False
        self.reg_clock = 0
        self.reg_HALT = False
        self.old_pc = 0

    def initialise_memory(self):
        self.set_board_info_memory()
        # array.array('q') uses 8-byte signed ints: ~8× less allocation than a Python list.
        self.memory = array.array("q", (0 for _ in range(self.max_memoryons)))
        self.stack_memory = list()

    def set_board_info_memory(self):
        (
            self.bi_blacks,
            self.bi_whites,
            self.bi_spaces,
            self.bi_white_freedoms,
            self.bi_black_freedoms,
            self.bi_legal_moves,  # not implemented
            self.bi_illegal_moves,  #      "
            self.bi_all_stones,
        ) = board_info.get_board_info(board=self.board)

    def boot(self, board=dict(), program=list()):
        self.board = board
        self.program = program
        self.initialise_memories()
        # Avoid re-compiling the same genome on every move within a game.
        # GoGenome objects support arbitrary attribute storage; fall back to
        # re-compilation for plain lists and other types that don't.
        compiled = getattr(program, "_vm_compiled", None)
        if compiled is None:
            compiled = self._compile_program(program)
            try:
                program._vm_compiled = compiled
            except AttributeError:
                pass  # program type doesn't support attribute storage (e.g. plain list)
        self._compiled_program = compiled

    # ------------------------------------------------------------------
    # Genome pre-compiler – called once per boot(), not per clock tick.
    # ------------------------------------------------------------------

    def _parse_single_operand(self, opdatum: str | None, idx: int, opcode: str) -> tuple | None:
        """Parse one raw operand string into a tagged (kind, value) tuple.

        Returns None for None operands so callers can skip them cleanly.
        The *kind* is one of the _OP_* module constants; *value* is the
        pre-resolved static part (constant int, or register attribute name).
        """
        if opdatum is None:
            return None

        first = opdatum[0]  # faster than str(opdatum)[0] – already a str

        if first in "0123456789-":
            val = int(opdatum)
            # A plain number as mov's second operand is a memory destination
            # address.  Canonicalise returns it as an int; opcode_mov stores
            # into memory[B], so no special tag is needed – just _OP_CONST.
            return (_OP_CONST, val)

        if first in "m*":
            mem_loc_str = opdatum[1:]
            if mem_loc_str[0] in "0123456789-":
                # Pre-apply the modulo so the hot loop skips it at runtime.
                addr = int(mem_loc_str) % self.max_memoryons
                if first == "m":
                    return (_OP_MEM_CONST, addr)
                return (_OP_DEREF_CONST, addr)
            else:
                reg_attr = mem_loc_str  # bare register name (no "reg_" prefix)
                if first == "m":
                    return (_OP_MEM_REG, reg_attr)
                return (_OP_DEREF_REG, reg_attr)

        # Register name
        if idx == 1 and opcode == "mov":
            # Destination register: keep the plain name for opcode_mov.
            return (_OP_MOV_REG, opdatum)
        if opdatum[:3] == "STN":
            tokens = opdatum.split("_")
            return (_OP_STN, (tokens[1], tokens[2]))
        return (_OP_REG, opdatum)  # bare register name (no "reg_" prefix)

    def _compile_program(self, program: list) -> list:
        """Pre-parse every instruction into (opcode_fn, [tagged_ops]) tuples.

        This is called once per boot().  The result replaces per-tick string
        parsing in the execution loop.
        """
        opcodes_map = GoVM.opcodes
        compiled: list = []
        for opcode, opdata in program:
            fn = opcodes_map[opcode]
            tagged_ops: list = []
            for idx, opdatum in enumerate(opdata):
                parsed = self._parse_single_operand(opdatum, idx, opcode)
                if parsed is not None:
                    tagged_ops.append(parsed)
            compiled.append((fn, tagged_ops))
        return compiled

    def _resolve_operands(self, tagged_ops: list) -> list:
        """Resolve pre-compiled operand tags to runtime values.

        This replaces canonicalise() in the hot execution loop.  It uses
        integer tag comparisons instead of string parsing, and direct dict
        lookups on self.regs instead of getattr() machinery.
        """
        if not tagged_ops:
            return []
        memory = self.memory
        max_mem = self.max_memoryons
        regs = self.regs  # local alias: avoids repeated slot lookup per iteration
        result: list = []
        for tag, val in tagged_ops:
            if tag == _OP_CONST:
                result.append(val)
            elif tag == _OP_REG:
                result.append(regs[val])
            elif tag == _OP_MEM_CONST:
                result.append(memory[val])
            elif tag == _OP_MEM_REG:
                result.append(memory[regs[val] % max_mem])
            elif tag == _OP_DEREF_CONST:
                result.append(memory[memory[val] % max_mem])
            elif tag == _OP_DEREF_REG:
                loc = regs[val] % max_mem
                result.append(memory[memory[loc] % max_mem])
            elif tag == _OP_MOV_REG:
                result.append(val)       # register name string – used by opcode_mov
            else:                        # _OP_STN
                bp, op = val
                stn_val = self.process_STN_op(bp=bp, op=op)
                result.append(0 if stn_val is None else stn_val)
        return result

    def canonicalise(self, opcode, opdata):
        # Ok lets look at whats going on here.

        # opdata - a list of data opcodes.
        # opcodes can be,
        """
        [digits]    -    constant value. use as is
        [REG]        -    use value currently in [REG]
        m[digits]    -    use value in memory at [digits]
        m[REG]       -    use value in memory at [REG]
        *[digits]    -    use value in memory at [digits] as m[digits]
        *[REG]        -    use value in memory at [REG] as m[digits]

        """

        # this is the not flexible hacky way to do it.
        # hardcoded state machines. TODO: abstract and use metadata instead...
        new_opdata = list()
        for idx, opdatum in [(idx, opdatum) for idx, opdatum in enumerate(opdata) if opdatum is not None]:
            # are we dealing with REG or digits,?
            first = str(opdatum)[0]

            if first in "0123456789-":
                val = int(opdatum)
            elif first in "m*":
                mem_loc = opdatum[1:]
                if mem_loc[0] in "0123456789-":
                    mem_loc = int(mem_loc)
                else:  # its a register
                    mem_loc = getattr(self, "reg_" + mem_loc)
                val = self.memory[mem_loc % self.max_memoryons]
                # print '\tm* deref->mem_loc',mem_loc,'val',val
                if first == "*":
                    val = self.memory[val % self.max_memoryons]
                    # print '\t\t*->',val
            else:  # its a register
                # special case, if i'm the second opdatum and opcode is mov,
                # keep register name, dont canonicalise / rather, is already
                # standard representation for that data
                if (idx == 1) and (opcode == "mov"):
                    val = opdatum
                elif opdatum[0:3] == "STN":
                    tokens = opdatum.split("_")
                    _op, boardpointer, stn_op = tokens
                    val = self.process_STN_op(bp=boardpointer, op=stn_op)
                    if val is None:
                        val = 0
                else:
                    val = getattr(self, "reg_" + opdatum)
                    # opdata[idx]=val #this turned out to be a really bad idea
            new_opdata.append(val)
        return new_opdata

    def process_STN_op(self, bp=None, op=None):
        if self.regs["STN"] is None:
            return
        if op == "STATS":
            return self.stn_STATS(bp)
        else:
            return self.stn_COORDS(op, bp)

    def stn_STATS(self, bp):
        coords = self.regs["STN"]
        x, y = coords
        offset = self.board_pointer_offsets[bp]
        xo, yo = offset
        x += xo
        y += yo
        coords = (x, y)
        state = 0
        in_bi_black_freedoms = coords in self.bi_black_freedoms
        in_bi_white_freedoms = coords in self.bi_white_freedoms
        in_both_freedoms = in_bi_black_freedoms and in_bi_white_freedoms

        # order important
        if coords in self.bi_blacks:
            state = -1
        elif coords in self.bi_whites:
            state = 1
        elif in_both_freedoms:
            state = 4
        elif in_bi_black_freedoms:
            state = 2
        elif in_bi_white_freedoms:
            state = 3
        elif coords in self.bi_spaces:
            state = 0
        else:
            # new coords off board
            state = 9999
            # print 'COULD NOT DETERMINE STATE'
            # print coords
            # print self.bi_blacks
            # print self.bi_whites
            # print self.bi_spaces
            # sys.exit(0)
        return state

    def stn_COORDS(self, op, bp):
        xo, yo = self.board_pointer_offsets[bp]
        xs, ys = self.regs["STN"]
        xc = xs + xo
        yc = ys + yo
        if "X" in op:
            return xc
        else:
            return yc

        # TODO: add STN register. STN is the current stone under consideration,
        # from all_stones board memory info, current pointed to stone is
        # accessible with STN.   STN enables special info to be available with the following registers
        #        STN_{board_pointer}  select stone or neighbor to provide following info:
        #                           _STAT - STAT returns -1 /0 / 1 / 2 / 3 / 4 black, empty, white / black freedom / white freedom / both freedom
        #                                            into RES
        #                            _COORD - puts coordinate into selected working X/Y registers
        #
        # set_stn instruction, sets coords used for stn sstn
        # next_stn                                        nstn
        # rev_stn                                        rstn
        #   NOTE: Stone is a bit of a misnomer, named because
        # it loops through all_stones list - but it maylso
        # point to an empty space as indicated by set_stn

        ###board info instructions
        # these set STN based on the equivalent board_info lists
        # next_black
        # rev_black
        # next_white
        # rev_white
        # next_friendly
        # rev_friendly
        # next_enemy
        # rev_enemy

        # next_space
        # rev_space

        # next_white_freedom
        # rev_white_freedom
        # next_friendly_freedom
        # rev_friendly_freedom
        # next_enemy_freedom
        # rev_enemy_freedom
        # next_black_freedom
        # rev_black_freedom

    def ab(self, opdata):
        return opdata[0], opdata[1]

    def opcode_sstn(self, opdata):
        self.regs["STN"] = (opdata[0], opdata[1])

    def opcode_nstn(self, opdata):
        self.regs["STN"] = self.bi_all_stones.next()
        if self.regs["STN"] == 0:
            self.regs["STN"] = (0, 0)

    def opcode_rstn(self, opdata):
        self.bi_all_stones.reverse()

    def opcode_nblk(self, opdata):
        self.regs["STN"] = self.bi_blacks.next()
        if self.regs["STN"] == 0:
            self.regs["STN"] = (0, 0)

    def opcode_rblk(self, opdata):
        self.bi_blacks.reverse()

    def opcode_nwht(self, opdata):
        self.regs["STN"] = self.bi_whites.next()
        if self.regs["STN"] == 0:
            self.regs["STN"] = (0, 0)

    def opcode_rwht(self, opdata):
        self.bi_whites.reverse()

    def opcode_nfrn(self, opdata):
        if self.regs["PLAYER"] == -1:
            self.regs["STN"] = self.bi_blacks.next()
        else:
            self.regs["STN"] = self.bi_whites.next()
        if self.regs["STN"] == 0:
            self.regs["STN"] = (0, 0)

    def opcode_rfrn(self, opdata):
        if self.regs["PLAYER"] == -1:
            self.bi_blacks.reverse()
        else:
            self.bi_whites.reverse()

    def opcode_nnme(self, opdata):
        if self.regs["PLAYER"] == -1:
            self.regs["STN"] = self.bi_whites.next()
        else:
            self.regs["STN"] = self.bi_blacks.next()
        if self.regs["STN"] == 0:
            self.regs["STN"] = (0, 0)

    def opcode_rnme(self, opdata):
        if self.regs["PLAYER"] == -1:
            self.bi_whites.reverse()
        else:
            self.bi_blacks.reverse()

    def opcode_nspc(self, opdata):
        self.regs["STN"] = self.bi_spaces.next()
        if self.regs["STN"] == 0:
            self.regs["STN"] = (0, 0)

    def opcode_rspc(self, opdata):
        self.bi_spaces.reverse()

    def opcode_nblkf(self, opdata):
        self.regs["STN"] = self.bi_black_freedoms.next()
        if self.regs["STN"] == 0:
            self.regs["STN"] = (0, 0)

    def opcode_rblkf(self, opdata):
        self.bi_black_freedoms.reverse()

    def opcode_nwhtf(self, opdata):
        self.regs["STN"] = self.bi_white_freedoms.next()
        if self.regs["STN"] == 0:
            self.regs["STN"] = (0, 0)

    def opcode_rwhtf(self, opdata):
        self.bi_white_freedoms.reverse()

    def opcode_nfrnf(self, opdata):
        if self.regs["PLAYER"] == -1:
            self.regs["STN"] = self.bi_black_freedoms.next()
        else:
            self.regs["STN"] = self.bi_white_freedoms.next()
        if self.regs["STN"] == 0:
            self.regs["STN"] = (0, 0)

    def opcode_rfrnf(self, opdata):
        if self.regs["PLAYER"] == -1:
            self.bi_black_freedoms.reverse()
        else:
            self.bi_white_freedoms.reverse()

    def opcode_nnmef(self, opdata):
        if self.regs["PLAYER"] == -1:
            self.regs["STN"] = self.bi_white_freedoms.next()
        else:
            self.regs["STN"] = self.bi_black_freedoms.next()
        if self.regs["STN"] == 0:
            self.regs["STN"] = (0, 0)

    def opcode_rnmef(self, opdata):
        if self.regs["PLAYER"] == -1:
            self.bi_white_freedoms.reverse()
        else:
            self.bi_black_freedoms.reverse()

    def opcode_iwxy(self, opdata):
        self.regs["WXY"] += 1
        if self.regs["WXY"] > 7:
            self.regs["WXY"] = 0

    def opcode_dwxy(self, opdata):
        self.regs["WXY"] -= 1
        if self.regs["WXY"] < 0:
            self.regs["WXY"] = 7

    def opcode_add(self, opdata):
        regs = self.regs
        regs["RES"] = opdata[0] + opdata[1]
        if regs["RES"] < 0:
            regs["SGN"] = -1
        elif regs["RES"] == 0:
            regs["SGN"] = 0
        else:
            regs["SGN"] = 1

    def opcode_sub(self, opdata):
        regs = self.regs
        regs["RES"] = opdata[0] - opdata[1]
        if regs["RES"] < 0:
            regs["SGN"] = -1
        elif regs["RES"] == 0:
            regs["SGN"] = 0
        else:
            regs["SGN"] = 1

    def opcode_incr(self, opdata):  # Taking no data / accept empty or nothing passed, or None?
        # turns out, every opcode gets a list of 2 data items, and only inspects what they need. extra cruft is cruft! so sue me!
        regs = self.regs
        regs["RES"] = regs["RES"] + 1
        if regs["RES"] < 0:
            regs["SGN"] = -1
        elif regs["RES"] == 0:
            regs["SGN"] = 0
        else:
            regs["SGN"] = 1

    def opcode_decr(self, opdata):
        regs = self.regs
        regs["RES"] = regs["RES"] - 1
        if regs["RES"] < 0:
            regs["SGN"] = -1
        elif regs["RES"] == 0:
            regs["SGN"] = 0
        else:
            regs["SGN"] = 1

    def opcode_mul(self, opdata):
        regs = self.regs
        regs["RES"] = opdata[0] * opdata[1]
        if regs["RES"] < 0:
            regs["SGN"] = -1
        elif regs["RES"] == 0:
            regs["SGN"] = 0
        else:
            regs["SGN"] = 1

    def opcode_div(self, opdata):
        regs = self.regs
        A, B = opdata[0], opdata[1]
        try:
            regs["RES"] = A // B  # integer division (Python 2 `/` behaviour)
            regs["CRY"] = A % B
        except ZeroDivisionError:
            regs["RES"] = 0
            regs["CRY"] = 0
        if regs["RES"] < 0:
            regs["SGN"] = -1
        elif regs["RES"] == 0:
            regs["SGN"] = 0
        else:
            regs["SGN"] = 1

    def opcode_cmpe(self, opdata):
        self.regs["LOG"] = 1 if opdata[0] == opdata[1] else 0

    def opcode_cmpne(self, opdata):
        self.regs["LOG"] = 1 if opdata[0] != opdata[1] else 0

    def opcode_cmp0(self, opdata):
        self.regs["LOG"] = 1 if opdata[0] == 0 else 0

    def opcode_cmplt(self, opdata):
        self.regs["LOG"] = 1 if opdata[0] < opdata[1] else 0

    def opcode_cmpgt(self, opdata):
        self.regs["LOG"] = 1 if opdata[0] > opdata[1] else 0

    def opcode_and(self, opdata):
        regs = self.regs
        regs["RES"] = opdata[0] & opdata[1]
        if regs["RES"] < 0: regs["SGN"] = -1
        elif regs["RES"] == 0: regs["SGN"] = 0
        else: regs["SGN"] = 1

    def opcode_or(self, opdata):
        regs = self.regs
        regs["RES"] = opdata[0] | opdata[1]
        if regs["RES"] < 0: regs["SGN"] = -1
        elif regs["RES"] == 0: regs["SGN"] = 0
        else: regs["SGN"] = 1

    def opcode_not(self, opdata):
        regs = self.regs
        regs["RES"] = ~opdata[0]
        if regs["RES"] < 0: regs["SGN"] = -1
        elif regs["RES"] == 0: regs["SGN"] = 0
        else: regs["SGN"] = 1

    def opcode_xor(self, opdata):
        regs = self.regs
        regs["RES"] = opdata[0] ^ opdata[1]
        if regs["RES"] < 0: regs["SGN"] = -1
        elif regs["RES"] == 0: regs["SGN"] = 0
        else: regs["SGN"] = 1

    def opcode_jmp(self, opdata):  # jmp, not call. so dont push/pop reg_pc + jmp onto the stack
        A = opdata[0]
        if A > 0:
            self.PC_INTERRUPT = True
            self.PC_INTERRUPT_A = A

    def opcode_jmpr(self, opdata):
        A = opdata[0]
        if A != 0:
            abs_A = self.reg_pc + A
            # maybe have a jump relative to given address as well as current PC?
            self.opcode_jmp((abs_A,))

    def opcode_jmp0(self, opdata):
        A = opdata[0]
        if self.regs["RES"] == 0:
            self.opcode_jmp((A,))

    def opcode_jmpl(self, opdata):
        A = opdata[0]
        if self.regs["LOG"]:
            self.opcode_jmp((A,))

    def opcode_jmprl(self, opdata):
        A = opdata[0]
        if A != 0:
            abs_A = self.reg_pc + A
            if self.regs["LOG"]:
                self.opcode_jmp((abs_A,))

    def opcode_jmpr0(self, opdata):
        A = opdata[0]
        if A != 0:
            if self.regs["RES"] == 0:
                abs_A = self.reg_pc + A
                self.opcode_jmpr((abs_A,))

    def opcode_call(self, opdata):
        A = opdata[0]
        if A > 0:
            self.push_pc()
            self.opcode_jmp((A,))

    def opcode_callr(self, opdata):
        A = opdata[0]
        if A != 0:
            self.push_pc()
            self.opcode_jmpr((A,))

    def opcode_call0(self, opdata):
        A = opdata[0]
        if A != 0:
            if self.regs["RES"] == 0:
                self.push_pc()
                self.opcode_jmp((A,))

    def opcode_callr0(self, opdata):
        A = opdata[0]
        if A != 0:
            if self.regs["RES"] == 0:
                self.push_pc()
                self.opcode_jmpr((A,))

    def opcode_calll(self, opdata):
        A = opdata[0]
        if A != 0:
            if self.regs["LOG"]:
                self.push_pc()
                self.opcode_jmp((A,))

    def opcode_callrl(self, opdata):
        A = opdata[0]
        if A != 0:
            if self.regs["LOG"]:
                self.push_pc()
                self.opcode_jmpr((A,))

    def opcode_ret(self, opdata):
        A = self.pop_pc()
        if A is not None:
            # print '\t\t..>returning'
            self.opcode_jmp((A,))

    def opcode_ret0(self, opdata):
        if self.regs["RES"] == 0:
            A = self.pop_pc()
            if A is not None:
                self.opcode_jmp((A,))

    def opcode_retl(self, opdata):
        if self.regs["LOG"]:
            A = self.pop_pc()
            if A is not None:
                self.opcode_jmp((A,))

    def opcode_mov(self, opdata):
        A = opdata[0]
        if A is None:
            A = 0
        B = opdata[1]
        if isinstance(B, str):
            if B == "WXY":
                A = A % config.board_size
            self.regs[B] = A
        else:
            # Clamp to signed 64-bit range for array.array('q') compatibility.
            self.memory[B % self.max_memoryons] = int(A) & 0x7FFFFFFFFFFFFFFF
        regs = self.regs
        if regs["RES"] < 0: regs["SGN"] = -1
        elif regs["RES"] == 0: regs["SGN"] = 0
        else: regs["SGN"] = 1

    def opcode_push(self, opdata):
        A = opdata[0]
        self.push(A)

    def opcode_pop(self, opdata):
        A = self.pop()
        if A is None:
            A = 0
        self.regs["RES"] = A

    def opcode_rnd(self, opdata: list) -> None:
        """Generate a random integer in [-rand_max/2, rand_max/2) and store in RES."""
        regs = self.regs
        regs["RES"] = int(random.random() * config.rand_max) - (config.rand_max // 2)
        if regs["RES"] < 0: regs["SGN"] = -1
        elif regs["RES"] == 0: regs["SGN"] = 0
        else: regs["SGN"] = 1

    def set_SGN(self):
        regs = self.regs
        if regs["RES"] < 0:
            regs["SGN"] = -1
        elif regs["RES"] == 0:
            regs["SGN"] = 0
        else:
            regs["SGN"] = 1

    def push_pc(self):
        self.push(self.reg_pc + 1)  # MEMORY_OUT_OF_BOUNDS STARTS HERE.
        # ((+1 to jump back to the intruction _after_ the originating call))

    def push(self, value):
        self.stack_memory.append(value)

    def pop(self):  # **use the collections module, waz
        # return 0 if stack empty
        if len(self.stack_memory) == 0:
            return None
        return self.stack_memory.pop()  # O(1) in-place pop, not list copy

    def pop_pc(self):
        return self.pop()

    def execute_program(self, max_clocks=10000):
        pc_history = list()
        try:
            running_genome = open(config.vm_running_genome_file, "w")
            running_genome.write(repr(self.program.dna) + "\n")
            running_genome.close()
        except OSError:
            pass  # non-fatal: running-genome debug file may not be writable in test env

        # Cache debug flag outside the loop so each tick avoids re-checking.
        _debug = logger.isEnabledFor(logging.DEBUG)

        compiled = self._compiled_program
        prog_len = len(compiled)

        # NEED TO IMPLEMENT pc LOOP DETECTION /ora t least stuck-pc etc../
        while (self.reg_clock < max_clocks) and (self.reg_pc < prog_len):
            if self.reg_pc < 0:
                print("DEBUG: REG_PC less than ZERO!! =", self.reg_pc)
                print("STAACK", self.stack_memory[-1:])
                # Note: original code set `global logging = True` here to
                # enable tracing, but that shadowed the logging module.  The
                # negative-PC path is a guard for a state that should never
                # occur; the print above is sufficient notification.
                self.reg_pc = self.old_pc
                self.reg_HALT = True

            pc_history.append(self.reg_pc)

            fn, tagged_ops = compiled[self.reg_pc]

            if _debug:
                op = self.program[self.reg_pc]
                opcode = op[0]
                opdata_raw = op[1]
                logger.debug(">CLOCK %d PC %d", self.reg_clock, self.reg_pc)
                logger.debug("\tBase op: %s%s", opcode, opdata_raw)

            opdata = self._resolve_operands(tagged_ops)

            if _debug:
                logger.debug("\tCanonical: %s%s", opcode, opdata)

            # exec
            fn(self, opdata)

            if _debug:
                regs = self.regs
                logger.debug(
                    "\top: %s%s, pc %d, clk %d, RES %d, CRY %d, SGN %d, LOG %d, X:Y %d:%d",
                    opcode, opdata,
                    self.reg_pc, self.reg_clock,
                    regs["RES"], regs["CRY"], regs["SGN"], regs["LOG"],
                    regs["X"], regs["Y"],
                )
                logger.debug(
                    "\tGP: %d %d %d %d %d %d %d %d",
                    regs["GP0"], regs["GP1"], regs["GP2"], regs["GP3"],
                    regs["GP4"], regs["GP5"], regs["GP6"], regs["GP7"],
                )
                logger.debug(
                    "\tGX: %d %d %d %d %d %d %d %d",
                    regs["X0"], regs["X1"], regs["X2"], regs["X3"],
                    regs["X4"], regs["X5"], regs["X6"], regs["X7"],
                )
                logger.debug(
                    "\tGY: %d %d %d %d %d %d %d %d",
                    regs["Y0"], regs["Y1"], regs["Y2"], regs["Y3"],
                    regs["Y4"], regs["Y5"], regs["Y6"], regs["Y7"],
                )
                logger.debug("\tWXY %d PLAYER %d Stone %s", regs["WXY"], regs["PLAYER"], regs["STN"])
                logger.debug("\twhites%s", self.bi_whites)
                logger.debug("\tblacks%s", self.bi_blacks)
                logger.debug("\tspaces%s", self.bi_spaces._direction)
                logger.debug("\twhiteF%s", self.bi_white_freedoms)
                logger.debug("\tblackF%s", self.bi_black_freedoms)
                logger.debug("\tallstns%s", self.bi_all_stones)
                logger.debug("\tstack: ...%d%s", len(self.stack_memory), self.stack_memory[-10:])
                logger.debug("\tMEM50: %s", self.memory[0:50])

            self.old_pc = self.reg_pc
            if self.PC_INTERRUPT:
                self.old_pc = self.reg_pc
                if _debug:
                    logger.debug("\tPC_INTERRUPT  ->  %s", self.PC_INTERRUPT_A)
                self.reg_pc = self.PC_INTERRUPT_A % prog_len
                self.PC_INTERRUPT = False
                self.PC_INTERRUPT_A = None
            else:
                if _debug:
                    logger.debug("\tIncr reg_pc")
                self.reg_pc += 1
            if self.reg_HALT:
                print("FORCED HALT BY reg_HALT")
                sys.exit(0)
            if _debug:
                logger.debug("\tIncr reg_clock")
            self.reg_clock += 1
        return pc_history

    # print 'HALT',self.reg_clock

    opcodes = {
        "add": opcode_add,
        "sub": opcode_sub,
        "incr": opcode_incr,
        "decr": opcode_decr,
        "mul": opcode_mul,
        "div": opcode_div,
        "cmpe": opcode_cmpe,
        "cmpne": opcode_cmpne,
        "cmp0": opcode_cmp0,
        "cmplt": opcode_cmplt,
        "cmpgt": opcode_cmpgt,
        "and": opcode_and,
        "or": opcode_or,
        "not": opcode_not,
        "xor": opcode_xor,
        "jmp": opcode_jmp,
        "jmpr": opcode_jmpr,
        "jmp0": opcode_jmp0,
        "jmpl": opcode_jmpl,
        "jmprl": opcode_jmprl,
        "jmpr0": opcode_jmpr0,
        "call": opcode_call,
        "callr": opcode_callr,
        "call0": opcode_call0,
        "callr0": opcode_callr0,
        "calll": opcode_calll,
        "callrl": opcode_callrl,
        "ret": opcode_ret,
        "ret0": opcode_ret0,
        "retl": opcode_retl,
        "mov": opcode_mov,
        "push": opcode_push,
        "pop": opcode_pop,
        "rnd": opcode_rnd,
        # The ~special sauce~ from here down
        "sstn": opcode_sstn,
        "nstn": opcode_nstn,
        "rstn": opcode_rstn,
        "nblk": opcode_nblk,
        "nwht": opcode_nwht,
        "rwht": opcode_rwht,
        "nfrn": opcode_nfrn,
        "rfrn": opcode_rfrn,
        "nnme": opcode_nnme,
        "rnme": opcode_rnme,
        "nspc": opcode_nspc,
        "rspc": opcode_rspc,
        "nblkf": opcode_nblkf,
        "rblkf": opcode_rblkf,
        "nwhtf": opcode_nwhtf,
        "rwhtf": opcode_rwhtf,
        "nfrnf": opcode_nfrnf,
        "rfrnf": opcode_rfrnf,
        "nnmef": opcode_nnmef,
        "rnmef": opcode_rnmef,
        "iwxy": opcode_iwxy,
        "dwxy": opcode_dwxy,
    }
