//! go_vm_rs – Rust re-implementation of the GoBreeder VM, exposed to Python
//! via PyO3.
//!
//! Public surface: a single free function `get_move(board, player, dna)` that
//! mirrors the Python `GoVM.get_move()` signature and return type.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};
use rand::Rng;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BOARD_SIZE: usize = 9;
const MEM_SIZE: usize = 640 * 1024;
const RAND_MAX: i64 = 9;
const MAX_CLOCKS: usize = 4000;
const NUM_REGS: usize = 34;

// Register indices in the flat regs array.
const R_X: usize = 0;
const R_Y: usize = 1;
const R_WXY: usize = 2;
const R_RES: usize = 3;
const R_CRY: usize = 4;
// R_SGN = 5, R_LOG = 6, R_PLAYER = 7 – referenced by const below
const R_SGN: usize = 5;
const R_LOG: usize = 6;
const R_PLAYER: usize = 7;
// X0..X7 → 8..15
// Y0..Y7 → 16..23
// GP0..GP7 → 24..31
const R_STN_X: usize = 32;
const R_STN_Y: usize = 33;

/// Board-pointer offsets: TL, TT, TR, ML, C, MR, BL, BB, BR
const BP_OFFSETS: [(i64, i64); 9] = [
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (0, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
];

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, Debug, PartialEq)]
#[repr(u8)]
enum Opcode {
    Add,
    Sub,
    Incr,
    Decr,
    Mul,
    Div,
    Cmpe,
    Cmpne,
    Cmp0,
    Cmplt,
    Cmpgt,
    And,
    Or,
    Not,
    Xor,
    Jmp,
    Jmpr,
    Jmp0,
    Jmpl,
    Jmprl,
    Jmpr0,
    Call,
    Callr,
    Call0,
    Callr0,
    Calll,
    Callrl,
    Ret,
    Ret0,
    Retl,
    Mov,
    Push,
    Pop,
    Rnd,
    Sstn,
    Nstn,
    Rstn,
    Nblk,
    Rblk,
    Nwht,
    Rwht,
    Nfrn,
    Rfrn,
    Nnme,
    Rnme,
    Nspc,
    Rspc,
    Nblkf,
    Rblkf,
    Nwhtf,
    Rwhtf,
    Nfrnf,
    Rfrnf,
    Nnmef,
    Rnmef,
    Iwxy,
    Dwxy,
}

/// Type of a STN board-pointer operation.
#[derive(Clone, Copy, Debug)]
enum StnOp {
    Stats,
    XCoord,
    YCoord,
}

/// Pre-compiled operand tag.  All variants are `Copy` so `Instr` is `Copy`.
#[derive(Clone, Copy, Debug)]
enum Operand {
    /// No operand (instruction takes fewer args than the slot count).
    None,
    /// Literal integer constant.
    Const(i64),
    /// Value of register at index.
    Reg(usize),
    /// Value of memory at constant address.
    MemConst(usize),
    /// Value of memory[regs[r] % MEM_SIZE].
    MemReg(usize),
    /// Value of memory[memory[addr] % MEM_SIZE].
    DerefConst(usize),
    /// Value of memory[memory[regs[r] % MEM_SIZE] % MEM_SIZE].
    DerefReg(usize),
    /// Result of a board-pointer STN query.
    StnOp(u8, StnOp),
    /// mov destination: a register index.
    RegDest(usize),
    /// mov destination: a memory address (already reduced mod MEM_SIZE).
    MemDest(usize),
}

/// One pre-compiled VM instruction.
#[derive(Clone, Copy, Debug)]
struct Instr {
    op: Opcode,
    a: Operand,
    b: Operand,
}

// ---------------------------------------------------------------------------
// CircularList
// ---------------------------------------------------------------------------

/// A post-incrementing circular list that mirrors `data_structures.CircularList`.
#[derive(Clone, Debug)]
struct CircularList {
    values: Vec<(i32, i32)>,
    ptr: usize,
    direction: i32, // +1 = forward, -1 = backward
}

impl CircularList {
    fn new() -> Self {
        CircularList {
            values: Vec::new(),
            ptr: 0,
            direction: 1,
        }
    }

    fn add(&mut self, coord: (i32, i32)) {
        self.values.push(coord);
    }

    /// Return current value and advance pointer, returning `(0,0)` if empty.
    fn next(&mut self) -> (i32, i32) {
        if self.values.is_empty() {
            return (0, 0);
        }
        let val = self.values[self.ptr];
        let len = self.values.len() as i64;
        let next_ptr = self.ptr as i64 + self.direction as i64;
        self.ptr = next_ptr.rem_euclid(len) as usize;
        val
    }

