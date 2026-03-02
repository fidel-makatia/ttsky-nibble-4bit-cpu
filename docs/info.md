## How it works

Nibble is a 4-bit accumulator-based CPU that fits in a single TinyTapeout tile (~300 standard cells).

**Architecture:**
- 4-bit accumulator (A), 4-bit program counter (PC)
- Carry (C) and Zero (Z) flags
- 2-cycle fetch-execute pipeline (Harvard architecture)
- 16 instructions addressed by PC, external program memory

**Instruction set (8-bit word: [7:4]=opcode, [3:0]=immediate):**

| Opcode | Mnemonic | Operation |
|--------|----------|-----------|
| 0x0 | NOP | No operation |
| 0x1 | LDI imm | A = imm |
| 0x2 | ADD imm | A = A + imm |
| 0x3 | SUB imm | A = A - imm |
| 0x4 | AND imm | A = A & imm |
| 0x5 | OR imm | A = A \| imm |
| 0x6 | XOR imm | A = A ^ imm |
| 0x7 | NOT | A = ~A |
| 0x8 | SHL | Shift left, MSB into carry |
| 0x9 | SHR | Shift right, LSB into carry |
| 0xA | JMP addr | Jump to addr |
| 0xB | JZ addr | Jump if zero |
| 0xC | JC addr | Jump if carry |
| 0xD | JNZ addr | Jump if not zero |
| 0xE | IN | A = input port |
| 0xF | HLT | Halt CPU |

**Execution cycle:**
1. FETCH: CPU outputs PC on `uio[3:0]`, latches instruction from `ui_in[7:0]`
2. EXECUTE: Decodes and executes, updates A/PC/flags

Each instruction takes exactly 2 clock cycles.

## How to test

**With TinyTapeout demo board (RP2040 as program ROM):**

The RP2040 microcontroller acts as the program memory. Program the RP2040 to:
1. Read the 4-bit PC address from `uio[3:0]`
2. Look up the instruction in a table
3. Drive the 8-bit instruction onto `ui_in[7:0]`

**Example: Counter program (counts 0 to 15 on LEDs)**
```
Address  Instruction  Assembly
0x0      0x10         LDI 0
0x1      0x21         ADD 1
0x2      0xD1         JNZ 1
0x3      0xF0         HLT
```

Connect LEDs to `uo_out[3:0]` to see the accumulator counting up.

**Pin mapping:**
- `ui_in[7:0]`: Instruction data from external memory
- `uo_out[3:0]`: Accumulator (connect LEDs here!)
- `uo_out[4]`: Carry flag
- `uo_out[5]`: Zero flag
- `uo_out[6]`: Halted indicator
- `uo_out[7]`: Phase (0=fetch, 1=execute)
- `uio[3:0]` (output): Program counter / address bus
- `uio[7:4]` (input): General-purpose input port (for IN instruction)

**Clock:** The CPU works at any clock frequency. Use 1 MHz or lower to easily observe with LEDs. The RP2040 needs to respond within one clock period.
