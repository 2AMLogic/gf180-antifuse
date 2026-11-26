"""Port-only cocotb suite for the routed antifuse_digital_top netlist.

Gate-level counterpart of test_spi_regs.py: the DUT is the post-route netlist
rtl/pnr/antifuse_digital_top_routed.v (fixed at N = 32 with the default
ARM_TIMEOUT = 4096 and READ_SETTLE = 8 baked into the cells), simulated with
the gf180mcu_fd_sc_mcu7t5v0 behavioural models resolved from the PDK by
`klt functional-verification` (request_digital_top.json).

Drives and observes only the top-level ports (clk, rst_n, sclk, mosi, cs_n,
miso, miso_oe, row_onehot, col_onehot, row_sel, col_sel, prog_en, read_en,
sense_in, busy) -- no hierarchical reference into the netlist -- so the same
suite also runs against rtl/antifuse_digital_top.v unchanged.

The per-cycle monitor checks the decoders on every test: row_onehot and
col_onehot are all zeros unless prog_en or read_en is high, and exactly
one-hot at row_sel / col_sel while a pulse is active. The SPI register tests
are the port-applicable subset of test_spi_regs.py, with the netlist's own
elaboration constants below (ARM_TIMEOUT is the netlist's 4096, not the RTL
request's 300) and frame rates kept inside the f_clk >= 8 x f_SCLK contract.
"""
import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

N = 32
ARM_TIMEOUT = 4096
READ_SETTLE = 8
SH = 8  # clk cycles per SCLK half period for frames that read MISO

A_ROW, A_COL, A_CTRL, A_PW, A_ST, A_RD = 0x00, 0x01, 0x02, 0x03, 0x04, 0x05
A_FIRE = 0x78
ST_BUSY, ST_DONE, ST_VALID, ST_PERR = 1, 2, 4, 8