    fn reverse(&mut self) {
        self.direction = -self.direction;
    }

    fn contains(&self, coord: (i32, i32)) -> bool {
        self.values.contains(&coord)
    }
}

// ---------------------------------------------------------------------------
// BoardInfo
// ---------------------------------------------------------------------------

struct BoardInfo {
    blacks: CircularList,
    whites: CircularList,
    spaces: CircularList,
    white_freedoms: CircularList,
    black_freedoms: CircularList,
    all_stones: CircularList,
}

impl BoardInfo {
    fn build(board: &[i8; BOARD_SIZE * BOARD_SIZE]) -> Self {
        let mut blacks = CircularList::new();
        let mut whites = CircularList::new();
        let mut spaces = CircularList::new();
        let mut white_freedoms = CircularList::new();
        let mut black_freedoms = CircularList::new();

        for x in 0..BOARD_SIZE as i32 {
            for y in 0..BOARD_SIZE as i32 {
                let v = board[y as usize * BOARD_SIZE + x as usize];
                match v {
                    -1 => blacks.add((x, y)),
                    1 => whites.add((x, y)),
                    _ => {
                        // empty: check straight neighbours
                        let mut has_black = false;
                        let mut has_white = false;
                        for (dx, dy) in [(0i32, 1i32), (-1, 0), (1, 0), (0, -1)] {
                            let nx = x + dx;
                            let ny = y + dy;
                            if nx >= 0
                                && nx < BOARD_SIZE as i32
                                && ny >= 0
                                && ny < BOARD_SIZE as i32
                            {
                                let nv = board[ny as usize * BOARD_SIZE + nx as usize];
                                if nv == -1 {
                                    has_black = true;
                                }
                                if nv == 1 {
                                    has_white = true;
                                }
                            }
                        }
                        if has_white {
                            white_freedoms.add((x, y));
                        }
                        if has_black {
                            black_freedoms.add((x, y));
                        }
                        spaces.add((x, y));
                    }
                }
            }
        }

        // all_stones = blacks + whites (in that order, matching Python)
        let mut all_stones = CircularList::new();
        for &c in &blacks.values {
            all_stones.add(c);
        }
        for &c in &whites.values {
            all_stones.add(c);
        }

        BoardInfo {
            blacks,
            whites,
            spaces,
            white_freedoms,
            black_freedoms,
            all_stones,
        }
    }
}

// ---------------------------------------------------------------------------
// Circular-list selectors (passed as u8 to circ_next / circ_reverse)
// ---------------------------------------------------------------------------
const CL_ALL: u8 = 0;
const CL_BLACKS: u8 = 1;
const CL_WHITES: u8 = 2;
const CL_SPACES: u8 = 3;
const CL_BLACK_F: u8 = 4;
const CL_WHITE_F: u8 = 5;

// ---------------------------------------------------------------------------
// VM
// ---------------------------------------------------------------------------

struct VM {
    regs: [i64; NUM_REGS],
    memory: Vec<i64>,
    stack: Vec<i64>,
    pc: usize,
    clock: usize,
    pc_interrupt: bool,
    pc_interrupt_a: usize,
    board_info: BoardInfo,
}

impl VM {
    fn new(board: &[i8; BOARD_SIZE * BOARD_SIZE]) -> Self {
        let mut regs = [0i64; NUM_REGS];
        regs[R_LOG] = 1; // LOG defaults to 1 in Python
        VM {
            regs,
            memory: vec![0i64; MEM_SIZE],
            stack: Vec::new(),
            pc: 0,
            clock: 0,
            pc_interrupt: false,
            pc_interrupt_a: 0,
            board_info: BoardInfo::build(board),
        }
    }

    // ------------------------------------------------------------------
    // Operand resolution (hot path)
    // ------------------------------------------------------------------

    #[inline(always)]
    fn resolve_val(&self, op: Operand) -> i64 {
        match op {
            Operand::None => 0,
            Operand::Const(v) => v,
            Operand::Reg(r) => self.regs[r],
            Operand::MemConst(addr) => self.memory[addr],
            Operand::MemReg(r) => {
                self.memory[self.regs[r].rem_euclid(MEM_SIZE as i64) as usize]
            }
            Operand::DerefConst(addr) => {
                self.memory[self.memory[addr].rem_euclid(MEM_SIZE as i64) as usize]
            }
            Operand::DerefReg(r) => {
                let loc = self.regs[r].rem_euclid(MEM_SIZE as i64) as usize;
                self.memory[self.memory[loc].rem_euclid(MEM_SIZE as i64) as usize]
            }
            Operand::StnOp(bp_idx, stn_op) => self.process_stn(bp_idx as usize, stn_op),
            // destinations – should not appear as a source; return 0 safely
            Operand::RegDest(_) | Operand::MemDest(_) => 0,
        }
    }

