// antifuse_decode.v -- binary index to one-hot select decoder with enable
//
// One instance per axis (row, column) in the digital partition, per
// spec/architecture.md section 1.1.  sel[i] = en & (idx == i) for i < N.
// While en is low every line is 0 (no row/column selected while idle).
// For non-power-of-two N, index values >= N select nothing (all zeros), so
// "exactly one hot" holds only for en = 1 and idx < N.
// Port and parameter notes: rtl/README.md.
//
// Verilog-2001, purely combinational.
`timescale 1ns/1ps

module antifuse_decode #(
    parameter N = 32            // number of select lines, 2..256; idx width = clog2(N)
) (
    input  wire [clog2(N)-1:0]  idx,       // binary index
    input  wire                 en,        // 0 forces sel to all zeros
    output wire [N-1:0]         sel        // one-hot select, sel[idx] = en when idx < N
);

    function integer clog2;
        input integer v;
        integer i;
        begin
            clog2 = 0;
            for (i = 1; i < v; i = i * 2) clog2 = clog2 + 1;
        end
    endfunction

    // synthesis translate_off
    initial begin
        if (N < 2 || N > 256) begin
            $display("antifuse_decode: unsupported N=%0d (need 2..256)", N);
            $finish;
        end
    end
    // synthesis translate_on

    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : g_sel
            assign sel[i] = en & (idx == i);
        end
    endgenerate

endmodule
