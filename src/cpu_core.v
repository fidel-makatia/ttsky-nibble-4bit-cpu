// ============================================================================
// Nibble — 4-bit Accumulator CPU
// ============================================================================
// A minimal 4-bit CPU designed for TinyTapeout SKY130
//
// Architecture:
//   - 4-bit accumulator (A)
//   - 4-bit program counter (PC), addresses 16 instructions
//   - Carry (C) and Zero (Z) flags
//   - 2-cycle fetch-execute pipeline
//   - External program memory (Harvard architecture)
//
// ISA: 8-bit instruction word [7:4]=opcode, [3:0]=immediate/address
//
//   0x0 NOP         No operation
//   0x1 LDI imm     A = imm
//   0x2 ADD imm     A = A + imm          (updates C, Z)
//   0x3 SUB imm     A = A - imm          (updates C, Z)
//   0x4 AND imm     A = A & imm          (updates Z)
//   0x5 OR  imm     A = A | imm          (updates Z)
//   0x6 XOR imm     A = A ^ imm          (updates Z)
//   0x7 NOT         A = ~A               (updates Z)
//   0x8 SHL         {C,A} = {A[3],A<<1}  (updates C, Z)
//   0x9 SHR         {A,C} = {A>>1,A[0]}  (updates C, Z)
//   0xA JMP addr    PC = addr
//   0xB JZ  addr    if Z: PC = addr
//   0xC JC  addr    if C: PC = addr
//   0xD JNZ addr    if !Z: PC = addr
//   0xE IN          A = port_in          (updates Z)
//   0xF HLT         Halt execution
// ============================================================================

module cpu_core (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] instr_data,   // instruction from external memory
    input  wire [3:0] port_in,      // general purpose input port
    output wire [3:0] pc_out,       // program counter (address bus)
    output wire [3:0] acc_out,      // accumulator value
    output wire       carry_out,    // carry flag
    output wire       zero_out,     // zero flag
    output wire       halted_out,   // CPU halted
    output wire       phase_out     // 0=FETCH, 1=EXECUTE
);

    // ---- Opcodes ----
    localparam [3:0] OP_NOP = 4'h0,
                     OP_LDI = 4'h1,
                     OP_ADD = 4'h2,
                     OP_SUB = 4'h3,
                     OP_AND = 4'h4,
                     OP_OR  = 4'h5,
                     OP_XOR = 4'h6,
                     OP_NOT = 4'h7,
                     OP_SHL = 4'h8,
                     OP_SHR = 4'h9,
                     OP_JMP = 4'hA,
                     OP_JZ  = 4'hB,
                     OP_JC  = 4'hC,
                     OP_JNZ = 4'hD,
                     OP_IN  = 4'hE,
                     OP_HLT = 4'hF;

    // ---- Registers ----
    reg [3:0] acc;
    reg [3:0] pc;
    reg       carry;
    reg       zero;
    reg       halted;
    reg       phase;    // 0=FETCH, 1=EXECUTE
    reg [7:0] ir;       // instruction register

    // ---- Instruction decode ----
    wire [3:0] opcode = ir[7:4];
    wire [3:0] imm    = ir[3:0];

    // ---- Combinational ALU ----
    reg  [4:0] alu_result;
    reg        next_carry;
    reg        next_zero;
    reg  [3:0] next_acc;
    reg  [3:0] next_pc;
    reg        next_halted;
    reg        take_branch;

    always @(*) begin
        // Defaults: no change
        next_acc    = acc;
        next_carry  = carry;
        next_zero   = zero;
        next_pc     = pc + 4'd1;
        next_halted = 1'b0;
        alu_result  = 5'd0;
        take_branch = 1'b0;

        case (opcode)
            OP_NOP: begin
                // nothing
            end

            OP_LDI: begin
                next_acc  = imm;
                next_zero = (imm == 4'd0);
            end

            OP_ADD: begin
                alu_result = {1'b0, acc} + {1'b0, imm};
                next_acc   = alu_result[3:0];
                next_carry = alu_result[4];
                next_zero  = (alu_result[3:0] == 4'd0);
            end

            OP_SUB: begin
                alu_result = {1'b0, acc} - {1'b0, imm};
                next_acc   = alu_result[3:0];
                next_carry = alu_result[4];  // borrow
                next_zero  = (alu_result[3:0] == 4'd0);
            end

            OP_AND: begin
                next_acc  = acc & imm;
                next_zero = ((acc & imm) == 4'd0);
            end

            OP_OR: begin
                next_acc  = acc | imm;
                next_zero = ((acc | imm) == 4'd0);
            end

            OP_XOR: begin
                next_acc  = acc ^ imm;
                next_zero = ((acc ^ imm) == 4'd0);
            end

            OP_NOT: begin
                next_acc  = ~acc;
                next_zero = (~acc == 4'd0);
            end

            OP_SHL: begin
                next_carry = acc[3];
                next_acc   = {acc[2:0], 1'b0};
                next_zero  = ({acc[2:0], 1'b0} == 4'd0);
            end

            OP_SHR: begin
                next_carry = acc[0];
                next_acc   = {1'b0, acc[3:1]};
                next_zero  = ({1'b0, acc[3:1]} == 4'd0);
            end

            OP_JMP: begin
                take_branch = 1'b1;
            end

            OP_JZ: begin
                take_branch = zero;
            end

            OP_JC: begin
                take_branch = carry;
            end

            OP_JNZ: begin
                take_branch = ~zero;
            end

            OP_IN: begin
                next_acc  = port_in;
                next_zero = (port_in == 4'd0);
            end

            OP_HLT: begin
                next_halted = 1'b1;
                next_pc     = pc;  // don't advance
            end
        endcase

        // Branch target
        if (take_branch)
            next_pc = imm;
    end

    // ---- Sequential logic ----
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc    <= 4'd0;
            pc     <= 4'd0;
            carry  <= 1'b0;
            zero   <= 1'b1;
            halted <= 1'b0;
            phase  <= 1'b0;
            ir     <= 8'd0;
        end else if (!halted) begin
            if (phase == 1'b0) begin
                // ---- FETCH ----
                ir    <= instr_data;
                phase <= 1'b1;
            end else begin
                // ---- EXECUTE ----
                acc    <= next_acc;
                pc     <= next_pc;
                carry  <= next_carry;
                zero   <= next_zero;
                halted <= next_halted;
                phase  <= 1'b0;
            end
        end
    end

    // ---- Output assignments ----
    assign pc_out     = pc;
    assign acc_out    = acc;
    assign carry_out  = carry;
    assign zero_out   = zero;
    assign halted_out = halted;
    assign phase_out  = phase;

endmodule