    #[inline(always)]
    fn process_stn(&self, bp_idx: usize, stn_op: StnOp) -> i64 {
        let (ox, oy) = BP_OFFSETS[bp_idx];
        let x = self.regs[R_STN_X] + ox;
        let y = self.regs[R_STN_Y] + oy;

        match stn_op {
            StnOp::XCoord => x,
            StnOp::YCoord => y,
            StnOp::Stats => {
                if x < 0 || x >= BOARD_SIZE as i64 || y < 0 || y >= BOARD_SIZE as i64 {
                    return 9999;
                }
                let coord = (x as i32, y as i32);
                let bi = &self.board_info;
                let in_blacks = bi.blacks.contains(coord);
                let in_whites = bi.whites.contains(coord);
                let in_black_f = bi.black_freedoms.contains(coord);
                let in_white_f = bi.white_freedoms.contains(coord);
                if in_blacks {
                    -1
                } else if in_whites {
                    1
                } else if in_black_f && in_white_f {
                    4
                } else if in_black_f {
                    2
                } else if in_white_f {
                    3
                } else {
                    0
                }
            }
        }
    }

    #[inline(always)]
    fn set_sgn(&mut self) {
        let res = self.regs[R_RES];
        self.regs[R_SGN] = if res < 0 { -1 } else if res == 0 { 0 } else { 1 };
    }

    // ------------------------------------------------------------------
    // CircularList helpers
    // ------------------------------------------------------------------

    fn circ_next(&mut self, which: u8) -> (i32, i32) {
        let bi = &mut self.board_info;
        match which {
            CL_ALL => bi.all_stones.next(),
            CL_BLACKS => bi.blacks.next(),
            CL_WHITES => bi.whites.next(),
            CL_SPACES => bi.spaces.next(),
            CL_BLACK_F => bi.black_freedoms.next(),
            CL_WHITE_F => bi.white_freedoms.next(),
            _ => (0, 0),
        }
    }

    fn circ_reverse(&mut self, which: u8) {
        let bi = &mut self.board_info;
        match which {
            CL_ALL => bi.all_stones.reverse(),
            CL_BLACKS => bi.blacks.reverse(),
            CL_WHITES => bi.whites.reverse(),
            CL_SPACES => bi.spaces.reverse(),
            CL_BLACK_F => bi.black_freedoms.reverse(),
            CL_WHITE_F => bi.white_freedoms.reverse(),
            _ => {}
        }
    }

    fn set_stn(&mut self, coord: (i32, i32)) {
        self.regs[R_STN_X] = coord.0 as i64;
        self.regs[R_STN_Y] = coord.1 as i64;
    }

    // ------------------------------------------------------------------
    // Execution loop
    // ------------------------------------------------------------------

