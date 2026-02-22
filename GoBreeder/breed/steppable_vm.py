"""Steppable GoVM: generator-based single-step execution with snapshot capture."""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

import config
import vm
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class BoardInfoSnapshot(BaseModel):
    """Snapshot of a single CircularList's state."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    values: list[Any]
    ptr: int
    current_value: Any | None


class VMStepSnapshot(BaseModel):
    """Complete snapshot of VM state at a single clock tick."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    clock: int
    pc: int
    current_instruction: tuple[str, list[Any]] | None  # (opcode, [operand1, operand2])
    canonical_opdata: list[Any]
    # Registers
    reg_X: int
    reg_Y: int
    reg_RES: int
    reg_CRY: int
    reg_SGN: int
    reg_LOG: int
    reg_STN: tuple[int, int]
    reg_WXY: int
    reg_PLAYER: int
    reg_PC_INTERRUPT: bool
    reg_PC_INTERRUPT_A: int | None
    reg_HALT: bool
    # X working registers
    reg_X0: int
    reg_X1: int
    reg_X2: int
    reg_X3: int
    reg_X4: int
    reg_X5: int
    reg_X6: int
    reg_X7: int
    # Y working registers
    reg_Y0: int
    reg_Y1: int
    reg_Y2: int
    reg_Y3: int
    reg_Y4: int
    reg_Y5: int
    reg_Y6: int
    reg_Y7: int
    # GP registers
    reg_GP0: int
    reg_GP1: int
    reg_GP2: int
    reg_GP3: int
    reg_GP4: int
    reg_GP5: int
    reg_GP6: int
    reg_GP7: int
    # Memory
    stack_top_10: list[Any]
    memory_0_to_50: list[int]
    # Board info
    board_info: dict[str, BoardInfoSnapshot]
    board: dict[str, int]  # "(x,y)" -> int
    halt: bool
    # Move (final output)
    move_x: int
    move_y: int


