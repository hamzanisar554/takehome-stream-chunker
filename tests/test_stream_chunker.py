"""
Hidden grading testbench for stream_chunker (MAX_PAYLOAD = 4).

Grading contract: the DUT must match a cycle-accurate Mealy reference model
on in_ready / out_valid every cycle, and on out_data / out_last whenever
out_valid is expected high. Accepted output beats are additionally
cross-checked against an independently computed expected byte stream
(second oracle). All expectations come from the models -- no magic numbers.

Failure-mode map (FM-x tags refer to the difficulty analysis):
  FM-1  buffered/registered datapath breaks zero-latency passthrough -> Mealy
        comb check on out_valid/out_data every payload beat
  FM-2  in_ready not deasserted during the trailer (or not tracking
        out_ready) -> in_ready checked every cycle; beat-loss shows in the
        stream oracle
  FM-3  in_last coincident with MAX-th beat: two trailers emitted, or wrong
        is_final -> directed len-4 / len-8 packets
  FM-4  trailer seed swapped (A5/5A) or applied to the wrong beat -> every
        trailer beat's out_data check
  FM-5  out_last on the wrong beat (final payload beat, or the length beat)
        -> every out_last check
  FM-6  fragment counter off-by-one (closes after MAX-1 or MAX+1 beats, or
        length beat off by one) -> directed len-3/4/5 packets + length checks
  FM-7  trailer beat duplicated, dropped, or skipped when out_ready stalls
        on either trailer beat -> directed stall storms + randomized
        backpressure
  FM-8  per-fragment state (crc/cnt/fin) cleared on entering the trailer,
        after the length beat, or never -> back-to-back packets; trailer
        value corruption
  FM-9  reset gating wrong (in_ready/out_valid high during rst) or stale
        crc after mid-fragment reset -> mid_stream_reset test
  FM-9b reset during the trailer phase (on a stalled length beat, or between
        the length and check beats): remaining trailer beats must be
        abandoned and out_valid rst-gated -> mid_stream_reset
  FM-9c rst coincident with a presented input beat: the beat must not be
        accepted or accumulated ("rst overrides everything") -> mid_stream_reset
  FM-10 CRC-8 convention wrong (reflected/LSB-first processing, init 0xFF,
        xor-in misplaced, wrong polynomial) -> every check beat's out_data
        compare against the model CRC
  FM-11 length beat wrong (payload count off by one, missing, or replaced
        by the checksum) -> every length beat's out_data compare
"""

import random
from pathlib import Path

import cocotb
from cocotb.triggers import RisingEdge, FallingEdge, Timer

SEED   = 0x0B0BA5
CLK_NS = 10
MAXP   = 4


def crc8(data, crc=0x00):
    """CRC-8, poly 0x07, init 0x00, MSB-first, no reflection, no final XOR."""
    for b in data:
        crc ^= b & 0xFF
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if (crc & 0x80) else (crc << 1) & 0xFF
    return crc


class ChunkModel:
    """Cycle-accurate Mealy mirror of the spec (independent reference)."""

    PH_PAY, PH_LEN, PH_CHK = 0, 1, 2

    def __init__(self, maxp=MAXP):
        self.maxp = maxp
        self.reset()

    def reset(self):
        self.phase = self.PH_PAY
        self.crc = 0
        self.cnt = 0
        self.fin = 0

    def check_byte(self):
        return self.crc ^ (0xA5 if self.fin else 0x5A)

    def comb(self, rst, in_valid, in_data, in_last, out_ready):
        """Expected combinational outputs for this cycle's inputs."""
        if rst:
            return {"in_ready": 0, "out_valid": 0,
                    "out_data": None, "out_last": None}
        if self.phase == self.PH_PAY:
            return {"in_ready": 1 if out_ready else 0,
                    "out_valid": 1 if in_valid else 0,
                    "out_data": in_data, "out_last": 0}
        if self.phase == self.PH_LEN:
            return {"in_ready": 0, "out_valid": 1,
                    "out_data": self.cnt, "out_last": 0}
        return {"in_ready": 0, "out_valid": 1,
                "out_data": self.check_byte(), "out_last": 1}

    def edge(self, rst, in_valid, in_data, in_last, out_ready):
        """State update at the clock edge ending this cycle."""
        if rst:
            self.reset()
            return
        pay_acc = (self.phase == self.PH_PAY) and in_valid and out_ready
        close   = pay_acc and (in_last or self.cnt == self.maxp - 1)
        len_acc = (self.phase == self.PH_LEN) and out_ready
        chk_acc = (self.phase == self.PH_CHK) and out_ready
        if pay_acc:
            self.crc = crc8([in_data], self.crc)
            self.cnt += 1
        if close:
            self.phase = self.PH_LEN
            self.fin = 1 if in_last else 0
        elif len_acc:
            self.phase = self.PH_CHK
        elif chk_acc:
            self.phase = self.PH_PAY
            self.crc = 0
            self.cnt = 0
            self.fin = 0


