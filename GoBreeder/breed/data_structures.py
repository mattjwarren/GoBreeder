"""Data structures for the GoBreeder genetic-programming system.

Defines the in-memory genome representation (GoGenome) and the circular list
(CircularList) used by the VM's board-information registers.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Iterator
from typing import Any

import vm


class CircularList:
    """A post-incrementing circular list with a current pointer.

    Iteration advances the internal pointer so successive calls to
    ``get()`` / ``__next__()`` cycle through all values.
    """

    def __init__(self) -> None:
        self.values: list[Any] = []
        self._ptr: int | None = None
        self._direction: int = 1

    def __contains__(self, n: Any) -> bool:
        return n in self.values

    def __iter__(self) -> Iterator[Any]:
        return self

    def __str__(self) -> str:
        direction = "<" if self._direction < 0 else ">"
        return direction + str(self._ptr) + str(self.values)

    def __next__(self) -> Any:
        return self.get()

    # Python 2 compatibility alias (vm.py calls .next() explicitly)
    next = __next__

    def _post_increment(self) -> None:
        self._ptr += self._direction
        if self._ptr < 0:
            self._ptr = len(self.values) - 1
        elif self._ptr > len(self.values) - 1:
            self._ptr = 0

    def reverse(self) -> None:
        """Reverse the traversal direction."""
        self._direction = -self._direction

    def get(self) -> Any:
        """Return the current value and advance the pointer."""
        if len(self.values) > 0:
            value = self.values[self._ptr]
            self._post_increment()
            return value
        return None

    def set_values(self, values: list[Any]) -> None:
        """Replace all values and reset the pointer to 0 with forward direction."""
        self.values = values
        self._ptr = 0
        self._direction = 1

    def set(self, value: Any) -> None:
        """Overwrite the value at the current pointer and advance."""
        self.values[self._ptr] = value
        self._post_increment()

    def add_value(self, value: Any) -> None:
        """Append *value* to the list.  Initialises the pointer if needed."""
        if self._ptr is None:
            self._ptr = 0
        self.values.append(value)

    def __add__(self, other: CircularList) -> CircularList:
        """Return a new CircularList containing values from self followed by other.

        Does NOT mutate self or other.
        """
        new_cl = CircularList()
        new_cl.set_values(self.values + other.values)
        return new_cl


def weighted_choice(choices: Any) -> Any:
    """Pick a random element from *choices* using the associated weights.

    *choices* may be any iterable of (item, weight) pairs — including generators
    and zip objects — since it is materialised to a list before sampling.
    """
    choices_list = list(choices)  # materialise so sum() doesn't exhaust it
    total = sum(w for c, w in choices_list)
    r = random.uniform(0, total)
    upto = 0.0
    for c, w in choices_list:
        if upto + w > r:
            return c
        upto += w


# DNA instruction type: (opcode, [operand_A | None, operand_B | None])
DnaInstruction = tuple[str, list[str | None]]


class GoGenome:
    """A fixed-length genetic-programming genome for a Go-playing agent.

    DNA is a list of (opcode, [A, B]) tuples interpreted by :class:`vm.GoVM`.
    The genome can reproduce (``mutate``), generate fresh random DNA (``genesis``),
    and is identified by a SHA-512 hash of its repr.
    """

    max_size: int = 1024

    def __str__(self) -> str:
        return self.hashname

    def __init__(self, dna: list[DnaInstruction] | None = None) -> None:
        self.evaluated: bool = False
        if not dna:
            self.genesis()
        else:
            self.dna: list[DnaInstruction] = dna
        self.hashname: str = hashlib.sha512(repr(self.dna).encode()).hexdigest()[:64]

    def __getitem__(self, idx: int) -> DnaInstruction:
        return self.dna[idx]

    def __len__(self) -> int:
        return len(self.dna)

    def mutate(self, idx: int) -> None:
        """Apply a random mutation to the instruction at *idx*.

        Mutation types (weighted):
            0 (weight 2): replace instruction with a completely new random one.
            1 (weight 1): jitter numeric constant operands by ±1.
        """
        choices = range(0, 2)  # 0 = new random op, 1 = data jitter
        weights = [2, 1]
        choices = zip(choices, weights)
        mutation = weighted_choice(choices)

        if mutation == 0:  # weight 2: completely new instruction
            new_dna = self.generate_dna()
            self.dna[idx] = new_dna

        elif mutation == 1:  # weight 1: data jitter by +/-1
            if self.dna[idx][1][0] is not None:
                first = str(self.dna[idx][1][0])[0]
                if first in "0123456789-":
                    # is about first char of int type data values always being 0-9,-
                    self.dna[idx][1][0] = str(int(self.dna[idx][1][0]) + (random.randint(0, 2) - 1))
            if self.dna[idx][1][1] is not None:
                first = str(self.dna[idx][1][1])[0]
                if first in "0123456789-":
                    self.dna[idx][1][1] = str(int(self.dna[idx][1][1]) + (random.randint(0, 2) - 1))

    def genesis(self):
        genome_length = GoGenome.max_size
        # putting this seed DNA here helped jumpstart the pop evolution.
        # without it, it takes a long time to ignite the fire.
        # however, other sparks may do better...

        # turns out the spark colours the fire a lot! esp if spark is small and simple..

        self.dna = [
            ("sstn", ["1", "1"]),  # stone cursor to 1,1
            ("mov", ["STN_C_STATS", "RES"]),  # stone state into RES
            ("cmpne", ["RES", "0"]),  # if its not 0
            ("jmprl", ["4"]),  # jump to next stone
            ("mov", ["STN_C_XCOORD", "X"]),  # else set x,y to empty stone
            ("mov", ["STN_C_YCOORD", "Y"]),
            ("jmp", ["250"]),  # jump 'somewhere'
            ("sstn", ["2", "2"]),  #'NEXT STONE' stone cursor to 1,1
            ("mov", ["STN_C_STATS", "RES"]),  # stone state into RES
            ("cmpne", ["RES", "0"]),  # if its not 0
            ("jmpr", ["4"]),  # jump to ..... past end of this block
            ("mov", ["STN_C_XCOORD", "X"]),  # else set x,y to empty stone
            ("mov", ["STN_C_YCOORD", "Y"]),
        ]  # then continue whatver crazy shennanigns

        genome_length -= len(self.dna)
        while genome_length > 0:
            new_dna = self.generate_dna()
            self.dna.append(new_dna)
            genome_length -= 1

    def generate_dna(self):
        #        opcode     operands   random choice weight
        opcodes = {
            "add": [["A", "B"], 10],
            "sub": [["A", "B"], 10],
            "incr": [[], 10],
            "decr": [[], 10],
            "mul": [["A", "B"], 3],
            "div": [["A", "B"], 3],
            "cmpe": [["A", "B"], 1],
            "cmpne": [["A", "B"], 1],
            "cmp0": [["A"], 1],
            "cmplt": [["A", "B"], 1],
            "cmpgt": [["A", "B"], 1],
            "and": [["A", "B"], 1],
            "or": [["A", "B"], 1],
            "not": [["A"], 1],
            "xor": [["A", "B"], 1],
            "jmp": [["A"], 1],
            "jmpr": [["A"], 1],
            "jmp0": [["A"], 1],
            "jmpl": [["A"], 1],
            "jmprl": [["A"], 1],
            "jmpr0": [["A"], 1],
            "call": [["A"], 1],
            "callr": [["A"], 1],
            "call0": [["A"], 1],
            "callr0": [["A"], 1],
            "calll": [["A"], 1],
            "callrl": [["A"], 1],
            "ret": [[], 1],
            "ret0": [[], 1],
            "retl": [[], 1],
            "mov": [["A", "B"], 30],
            "push": [["A"], 3],
            "pop": [[], 3],
            "sstn": [["A", "B"], 6],
            "nstn": [[], 3],
            "rstn": [[], 3],
            "nblk": [[], 3],
            "nwht": [[], 3],
            "rwht": [[], 3],
            "nfrn": [[], 3],
            "rfrn": [[], 3],
            "nnme": [[], 3],
            "rnme": [[], 3],
            "nspc": [[], 3],
            "rspc": [[], 3],
            "nblkf": [[], 3],
            "rblkf": [[], 3],
            "nwhtf": [[], 3],
            "rwhtf": [[], 3],
            "nfrnf": [[], 3],
            "rfrnf": [[], 3],
            "nnmef": [[], 3],
            "rnmef": [[], 3],
            "iwxy": [[], 3],
            "dwxy": [[], 3],
            "rnd": [[], 3],  ####aah the first element is the list
        }

        board_pointers = ["TL", "TT", "TR", "ML", "C", "MR", "BL", "BB", "BR"]
        stn_ops = ["STATS", "XCOORD", "YCOORD"]

        # create a random genome string

        instruction_points = opcodes.keys()
        instruction_points = [(key, opcodes[key][1]) for key in instruction_points]

        do_not_modify = vm.GoVM.special_info_registers + ["WXY"]
        DO_NOT_MODIFY = False
        # get instruction
        instruction = weighted_choice(instruction_points)
        data_choices = opcodes[instruction][0]

        # whats really going on hhere, hows it breaking down

        # choose data from appropriate data points
        data = {"A": None, "B": None}
        choices = {}

        # I have no idea how this works, but I do remember its much better than the first try
        if instruction == "mov":
            choices["A"] = vm.GoVM.general_purpose_registers + vm.GoVM.special_info_registers + vm.GoVM.stn_registers
            A_weights = vm.GoVM.general_purpose_weights + vm.GoVM.special_info_weights + vm.GoVM.stn_weights
            choices["A"] = zip(choices["A"], A_weights)

            choices["B"] = vm.GoVM.general_purpose_registers
            B_weights = vm.GoVM.general_purpose_weights
            choices["B"] = zip(choices["B"], B_weights)

        elif instruction in vm.GoVM.branching_instructions:
            choices["A"] = vm.GoVM.general_purpose_registers
            A_weights = vm.GoVM.general_purpose_weights
            choices["A"] = zip(choices["A"], A_weights)

        else:
            choices["A"] = vm.GoVM.general_purpose_registers + vm.GoVM.special_info_registers + vm.GoVM.stn_registers
            A_weights = vm.GoVM.general_purpose_weights + vm.GoVM.special_info_weights + vm.GoVM.stn_weights
            choices["A"] = zip(choices["A"], A_weights)
            choices["B"] = vm.GoVM.general_purpose_registers + vm.GoVM.special_info_registers + vm.GoVM.stn_registers
            B_weights = vm.GoVM.general_purpose_weights + vm.GoVM.special_info_weights + vm.GoVM.stn_weights
            choices["B"] = zip(choices["B"], B_weights)

        for data_point in data_choices:
            choice = random.choice(["constant", weighted_choice(choices[data_point])])
            if choice == "constant":
                choice = random.randrange(0, 8192)  # ooohh a magic number
            if choice == "STN":
                choice = "_".join([choice, random.choice(board_pointers), random.choice(stn_ops)])
                DO_NOT_MODIFY = True
                # |
            if (choice not in do_not_modify) and (not DO_NOT_MODIFY):
                access_modifier = random.choice(["", "m", "*"])
            else:
                access_modifier = ""
            data[data_point] = access_modifier + str(choice)

        return (instruction, [data["A"], data["B"]])

    def render(self):
        for opcode, opdata in self.dna:
            print(opcode, opdata)