class Bench:
    def __init__(self, dut):
        self.dut = dut
        self.prog_pulses = []
        self.read_pulses = []
        self.violations = []
        self.prog_cycles = 0
        self.cycle = 0

    async def reset(self):
        d = self.dut
        d.rst_n.value = 0
        d.sclk.value = 0
        d.mosi.value = 0
        d.cs_n.value = 1
        d.sense_in.value = 0
        period_ns = int(os.environ.get("ANTIFUSE_GATE_CLOCK_NS", "10"))
        cocotb.start_soon(Clock(d.clk, period_ns, unit="ns").start())
        await ClockCycles(d.clk, 4)
        d.rst_n.value = 1
        await ClockCycles(d.clk, 8)
        cocotb.start_soon(self._monitor())

    async def _monitor(self):
        d = self.dut
        pl = rl = 0
        frozen = None  # (row_sel, col_sel) latched at pulse start
        while True:
            await RisingEdge(d.clk)
            self.cycle += 1
            p, r, b = int(d.prog_en.value), int(d.read_en.value), int(d.busy.value)
            row, col = int(d.row_sel.value), int(d.col_sel.value)
            roh, coh = int(d.row_onehot.value), int(d.col_onehot.value)
            if p and r:
                self.violations.append("prog_en and read_en high together")
            if b != (p | r):
                self.violations.append("busy != prog_en | read_en")
            if p or r:
                if frozen is None:
                    frozen = (row, col)
                elif (row, col) != frozen:
                    self.violations.append(("row_sel/col_sel moved during pulse", frozen, (row, col)))
                if roh != (1 << row) or coh != (1 << col):
                    self.violations.append(("one-hot mismatch", row, col, roh, coh))
            else:
                frozen = None
                if roh or coh:
                    self.violations.append(("one-hot active while idle", roh, coh))
            if p:
                pl += 1
                self.prog_cycles += 1
            elif pl:
                self.prog_pulses.append(pl)
                pl = 0
            if r:
                rl += 1
            elif rl:
                self.read_pulses.append(rl)
                rl = 0

    async def idle(self, n):
        await ClockCycles(self.dut.clk, n)

    async def frame(self, nbits, value, sh=SH, tail=8):
        """One CS_N-framed transfer of nbits (MSB first); returns MISO bits."""
        d = self.dut
        d.cs_n.value = 0
        await self.idle(4)
        rx = 0
        for i in range(nbits - 1, -1, -1):
            d.mosi.value = (value >> i) & 1
            await self.idle(sh)
            rx = (rx << 1) | int(d.miso.value)
            d.sclk.value = 1
            await self.idle(sh)
            d.sclk.value = 0
        await self.idle(4)
        d.cs_n.value = 1
        await self.idle(tail)
        return rx

    async def xfer(self, cmd, data, sh=SH, tail=8):
        return await self.frame(16, (cmd << 8) | data, sh, tail) & 0xFF

    async def wr(self, a, data, **kw):
        await self.xfer(0x80 | a, data, **kw)

    async def rd(self, a, **kw):
        return await self.xfer(a, 0, **kw)

    async def status(self):
        return await self.rd(A_ST)

    async def wait_idle(self):
        while int(self.dut.busy.value):
            await RisingEdge(self.dut.clk)
        await self.idle(6)

    async def onehot_during_pulse(self, sh=SH):
        """Fire with no tail, then catch the pulse's first prog_en cycle.

        The frame epilogue (4 cycles before CS_N rises, plus the tail) can
        outlast a short PULSE_WIDTH, so the FIRE frame is issued with tail=0
        and the one-hot outputs are sampled on the first prog_en cycle after
        the commit.
        """
        d = self.dut
        await self.xfer(0x80 | A_FIRE, 0, sh=sh, tail=0)
        for _ in range(64):
            await RisingEdge(d.clk)
            if int(d.prog_en.value):
                return int(d.row_onehot.value), int(d.col_onehot.value)
        raise AssertionError("no prog_en pulse within 64 cycles")

    def assert_clean(self):
        assert not self.violations, self.violations[:3]

    async def __aenter__(self):
        await self.reset()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.assert_clean()


async def arm_and_fire(b, row, col, pw, sh=SH):
    await b.wr(A_ROW, row, sh=sh)
    await b.wr(A_COL, col, sh=sh)
    await b.wr(A_PW, pw, sh=sh)
    await b.wr(A_CTRL, 1, sh=sh)
    await b.xfer(0x80 | A_FIRE, 0, sh=sh)


@cocotb.test()
async def reset_values_and_idle_outputs(dut):
    async with Bench(dut) as b:
        assert int(dut.row_sel.value) == 0 and int(dut.col_sel.value) == 0
        assert int(dut.prog_en.value) == 0 and int(dut.read_en.value) == 0
        assert int(dut.busy.value) == 0 and int(dut.miso_oe.value) == 0
        assert int(dut.miso.value) == 0
        assert int(dut.row_onehot.value) == 0 and int(dut.col_onehot.value) == 0
        assert await b.rd(A_ROW) == 0
        assert await b.rd(A_COL) == 0
        assert await b.rd(A_CTRL) == 0
        assert await b.rd(A_PW) == 0x01  # netlist default, not a request override
        assert await b.rd(A_RD) == 0
        assert await b.status() == 0


@cocotb.test()
async def miso_enable_follows_cs(dut):
    async with Bench(dut) as b:
        dut.cs_n.value = 0
        await b.idle(5)
        assert int(dut.miso_oe.value) == 1
        dut.cs_n.value = 1
        await b.idle(5)
        assert int(dut.miso_oe.value) == 0 and int(dut.miso.value) == 0