def expected_stream(packets, maxp=MAXP):
    """Independent oracle: the full expected (data, last) output sequence."""
    out = []
    for pkt in packets:
        i = 0
        while i < len(pkt):
            chunk = pkt[i:i + maxp]
            i += len(chunk)
            fin = (i == len(pkt))
            out += [(byte, 0) for byte in chunk]
            out.append((len(chunk), 0))
            out.append((crc8(chunk) ^ (0xA5 if fin else 0x5A), 1))
    return out


async def clock_gen(clk):
    while True:
        clk.value = 0
        await Timer(CLK_NS // 2, "ns")
        clk.value = 1
        await Timer(CLK_NS // 2, "ns")


class Bench:
    def __init__(self, dut):
        self.dut = dut
        self.m = ChunkModel()
        self.n = 0
        self.collected = []   # accepted output beats as (data, last)

    async def reset(self, cycles=3):
        d = self.dut
        d.rst.value = 1
        d.in_valid.value = 0
        d.in_data.value = 0
        d.in_last.value = 0
        d.out_ready.value = 0
        for _ in range(cycles):
            await RisingEdge(d.clk)
        d.rst.value = 0
        self.m.reset()
        # NOTE: every cycle() call must begin just after a rising edge; this
        # method returns in exactly that alignment.

    async def cycle(self, in_valid=0, in_data=0, in_last=0, out_ready=0,
                    rst=0, note=""):
        """Drive one cycle's inputs just after the rising edge, check the
        combinational outputs mid-cycle, step the model at the next edge.
        Returns True iff the input beat was accepted this cycle."""
        d, m = self.dut, self.m
        d.rst.value = rst
        d.in_valid.value = in_valid
        d.in_data.value = in_data
        d.in_last.value = in_last
        d.out_ready.value = out_ready
        await FallingEdge(d.clk)
        exp = m.comb(rst, in_valid, in_data, in_last, out_ready)
        self.n += 1
        c = self.n
        got_ir = int(d.in_ready.value)
        got_ov = int(d.out_valid.value)
        assert got_ir == exp["in_ready"], \
            f"[cyc {c}] {note} in_ready mismatch: exp {exp['in_ready']} got {got_ir}"
        assert got_ov == exp["out_valid"], \
            f"[cyc {c}] {note} out_valid mismatch: exp {exp['out_valid']} got {got_ov}"
        if exp["out_valid"]:
            got_od = int(d.out_data.value)
            got_ol = int(d.out_last.value)
            assert got_od == exp["out_data"], \
                f"[cyc {c}] {note} out_data mismatch: exp 0x{exp['out_data']:02X} got 0x{got_od:02X}"
            assert got_ol == exp["out_last"], \
                f"[cyc {c}] {note} out_last mismatch: exp {exp['out_last']} got {got_ol}"
            if out_ready:
                self.collected.append((exp["out_data"], exp["out_last"]))
        accepted = (not rst) and exp["in_ready"] == 1 and in_valid == 1
        await RisingEdge(d.clk)
        m.edge(rst, in_valid, in_data, in_last, out_ready)
        return accepted


async def send_packets(bench, packets, rnd=None, gap_p=0.0, ready_p=1.0,
                       ready_seq=None, note=""):
    """Drive packets through the DUT.

    Upstream contract: once in_valid is asserted, the beat is held unchanged
    until accepted. Gaps (in_valid low) may be inserted only between beats.
    out_ready follows ready_seq if given, else Bernoulli(ready_p) via rnd,
    else constant 1.
    """
    beats = []
    for pkt in packets:
        for i, byte in enumerate(pkt):
            beats.append((byte, 1 if i == len(pkt) - 1 else 0))
    idx = 0
    asserting = False
    rd_i = 0

    def next_ready():
        nonlocal rd_i
        if ready_seq is not None:
            v = ready_seq[min(rd_i, len(ready_seq) - 1)]
            rd_i += 1
            return v
        if rnd is None:
            return 1
        return 1 if rnd.random() < ready_p else 0

    guard = 0
    while idx < len(beats) or bench.m.phase != ChunkModel.PH_PAY:
        guard += 1
        assert guard < 20000, "TB guard: stream did not drain"
        if idx < len(beats) and not asserting:
            if rnd is None or rnd.random() >= gap_p:
                asserting = True
        iv = 1 if (asserting and idx < len(beats)) else 0
        data, last = beats[idx] if iv else (0, 0)
        acc = await bench.cycle(in_valid=iv, in_data=data, in_last=last,
                                out_ready=next_ready(), note=note)
        if acc:
            idx += 1
            asserting = False
    for _ in range(2):
        await bench.cycle(out_ready=1, note=note + "/drain")


@cocotb.test()
async def directed_corners(dut):
    """Directed sequences that isolate each specified corner (FM-1 .. FM-11)."""
    cocotb.start_soon(clock_gen(dut.clk))
    b = Bench(dut)
    await b.reset()

    sent = []

    async def send(pkts, **kw):
        sent.extend(pkts)
        await send_packets(b, pkts, **kw)

    # FM-3 / FM-6: in_last exactly on the MAX-th beat -> ONE final trailer.
    await send([[0x11, 0x22, 0x33, 0x44]], note="len4-exact")
    # Minimum fragment: single-beat packet (length beat must read 1).
    await send([[0x99]], note="len1")
    # len 5 = full non-final chunk + 1-byte final chunk (FM-6 boundary).
    await send([[1, 2, 3, 4, 5]], note="len5")
    # len 8 = two exact chunks; second closes via last AND max together.
    await send([[7, 7, 7, 7, 9, 9, 9, 9]], note="len8")
    # Assorted lengths: 3 (below max), 9, 12 (exact multiple x3).
    await send([[5, 6, 7], list(range(9)), list(range(40, 52))], note="mixed")
    # Back-to-back packets, zero gap (FM-8: state must clear between).
    await send([[0xAA, 0xBB], [0xCC]], note="b2b")
    # FM-7: out_ready stall storm across the LENGTH beat of a len-2 packet.
    await send([[0xDE, 0xAD]], ready_seq=[1, 1, 0, 0, 0, 1, 1],
               note="len-beat-stall")
    # FM-7: stall landing on the CHECK beat (length beat accepted first).
    await send([[0x5E]], ready_seq=[1, 1, 0, 0, 1],
               note="chk-beat-stall")
    # FM-2: next packet already waiting while the trailer goes out; in_ready
    # must stay low for BOTH trailer beats.
    await send([[0x10, 0x20, 0x30, 0x40, 0x50], [0x60]], note="hold")

    # in_valid gaps mid-fragment: crc/count must persist across idles.
    await b.cycle(in_valid=1, in_data=0x0F, in_last=0, out_ready=1, note="gap p0")
    await b.cycle(out_ready=1, note="gap idle1")
    await b.cycle(out_ready=1, note="gap idle2")
    await b.cycle(in_valid=1, in_data=0xF0, in_last=1, out_ready=1, note="gap p1")
    await b.cycle(out_ready=1, note="gap len beat")
    await b.cycle(out_ready=1, note="gap chk beat")
    await b.cycle(out_ready=1, note="gap drain")
    sent.append([0x0F, 0xF0])

    # Second oracle: the accepted output stream must match exactly.
    assert b.collected == expected_stream(sent), \
        "accepted output stream diverged from the expected-stream oracle"


@cocotb.test()
async def mid_stream_reset(dut):
    """FM-9: reset mid-fragment aborts it with no trailer; crc/cnt/fin must
    clear (stale-CRC detector), and in_ready/out_valid must be low while rst
    is asserted. Also covers reset landing in the trailer phase (FM-9b: on a
    stalled length beat, and between the length and check beats) and rst
    coincident with a presented input beat (FM-9c)."""
    cocotb.start_soon(clock_gen(dut.clk))
    b = Bench(dut)
    await b.reset()

    # Start (but do not finish) a fragment.
    await b.cycle(in_valid=1, in_data=0x5C, in_last=0, out_ready=1, note="pre-rst b0")
    await b.cycle(in_valid=1, in_data=0xA3, in_last=0, out_ready=1, note="pre-rst b1")
    # Synchronous reset; out_ready high on purpose (gating check).
    await b.cycle(rst=1, out_ready=1, note="rst0")
    await b.cycle(rst=1, note="rst1")
    b.collected.clear()
    # Fresh packet: a stale CRC (over 0x5C,0xA3) would corrupt this trailer.
    await send_packets(b, [[0x01, 0x02, 0x03]], note="post-rst")
    assert b.collected == expected_stream([[0x01, 0x02, 0x03]]), \
        "output stream after mid-fragment reset diverged (stale state?)"

    # --- FM-9b: reset landing on a STALLED length beat, with an input beat
    # --- presented and out_ready high during rst. out_valid must be 0 while
    # --- rst is 1 even though a trailer is pending, and no trailer beat of
    # --- the abandoned fragment may ever be emitted.
    await b.cycle(in_valid=1, in_data=0x77, in_last=1, out_ready=1,
                  note="trl-rst close")
    await b.cycle(out_ready=0, note="trl-rst len stalled")
    await b.cycle(rst=1, in_valid=1, in_data=0x88, in_last=0, out_ready=1,
                  note="trl-rst rst0")
    await b.cycle(rst=1, in_valid=1, in_data=0x88, in_last=0, out_ready=1,
                  note="trl-rst rst1")
    b.collected.clear()
    await send_packets(b, [[0x88, 0x99]], note="post-trl-rst")
    assert b.collected == expected_stream([[0x88, 0x99]]), \
        "output stream after trailer-phase reset diverged (trailer not abandoned?)"

    # --- FM-9b: reset BETWEEN the length beat and the check beat. The check
    # --- beat of the abandoned fragment must never appear.
    await b.cycle(in_valid=1, in_data=0x21, in_last=1, out_ready=1,
                  note="mid-trl close")
    await b.cycle(out_ready=1, note="mid-trl len accepted")
    await b.cycle(rst=1, out_ready=1, note="mid-trl rst")
    b.collected.clear()
    await send_packets(b, [[0x44]], note="post-mid-trl-rst")
    assert b.collected == expected_stream([[0x44]]), \
        "output stream after between-beats reset diverged (check beat leaked?)"

    # --- FM-9c: rst coincident with a presented payload beat (in_valid=1,
    # --- out_ready=1). The beat must not be accepted or accumulated.
    await b.cycle(in_valid=1, in_data=0x3C, in_last=0, out_ready=1,
                  note="pay-rst b0")
    await b.cycle(rst=1, in_valid=1, in_data=0x5A, in_last=0, out_ready=1,
                  note="pay-rst rst")
    b.collected.clear()
    await send_packets(b, [[0x01]], note="post-pay-rst")
    assert b.collected == expected_stream([[0x01]]), \
        "output stream after same-cycle rst+in_valid diverged (beat accepted during rst?)"


@cocotb.test()
async def randomized_stress(dut):
    """Fixed-seed random packets, gaps and backpressure. Catches FM-1/2/7/8
    interactions that only appear under irregular handshake timing."""
    cocotb.start_soon(clock_gen(dut.clk))
    b = Bench(dut)
    await b.reset()
    rnd = random.Random(SEED)
    lens = [1, 2, 3, 4, 4, 4, 5, 6, 7, 8, 8, 9, 10]
    packets = [[rnd.randint(0, 255) for _ in range(rnd.choice(lens))]
               for _ in range(40)]
    await send_packets(b, packets, rnd=rnd, gap_p=0.30, ready_p=0.70,
                       note="rand")
    assert b.collected == expected_stream(packets), \
        "randomized output stream diverged from the expected-stream oracle"


def test_stream_chunker_runner():
    """pytest entry point: build sources/stream_chunker.sv under Icarus and
    run this cocotb module against it."""
    try:
        from cocotb_tools.runner import get_runner   # cocotb >= 2.0
    except ImportError:                              # cocotb 1.9.x fallback
        from cocotb.runner import get_runner
    proj = Path(__file__).resolve().parent.parent
    runner = get_runner("icarus")
    runner.build(
        sources=[proj / "sources" / "stream_chunker.sv"],
        hdl_toplevel="stream_chunker",
        build_args=["-g2012"],
        build_dir=str(proj / "sim_build"),
        always=True,
    )
    runner.test(
        hdl_toplevel="stream_chunker",
        test_module="test_stream_chunker",
        test_dir=str(Path(__file__).resolve().parent),
    )