    fn execute(&mut self, compiled: &[Instr]) -> Vec<usize> {
        let mut pc_history: Vec<usize> = Vec::new();
        let prog_len = compiled.len();
        let mut rng = rand::thread_rng();

        while self.clock < MAX_CLOCKS && self.pc < prog_len {
            pc_history.push(self.pc);
            let instr = compiled[self.pc];

            match instr.op {
                Opcode::Add => {
                    let a = self.resolve_val(instr.a);
                    let b = self.resolve_val(instr.b);
                    self.regs[R_RES] = a.wrapping_add(b);
                    self.set_sgn();
                }
                Opcode::Sub => {
                    let a = self.resolve_val(instr.a);
                    let b = self.resolve_val(instr.b);
                    self.regs[R_RES] = a.wrapping_sub(b);
                    self.set_sgn();
                }
                Opcode::Incr => {
                    self.regs[R_RES] = self.regs[R_RES].wrapping_add(1);
                    self.set_sgn();
                }
                Opcode::Decr => {
                    self.regs[R_RES] = self.regs[R_RES].wrapping_sub(1);
                    self.set_sgn();
                }
                Opcode::Mul => {
                    let a = self.resolve_val(instr.a);
                    let b = self.resolve_val(instr.b);
                    self.regs[R_RES] = a.wrapping_mul(b);
                    self.set_sgn();
                }
                Opcode::Div => {
                    let a = self.resolve_val(instr.a);
                    let b = self.resolve_val(instr.b);
                    if b == 0 {
                        self.regs[R_RES] = 0;
                        self.regs[R_CRY] = 0;
                    } else {
                        self.regs[R_RES] = a / b;
                        self.regs[R_CRY] = a % b;
                    }
                    self.set_sgn();
                }
                Opcode::Cmpe => {
                    let a = self.resolve_val(instr.a);
                    let b = self.resolve_val(instr.b);
                    self.regs[R_LOG] = if a == b { 1 } else { 0 };
                }
                Opcode::Cmpne => {
                    let a = self.resolve_val(instr.a);
                    let b = self.resolve_val(instr.b);
                    self.regs[R_LOG] = if a != b { 1 } else { 0 };
                }
                Opcode::Cmp0 => {
                    let a = self.resolve_val(instr.a);
                    self.regs[R_LOG] = if a == 0 { 1 } else { 0 };
                }
                Opcode::Cmplt => {
                    let a = self.resolve_val(instr.a);
                    let b = self.resolve_val(instr.b);
                    self.regs[R_LOG] = if a < b { 1 } else { 0 };
                }
                Opcode::Cmpgt => {
                    let a = self.resolve_val(instr.a);
                    let b = self.resolve_val(instr.b);
                    self.regs[R_LOG] = if a > b { 1 } else { 0 };
                }
                Opcode::And => {
                    let a = self.resolve_val(instr.a);
                    let b = self.resolve_val(instr.b);
                    self.regs[R_RES] = a & b;
                    self.set_sgn();
                }
                Opcode::Or => {
                    let a = self.resolve_val(instr.a);
                    let b = self.resolve_val(instr.b);
                    self.regs[R_RES] = a | b;
                    self.set_sgn();
                }
                Opcode::Not => {
                    let a = self.resolve_val(instr.a);
                    self.regs[R_RES] = !a;
                    self.set_sgn();
                }
                Opcode::Xor => {
                    let a = self.resolve_val(instr.a);
                    let b = self.resolve_val(instr.b);
                    self.regs[R_RES] = a ^ b;
                    self.set_sgn();
                }

                // --- Branching ---

                Opcode::Jmp => {
                    let a = self.resolve_val(instr.a);
                    if a > 0 {
                        self.pc_interrupt = true;
                        self.pc_interrupt_a = a as usize;
                    }
                }
                Opcode::Jmpr => {
                    let a = self.resolve_val(instr.a);
                    if a != 0 {
                        let abs_a = self.pc as i64 + a;
                        if abs_a > 0 {
                            self.pc_interrupt = true;
                            self.pc_interrupt_a = abs_a as usize;
                        }
                    }
                }
                Opcode::Jmp0 => {
                    if self.regs[R_RES] == 0 {
                        let a = self.resolve_val(instr.a);
                        if a > 0 {
                            self.pc_interrupt = true;
                            self.pc_interrupt_a = a as usize;
                        }
                    }
                }
                Opcode::Jmpl => {
                    if self.regs[R_LOG] != 0 {
                        let a = self.resolve_val(instr.a);
                        if a > 0 {
                            self.pc_interrupt = true;
                            self.pc_interrupt_a = a as usize;
                        }
                    }
                }
                Opcode::Jmprl => {
                    let a = self.resolve_val(instr.a);
                    if a != 0 && self.regs[R_LOG] != 0 {
                        let abs_a = self.pc as i64 + a;
                        if abs_a > 0 {
                            self.pc_interrupt = true;
                            self.pc_interrupt_a = abs_a as usize;
                        }
                    }
                }
                Opcode::Jmpr0 => {
                    let a = self.resolve_val(instr.a);
                    if a != 0 && self.regs[R_RES] == 0 {
                        let abs_a = self.pc as i64 + a;
                        if abs_a > 0 {
                            self.pc_interrupt = true;
                            self.pc_interrupt_a = abs_a as usize;
                        }
                    }
                }

                // --- Calls (push return addr BEFORE checking jump validity,
                //     mirroring the Python push_pc() + opcode_jmp() split) ---

                Opcode::Call => {
                    let a = self.resolve_val(instr.a);
                    if a > 0 {
                        self.stack.push(self.pc as i64 + 1);
                        self.pc_interrupt = true;
                        self.pc_interrupt_a = a as usize;
                    }
                }
                Opcode::Callr => {
                    let a = self.resolve_val(instr.a);
                    if a != 0 {
                        // Python: push_pc() first, then jmpr() (which may not jump)
                        self.stack.push(self.pc as i64 + 1);
                        let abs_a = self.pc as i64 + a;
                        if abs_a > 0 {
                            self.pc_interrupt = true;
                            self.pc_interrupt_a = abs_a as usize;
                        }
                    }
                }
                Opcode::Call0 => {
                    let a = self.resolve_val(instr.a);
                    if a != 0 && self.regs[R_RES] == 0 {
                        self.stack.push(self.pc as i64 + 1);
                        if a > 0 {
                            self.pc_interrupt = true;
                            self.pc_interrupt_a = a as usize;
                        }
                    }
                }
                Opcode::Callr0 => {
                    let a = self.resolve_val(instr.a);
                    if a != 0 && self.regs[R_RES] == 0 {
                        self.stack.push(self.pc as i64 + 1);
                        let abs_a = self.pc as i64 + a;
                        if abs_a > 0 {
                            self.pc_interrupt = true;
                            self.pc_interrupt_a = abs_a as usize;
                        }
                    }
                }
                Opcode::Calll => {
                    let a = self.resolve_val(instr.a);
                    if a != 0 && self.regs[R_LOG] != 0 {
                        self.stack.push(self.pc as i64 + 1);
                        if a > 0 {
                            self.pc_interrupt = true;
                            self.pc_interrupt_a = a as usize;
                        }
                    }
                }
                Opcode::Callrl => {
                    let a = self.resolve_val(instr.a);
                    if a != 0 && self.regs[R_LOG] != 0 {
                        self.stack.push(self.pc as i64 + 1);
                        let abs_a = self.pc as i64 + a;
                        if abs_a > 0 {
                            self.pc_interrupt = true;
                            self.pc_interrupt_a = abs_a as usize;
                        }
                    }
                }

                // --- Returns ---

                Opcode::Ret => {
                    if let Some(addr) = self.stack.pop() {
                        if addr > 0 {
                            self.pc_interrupt = true;
                            self.pc_interrupt_a = addr as usize;
                        }
                    }
                }
                Opcode::Ret0 => {
                    if self.regs[R_RES] == 0 {
                        if let Some(addr) = self.stack.pop() {
                            if addr > 0 {
                                self.pc_interrupt = true;
                                self.pc_interrupt_a = addr as usize;
                            }
                        }
                    }
                }
                Opcode::Retl => {
                    if self.regs[R_LOG] != 0 {
                        if let Some(addr) = self.stack.pop() {
                            if addr > 0 {
                                self.pc_interrupt = true;
                                self.pc_interrupt_a = addr as usize;
                            }
                        }
                    }
                }

                // --- Data movement ---

                Opcode::Mov => {
                    let a_val = self.resolve_val(instr.a);
                    match instr.b {
                        Operand::RegDest(r) => {
                            let v = if r == R_WXY {
                                a_val.rem_euclid(BOARD_SIZE as i64)
                            } else {
                                a_val
                            };
                            self.regs[r] = v;
                        }
                        Operand::MemDest(addr) => {
                            self.memory[addr] = a_val & 0x7FFF_FFFF_FFFF_FFFF;
                        }
                        _ => {}
                    }
                    // mov updates SGN based on RES (not the value moved)
                    self.set_sgn();
                }
                Opcode::Push => {
                    let a = self.resolve_val(instr.a);
                    self.stack.push(a);
                }
                Opcode::Pop => {
                    let v = self.stack.pop().unwrap_or(0);
                    self.regs[R_RES] = v;
                    self.set_sgn();
                }
                Opcode::Rnd => {
                    let r: i64 = rng.gen_range(0..RAND_MAX) - (RAND_MAX / 2);
                    self.regs[R_RES] = r;
                    self.set_sgn();
                }

                // --- STN / board-navigation opcodes ---

                Opcode::Sstn => {
                    let a = self.resolve_val(instr.a);
                    let b = self.resolve_val(instr.b);
                    self.regs[R_STN_X] = a;
                    self.regs[R_STN_Y] = b;
                }
                Opcode::Nstn => {
                    let c = self.circ_next(CL_ALL);
                    self.set_stn(c);
                }
                Opcode::Rstn => self.circ_reverse(CL_ALL),
                Opcode::Nblk => {
                    let c = self.circ_next(CL_BLACKS);
                    self.set_stn(c);
                }
                Opcode::Rblk => self.circ_reverse(CL_BLACKS),
                Opcode::Nwht => {
                    let c = self.circ_next(CL_WHITES);
                    self.set_stn(c);
                }
                Opcode::Rwht => self.circ_reverse(CL_WHITES),
                Opcode::Nfrn => {
                    let which = if self.regs[R_PLAYER] == -1 {
                        CL_BLACKS
                    } else {
                        CL_WHITES
                    };
                    let c = self.circ_next(which);
                    self.set_stn(c);
                }
                Opcode::Rfrn => {
                    let which = if self.regs[R_PLAYER] == -1 {
                        CL_BLACKS
                    } else {
                        CL_WHITES
                    };
                    self.circ_reverse(which);
                }
                Opcode::Nnme => {
                    let which = if self.regs[R_PLAYER] == -1 {
                        CL_WHITES
                    } else {
                        CL_BLACKS
                    };
                    let c = self.circ_next(which);
                    self.set_stn(c);
                }
                Opcode::Rnme => {
                    let which = if self.regs[R_PLAYER] == -1 {
                        CL_WHITES
                    } else {
                        CL_BLACKS
                    };
                    self.circ_reverse(which);
                }
                Opcode::Nspc => {
                    let c = self.circ_next(CL_SPACES);
                    self.set_stn(c);
                }
                Opcode::Rspc => self.circ_reverse(CL_SPACES),
                Opcode::Nblkf => {
                    let c = self.circ_next(CL_BLACK_F);
                    self.set_stn(c);
                }
                Opcode::Rblkf => self.circ_reverse(CL_BLACK_F),
                Opcode::Nwhtf => {
                    let c = self.circ_next(CL_WHITE_F);
                    self.set_stn(c);
                }
                Opcode::Rwhtf => self.circ_reverse(CL_WHITE_F),
                Opcode::Nfrnf => {
                    let which = if self.regs[R_PLAYER] == -1 {
                        CL_BLACK_F
                    } else {
                        CL_WHITE_F
                    };
                    let c = self.circ_next(which);
                    self.set_stn(c);
                }
                Opcode::Rfrnf => {
                    let which = if self.regs[R_PLAYER] == -1 {
                        CL_BLACK_F
                    } else {
                        CL_WHITE_F
                    };
                    self.circ_reverse(which);
                }
                Opcode::Nnmef => {
                    let which = if self.regs[R_PLAYER] == -1 {
                        CL_WHITE_F
                    } else {
                        CL_BLACK_F
                    };
                    let c = self.circ_next(which);
                    self.set_stn(c);
                }
                Opcode::Rnmef => {
                    let which = if self.regs[R_PLAYER] == -1 {
                        CL_WHITE_F
                    } else {
                        CL_BLACK_F
                    };
                    self.circ_reverse(which);
                }
                Opcode::Iwxy => {
                    self.regs[R_WXY] += 1;
                    if self.regs[R_WXY] > 7 {
                        self.regs[R_WXY] = 0;
                    }
                }
                Opcode::Dwxy => {
                    self.regs[R_WXY] -= 1;
                    if self.regs[R_WXY] < 0 {
                        self.regs[R_WXY] = 7;
                    }
                }
            } // end match instr.op

            // --- PC update ---
            if self.pc_interrupt {
                self.pc = self.pc_interrupt_a % prog_len;
                self.pc_interrupt = false;
            } else {
                self.pc += 1;
            }
            self.clock += 1;
        }

        pc_history
    }
}

