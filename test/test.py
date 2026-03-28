# SPDX-FileCopyrightText: © 2024 Fidel Makatia
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, FallingEdge, Timer


# ---- Opcode encoding helpers ----
def NOP():     return 0x00
def LDI(imm):  return (0x1 << 4) | (imm & 0xF)
def ADD(imm):  return (0x2 << 4) | (imm & 0xF)
def SUB(imm):  return (0x3 << 4) | (imm & 0xF)
def AND(imm):  return (0x4 << 4) | (imm & 0xF)
def OR(imm):   return (0x5 << 4) | (imm & 0xF)
def XOR(imm):  return (0x6 << 4) | (imm & 0xF)
def NOT():     return 0x70
def SHL():     return 0x80
def SHR():     return 0x90
def JMP(addr): return (0xA << 4) | (addr & 0xF)
def JZ(addr):  return (0xB << 4) | (addr & 0xF)
def JC(addr):  return (0xC << 4) | (addr & 0xF)
def JNZ(addr): return (0xD << 4) | (addr & 0xF)
def INP():     return 0xE0
def HLT():     return 0xF0


def get_acc(dut):
    return int(dut.uo_out.value) & 0x0F

def get_carry(dut):
    return (int(dut.uo_out.value) >> 4) & 1

def get_zero(dut):
    return (int(dut.uo_out.value) >> 5) & 1

def get_halted(dut):
    return (int(dut.uo_out.value) >> 6) & 1

def get_phase(dut):
    return (int(dut.uo_out.value) >> 7) & 1

def get_pc(dut):
    return int(dut.uio_out.value) & 0x0F


async def rom_driver(dut, rom):
    """Continuously drive ui_in based on PC, like a combinational ROM.

    Updates ui_in on every falling edge so it's stable before the next
    rising edge where the CPU latches the instruction during FETCH.
    """
    while True:
        await FallingEdge(dut.clk)
        pc = get_pc(dut)
        dut.ui_in.value = rom.get(pc, 0x00)


async def reset_cpu(dut, rom=None):
    """Reset the CPU and release cleanly.

    If rom is provided, pre-loads ui_in with rom[0] so the first FETCH
    gets the correct instruction (the rom_driver coroutine runs on
    FallingEdge, which is too late for the very first RisingEdge FETCH).
    """
    dut.ena.value = 1
    dut.rst_n.value = 0
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 2)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    if rom is not None:
        dut.ui_in.value = rom.get(0, 0x00)


async def run_instructions(dut, n):
    """Run N full instructions (2 clock cycles each: FETCH + EXECUTE).
    After this, the Nth instruction's result is visible.
    We wait until the falling edge to allow gate-level outputs to settle."""
    for _ in range(n):
        await RisingEdge(dut.clk)  # FETCH
        await RisingEdge(dut.clk)  # EXECUTE
    await FallingEdge(dut.clk)


@cocotb.test()
async def test_basic_alu(dut):
    """Test 1: Basic ALU operations (LDI, ADD, SUB, AND, OR, XOR, NOT)."""
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    rom = {
        0: LDI(5),    # A = 5
        1: ADD(3),    # A = 8
        2: SUB(2),    # A = 6
        3: AND(12),   # A = 6 & 12 = 4
        4: OR(1),     # A = 4 | 1 = 5
        5: XOR(15),   # A = 5 ^ 15 = 10
        6: NOT(),     # A = ~10 = 5
        7: LDI(0),    # A = 0, Z=1
        8: SUB(1),    # A = 15 (underflow), C=1
        9: HLT(),
    }

    await reset_cpu(dut, rom)
    cocotb.start_soon(rom_driver(dut, rom))

    await run_instructions(dut, 1)  # LDI 5
    assert get_acc(dut) == 5, f"LDI 5: expected 5, got {get_acc(dut)}"

    await run_instructions(dut, 1)  # ADD 3
    assert get_acc(dut) == 8, f"ADD 3: expected 8, got {get_acc(dut)}"

    await run_instructions(dut, 1)  # SUB 2
    assert get_acc(dut) == 6, f"SUB 2: expected 6, got {get_acc(dut)}"

    await run_instructions(dut, 1)  # AND 12
    assert get_acc(dut) == 4, f"AND 12: expected 4, got {get_acc(dut)}"

    await run_instructions(dut, 1)  # OR 1
    assert get_acc(dut) == 5, f"OR 1: expected 5, got {get_acc(dut)}"

    await run_instructions(dut, 1)  # XOR 15
    assert get_acc(dut) == 10, f"XOR 15: expected 10, got {get_acc(dut)}"

    await run_instructions(dut, 1)  # NOT
    assert get_acc(dut) == 5, f"NOT: expected 5, got {get_acc(dut)}"

    await run_instructions(dut, 1)  # LDI 0
    assert get_acc(dut) == 0, f"LDI 0: expected 0, got {get_acc(dut)}"
    assert get_zero(dut) == 1, "Z flag should be set after LDI 0"

    await run_instructions(dut, 1)  # SUB 1
    assert get_acc(dut) == 15, f"SUB 1 underflow: expected 15, got {get_acc(dut)}"
    assert get_carry(dut) == 1, "C flag should be set after underflow"

    await run_instructions(dut, 1)  # HLT
    assert get_halted(dut) == 1, "CPU should be halted"