@cocotb.test()
async def row_col_pw_read_write(dut):
    async with Bench(dut) as b:
        for v in (0, 1, 17, 31):
            await b.wr(A_ROW, v)
            assert await b.rd(A_ROW) == v and int(dut.row_sel.value) == v
            await b.wr(A_COL, v)
            assert await b.rd(A_COL) == v and int(dut.col_sel.value) == v
        for v in (1, 2, 16, 255):
            await b.wr(A_PW, v)
            assert await b.rd(A_PW) == v
        assert await b.status() == 0  # no rejected frame so far


@cocotb.test()
async def onehot_idle_while_sel_changes(dut):
    """Decoder enable: no one-hot line while registers change but no pulse."""
    async with Bench(dut) as b:
        for v in (0, 5, 31, 7):
            await b.wr(A_ROW, v)
            await b.wr(A_COL, 31 - v)
            await b.idle(3)
            assert int(dut.row_onehot.value) == 0
            assert int(dut.col_onehot.value) == 0


@cocotb.test()
async def out_of_range_row_col_rejected(dut):
    async with Bench(dut) as b:
        await b.wr(A_ROW, 5)
        await b.wr(A_COL, 6)
        for a in (A_ROW, A_COL):
            for bad in (N, N + 1, 255):
                await b.wr(a, bad)
                assert await b.status() & ST_PERR, (a, bad)
        assert await b.rd(A_ROW) == 5 and await b.rd(A_COL) == 6
        assert int(dut.row_sel.value) == 5 and int(dut.col_sel.value) == 6
        await b.wr(A_PW, 0)  # zero pulse width is invalid
        assert await b.status() & ST_PERR
        assert await b.rd(A_PW) == 1


@cocotb.test()
async def ctrl_arm_disarm_and_reserved(dut):
    async with Bench(dut) as b:
        await b.wr(A_CTRL, 1)
        assert await b.rd(A_CTRL) == 1
        await b.wr(A_CTRL, 0)
        assert await b.rd(A_CTRL) == 0
        assert await b.status() == 0
        for bad in (0x08, 0x80, 0x02, 0x03, 0x05, 0x06, 0x07):
            await b.wr(A_CTRL, bad)
            assert await b.status() & ST_PERR, bad
            assert int(dut.prog_en.value) == 0
        assert await b.rd(A_CTRL) == 0  # a rejected write leaves the register unarmed
        assert b.prog_cycles == 0


@cocotb.test()
async def read_only_and_unknown_addresses(dut):
    async with Bench(dut) as b:
        for a in (A_ST, A_RD, 0x06, 0x7F):
            await b.wr(a, 0xFF)
            assert await b.status() & ST_PERR, a
        assert await b.status() == 0
        for a in (0x06, 0x40, A_FIRE):  # unknown-address read, FIRE is not readable
            assert await b.rd(a) == 0
            assert await b.status() & ST_PERR, a
        assert b.prog_cycles == 0


@cocotb.test()
async def status_read_clears_protocol_error(dut):
    async with Bench(dut) as b:
        await b.wr(A_ROW, N)
        assert await b.status() & ST_PERR
        assert await b.status() == 0


@cocotb.test()
async def program_full_sequence(dut):
    async with Bench(dut) as b:
        await b.wr(A_ROW, 9)
        await b.wr(A_COL, 21)
        await b.wr(A_PW, 5)
        await b.wr(A_CTRL, 1)
        roh, coh = await b.onehot_during_pulse()
        assert roh == (1 << 9) and coh == (1 << 21), (roh, coh)
        await b.wait_idle()
        assert b.prog_pulses == [5], b.prog_pulses
        assert int(dut.row_sel.value) == 9 and int(dut.col_sel.value) == 21
        st = await b.status()
        assert st & ST_DONE and not st & (ST_BUSY | ST_PERR), st
        assert await b.rd(A_CTRL) == 0  # arm drops after the pulse
        assert int(dut.row_onehot.value) == 0 and int(dut.col_onehot.value) == 0