// ---------------------------------------------------------------------------
// Compiler: Python DNA → Vec<Instr>
// ---------------------------------------------------------------------------

fn parse_opcode(s: &str) -> Opcode {
    match s {
        "add" => Opcode::Add,
        "sub" => Opcode::Sub,
        "incr" => Opcode::Incr,
        "decr" => Opcode::Decr,
        "mul" => Opcode::Mul,
        "div" => Opcode::Div,
        "cmpe" => Opcode::Cmpe,
        "cmpne" => Opcode::Cmpne,
        "cmp0" => Opcode::Cmp0,
        "cmplt" => Opcode::Cmplt,
        "cmpgt" => Opcode::Cmpgt,
        "and" => Opcode::And,
        "or" => Opcode::Or,
        "not" => Opcode::Not,
        "xor" => Opcode::Xor,
        "jmp" => Opcode::Jmp,
        "jmpr" => Opcode::Jmpr,
        "jmp0" => Opcode::Jmp0,
        "jmpl" => Opcode::Jmpl,
        "jmprl" => Opcode::Jmprl,
        "jmpr0" => Opcode::Jmpr0,
        "call" => Opcode::Call,
        "callr" => Opcode::Callr,
        "call0" => Opcode::Call0,
        "callr0" => Opcode::Callr0,
        "calll" => Opcode::Calll,
        "callrl" => Opcode::Callrl,
        "ret" => Opcode::Ret,
        "ret0" => Opcode::Ret0,
        "retl" => Opcode::Retl,
        "mov" => Opcode::Mov,
        "push" => Opcode::Push,
        "pop" => Opcode::Pop,
        "rnd" => Opcode::Rnd,
        "sstn" => Opcode::Sstn,
        "nstn" => Opcode::Nstn,
        "rstn" => Opcode::Rstn,
        "nblk" => Opcode::Nblk,
        "rblk" => Opcode::Rblk,
        "nwht" => Opcode::Nwht,
        "rwht" => Opcode::Rwht,
        "nfrn" => Opcode::Nfrn,
        "rfrn" => Opcode::Rfrn,
        "nnme" => Opcode::Nnme,
        "rnme" => Opcode::Rnme,
        "nspc" => Opcode::Nspc,
        "rspc" => Opcode::Rspc,
        "nblkf" => Opcode::Nblkf,
        "rblkf" => Opcode::Rblkf,
        "nwhtf" => Opcode::Nwhtf,
        "rwhtf" => Opcode::Rwhtf,
        "nfrnf" => Opcode::Nfrnf,
        "rfrnf" => Opcode::Rfrnf,
        "nnmef" => Opcode::Nnmef,
        "rnmef" => Opcode::Rnmef,
        "iwxy" => Opcode::Iwxy,
        "dwxy" => Opcode::Dwxy,
        _ => Opcode::Add, // unknown → silent nop
    }
}