class SteppableGoVM(vm.GoVM):
    """GoVM subclass with generator-based step execution."""

    # Inherit all slots from GoVM without adding a __dict__.
    __slots__ = ()

    # Type annotations for parent-class attributes that are set dynamically in
    # GoVM.boot() / GoVM.initialise_registers().  These declarations shadow the
    # untyped parent attributes so mypy can reason about them here.
    reg_pc: int
    reg_clock: int
    reg_HALT: bool
    PC_INTERRUPT: bool
    PC_INTERRUPT_A: int | None
    old_pc: int
    program: Any

    def _capture_board_info(self) -> dict[str, BoardInfoSnapshot]:
        result: dict[str, BoardInfoSnapshot] = {}
        for name, bi in [
            ("blacks", self.bi_blacks),
            ("whites", self.bi_whites),
            ("spaces", self.bi_spaces),
            ("white_freedoms", self.bi_white_freedoms),
            ("black_freedoms", self.bi_black_freedoms),
            ("all_stones", self.bi_all_stones),
        ]:
            try:
                values = list(bi.values) if bi.values else []
                ptr = bi._ptr if bi._ptr is not None else 0
                current_value = values[ptr] if values and 0 <= ptr < len(values) else None
            except Exception:  # noqa: BLE001
                values = []
                ptr = 0
                current_value = None
            result[name] = BoardInfoSnapshot(values=values, ptr=ptr, current_value=current_value)
        return result

    def _capture_snapshot(
        self,
        current_instruction: tuple[str, list[Any]] | None = None,
        canonical_opdata: list[Any] | None = None,
    ) -> VMStepSnapshot:
        """Capture the complete current VM state as a snapshot."""
        board_str_keys = {str(k): v for k, v in self.board.items()}

        regs = self.regs
        stn = regs["STN"] if isinstance(regs["STN"], tuple) else (0, 0)

        return VMStepSnapshot(
            clock=self.reg_clock,
            pc=self.reg_pc,
            current_instruction=current_instruction,
            canonical_opdata=canonical_opdata or [],
            reg_X=regs["X"],
            reg_Y=regs["Y"],
            reg_RES=regs["RES"],
            reg_CRY=regs["CRY"],
            reg_SGN=regs["SGN"],
            reg_LOG=regs["LOG"],
            reg_STN=stn,
            reg_WXY=regs["WXY"],
            reg_PLAYER=regs["PLAYER"],
            reg_PC_INTERRUPT=self.PC_INTERRUPT,
            reg_PC_INTERRUPT_A=self.PC_INTERRUPT_A,
            reg_HALT=self.reg_HALT,
            reg_X0=regs["X0"],
            reg_X1=regs["X1"],
            reg_X2=regs["X2"],
            reg_X3=regs["X3"],
            reg_X4=regs["X4"],
            reg_X5=regs["X5"],
            reg_X6=regs["X6"],
            reg_X7=regs["X7"],
            reg_Y0=regs["Y0"],
            reg_Y1=regs["Y1"],
            reg_Y2=regs["Y2"],
            reg_Y3=regs["Y3"],
            reg_Y4=regs["Y4"],
            reg_Y5=regs["Y5"],
            reg_Y6=regs["Y6"],
            reg_Y7=regs["Y7"],
            reg_GP0=regs["GP0"],
            reg_GP1=regs["GP1"],
            reg_GP2=regs["GP2"],
            reg_GP3=regs["GP3"],
            reg_GP4=regs["GP4"],
            reg_GP5=regs["GP5"],
            reg_GP6=regs["GP6"],
            reg_GP7=regs["GP7"],
            stack_top_10=list(self.stack_memory[-10:]),
            memory_0_to_50=list(self.memory[0:50]),
            board_info=self._capture_board_info(),
            board=board_str_keys,
            halt=bool(self.reg_HALT),
            move_x=regs["X"],
            move_y=regs["Y"],
        )

    def step_generator(self, max_clocks: int = 4000) -> Generator[VMStepSnapshot, None, None]:
        """Generator that yields a VMStepSnapshot after each instruction execution.

        The generator replaces execute_program(). Call next() to step one instruction.
        The generator terminates when the program ends or max_clocks is reached.

        The body of each iteration matches execute_program() exactly so results
        are identical to running the program in one shot.
        """
        compiled = self._compiled_program
        prog_len = len(compiled)

        while (self.reg_clock < max_clocks) and (self.reg_pc < prog_len):
            if self.reg_pc < 0:
                logger.debug("REG_PC less than ZERO: %d", self.reg_pc)
                self.reg_pc = getattr(self, "old_pc", 0)
                self.reg_HALT = True

            op = self.program[self.reg_pc]
            opcode = op[0]
            current_instr: tuple[str, list[Any]] = (opcode, list(op[1]) if op[1] else [])

            fn, tagged_ops = compiled[self.reg_pc]
            canonical = self._resolve_operands(tagged_ops)

            logger.debug(">CLOCK %d PC %d opcode=%s", self.reg_clock, self.reg_pc, opcode)

            fn(self, canonical)

            self.old_pc = self.reg_pc
            if self.PC_INTERRUPT and self.PC_INTERRUPT_A is not None:
                self.old_pc = self.reg_pc
                self.reg_pc = self.PC_INTERRUPT_A % prog_len
                self.PC_INTERRUPT = False
                self.PC_INTERRUPT_A = None
            else:
                self.reg_pc += 1

            if self.reg_HALT:
                logger.debug("FORCED HALT BY reg_HALT at clock %d", self.reg_clock)
                snapshot = self._capture_snapshot(current_instr, list(canonical))
                yield snapshot
                return

            self.reg_clock += 1

            snapshot = self._capture_snapshot(current_instr, list(canonical))
            yield snapshot

    def get_move(
        self,
        board: dict = {},  # noqa: B006
        player: str = "black",
        program: list = [],  # noqa: B006
    ) -> tuple:
        """Override get_move to use step_generator for identical results to GoVM."""
        self.boot(board=board, program=program)
        self.regs["PLAYER"] = vm.GoVM.player_reg_lookup[player]

        logger.debug("SteppableGoVM exec starts")

        last_snapshot = None
        for snapshot in self.step_generator(max_clocks=4000):
            last_snapshot = snapshot  # noqa: F841

        logger.debug("SteppableGoVM exec ends")

        regs = self.regs
        move = (regs["X"] % config.board_size, regs["Y"] % config.board_size)
        self.set_board_info_memory()
        return move, []
