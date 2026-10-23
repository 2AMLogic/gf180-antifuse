// tb_antifuse_decode.v -- exhaustive self-checking bench for antifuse_decode
//
// For every (en, idx) pair, including idx >= N when N is not a power of two:
//   en = 0            : all N lines are 0
//   en = 1, idx <  N  : exactly one line hot, and it is sel[idx]
//   en = 1, idx >= N  : all N lines are 0 (nothing selected)
// "Exactly one hot" is asserted only for en = 1 and idx < N.
// Parameter TB_N is overridden by verification/run_decode.sh.
`timescale 1ns/1ps

module tb_antifuse_decode;
    parameter TB_N = 32;

    function integer clog2;
        input integer v;
        integer i;
        begin
            clog2 = 0;
            for (i = 1; i < v; i = i * 2) clog2 = clog2 + 1;
        end
    endfunction

    localparam AW = clog2(TB_N);

    reg  [AW-1:0]  idx;
    reg            en;
    wire [TB_N-1:0] sel;

    antifuse_decode #(.N(TB_N)) dut (.idx(idx), .en(en), .sel(sel));

    function integer popcount;
        input [TB_N-1:0] v;
        integer k;
        begin
            popcount = 0;
            for (k = 0; k < TB_N; k = k + 1) popcount = popcount + v[k];
        end
    endfunction

    integer e, i, checks, fails;
    reg [TB_N-1:0] expect_sel;

    initial begin
        checks = 0;
        fails  = 0;
        for (e = 0; e < 2; e = e + 1) begin
            for (i = 0; i < (1 << AW); i = i + 1) begin
                en  = e[0];
                idx = i[AW-1:0];
                #1;
                expect_sel = {TB_N{1'b0}};
                if (e == 1 && i < TB_N) expect_sel[i] = 1'b1;
                checks = checks + 1;
                if (sel !== expect_sel) begin
                    fails = fails + 1;
                    $display("[FAIL] N=%0d en=%0d idx=%0d sel=%b expected=%b",
                             TB_N, e, i, sel, expect_sel);
                end
                if (e == 1 && i < TB_N && popcount(sel) != 1) begin
                    fails = fails + 1;
                    $display("[FAIL] N=%0d idx=%0d not exactly one hot (popcount=%0d)",
                             TB_N, i, popcount(sel));
                end
                if ((e == 0 || i >= TB_N) && popcount(sel) != 0) begin
                    fails = fails + 1;
                    $display("[FAIL] N=%0d en=%0d idx=%0d lines hot when none expected",
                             TB_N, e, i);
                end
            end
        end
        if (fails == 0) begin
            $display("[PASS] decode_exhaustive N=%0d (%0d checks)", TB_N, checks);
            $display("RESULT: ALL 1 TESTS PASSED");
        end else begin
            $display("RESULT: %0d FAILURES", fails);
        end
        $finish;
    end
endmodule