@cocotb.test()
async def decoder_onehot_all_indices(dut):
    """Every row index and every column index selects exactly its own line."""
    async with Bench(dut) as b:
        await b.wr(A_PW, 2)
        for i in range(N):
            await b.wr(A_ROW, i)
            await b.wr(A_COL, 0)
            await b.wr(A_CTRL, 1)
            roh, coh = await b.onehot_during_pulse()
            assert roh == (1 << i) and coh == 1, (i, roh, coh)
            await b.wait_idle()
        for j in range(N):
            await b.wr(A_ROW, 0)
            await b.wr(A_COL, j)
            await b.wr(A_CTRL, 1)
            roh, coh = await b.onehot_during_pulse()
            assert roh == 1 and coh == (1 << j), (j, roh, coh)
            await b.wait_idle()
        assert len(b.prog_pulses) == 2 * N, b.prog_pulses


@cocotb.test()
async def pulse_width_cycle_counts(dut):
    async with Bench(dut) as b:
        widths = (1, 2, 3, 16, 255)
        for w in widths:
            await arm_and_fire(b, 1, 2, w)
            await b.wait_idle()
        assert b.prog_pulses == list(widths), b.prog_pulses


@cocotb.test()
async def read_settle_cycle_count_and_data(dut):
    async with Bench(dut) as b:
        for sense in (1, 0):
            dut.sense_in.value = sense
            await b.wr(A_CTRL, 4)
            for _ in range(64):
                await RisingEdge(dut.clk)
                if int(dut.read_en.value):
                    assert int(dut.row_onehot.value) == 1  # row 0, col 0 after reset
                    assert int(dut.col_onehot.value) == 1
                    break
            await b.wait_idle()
            st = await b.status()
            assert st & ST_VALID and not st & ST_BUSY, st
            assert await b.rd(A_RD) == sense
        assert b.read_pulses == [READ_SETTLE] * 2, b.read_pulses
        assert b.prog_cycles == 0


@cocotb.test()
async def read_while_armed_rejected(dut):
    async with Bench(dut) as b:
        await b.wr(A_CTRL, 1)
        await b.wr(A_CTRL, 4)
        assert await b.status() & ST_PERR
        assert b.read_pulses == [] and int(dut.read_en.value) == 0


@cocotb.test()
async def fire_unarmed_rejected(dut):
    async with Bench(dut) as b:
        await b.xfer(0x80 | A_FIRE, 0)
        await b.idle(40)
        assert b.prog_cycles == 0 and int(dut.prog_en.value) == 0
        assert await b.status() & ST_PERR
        # a FIRE after a CTRL disarm is the same case
        await b.wr(A_CTRL, 1)
        await b.wr(A_CTRL, 0)
        await b.xfer(0x80 | A_FIRE, 0)
        await b.idle(40)
        assert b.prog_cycles == 0
        assert await b.status() & ST_PERR


@cocotb.test()
async def fire_with_other_command_bytes_never_pulses(dut):
    async with Bench(dut) as b:
        await b.wr(A_CTRL, 1)
        for cmd in (0xF9, 0xFA, 0xF0, 0x78, 0xF8 ^ 0x01, 0xF8 ^ 0x80, 0x82):
            await b.xfer(cmd, 0x00)
            await b.idle(20)
            assert b.prog_cycles == 0, hex(cmd)
            await b.wr(A_CTRL, 1)  # re-arm after the error drops it


@cocotb.test()
async def fire_while_busy_rejected(dut):
    async with Bench(dut) as b:
        await b.wr(A_PW, 255)
        await b.wr(A_CTRL, 1)
        await b.xfer(0x80 | A_FIRE, 0)
        assert int(dut.busy.value) == 1
        await b.xfer(0x80 | A_FIRE, 0, sh=4, tail=2)  # re-FIRE inside the pulse
        await b.wait_idle()
        assert b.prog_pulses == [255], b.prog_pulses
        assert await b.status() & ST_PERR
        # writes are rejected while busy too
        await b.wr(A_CTRL, 1)
        await b.xfer(0x80 | A_FIRE, 0)
        await b.wr(A_ROW, 7, sh=4, tail=2)
        await b.wait_idle()
        assert await b.rd(A_ROW) == 0


