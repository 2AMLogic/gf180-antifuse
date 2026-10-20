// Self-checking bench for rtl/antifuse_spi_regs.v.
// Run via verification/run_spi_regs.sh (see verification/README.md).
// Parameters TB_N / TB_SETTLE / TB_TIMEOUT select the DUT configuration.
`timescale 1ns/1ps

module tb_antifuse_spi_regs;
    parameter TB_N       = 32;
    parameter TB_SETTLE  = 8;
    parameter TB_TIMEOUT = 4096;

    localparam AW = (TB_N <= 2) ? 1 : (TB_N <= 4) ? 2 : (TB_N <= 8) ? 3 :
                    (TB_N <= 16) ? 4 : (TB_N <= 32) ? 5 : (TB_N <= 64) ? 6 :
                    (TB_N <= 128) ? 7 : 8;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg sclk = 1'b0, mosi = 1'b0, cs_n = 1'b1;
    reg sense_in = 1'b0;
    wire miso, miso_oe, prog_en, read_en, busy;
    wire [AW-1:0] row_sel, col_sel;

    antifuse_spi_regs #(.N(TB_N), .ARM_TIMEOUT(TB_TIMEOUT), .READ_SETTLE(TB_SETTLE)) dut (
        .clk(clk), .rst_n(rst_n), .sclk(sclk), .mosi(mosi), .cs_n(cs_n),
        .miso(miso), .miso_oe(miso_oe), .row_sel(row_sel), .col_sel(col_sel),
        .prog_en(prog_en), .read_en(read_en), .sense_in(sense_in), .busy(busy));

    always #5 clk = ~clk;

    // ------------------------------------------------------------------
    // Monitors (always on)
    // ------------------------------------------------------------------
    integer cyc = 0;
    integer prog_cycles = 0, pulse_cnt = 0, cur_len = 0, last_len = 0;
    integer read_cnt = 0, rcur_len = 0, rlast_len = 0;
    integer excl_viol = 0, stab_viol = 0, miso_viol = 0;
    integer arm_first_cyc = -1, commit_cyc = -1;
    integer arm_run = 0, arm_last_len = 0;
    reg pe_q = 0, re_q = 0, arm_q = 0;
    reg [AW-1:0] pulse_row, pulse_col;

    always @(posedge clk) begin
        cyc <= cyc + 1;
        pe_q <= prog_en; re_q <= read_en; arm_q <= dut.arm;
        if (prog_en) begin prog_cycles <= prog_cycles + 1; cur_len <= cur_len + 1; end
        else if (pe_q) begin last_len <= cur_len; cur_len <= 0; end
        if (prog_en && !pe_q) begin pulse_cnt <= pulse_cnt + 1; pulse_row <= row_sel; pulse_col <= col_sel; end
        if (prog_en && pe_q && (row_sel !== pulse_row || col_sel !== pulse_col)) stab_viol <= stab_viol + 1;
        if (read_en) rcur_len <= rcur_len + 1;
        else if (re_q) begin rlast_len <= rcur_len; rcur_len <= 0; read_cnt <= read_cnt + 1; end
        if ((prog_en && read_en) || (read_en && dut.arm)) excl_viol <= excl_viol + 1;
        if (dut.arm && !arm_q) arm_first_cyc <= cyc;
        if (dut.arm) arm_run <= arm_run + 1;
        else if (arm_q) begin arm_last_len <= arm_run; arm_run <= 0; end
        if (dut.commit_ev) commit_cyc <= cyc;
    end
    // MISO may only change while SCLK is low (launch on falling edge)
    always @(miso) if (!cs_n && sclk) miso_viol = miso_viol + 1;

    // ------------------------------------------------------------------
    // Test infrastructure
    // ------------------------------------------------------------------
    integer errs = 0, tests = 0, test_errs = 0, sh = 8;
    reg [8*48-1:0] tname;
    reg [15:0] rxsr;
    reg [7:0] rd;
    reg skipped = 1'b0;

    task check;
        input c;
        input [8*56-1:0] msg;
        begin
            if (!c) begin
                errs = errs + 1; test_errs = test_errs + 1;
                $display("    FAIL: %0s (t=%0t)", msg, $time);
            end
        end
    endtask

    task begin_test;
        input [8*48-1:0] n;
        begin tname = n; test_errs = 0; tests = tests + 1; end
    endtask

    task end_test;
        begin
            if (skipped) begin $display("[SKIP] %0s", tname); skipped = 1'b0; end
            else if (test_errs == 0) $display("[PASS] %0s", tname);
            else $display("[FAIL] %0s (%0d checks failed)", tname, test_errs);
        end
    endtask

    task tick; input integer n; begin repeat (n) @(posedge clk); #1; end endtask

    task hard_reset;
        begin
            #1 rst_n = 1'b0; sclk = 0; mosi = 0; cs_n = 1; sense_in = 0; sh = 8;
            tick(4); rst_n = 1'b1; tick(8);
        end
    endtask

    task send_bit;
        input b;
        begin
            mosi = b; tick(sh);
            rxsr = {rxsr[14:0], miso};
            sclk = 1'b1; tick(sh); sclk = 1'b0;
        end
    endtask

    // clock nb bits of v (MSB first) without touching CS_N
    task send_bits;
        input integer nb;
        input [31:0] v;
        integer i;
        begin for (i = nb - 1; i >= 0; i = i - 1) send_bit(v[i]); end
    endtask

    task cs_low;  begin rxsr = 0; cs_n = 1'b0; tick(4); end endtask
    task cs_high; begin tick(4); cs_n = 1'b1; tick(8); end endtask

    // complete 16-bit frame
    task xfer; input [7:0] c; input [7:0] d;
        begin cs_low; send_bits(8, {24'b0, c}); send_bits(8, {24'b0, d}); cs_high; rd = rxsr[7:0]; end
    endtask
    task xw; input [6:0] a; input [7:0] d; begin xfer({1'b1, a}, d); end endtask
    task xr; input [6:0] a;
        begin
            xfer({1'b0, a}, 8'h00);
            check(rxsr[15:8] == 8'h00, "MISO low during command byte");
        end
    endtask

    // register addresses / helpers
    localparam A_ROW = 7'h00, A_COL = 7'h01, A_CTRL = 7'h02, A_PW = 7'h03, A_ST = 7'h04, A_RD = 7'h05;
    localparam A_FIRE = 7'h78;      // FIRE command (spec/architecture.md section 5, amendment A1)
    localparam S_BUSY = 0, S_DONE = 1, S_VALID = 2, S_PERR = 3;

    task wait_idle; begin while (busy) @(posedge clk); tick(6); end endtask
    task st; begin xr(A_ST); end endtask
    task clear_perr; begin st; end endtask      // STATUS read clears PROTOCOL_ERROR

    task prog_seq; input [7:0] r; input [7:0] c; input [7:0] w;
        begin
            xw(A_ROW, r); xw(A_COL, c); xw(A_PW, w);
            xw(A_CTRL, 8'h01); xw(A_FIRE, 8'h00);
            wait_idle;
        end
    endtask

    integer p0, c0, r0, i, k, trial, fired_n;
    reg [7:0] v;

    // ------------------------------------------------------------------
    // Tests
    // ------------------------------------------------------------------
    task t_reset_values;
        begin
            begin_test("reset_values_and_idle_outputs");
            hard_reset;
            check(!prog_en && !read_en && !busy, "outputs idle after reset");
            check(row_sel == 0 && col_sel == 0, "row/col reset to 0");
            check(miso_oe == 0 && miso == 0, "MISO released while CS_N high");
            xr(A_ROW); check(rd == 8'h00, "ADDR_ROW reset 0x00");
            xr(A_COL); check(rd == 8'h00, "ADDR_COL reset 0x00");
            xr(A_CTRL); check(rd == 8'h00, "CTRL reset 0x00");
            xr(A_PW); check(rd == 8'h01, "PULSE_WIDTH reset 0x01");
            xr(A_ST); check(rd == 8'h00, "STATUS reset 0x00");
            xr(A_RD); check(rd == 8'h00, "RDATA reset 0x00");
            end_test;
        end
    endtask

    task t_rw_all_registers;
        begin
            begin_test("read_write_every_register");
            hard_reset;
            xw(A_ROW, TB_N - 1); xr(A_ROW); check(rd == TB_N - 1, "ROW max readback");
            check(row_sel == TB_N - 1, "row_sel follows ADDR_ROW");
            xw(A_ROW, 8'h00);    xr(A_ROW); check(rd == 8'h00, "ROW 0 readback");
            xw(A_COL, TB_N - 1); xr(A_COL); check(rd == TB_N - 1, "COL max readback");
            check(col_sel == TB_N - 1, "col_sel follows ADDR_COL");
            xw(A_COL, 8'h01);    xr(A_COL); check(rd == 8'h01, "COL 1 readback");
            xw(A_PW, 8'hA5);     xr(A_PW); check(rd == 8'hA5, "PW readback 0xA5");
            xw(A_PW, 8'hFF);     xr(A_PW); check(rd == 8'hFF, "PW readback 0xFF");
            xw(A_CTRL, 8'h01);   xr(A_CTRL); check(rd == 8'h01, "CTRL reads PROG_ARM");
            xw(A_CTRL, 8'h00);   xr(A_CTRL); check(rd == 8'h00, "CTRL disarm reads 0");
            st; check(rd[S_PERR] == 0, "no PROTOCOL_ERROR on legal accesses");
            end_test;
        end
    endtask

    task t_reserved_bits;
        begin
            begin_test("reserved_bits_read_zero");
            hard_reset;
            xw(A_ROW, TB_N - 1); xr(A_ROW);
            check((rd >> AW) == 0, "ADDR_ROW bits above address width read 0");
            xw(A_COL, TB_N - 1); xr(A_COL);
            check((rd >> AW) == 0, "ADDR_COL bits above address width read 0");
            xw(A_CTRL, 8'h01); xr(A_CTRL); check(rd[7:3] == 0 && rd[2:1] == 0, "CTRL reserved bits read 0");
            xw(A_CTRL, 8'h00);
            st; check(rd[7:4] == 0, "STATUS[7:4] read 0");
            xr(A_RD); check(rd[7:1] == 0, "RDATA[7:1] read 0");
            sense_in = 1; xw(A_CTRL, 8'h04); wait_idle; xr(A_RD);
            check(rd == 8'h01, "RDATA reads 0x01 for sense=1 (reserved bits 0)");
            end_test;
        end
    endtask

    task t_ctrl_reserved_write;
        begin
            begin_test("ctrl_reserved_bits_rejected");
            hard_reset; p0 = prog_cycles;
            xw(A_CTRL, 8'h08); st; check(rd[S_PERR], "CTRL bit3 write -> PROTOCOL_ERROR");
            xw(A_CTRL, 8'h81); st; check(rd[S_PERR], "CTRL 0x81 write -> PROTOCOL_ERROR");
            xr(A_CTRL); check(rd == 8'h00, "rejected CTRL write did not arm");
            check(prog_cycles == p0, "no pulse");
            end_test;
        end
    endtask

    task t_unknown_and_ro;
        begin
            begin_test("unknown_address_and_read_only_writes");
            hard_reset;
            xw(A_ROW, 8'h03);
            xr(7'h06); check(rd == 8'h00, "unknown address reads 0");
            st; check(rd[S_PERR], "unknown read sets PROTOCOL_ERROR");
            xr(7'h7F); check(rd == 8'h00, "addr 0x7F reads 0");
            xw(7'h06, 8'hFF); xw(7'h7F, 8'h55);
            xr(A_ROW); check(rd == 8'h03, "unknown-address write changed nothing");
            st; check(rd[S_PERR], "unknown write sets PROTOCOL_ERROR");
            st; check(!rd[S_PERR], "STATUS read cleared PROTOCOL_ERROR");
            xw(A_ST, 8'hFF); xr(A_ST); check(rd[S_PERR], "STATUS write -> PROTOCOL_ERROR (flag set)");
            xr(A_ST);
            xw(A_RD, 8'hFF); xr(A_RD); check(rd == 8'h00, "RDATA write ignored");
            st; check(rd[S_PERR], "RDATA write -> PROTOCOL_ERROR");
            end_test;
        end
    endtask

    task t_program_full_sequence;
        begin
            begin_test("program_full_sequence");
            hard_reset; p0 = prog_cycles; c0 = pulse_cnt;
            xw(A_ROW, 8'h05); xw(A_COL, 8'h02); xw(A_PW, 8'd20);
            st; check(!rd[S_BUSY] && !rd[S_DONE], "idle before arm");
            xw(A_CTRL, 8'h01);
            check(!prog_en, "arm alone emits no pulse");
            xr(A_CTRL); check(rd == 8'h01, "armed");
            tick(30); check(pulse_cnt == c0, "still no pulse before strobe");
            xw(A_FIRE, 8'h00);
            wait_idle;
            check(pulse_cnt == c0 + 1, "exactly one pulse");
            check(last_len == 20, "pulse length == PULSE_WIDTH cycles");
            check(pulse_row == 5 && pulse_col == 2, "pulse addressed row 5 col 2");
            st; check(rd[S_DONE] && !rd[S_BUSY] && !rd[S_PERR], "PROG_DONE set, BUSY clear, no error");
            xr(A_CTRL); check(rd == 8'h00, "PROG_ARM and PROG_STROBE self-cleared");
            xw(A_CTRL, 8'h01); st; check(!rd[S_DONE], "new arm clears PROG_DONE");
            end_test;
        end
    endtask

    task t_pulse_widths;
        begin
            begin_test("pulse_width_min_default_mid_max");
            hard_reset;
            // default (reset) code, SCLK idle during the pulse
            c0 = pulse_cnt;
            xw(A_CTRL, 8'h01); xw(A_FIRE, 8'h00); wait_idle;
            check(pulse_cnt == c0 + 1 && last_len == 1, "default code 0x01 -> 1 cycle");
            prog_seq(1, 1, 8'd1);   check(last_len == 1, "min code 1 -> 1 cycle");
            prog_seq(1, 1, 8'd16);  check(last_len == 16, "code 16 -> 16 cycles");
            prog_seq(1, 1, 8'd255); check(last_len == 255, "max code 255 -> 255 cycles");
            prog_seq(1, 1, 8'd2);   check(last_len == 2, "code 2 -> 2 cycles");
            end_test;
        end
    endtask

    task t_zero_code;
        begin
            begin_test("pulse_width_zero_code_rejected");
            hard_reset; xw(A_PW, 8'd7); p0 = prog_cycles;
            xw(A_PW, 8'h00);
            st; check(rd[S_PERR], "zero code -> PROTOCOL_ERROR");
            xr(A_PW); check(rd == 8'd7, "PULSE_WIDTH unchanged by zero write");
            prog_seq(0, 0, 8'd7); check(last_len == 7, "programming still uses prior code");
            // zero code written from the reset default
            hard_reset; xw(A_PW, 8'h00); xr(A_PW); check(rd == 8'h01, "reset default survives zero write");
            end_test;
        end
    endtask

    // ---- interlock negative cases -------------------------------------
    task t_neg_strobe_without_arm;
        begin
            begin_test("neg_strobe_without_arm");
            hard_reset; p0 = prog_cycles; c0 = pulse_cnt;
            xw(A_CTRL, 8'h02); tick(20);
            st; check(rd[S_PERR] && !rd[S_BUSY], "CTRL strobe-only -> PROTOCOL_ERROR, not BUSY");
            xw(A_FIRE, 8'h00);   // arm+strobe via CTRL: PROG_STROBE is not writable
            tick(20);
            st; check(rd[S_PERR] && !rd[S_BUSY], "CTRL 0x03 -> PROTOCOL_ERROR, not BUSY");
            xw(A_FIRE, 8'h00);   // FIRE needs a prior arm
            tick(20);
            st; check(rd[S_PERR] && !rd[S_BUSY], "FIRE while unarmed -> PROTOCOL_ERROR, not BUSY");
            check(prog_cycles == p0 && pulse_cnt == c0, "no program pulse");
            check(!prog_en, "prog_en low");
            end_test;
        end
    endtask

    task t_neg_arm_and_strobe_one_txn;
        begin
            begin_test("neg_arm_and_strobe_in_one_transaction");
            hard_reset; p0 = prog_cycles; c0 = pulse_cnt;
            xw(A_FIRE, 8'h00); tick(40);
            check(pulse_cnt == c0 && prog_cycles == p0, "no pulse from combined write");
            xr(A_CTRL); check(rd == 8'h00, "combined write did not arm");
            xw(A_CTRL, 8'h02); tick(40);
            check(pulse_cnt == c0 && prog_cycles == p0, "no pulse from following strobe");
            xw(A_FIRE, 8'h00); tick(40);
            check(pulse_cnt == c0 && prog_cycles == p0, "no pulse from following FIRE");
            st; check(rd[S_PERR], "PROTOCOL_ERROR flagged");
            end_test;
        end
    endtask

    task t_neg_strobe_after_timeout;
        begin
            begin_test("neg_strobe_after_arm_timeout");
            hard_reset; p0 = prog_cycles; c0 = pulse_cnt;
            xw(A_CTRL, 8'h01);
            tick(TB_TIMEOUT + 50);
            xr(A_CTRL); check(rd == 8'h00, "PROG_ARM auto-cleared after timeout");
            st; check(!rd[S_PERR], "timeout itself is not a protocol error");
            xw(A_FIRE, 8'h00); tick(40);
            check(pulse_cnt == c0 && prog_cycles == p0, "no pulse after timeout");
            st; check(rd[S_PERR], "late strobe -> PROTOCOL_ERROR");
            end_test;
        end
    endtask

    task t_neg_stuck_high_strobe;
        begin
            begin_test("neg_stuck_high_strobe");
            hard_reset; p0 = prog_cycles; c0 = pulse_cnt;
            for (i = 0; i < 4; i = i + 1) begin xw(A_CTRL, 8'h02); xw(A_FIRE, 8'h00); end
            tick(40);
            check(pulse_cnt == c0 && prog_cycles == p0, "repeated strobe writes emit no pulse");
            // MOSI stuck high through one long frame: a single overlong frame
            sh = 4; cs_low; mosi = 1; for (i = 0; i < 40; i = i + 1) begin tick(sh); sclk = 1; tick(sh); sclk = 0; end
            cs_high; sh = 8; tick(20);
            check(pulse_cnt == c0 && prog_cycles == p0, "stuck-high MOSI emits no pulse");
            xr(A_CTRL); check(rd == 8'h00, "stuck-high MOSI did not arm");
            end_test;
        end
    endtask

    task t_neg_repeat_strobe_after_completion;
        begin
            begin_test("neg_repeated_strobe_after_completion");
            hard_reset; prog_seq(2, 3, 8'd5);
            c0 = pulse_cnt; p0 = prog_cycles;
            xw(A_FIRE, 8'h00); xw(A_CTRL, 8'h02); tick(40);
            check(pulse_cnt == c0 && prog_cycles == p0, "no second pulse without re-arm");
            xr(A_CTRL); check(rd == 8'h00, "arm stayed cleared");
            end_test;
        end
    endtask

    task t_neg_write_while_armed;
        integer which;
        begin
            begin_test("neg_target_or_width_write_while_armed");
            for (which = 0; which < 4; which = which + 1) begin
                hard_reset; xw(A_ROW, 1); xw(A_COL, 1);
                p0 = prog_cycles; c0 = pulse_cnt;
                xw(A_CTRL, 8'h01);
                case (which)
                    0: xw(A_ROW, 2);
                    1: xw(A_COL, 2);
                    2: xw(A_PW, 8'd9);
                    3: xw(A_ROW, TB_N);          // out-of-range write while armed
                endcase
                xr(A_CTRL); check(rd == 8'h00, "write while armed cleared PROG_ARM");
                st; check(rd[S_PERR], "write while armed set PROTOCOL_ERROR");
                xw(A_FIRE, 8'h00); tick(40);
                check(pulse_cnt == c0 && prog_cycles == p0, "following strobe emits no pulse");
            end
            end_test;
        end
    endtask

    task t_neg_arm_timeout_boundary;
        integer off;
        begin
            begin_test("neg_arm_timeout_boundary");
            fired_n = 0;
            for (trial = 0; trial < 9; trial = trial + 1) begin
                hard_reset; xw(A_PW, 8'd1);
                c0 = pulse_cnt;
                xw(A_CTRL, 8'h01);
                // strobe frame: clock all 16 bits, then hold CS_N low until the target cycle
                cs_low; send_bits(8, 32'hF8); send_bits(8, 32'h00);
                while (cyc < arm_first_cyc + TB_TIMEOUT - 6 + trial) @(posedge clk);
                #1 cs_n = 1'b1;
                tick(TB_TIMEOUT / 8 + 40);
                off = commit_cyc - arm_first_cyc;
                if (off < TB_TIMEOUT) begin
                    check(pulse_cnt == c0 + 1, "commit inside armed window fires");
                end else begin
                    check(pulse_cnt == c0, "commit outside armed window does not fire");
                end
                if (off == TB_TIMEOUT - 1) begin check(pulse_cnt == c0 + 1, "last armed cycle fires"); fired_n = fired_n + 1000; end
                if (off == TB_TIMEOUT)     begin check(pulse_cnt == c0,     "first expired cycle does not fire"); fired_n = fired_n + 1; end
                tick(10);
            end
            check(fired_n == 1001, "trials covered both boundary cycles");
            end_test;
        end
    endtask

    task t_arm_flag_duration;
        begin
            begin_test("arm_flag_high_exactly_ARM_TIMEOUT_cycles");
            hard_reset;
            xw(A_CTRL, 8'h01);
            tick(TB_TIMEOUT + 20);
            check(arm_last_len == TB_TIMEOUT, "armed for exactly ARM_TIMEOUT cycles");
            end_test;
        end
    endtask

    // ---- fault model and single-bit-fault coverage ----------------------------
    // Fault model (spec/spi-register-implementation-decision.md, "Fault model"):
    //   FM1  one MOSI bit of one 16-bit frame is inverted (any of 16 positions,
    //        command or data byte);
    //   FM2  at most one such fault per host sequence between resets, so every
    //        other frame of the sequence is as the host intended;
    //   FM3  one transaction-boundary fault: a missing or extra SCLK edge, a
    //        spurious CS_N rise inside a frame, or a missed CS_N rise between
    //        two frames.
    // Claim: a program pulse needs a committed FIRE frame (command byte 0xF8)
    // while armed, and no defined-register frame (command bytes 0x00..0x05 and
    // 0x80..0x85, any data) is within Hamming distance 3 of 0xF8 -- so no
    // fault in FM1..FM3 turns a host sequence that contains no FIRE into a pulse.

    // Program-capable commands: every 8-bit command byte, three data bytes, armed
    // and unarmed. Exactly the FIRE command with the arm in place may pulse.
    task t_fire_only_via_fire_cmd;
        integer cb, di, ar;
        reg [7:0] cmdb, datb;
        integer expect_n;
        begin
            begin_test("fire_only_via_fire_command_all_cmd_bytes");
            sh = 4; expect_n = 0;
            for (ar = 0; ar < 2; ar = ar + 1)
                for (cb = 0; cb < 256; cb = cb + 1)
                    for (di = 0; di < 3; di = di + 1) begin
                        cmdb = cb;
                        datb = (di == 0) ? 8'h00 : (di == 1) ? 8'h03 : 8'hFF;
                        hard_reset; sh = 4; xw(A_PW, 8'd1);
                        if (ar) xw(A_CTRL, 8'h01);
                        c0 = pulse_cnt;
                        xfer(cmdb, datb); tick(8);
                        wait_idle;
                        if (ar && cmdb == 8'hF8) begin
                            expect_n = expect_n + 1;
                            check(pulse_cnt == c0 + 1, "armed FIRE command pulses once");
                        end else
                            check(pulse_cnt == c0, "no pulse from any other command byte or state");
                    end
            check(expect_n == 3, "FIRE command was exercised");
            sh = 8;
            end_test;
        end
    endtask

    // CTRL carries no strobe: every CTRL data value, written while armed, leaves
    // the pulse count unchanged (the pre-amendment fire code 0x03 included).
    task t_ctrl_cannot_fire;
        integer vv;
        begin
            begin_test("ctrl_write_cannot_fire_any_value");
            sh = 4;
            for (vv = 0; vv < 256; vv = vv + 1) begin
                hard_reset; sh = 4; xw(A_CTRL, 8'h01); c0 = pulse_cnt;
                xw(A_CTRL, vv); wait_idle;
                check(pulse_cnt == c0, "no CTRL data value fires");
            end
            sh = 8;
            end_test;
        end
    endtask

    // FM1: every defined-register frame the host can legitimately issue (all 12
    // command bytes, a spread of data bytes), each of its 16 bits flipped, in the
    // armed and the unarmed state. None of the 2 x 12 x 6 x 16 faulted frames
    // may produce a pulse.
    task t_single_bit_flip_never_fires;
        integer ar, ci, di, bit;
        reg [7:0] cmdb, datb;
        reg [15:0] fr;
        begin
            begin_test("single_bit_flip_of_any_register_frame_never_fires");
            sh = 4;
            for (ar = 0; ar < 2; ar = ar + 1)
                for (ci = 0; ci < 12; ci = ci + 1)
                    for (di = 0; di < 6; di = di + 1) begin
                        cmdb = (ci < 6) ? ci : (8'h80 | (ci - 6));
                        datb = (di == 0) ? 8'h00 : (di == 1) ? 8'h01 : (di == 2) ? 8'h03 :
                               (di == 3) ? 8'h04 : (di == 4) ? 8'h07 : 8'hFF;
                        for (bit = 0; bit < 16; bit = bit + 1) begin
                            fr = {cmdb, datb} ^ (16'h0001 << bit);
                            hard_reset; sh = 4; xw(A_PW, 8'd1);
                            if (ar) xw(A_CTRL, 8'h01);
                            c0 = pulse_cnt;
                            xfer(fr[15:8], fr[7:0]); wait_idle;
                            check(pulse_cnt == c0, "single-bit-flipped register frame must not program");
                        end
                    end
            sh = 8;
            end_test;
        end
    endtask

    // FM1 on the legitimate sequence: arm, then a flip anywhere in the FIRE
    // frame. A data-byte flip is still the host's FIRE (one pulse, as intended);
    // a command-byte flip is no longer a FIRE: no pulse, PROTOCOL_ERROR, arm dropped.
    task t_fire_frame_single_bit_flip;
        integer bit;
        reg [15:0] fr;
        begin
            begin_test("fire_frame_single_bit_flip_fail_safe");
            sh = 4;
            for (bit = 0; bit < 16; bit = bit + 1) begin
                fr = 16'hF800 ^ (16'h0001 << bit);
                hard_reset; sh = 4; xw(A_PW, 8'd1); xw(A_CTRL, 8'h01); c0 = pulse_cnt;
                xfer(fr[15:8], fr[7:0]); wait_idle;
                if (bit < 8) check(pulse_cnt == c0 + 1, "data-bit flip of FIRE is still the intended FIRE");
                else begin
                    check(pulse_cnt == c0, "command-bit flip of FIRE does not program");
                    st; check(rd[S_PERR], "command-bit flip of FIRE -> PROTOCOL_ERROR");
                    xr(A_CTRL); check(rd == 8'h00, "command-bit flip of FIRE dropped the arm");
                end
            end
            sh = 8;
            end_test;
        end
    endtask

    // FM3: transaction-boundary faults around the FIRE frame and its neighbours.
    task t_boundary_faults_never_fire;
        integer k, which;
        reg [15:0] fr;
        begin
            begin_test("transaction_boundary_faults_never_fire");
            sh = 4;
            // (a) spurious CS_N rise inside a frame at every bit position: the
            //     frame is split into two, neither of which is 16 bits.
            for (which = 0; which < 2; which = which + 1) begin
                fr = which ? 16'hF800 : 16'h8200;        // FIRE frame / DISARM frame
                for (k = 1; k < 16; k = k + 1) begin
                    hard_reset; sh = 4; xw(A_PW, 8'd1); xw(A_CTRL, 8'h01); c0 = pulse_cnt;
                    cs_low; send_bits(k, fr >> (16 - k)); cs_high;
                    cs_low; send_bits(16 - k, fr); cs_high; wait_idle;
                    check(pulse_cnt == c0, "CS_N glitch inside a frame never programs");
                    xr(A_CTRL); check(rd == 8'h00, "CS_N glitch dropped the arm");
                end
            end
            // (b) missed CS_N rise between two frames (32 edges in one frame)
            for (which = 0; which < 3; which = which + 1) begin
                hard_reset; sh = 4; xw(A_PW, 8'd1); xw(A_CTRL, 8'h01); c0 = pulse_cnt;
                cs_low;
                case (which)
                    0: begin send_bits(16, 32'h8200); send_bits(16, 32'hF800); end   // DISARM,FIRE
                    1: begin send_bits(16, 32'h0400); send_bits(16, 32'hF800); end   // STATUS read,FIRE
                    default: begin send_bits(16, 32'h8201); send_bits(16, 32'hF800); end // ARM,FIRE
                endcase
                cs_high; wait_idle;
                check(pulse_cnt == c0, "merged frames (missed CS_N rise) never program");
            end
            // (c) one SCLK edge missing / extra inside a FIRE frame: not a 16-edge frame
            for (which = 0; which < 2; which = which + 1) begin
                for (k = 0; k < 16; k = k + 1) begin
                    hard_reset; sh = 4; xw(A_PW, 8'd1); xw(A_CTRL, 8'h01); c0 = pulse_cnt;
                    cs_low;
                    if (which == 0) begin   // drop bit k from the stream
                        if (k > 0) send_bits(k, 32'hF800 >> (16 - k));
                        if (k < 15) send_bits(15 - k, 32'hF800);
                    end else begin          // repeat bit k
                        send_bits(k + 1, 32'hF800 >> (15 - k));
                        send_bits(16 - k, 32'hF800 >> 0);
                    end
                    cs_high; wait_idle;
                    check(pulse_cnt == c0, "missing/extra SCLK edge never programs");
                end
            end
            sh = 8;
            end_test;
        end
    endtask

    task t_disarm_and_rearm;
        begin
            begin_test("disarm_write_and_rearm");
            hard_reset; c0 = pulse_cnt;
            xw(A_CTRL, 8'h01); xw(A_CTRL, 8'h00);
            xr(A_CTRL); check(rd == 8'h00, "CTRL=0 disarms");
            st; check(!rd[S_PERR], "disarm is not an error");
            xw(A_FIRE, 8'h00); tick(40);
            check(pulse_cnt == c0, "strobe after disarm emits no pulse");
            prog_seq(0, 0, 8'd3); check(pulse_cnt == c0 + 1, "re-arm then strobe works");
            end_test;
        end
    endtask

    // One rejected transaction per pulse: a 16-bit frame at the fastest
    // supported SCLK (8 clk period) takes ~140 clk, the longest pulse is 255.
    task t_neg_busy_writes_program;
        integer which;
        begin
            begin_test("busy_writes_rejected_during_program_pulse");
            for (which = 0; which < 7; which = which + 1) begin
                hard_reset; sh = 4;
                xw(A_ROW, 4); xw(A_COL, 6); xw(A_PW, 8'd255);
                xw(A_CTRL, 8'h01); c0 = pulse_cnt; r0 = read_cnt;
                xw(A_FIRE, 8'h00);                         // pulse now running
                check(busy, "BUSY during pulse");
                case (which)
                    0: xw(A_ROW, 8'h09);
                    1: xw(A_COL, 8'h09);
                    2: xw(A_PW, 8'd3);
                    3: xw(A_CTRL, 8'h01);
                    4: xw(A_CTRL, 8'h04);
                    5: xw(A_FIRE, 8'h00);                    // second FIRE while the pulse runs
                    default: st;
                endcase
                if (which == 6) check(rd[S_BUSY], "STATUS read during pulse shows BUSY");
                check(prog_en, "pulse still running after the transaction");
                wait_idle;
                check(pulse_cnt == c0 + 1 && last_len == 255, "single full-length pulse");
                check(pulse_row == 4 && pulse_col == 6 && stab_viol == 0, "target frozen during pulse");
                check(read_cnt == r0, "no read started during/after pulse");
                xr(A_PW); check(rd == 8'd255, "PULSE_WIDTH unchanged");
                xr(A_CTRL); check(rd == 8'h00, "CTRL clear after pulse");
                st;
                if (which == 6) check(!rd[S_PERR], "legal STATUS read during pulse is not an error");
                else check(rd[S_PERR], "BUSY write -> PROTOCOL_ERROR");
                sh = 8;
            end
            end_test;
        end
    endtask

    task t_neg_busy_writes_read;
        integer which;
        begin
            begin_test("busy_writes_rejected_during_read_settle");
            if (TB_SETTLE < 160) begin
                skipped = 1'b1;
            end else begin
                for (which = 0; which < 3; which = which + 1) begin
                    hard_reset; sh = 4; sense_in = 1; c0 = read_cnt;
                    xw(A_ROW, 2);
                    xw(A_CTRL, 8'h04); check(busy && read_en, "BUSY with READ_EN");
                    case (which)
                        0: xw(A_ROW, 8'h07);
                        1: xw(A_CTRL, 8'h01);
                        default: xw(A_CTRL, 8'h04);
                    endcase
                    check(read_en, "read still settling after the transaction");
                    wait_idle;
                    check(read_cnt == c0 + 1 && rlast_len == TB_SETTLE, "exactly one full-length read");
                    xr(A_ROW); check(rd == 8'h02, "ROW unchanged by write during read");
                    xr(A_CTRL); check(rd == 8'h00, "CTRL clear: arm during read rejected");
                    st; check(rd[S_PERR] && rd[S_VALID], "PROTOCOL_ERROR set, read completed");
                    sh = 8;
                end
            end
            end_test;
        end
    endtask

    task t_reset_while_armed_or_active;
        begin
            begin_test("reset_while_armed_and_while_active");
            hard_reset; xw(A_ROW, 3); xw(A_PW, 8'd200); xw(A_CTRL, 8'h01);
            #1 rst_n = 0; tick(4); rst_n = 1; tick(8);
            xr(A_CTRL); check(rd == 8'h00, "reset cleared PROG_ARM");
            xr(A_ROW); check(rd == 8'h00, "reset cleared ADDR_ROW");
            xr(A_PW); check(rd == 8'h01, "reset restored PULSE_WIDTH");
            c0 = pulse_cnt; xw(A_FIRE, 8'h00); tick(40);
            check(pulse_cnt == c0, "strobe after reset emits no pulse");
            // reset in the middle of a pulse
            hard_reset; sh = 4; xw(A_PW, 8'd200); xw(A_CTRL, 8'h01); c0 = pulse_cnt; xw(A_FIRE, 8'h00);
            tick(20); check(prog_en, "pulse running");
            #1 rst_n = 0; #1 check(!prog_en && !busy, "prog_en drops immediately on reset");
            tick(4); rst_n = 1; tick(8);
            check(pulse_cnt == c0 + 1 && last_len < 200, "pulse truncated, not restarted");
            tick(300); check(pulse_cnt == c0 + 1, "no pulse after release");
            st; check(rd == 8'h00, "STATUS clean after reset");
            sh = 8;
            end_test;
        end
    endtask

    // ---- read path -----------------------------------------------------
    task t_read_sequence;
        begin
            begin_test("read_strobe_rdata_and_settle");
            hard_reset; sense_in = 0; c0 = read_cnt;
            xw(A_ROW, 1); xw(A_COL, 1); xw(A_CTRL, 8'h04);
            tick(TB_SETTLE + 10);
            check(read_cnt == c0 + 1 && rlast_len == TB_SETTLE, "READ_EN high exactly READ_SETTLE cycles");
            st; check(rd[S_VALID] && !rd[S_BUSY], "READ_VALID set, BUSY clear");
            xr(A_RD); check(rd == 8'h00, "RDATA = 0 for sense 0");
            xr(A_CTRL); check(rd == 8'h00, "READ_STROBE self-cleared");
            sense_in = 1; xw(A_CTRL, 8'h04);
            tick(TB_SETTLE + 10);
            st; check(rd[S_VALID], "READ_VALID set again");
            xr(A_RD); check(rd == 8'h01, "RDATA = 1 for sense 1");
            check(!prog_en, "prog_en never asserted by a read");
            // READ_VALID clears when the next read starts
            sense_in = 0; xw(A_CTRL, 8'h04);
            check(dut.read_valid == 0 && busy, "READ_VALID cleared at read start");
            wait_idle;
            xr(A_RD); check(rd == 8'h00, "RDATA follows sense_in again");
            check(excl_viol == 0, "READ_EN never overlapped arm/pulse");
            end_test;
        end
    endtask

    task t_neg_read_while_armed;
        begin
            begin_test("neg_read_strobe_while_armed");
            hard_reset; c0 = read_cnt; p0 = prog_cycles;
            xw(A_CTRL, 8'h01); xw(A_CTRL, 8'h04); tick(TB_SETTLE + 10);
            check(read_cnt == c0, "READ_EN stays disabled while armed");
            st; check(rd[S_PERR], "PROTOCOL_ERROR");
            xr(A_CTRL); check(rd == 8'h00, "error dropped the arm");
            // combined read bits rejected
            for (i = 5; i < 8; i = i + 1) begin xw(A_CTRL, i); tick(TB_SETTLE + 10); end
            check(read_cnt == c0 && prog_cycles == p0, "CTRL 0x05/0x06/0x07 start nothing");
            end_test;
        end
    endtask

    // ---- addressing -----------------------------------------------------
    task t_addr_boundaries;
        reg [8:0] bad;
        begin
            begin_test("address_range_boundaries_no_aliasing");
            hard_reset; c0 = pulse_cnt;
            xw(A_ROW, TB_N - 1); xr(A_ROW); check(rd == TB_N - 1, "N-1 accepted");
            xw(A_COL, TB_N - 1); xr(A_COL); check(rd == TB_N - 1, "N-1 accepted (col)");
            st; check(!rd[S_PERR], "boundary-valid writes raise no error");
            xw(A_ROW, 8'd1); xw(A_COL, 8'd1);
            // candidate invalid values: N, 2^AW-1 (if >= N), N+1, 2^AW | 5, 0x80|5, 0xFF, 0xFE
            for (k = 0; k < 7; k = k + 1) begin
                case (k)
                    0: v = TB_N;
                    1: v = (1 << AW) - 1;
                    2: v = TB_N + 1;
                    3: v = ((1 << AW) | 8'd5);
                    4: v = 8'h80 | 8'd5;
                    5: v = 8'hFF;
                    default: v = 8'hFE;
                endcase
                if (v >= TB_N) begin
                    xw(A_ROW, v); xr(A_ROW); check(rd == 8'd1, "invalid ROW write ignored");
                    check(row_sel == 1, "row_sel did not alias");
                    st; check(rd[S_PERR], "invalid ROW write -> PROTOCOL_ERROR");
                    xw(A_COL, v); xr(A_COL); check(rd == 8'd1, "invalid COL write ignored");
                    check(col_sel == 1, "col_sel did not alias");
                    st; check(rd[S_PERR], "invalid COL write -> PROTOCOL_ERROR");
                end
            end
            // an invalid write must not retarget a following pulse to the aliased cell
            xw(A_ROW, 8'h80 | 8'd5); xw(A_COL, (1 << AW) | 8'd5);
            xw(A_CTRL, 8'h01); xw(A_FIRE, 8'h00); wait_idle;
            check(pulse_cnt == c0 + 1 && pulse_row == 1 && pulse_col == 1, "pulse lands on last valid cell, not alias");
            end_test;
        end
    endtask

    // ---- SPI framing ------------------------------------------------------
    task t_framing;
        begin
            begin_test("spi_truncated_and_overlong_frames");
            hard_reset; p0 = prog_cycles; c0 = pulse_cnt;
            // CS_N toggled with no clocks: not an error
            cs_low; cs_high; st; check(!rd[S_PERR], "empty frame is not an error");
            // truncated arm frames: 7, 8, 15 bits
            for (k = 0; k < 3; k = k + 1) begin
                cs_low;
                case (k)
                    0: send_bits(7, 32'h41);
                    1: send_bits(8, 32'h82);
                    default: send_bits(15, 32'h4101);
                endcase
                cs_high;
                st; check(rd[S_PERR], "truncated frame -> PROTOCOL_ERROR");
                xr(A_CTRL); check(rd == 8'h00, "truncated arm frame did not arm");
            end
            // overlong arm frames: 17 and 24 bits
            for (k = 0; k < 2; k = k + 1) begin
                cs_low; send_bits(16, 32'h8201);
                if (k == 0) send_bits(1, 1); else send_bits(8, 8'hFF);
                cs_high;
                st; check(rd[S_PERR], "overlong frame -> PROTOCOL_ERROR");
                xr(A_CTRL); check(rd == 8'h00, "overlong arm frame did not arm");
            end
            // truncated / overlong strobe after a legitimate arm: no pulse, arm dropped
            xw(A_CTRL, 8'h01);
            cs_low; send_bits(15, 32'h4101); cs_high;
            xr(A_CTRL); check(rd == 8'h00, "malformed frame while armed drops the arm");
            xw(A_CTRL, 8'h01);
            cs_low; send_bits(16, 32'hF800); send_bits(1, 0); cs_high;
            tick(40);
            check(pulse_cnt == c0 && prog_cycles == p0, "no pulse from malformed strobe frames");
            // truncated write must not change a register
            xw(A_ROW, 8'd9);
            cs_low; send_bits(15, 32'h4005 >> 0); cs_high;   // 0x80 0x05 minus last bit
            xr(A_ROW); check(rd == 8'd9, "truncated write left ADDR_ROW unchanged");
            // a good frame after errors still works
            xw(A_ROW, 8'd4); xr(A_ROW); check(rd == 8'd4, "bus recovers after malformed frames");
            end_test;
        end
    endtask

    task t_cs_isolation_and_miso;
        begin
            begin_test("spi_cs_isolation_and_miso_timing");
            hard_reset; p0 = prog_cycles; c0 = pulse_cnt;
            xw(A_ROW, 8'h15 % TB_N);
            // SCLK activity while CS_N high: nothing happens
            mosi = 1;
            for (i = 0; i < 40; i = i + 1) begin tick(sh); sclk = 1; tick(sh); sclk = 0; end
            mosi = 0; tick(10);
            check(miso_oe == 0 && miso == 0, "MISO released while CS_N high");
            st; check(!rd[S_PERR], "no error from clocking with CS_N high");
            xr(A_CTRL); check(rd == 8'h00, "nothing armed");
            // arm command clocked in, CS_N never asserted
            send_bits(16, 32'h8201); tick(10);
            xr(A_CTRL); check(rd == 8'h00, "frame without CS_N is ignored");
            // abort a frame mid-way, then a fresh frame is clean
            cs_low; send_bits(8, 32'h82); cs_high;
            st; check(rd[S_PERR], "aborted frame flagged");
            xw(A_ROW, 8'h07 % TB_N); xr(A_ROW); check(rd == 8'h07 % TB_N, "next frame unaffected by aborted frame");
            // MISO output enable follows CS_N, data MSB first
            cs_n = 0; tick(6); check(miso_oe == 1, "MISO enabled with CS_N low"); cs_n = 1; tick(8);
            xw(A_ROW, 8'hA5 % TB_N); xr(A_ROW); check(rd == (8'hA5 % TB_N), "MSB-first MISO data");
            check(miso_viol == 0, "MISO changed only while SCLK low");
            check(prog_cycles == p0 && pulse_cnt == c0, "no pulse");
            end_test;
        end
    endtask

    // fast SCLK (4 clk per half period) still works
    task t_fast_sclk;
        begin
            begin_test("spi_minimum_sclk_period_8_clk");
            hard_reset; sh = 4;
            xw(A_ROW, 8'd6 % TB_N); xr(A_ROW); check(rd == 8'd6 % TB_N, "readback at clk/8");
            xw(A_PW, 8'h5A); xr(A_PW); check(rd == 8'h5A, "PW readback at clk/8");
            check(miso_viol == 0, "MISO stable at sample edge");
            sh = 8;
            end_test;
        end
    endtask

    initial begin : main
        #1;
        $display("antifuse_spi_regs bench: N=%0d AW=%0d READ_SETTLE=%0d ARM_TIMEOUT=%0d", TB_N, AW, TB_SETTLE, TB_TIMEOUT);
        hard_reset;
        t_reset_values;
        t_rw_all_registers;
        t_reserved_bits;
        t_ctrl_reserved_write;
        t_unknown_and_ro;
        t_program_full_sequence;
        t_pulse_widths;
        t_zero_code;
        t_neg_strobe_without_arm;
        t_neg_arm_and_strobe_one_txn;
        t_neg_strobe_after_timeout;
        t_neg_stuck_high_strobe;
        t_neg_repeat_strobe_after_completion;
        t_neg_write_while_armed;
        t_arm_flag_duration;
        t_neg_arm_timeout_boundary;
        t_fire_only_via_fire_cmd;
        t_ctrl_cannot_fire;
        t_single_bit_flip_never_fires;
        t_fire_frame_single_bit_flip;
        t_boundary_faults_never_fire;
        t_disarm_and_rearm;
        t_neg_busy_writes_program;
        t_neg_busy_writes_read;
        t_reset_while_armed_or_active;
        t_read_sequence;
        t_neg_read_while_armed;
        t_addr_boundaries;
        t_framing;
        t_cs_isolation_and_miso;
        t_fast_sclk;
        begin_test("global_monitors");
        check(excl_viol == 0, "prog_en/read_en/arm exclusion held for the whole run");
        check(stab_viol == 0, "row/col stable during every pulse");
        check(miso_viol == 0, "no MISO change while SCLK high");
        end_test;
        if (errs == 0) $display("RESULT: ALL %0d TESTS PASSED (N=%0d)", tests, TB_N);
        else $display("RESULT: FAIL %0d checks failed (N=%0d)", errs, TB_N);
        $finish;
    end

    initial begin
        #200_000_000;
        $display("RESULT: FAIL watchdog timeout");
        $finish;
    end
endmodule