@cocotb.test()
async def test_shift_operations(dut):
    """Test 2: Shift operations (SHL, SHR) with carry propagation."""
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    rom = {
        0:  LDI(1),   # A = 0001
        1:  SHL(),    # A = 0010, C=0
        2:  SHL(),    # A = 0100, C=0
        3:  SHL(),    # A = 1000, C=0
        4:  SHL(),    # A = 0000, C=1, Z=1
        5:  LDI(8),   # A = 1000
        6:  SHR(),    # A = 0100, C=0
        7:  SHR(),    # A = 0010, C=0
        8:  SHR(),    # A = 0001, C=0
        9:  SHR(),    # A = 0000, C=1, Z=1
        10: HLT(),
    }

    await reset_cpu(dut, rom)
    cocotb.start_soon(rom_driver(dut, rom))

    await run_instructions(dut, 1)  # LDI 1
    assert get_acc(dut) == 1

    await run_instructions(dut, 1)  # SHL
    assert get_acc(dut) == 2
    assert get_carry(dut) == 0

    await run_instructions(dut, 1)  # SHL
    assert get_acc(dut) == 4

    await run_instructions(dut, 1)  # SHL
    assert get_acc(dut) == 8

    await run_instructions(dut, 1)  # SHL overflow
    assert get_acc(dut) == 0
    assert get_carry(dut) == 1, "Carry should be set after SHL overflow"
    assert get_zero(dut) == 1, "Zero should be set after SHL to 0"

    await run_instructions(dut, 1)  # LDI 8
    assert get_acc(dut) == 8

    await run_instructions(dut, 1)  # SHR
    assert get_acc(dut) == 4

    await run_instructions(dut, 1)  # SHR
    assert get_acc(dut) == 2

    await run_instructions(dut, 1)  # SHR
    assert get_acc(dut) == 1

    await run_instructions(dut, 1)  # SHR underflow
    assert get_acc(dut) == 0
    assert get_carry(dut) == 1, "Carry should be set after SHR underflow"
    assert get_zero(dut) == 1, "Zero should be set after SHR to 0"