fn parse_reg_name(s: &str) -> usize {
    match s {
        "X" => R_X,
        "Y" => R_Y,
        "WXY" => R_WXY,
        "RES" => R_RES,
        "CRY" => R_CRY,
        "SGN" => R_SGN,
        "LOG" => R_LOG,
        "PLAYER" => R_PLAYER,
        "X0" => 8,
        "X1" => 9,
        "X2" => 10,
        "X3" => 11,
        "X4" => 12,
        "X5" => 13,
        "X6" => 14,
        "X7" => 15,
        "Y0" => 16,
        "Y1" => 17,
        "Y2" => 18,
        "Y3" => 19,
        "Y4" => 20,
        "Y5" => 21,
        "Y6" => 22,
        "Y7" => 23,
        "GP0" => 24,
        "GP1" => 25,
        "GP2" => 26,
        "GP3" => 27,
        "GP4" => 28,
        "GP5" => 29,
        "GP6" => 30,
        "GP7" => 31,
        _ => R_RES, // fallback
    }
}

fn parse_bp(s: &str) -> u8 {
    match s {
        "TL" => 0,
        "TT" => 1,
        "TR" => 2,
        "ML" => 3,
        "C" => 4,
        "MR" => 5,
        "BL" => 6,
        "BB" => 7,
        "BR" => 8,
        _ => 4, // default to centre
    }
}

