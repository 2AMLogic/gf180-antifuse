// antifuse_digital_top.v -- digital partition top
//
// SPI slave / register file / sequencer (antifuse_spi_regs) plus the global
// row and column one-hot decoders of spec/architecture.md section 1.1.
// The decoder enable is prog_en | read_en: a row/column line is selected only
// while a program pulse or a read leg is active (section 1.2 -- both are
// already mutually exclusive, and every pass-gate is OFF while idle).
// All other spi_regs ports pass through unchanged; row_sel/col_sel binary
// indices stay visible for readback and bench use.
// Port and parameter notes: rtl/README.md.
`timescale 1ns/1ps

module antifuse_digital_top #(
    parameter N            = 32,    // grid size, 2..256
    parameter ARM_TIMEOUT  = 4096,  // see antifuse_spi_regs
    parameter READ_SETTLE  = 8      // see antifuse_spi_regs
) (
    input  wire                 clk,
    input  wire                 rst_n,

    input  wire                 sclk,
    input  wire                 mosi,
    input  wire                 cs_n,
    output wire                 miso,
    output wire                 miso_oe,

    output wire [N-1:0]         row_onehot,  // one-hot row select, all zeros while idle
    output wire [N-1:0]         col_onehot,  // one-hot column select, all zeros while idle
    output wire [clog2(N)-1:0]  row_sel,     // binary target row (from antifuse_spi_regs)
    output wire [clog2(N)-1:0]  col_sel,     // binary target column
    output wire                 prog_en,
    output wire                 read_en,
    input  wire                 sense_in,
    output wire                 busy
);

    function integer clog2;
        input integer v;
        integer i;
        begin
            clog2 = 0;
            for (i = 1; i < v; i = i * 2) clog2 = clog2 + 1;
        end
    endfunction

    wire dec_en = prog_en | read_en;

    antifuse_spi_regs #(
        .N(N), .ARM_TIMEOUT(ARM_TIMEOUT), .READ_SETTLE(READ_SETTLE)
    ) u_regs (
        .clk(clk), .rst_n(rst_n),
        .sclk(sclk), .mosi(mosi), .cs_n(cs_n),
        .miso(miso), .miso_oe(miso_oe),
        .row_sel(row_sel), .col_sel(col_sel),
        .prog_en(prog_en), .read_en(read_en),
        .sense_in(sense_in), .busy(busy)
    );

    antifuse_decode #(.N(N)) u_row_dec (.idx(row_sel), .en(dec_en), .sel(row_onehot));
    antifuse_decode #(.N(N)) u_col_dec (.idx(col_sel), .en(dec_en), .sel(col_onehot));

endmodule