@cocotb.test()
async def test_branching(dut):
    """Test 3: Branch instructions (JMP, JZ, JNZ, JC)."""
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    rom = {
        0:  LDI(0),    # A=0, Z=1
        1:  JZ(4),     # should jump to 4
        2:  LDI(15),   # SHOULD NOT EXECUTE
        3:  HLT(),     # SHOULD NOT EXECUTE
        4:  LDI(7),    # A=7
        5:  JNZ(8),    # should jump to 8 (Z=0)
        6:  LDI(15),   # SHOULD NOT EXECUTE
        7:  HLT(),     # SHOULD NOT EXECUTE
        8:  ADD(9),    # A=7+9=16=0 (overflow), C=1
        9:  JC(12),    # should jump to 12
        10: LDI(15),   # SHOULD NOT EXECUTE
        11: HLT(),     # SHOULD NOT EXECUTE
        12: JMP(14),   # unconditional jump
        13: HLT(),     # SHOULD NOT EXECUTE
        14: LDI(3),    # A=3 (final value)
        15: HLT(),
    }

    await reset_cpu(dut, rom)
    cocotb.start_soon(rom_driver(dut, rom))

    await run_instructions(dut, 1)  # LDI 0
    assert get_acc(dut) == 0
    assert get_zero(dut) == 1

    await run_instructions(dut, 1)  # JZ 4

    await run_instructions(dut, 1)  # LDI 7 (at addr 4)
    assert get_acc(dut) == 7, f"JZ should have jumped: expected 7, got {get_acc(dut)}"

    await run_instructions(dut, 1)  # JNZ 8

    await run_instructions(dut, 1)  # ADD 9 (at addr 8)
    assert get_acc(dut) == 0, f"7+9 overflow: expected 0, got {get_acc(dut)}"
    assert get_carry(dut) == 1

    await run_instructions(dut, 1)  # JC 12
    await run_instructions(dut, 1)  # JMP 14 (at addr 12)

    await run_instructions(dut, 1)  # LDI 3 (at addr 14)
    assert get_acc(dut) == 3, f"JMP chain: expected 3, got {get_acc(dut)}"

    await run_instructions(dut, 1)  # HLT
    assert get_halted(dut) == 1


@cocotb.test()
async def test_counter_loop(dut):
    """Test 4: Counter loop (counts 0 to 15, wraps to 0, halts)."""
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    rom = {
        0: LDI(0),    # A = 0
        1: ADD(1),    # A = A + 1
        2: JNZ(1),    # loop if A != 0
        3: HLT(),     # halt when A wraps to 0
    }

    await reset_cpu(dut, rom)
    cocotb.start_soon(rom_driver(dut, rom))

    # LDI 0
    await run_instructions(dut, 1)
    assert get_acc(dut) == 0

    # Run 15 iterations of (ADD + JNZ) = 30 instructions
    await run_instructions(dut, 30)
    assert get_acc(dut) == 15, f"Counter at 15: expected 15, got {get_acc(dut)}"

    # One more ADD wraps to 0, then JNZ falls through
    await run_instructions(dut, 2)
    assert get_acc(dut) == 0
    assert get_zero(dut) == 1

    # HLT
    await run_instructions(dut, 1)
    assert get_halted(dut) == 1


@cocotb.test()
async def test_fibonacci(dut):
    """Test 5: Fibonacci sequence (4-bit: 0,1,1,2,3,5,8,13)."""
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    rom = {
        0: LDI(0),    # fib(0) = 0
        1: ADD(1),    # fib(1) = 1
        2: ADD(0),    # fib(2) = 1
        3: ADD(1),    # fib(3) = 2
        4: ADD(1),    # fib(4) = 3
        5: ADD(2),    # fib(5) = 5
        6: ADD(3),    # fib(6) = 8
        7: ADD(5),    # fib(7) = 13
        8: HLT(),
    }

    expected = [0, 1, 1, 2, 3, 5, 8, 13]

    await reset_cpu(dut, rom)
    cocotb.start_soon(rom_driver(dut, rom))

    for i, exp in enumerate(expected):
        await run_instructions(dut, 1)
        assert get_acc(dut) == exp, f"fib({i}) = {exp}: got {get_acc(dut)}"

    await run_instructions(dut, 1)  # HLT
    assert get_halted(dut) == 1


@cocotb.test()
async def test_input_port(dut):
    """Test 6: Input port (IN instruction reads from uio_in[7:4])."""
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    rom = {
        0: INP(),     # A = port_in
        1: ADD(1),    # A = A + 1
        2: HLT(),
    }

    await reset_cpu(dut, rom)
    dut.uio_in.value = 0x90  # port_in = 9 (upper nibble)
    cocotb.start_soon(rom_driver(dut, rom))

    await run_instructions(dut, 1)  # IN
    assert get_acc(dut) == 9, f"IN: expected 9, got {get_acc(dut)}"

    await run_instructions(dut, 1)  # ADD 1
    assert get_acc(dut) == 10, f"ADD 1: expected 10, got {get_acc(dut)}"

    await run_instructions(dut, 1)  # HLT
    assert get_halted(dut) == 1
