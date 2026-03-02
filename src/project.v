// ============================================================================
// TinyTapeout Wrapper — Nibble 4-bit CPU
// ============================================================================
// Top-level module for TinyTapeout SKY130
//
// Pin Mapping:
//   ui_in[7:0]    Instruction data (from external ROM / RP2040)
//   uo_out[3:0]   Accumulator value (connect LEDs!)
//   uo_out[4]     Carry flag
//   uo_out[5]     Zero flag
//   uo_out[6]     Halted
//   uo_out[7]     Phase (0=FETCH, 1=EXECUTE)
//   uio[3:0]      OUTPUT: Program counter (address to external ROM)
//   uio[7:4]      INPUT:  General-purpose input port (for IN instruction)
//
// How it works:
//   1. CPU outputs PC on uio[3:0] during FETCH phase
//   2. External memory (RP2040 or EEPROM) responds with instruction on ui_in
//   3. CPU latches instruction, then executes on the next cycle
//   4. 2 clock cycles per instruction
//
// Testing with TinyTapeout demo board:
//   The RP2040 microcontroller acts as the program memory. It reads PC
//   from uio[3:0] and drives ui_in[7:0] with the corresponding instruction.
// ============================================================================

module tt_um_fidel_makatia_4bit_cpu (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       ena,
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe
);

    wire [3:0] pc_out;
    wire [3:0] acc_out;
    wire       carry_out;
    wire       zero_out;
    wire       halted_out;
    wire       phase_out;

    cpu_core u_cpu (
        .clk        (clk),
        .rst_n      (rst_n & ena),
        .instr_data (ui_in),
        .port_in    (uio_in[7:4]),
        .pc_out     (pc_out),
        .acc_out    (acc_out),
        .carry_out  (carry_out),
        .zero_out   (zero_out),
        .halted_out (halted_out),
        .phase_out  (phase_out)
    );

    // Output mapping
    assign uo_out[3:0] = acc_out;
    assign uo_out[4]   = carry_out;
    assign uo_out[5]   = zero_out;
    assign uo_out[6]   = halted_out;
    assign uo_out[7]   = phase_out;

    // Bidirectional: lower 4 = output (PC), upper 4 = input (port)
    assign uio_out[3:0] = pc_out;
    assign uio_out[7:4] = 4'b0000;
    assign uio_oe       = 8'b0000_1111;  // lower nibble output, upper nibble input

endmodule
