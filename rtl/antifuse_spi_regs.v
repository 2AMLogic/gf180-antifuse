// antifuse_spi_regs.v -- SPI slave, register file and program/read sequencer
//
// Implements the register map, the enable-then-strobe program interlock and
// the read sequence ratified in spec/architecture.md section 5 (as amended by
// A1: the strobe is the FIRE command at address 0x78, not a CTRL bit), with the
// design-stage choices recorded in spec/spi-register-implementation-decision.md.
// Port, clock/reset and timing contract: rtl/README.md.
//
// Verilog-2001, single clock domain.  SCLK, MOSI and CS_N are treated as
// asynchronous inputs: they are double-flop synchronized to `clk`, SCLK edges
// are detected by oversampling, and all state lives on `clk`.  Pulse length,
// read settle time and the arm timeout are therefore counted in `clk` cycles
// and keep running when SCLK stops.
`timescale 1ns/1ps

module antifuse_spi_regs #(
    parameter N            = 32,    // grid size, 2..256; row/col address width = clog2(N)
    parameter ARM_TIMEOUT  = 4096,  // PROG_ARM lifetime in clk cycles, >= 1
    parameter READ_SETTLE  = 8      // read_en duration in clk cycles, 3..255
) (
    input  wire                 clk,       // free-running sequencer clock
    input  wire                 rst_n,     // active-low reset; async assert, sync release (inside)

    input  wire                 sclk,      // SPI mode 0
    input  wire                 mosi,
    input  wire                 cs_n,
    output wire                 miso,      // 0 whenever miso_oe is 0
    output wire                 miso_oe,   // high while CS_N is low

    output wire [clog2(N)-1:0]  row_sel,   // target row, always a valid row (< N)
    output wire [clog2(N)-1:0]  col_sel,   // target column, always a valid column (< N)
    output wire                 prog_en,   // program pulse, high for exactly PULSE_WIDTH clk cycles
    output wire                 read_en,   // read leg enable, high for READ_SETTLE clk cycles
    input  wire                 sense_in,  // sensed cell state, 1 = programmed (async, synchronized here)
    output wire                 busy       // program pulse or read settle in progress
);

    // ------------------------------------------------------------------
    // Elaboration-time helpers and checks
    // ------------------------------------------------------------------
    function integer clog2;
        input integer v;
        integer i;
        begin
            clog2 = 0;
            for (i = 1; i < v; i = i * 2) clog2 = clog2 + 1;
        end
    endfunction

    localparam AW = clog2(N);
    localparam CW = clog2(ARM_TIMEOUT + 1);
    localparam [6:0] A_FIRE = 7'h78;           // FIRE command address (spec/architecture.md section 5, amendment A1)
    localparam [8:0] NV = N;                   // N as a 9-bit value (N = 256 fits)

    // synthesis translate_off
    initial begin
        if (N < 2 || N > 256) begin
            $display("antifuse_spi_regs: unsupported N=%0d (need 2..256)", N);
            $finish;
        end
        if (ARM_TIMEOUT < 1) begin
            $display("antifuse_spi_regs: ARM_TIMEOUT must be >= 1");
            $finish;
        end
        if (READ_SETTLE < 3 || READ_SETTLE > 255) begin
            $display("antifuse_spi_regs: READ_SETTLE must be 3..255");
            $finish;
        end
    end
    // synthesis translate_on

    // ------------------------------------------------------------------
    // Reset: asynchronous assert, synchronous release (2 clk cycles)
    // ------------------------------------------------------------------
    reg rs1, rst_s;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rs1   <= 1'b0;
            rst_s <= 1'b0;
        end else begin
            rs1   <= 1'b1;
            rst_s <= rs1;
        end
    end

    // ------------------------------------------------------------------
    // Input synchronizers and edge detection
    // ------------------------------------------------------------------
    reg cs_1, cs_2, cs_d;
    reg sck_1, sck_2, sck_d;
    reg mosi_1, mosi_2;
    reg sns_1, sns_2;

    always @(posedge clk or negedge rst_s) begin
        if (!rst_s) begin
            cs_1 <= 1'b1;  cs_2 <= 1'b1;  cs_d <= 1'b1;
            sck_1 <= 1'b0; sck_2 <= 1'b0; sck_d <= 1'b0;
            mosi_1 <= 1'b0; mosi_2 <= 1'b0;
            sns_1 <= 1'b0; sns_2 <= 1'b0;
        end else begin
            cs_1 <= cs_n;   cs_2 <= cs_1;   cs_d <= cs_2;
            sck_1 <= sclk;  sck_2 <= sck_1; sck_d <= sck_2;
            mosi_1 <= mosi; mosi_2 <= mosi_1;
            sns_1 <= sense_in; sns_2 <= sns_1;
        end
    end

    wire cs_fall    = cs_d & ~cs_2;           // frame start
    wire commit_ev  = cs_2 & ~cs_d;           // CS_N rise: frame end = commit point
    wire sck_rise   = sck_2 & ~sck_d & ~cs_2; // sample edge (only while selected)
    wire sck_fall   = ~sck_2 & sck_d & ~cs_2; // launch edge (only while selected)

    // ------------------------------------------------------------------
    // Registers and sequencer state
    // ------------------------------------------------------------------
    reg [AW-1:0] row_r, col_r;
    reg [7:0]    pw_r;
    reg          arm;                 // PROG_ARM
    reg [CW-1:0] arm_cnt;             // remaining armed cycles
    reg          strobe;              // PROG_STROBE; high for the whole pulse
    reg [7:0]    pw_cnt;
    reg          rd_busy;             // READ_STROBE in flight
    reg [7:0]    rd_cnt;
    reg          prog_done, read_valid, perr, rdata;

    wire busy_i = strobe | rd_busy;

    // ------------------------------------------------------------------
    // SPI shifter
    // ------------------------------------------------------------------
    reg [4:0] bitcnt;                 // SCLK rising edges seen this frame, saturates at 17
    reg [7:0] cmd, dat;
    reg [7:0] rd_byte;
    reg       miso_r;

    wire [7:0] cmd_n = {cmd[6:0], mosi_2};

    // register read mux (address is a 7-bit value)
    reg [7:0] rmux;
    always @* begin
        case (cmd_n[6:0])
            7'h00:   rmux = { {(8-AW){1'b0}}, row_r };
            7'h01:   rmux = { {(8-AW){1'b0}}, col_r };
            7'h02:   rmux = {5'b0, rd_busy, strobe, arm};
            7'h03:   rmux = pw_r;
            7'h04:   rmux = {4'b0, perr, read_valid, prog_done, busy_i};
            7'h05:   rmux = {7'b0, rdata};
            default: rmux = 8'h00;
        endcase
    end

    // ------------------------------------------------------------------
    // Commit decode (evaluated on the CS_N rising edge)
    // ------------------------------------------------------------------
    wire        frame_ok  = (bitcnt == 5'd16);
    wire        frame_bad = (bitcnt != 5'd0) && (bitcnt != 5'd16);
    wire        is_wr     = cmd[7];
    wire [6:0]  a         = cmd[6:0];
    wire        in_range  = ({1'b0, dat} < NV);

    reg wr_row, wr_col, wr_pw, do_arm, do_disarm, do_fire, do_read, err, clr_perr;

    always @* begin
        wr_row = 1'b0; wr_col = 1'b0; wr_pw = 1'b0;
        do_arm = 1'b0; do_disarm = 1'b0; do_fire = 1'b0; do_read = 1'b0;
        err = 1'b0; clr_perr = 1'b0;
        if (commit_ev && frame_bad) err = 1'b1;
        if (commit_ev && frame_ok) begin
            if (is_wr) begin
                if (busy_i) err = 1'b1;                       // all writes rejected while BUSY
                else case (a)
                    7'h00: begin
                        if (in_range) wr_row = 1'b1; else err = 1'b1;
                        if (arm) err = 1'b1;                  // target change while armed
                    end
                    7'h01: begin
                        if (in_range) wr_col = 1'b1; else err = 1'b1;
                        if (arm) err = 1'b1;
                    end
                    7'h03: begin
                        if (dat != 8'h00) wr_pw = 1'b1; else err = 1'b1;
                        if (arm) err = 1'b1;
                    end
                    7'h02: begin
                        if (dat[7:3] != 5'b0) err = 1'b1;
                        else case (dat[2:0])
                            3'b000: do_disarm = 1'b1;
                            3'b001: if (arm) err = 1'b1; else do_arm = 1'b1;
                            3'b100: if (arm) err = 1'b1; else do_read = 1'b1;
                            default: err = 1'b1;              // incl. PROG_STROBE: not writable via CTRL
                        endcase
                    end
                    A_FIRE: begin                             // the only path to a program pulse
                        if (arm) do_fire = 1'b1; else err = 1'b1; // ARM-GUARD
                    end
                    default: err = 1'b1;                      // RO register or unknown address
                endcase
            end else begin
                if (a > 7'h05) err = 1'b1;                    // unknown address read
                if (a == 7'h04) clr_perr = 1'b1;              // STATUS read clears PROTOCOL_ERROR
            end
        end
    end

    // ------------------------------------------------------------------
    // Sequential logic
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_s) begin
        if (!rst_s) begin
            row_r <= {AW{1'b0}};
            col_r <= {AW{1'b0}};
            pw_r  <= 8'h01;
            arm <= 1'b0;  arm_cnt <= {CW{1'b0}};
            strobe <= 1'b0; pw_cnt <= 8'h00;
            rd_busy <= 1'b0; rd_cnt <= 8'h00;
            prog_done <= 1'b0; read_valid <= 1'b0; perr <= 1'b0; rdata <= 1'b0;
            bitcnt <= 5'd0; cmd <= 8'h00; dat <= 8'h00; rd_byte <= 8'h00; miso_r <= 1'b0;
        end else begin
            // ---- SPI shifting ----
            if (cs_fall) begin
                bitcnt <= 5'd0;
            end else if (sck_rise) begin
                if (bitcnt != 5'd17) bitcnt <= bitcnt + 5'd1;
                if (bitcnt < 5'd8) begin
                    cmd <= cmd_n;
                    if (bitcnt == 5'd7) rd_byte <= cmd_n[7] ? 8'h00 : rmux;
                end else if (bitcnt < 5'd16) begin
                    dat <= {dat[6:0], mosi_2};
                end
            end
            if (sck_fall)
                miso_r <= (bitcnt >= 5'd8 && bitcnt <= 5'd15) ? rd_byte[~bitcnt[2:0]] : 1'b0;
            if (commit_ev) begin
                bitcnt <= 5'd0;
                miso_r <= 1'b0;
            end

            // ---- arm timeout (flag is high for exactly ARM_TIMEOUT cycles) ----
            if (arm && !strobe) begin
                if (arm_cnt == {{(CW-1){1'b0}}, 1'b1}) arm <= 1'b0;
                else arm_cnt <= arm_cnt - 1'b1;
            end

            // ---- any protocol error drops an idle arm ----
            if (err && !strobe) arm <= 1'b0;

            // ---- program pulse ----
            if (strobe) begin
                if (pw_cnt == 8'h01) begin
                    strobe <= 1'b0;
                    arm <= 1'b0;
                    prog_done <= 1'b1;
                end
                pw_cnt <= pw_cnt - 8'h01;
            end

            // ---- read settle ----
            if (rd_busy) begin
                if (rd_cnt == 8'h01) begin
                    rd_busy <= 1'b0;
                    rdata <= sns_2;
                    read_valid <= 1'b1;
                end
                rd_cnt <= rd_cnt - 8'h01;
            end

            // ---- committed register effects ----
            if (wr_row) row_r <= dat[AW-1:0];
            if (wr_col) col_r <= dat[AW-1:0];
            if (wr_pw)  pw_r  <= dat;
            if (do_disarm) arm <= 1'b0;
            if (do_arm) begin
                arm <= 1'b1;
                arm_cnt <= ARM_TIMEOUT;
                prog_done <= 1'b0;
            end
            if (do_fire) begin
                strobe <= 1'b1;
                arm <= 1'b1;            // stays set until the pulse completes
                pw_cnt <= pw_r;
            end
            if (do_read) begin
                rd_busy <= 1'b1;
                rd_cnt <= READ_SETTLE;
                read_valid <= 1'b0;
            end
            if (err) perr <= 1'b1;
            else if (clr_perr) perr <= 1'b0;
        end
    end

    // ------------------------------------------------------------------
    // Outputs
    // ------------------------------------------------------------------
    assign row_sel = row_r;
    assign col_sel = col_r;
    assign prog_en = strobe;
    assign read_en = rd_busy;
    assign busy    = busy_i;
    assign miso_oe = ~cs_2;
    assign miso    = miso_r & ~cs_2;

endmodule