/// Parse a source operand string into an `Operand` variant.
fn parse_source_operand(s: &str) -> Operand {
    if s.is_empty() {
        return Operand::None;
    }
    let first = s.as_bytes()[0] as char;

    // Numeric constant (positive or negative)
    if first.is_ascii_digit() || first == '-' {
        let v: i64 = s.parse().unwrap_or(0);
        return Operand::Const(v);
    }

    // Memory indirection: m<addr|reg>
    if first == 'm' || first == '*' {
        let rest = &s[1..];
        if rest.is_empty() {
            return Operand::None;
        }
        let rest_first = rest.as_bytes()[0] as char;
        if rest_first.is_ascii_digit() || rest_first == '-' {
            let addr_i: i64 = rest.parse().unwrap_or(0);
            let addr = addr_i.rem_euclid(MEM_SIZE as i64) as usize;
            return if first == 'm' {
                Operand::MemConst(addr)
            } else {
                Operand::DerefConst(addr)
            };
        } else {
            let r = parse_reg_name(rest);
            return if first == 'm' {
                Operand::MemReg(r)
            } else {
                Operand::DerefReg(r)
            };
        }
    }

    // STN board-pointer operation: STN_<BP>_<OP>
    if s.starts_with("STN") {
        let parts: Vec<&str> = s.splitn(3, '_').collect();
        if parts.len() == 3 {
            let bp = parse_bp(parts[1]);
            let stn_op = match parts[2] {
                "STATS" => StnOp::Stats,
                "XCOORD" => StnOp::XCoord,
                _ => StnOp::YCoord,
            };
            return Operand::StnOp(bp, stn_op);
        }
    }

    // Plain register
    Operand::Reg(parse_reg_name(s))
}

/// Parse a `mov` destination operand.
///
/// In Python a mov destination is either a register name (str) or a numeric
/// memory address.  The `m<n>` form is not generated by the genome but may
/// appear in hand-written DNA, so we handle it too.
fn parse_mov_dest(s: &str) -> Operand {
    if s.is_empty() {
        return Operand::None;
    }
    let first = s.as_bytes()[0] as char;
    if first.is_ascii_digit() || first == '-' {
        let addr_i: i64 = s.parse().unwrap_or(0);
        let addr = addr_i.rem_euclid(MEM_SIZE as i64) as usize;
        return Operand::MemDest(addr);
    }
    if first == 'm' {
        let rest = &s[1..];
        if let Ok(addr_i) = rest.parse::<i64>() {
            let addr = addr_i.rem_euclid(MEM_SIZE as i64) as usize;
            return Operand::MemDest(addr);
        }
    }
    Operand::RegDest(parse_reg_name(s))
}