@cocotb.test()
async def bad_frame_length_sets_protocol_error(dut):
    async with Bench(dut) as b:
        await b.wr(A_ROW, 3)
        for nbits in (1, 7, 8, 12, 15, 17, 18, 24):
            await b.frame(nbits, (0x80 | A_ROW) << (nbits - 8) if nbits >= 8 else 1)
            assert await b.status() & ST_PERR, nbits
        # a frame with no SCLK edges at all is not an error and changes nothing
        await b.frame(0, 0)
        assert await b.status() == 0
        assert await b.rd(A_ROW) == 3


@cocotb.test()
async def truncated_and_overlong_writes_do_not_commit(dut):
    async with Bench(dut) as b:
        await b.wr(A_ROW, 3)
        await b.frame(15, ((0x80 | A_ROW) << 7) | 0x09)  # 15 bits: data would be 0x04.. shifted
        await b.status()
        await b.frame(17, ((0x80 | A_ROW) << 9) | (0x09 << 1))
        await b.status()
        assert await b.rd(A_ROW) == 3 and int(dut.row_sel.value) == 3


@cocotb.test()
async def overlong_fire_frame_never_pulses(dut):
    async with Bench(dut) as b:
        await b.wr(A_CTRL, 1)
        await b.frame(17, (0x80 | A_FIRE) << 9)
        await b.idle(20)
        assert b.prog_cycles == 0
        assert await b.status() & ST_PERR
        await b.wr(A_CTRL, 1)
        await b.frame(15, (0x80 | A_FIRE) << 7)
        await b.idle(20)
        assert b.prog_cycles == 0


@cocotb.test()
async def arm_timeout_expires(dut):
    """Netlist ARM_TIMEOUT is 4096 (baked in), not the RTL request's 300."""
    async with Bench(dut) as b:
        await b.wr(A_CTRL, 1)
        await b.idle(ARM_TIMEOUT + 40)
        assert await b.rd(A_CTRL) == 0  # a timeout is not a protocol error
        assert await b.status() == 0
        await b.xfer(0x80 | A_FIRE, 0)
        await b.idle(40)
        assert b.prog_cycles == 0
        assert await b.status() & ST_PERR


@cocotb.test()
async def arm_timeout_boundary(dut):
    """FIRE commit one cycle inside the window pulses; one cycle past does not.

    Frames run at sh=4 (the contract minimum) so the sweep stays inside the
    SPI contract on the gate-level netlist.
    """
    async with Bench(dut) as b:
        await b.wr(A_PW, 1)
        results = {}
        fast = 4
        # frame length in clk cycles is fixed for a given sh; measure it once
        start = b.cycle
        await b.xfer(0x80 | A_CTRL, 0, sh=fast, tail=0)
        frame_len = b.cycle - start
        await b.idle(8)
        for gap in range(ARM_TIMEOUT - frame_len - 8, ARM_TIMEOUT - frame_len + 9):
            before = len(b.prog_pulses)
            await b.wr(A_CTRL, 1, sh=fast, tail=0)
            await b.idle(gap)
            await b.xfer(0x80 | A_FIRE, 0, sh=fast, tail=0)
            await b.idle(12)
            await b.wait_idle()
            fired = len(b.prog_pulses) > before
            results[gap] = fired
            await b.wr(A_CTRL, 0, sh=fast, tail=8)
            await b.status()
        seq = [results[g] for g in sorted(results)]
        dut._log.info("boundary sweep: %s", results)
        # sharp, monotonic boundary: some early gaps fire, some late ones do not
        assert seq[0] and not seq[-1], dict(results)
        assert seq == sorted(seq, reverse=True), results