/// Compile a flat list of `(opcode_str, Option<a_str>, Option<b_str>)` into
/// the internal instruction representation.
fn compile_program(raw: &[(String, Option<String>, Option<String>)]) -> Vec<Instr> {
    raw.iter()
        .map(|(opcode_str, a_opt, b_opt)| {
            let op = parse_opcode(opcode_str);
            let is_mov = matches!(op, Opcode::Mov);

            let a = match a_opt {
                Some(s) if !s.is_empty() => parse_source_operand(s),
                _ => Operand::None,
            };

            let b = match b_opt {
                Some(s) if !s.is_empty() => {
                    if is_mov {
                        parse_mov_dest(s)
                    } else {
                        parse_source_operand(s)
                    }
                }
                _ => Operand::None,
            };

            Instr { op, a, b }
        })
        .collect()
}

// ---------------------------------------------------------------------------
// PyO3 interface
// ---------------------------------------------------------------------------

/// Extract the DNA list from a Python object that is either:
///   - a `GoGenome` (with a `.dna` attribute), or
///   - a plain Python list.
///
/// Returns a flat `Vec<(opcode, a, b)>`.
fn extract_dna(dna_obj: &Bound<'_, PyAny>) -> PyResult<Vec<(String, Option<String>, Option<String>)>> {
    // Unwrap GoGenome → list via .dna attribute if present
    let dna_list: Bound<'_, PyList> = if let Ok(attr) = dna_obj.getattr("dna") {
        attr.downcast::<PyList>()?.clone()
    } else {
        dna_obj.downcast::<PyList>()?.clone()
    };

    let mut result = Vec::with_capacity(dna_list.len());

    for item in dna_list.iter() {
        let tuple = item.downcast::<PyTuple>()?;

        let opcode: String = tuple.get_item(0)?.extract()?;

        let operands = tuple.get_item(1)?;
        let operands_list: Bound<'_, PyList> = if let Ok(lst) = operands.downcast::<PyList>() {
            lst.clone()
        } else {
            // Shouldn't happen with well-formed DNA, but be defensive
            result.push((opcode, None, None));
            continue;
        };

        let a: Option<String> = if operands_list.len() > 0 {
            let v = operands_list.get_item(0)?;
            if v.is_none() {
                None
            } else {
                Some(v.extract::<String>()?)
            }
        } else {
            None
        };

        let b: Option<String> = if operands_list.len() > 1 {
            let v = operands_list.get_item(1)?;
            if v.is_none() {
                None
            } else {
                Some(v.extract::<String>()?)
            }
        } else {
            None
        };

        result.push((opcode, a, b));
    }

    Ok(result)
}

/// Main entry point called from Python.
///
/// `board`   – `dict[tuple[int,int], int]`  (-1 = black, 0 = empty, 1 = white)
/// `player`  – `"black"` or `"white"`
/// `program` – a `GoGenome` (has `.dna`) or a plain list of `(opcode, [A, B])` tuples
///
/// Returns `((x, y), pc_history)`.
#[pyfunction]
fn get_move(
    board: &Bound<'_, PyDict>,
    player: &str,
    program: &Bound<'_, PyAny>,
) -> PyResult<((i64, i64), Vec<usize>)> {
    // --- Build flat board array ---
    let mut flat_board = [0i8; BOARD_SIZE * BOARD_SIZE];
    for (k, v) in board.iter() {
        let (x, y): (i32, i32) = k.extract()?;
        let state: i32 = v.extract()?;
        if x >= 0 && x < BOARD_SIZE as i32 && y >= 0 && y < BOARD_SIZE as i32 {
            flat_board[y as usize * BOARD_SIZE + x as usize] = state as i8;
        }
    }

    // --- Extract and compile program ---
    let raw_dna = extract_dna(program)?;
    let compiled = compile_program(&raw_dna);

    // --- Create and initialise VM ---
    let mut vm = VM::new(&flat_board);
    vm.regs[R_PLAYER] = if player == "black" { -1 } else { 1 };

    // --- Run ---
    let pc_history = vm.execute(&compiled);

    // --- Extract result ---
    let x = vm.regs[R_X].rem_euclid(BOARD_SIZE as i64);
    let y = vm.regs[R_Y].rem_euclid(BOARD_SIZE as i64);

    Ok(((x, y), pc_history))
}

// ---------------------------------------------------------------------------
// Module registration
// ---------------------------------------------------------------------------

#[pymodule]
fn go_vm_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(get_move, m)?)?;
    Ok(())
}
