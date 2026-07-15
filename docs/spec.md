# `stream_chunker` — Functional Specification

## 1. Overview

`stream_chunker` segments a byte stream of packets into fragments of at
most `MAX_PAYLOAD` payload beats and inserts a one-byte trailer after each
fragment. Payload beats pass through combinationally (zero latency); each
trailer occupies exactly one extra output beat. Single clock domain;
synchronous, active-high reset.

## 2. Interface

| Port        | Dir | Type            | Description                                   |
|-------------|-----|-----------------|-----------------------------------------------|
| `clk`       | in  | `logic`         | Clock.                                        |
| `rst`       | in  | `logic`         | Synchronous, active-high reset.               |
| `in_valid`  | in  | `logic`         | Input beat available.                         |
| `in_ready`  | out | `logic`         | Module accepts an input beat this cycle.      |
| `in_data`   | in  | `logic [7:0]`   | Input payload byte.                           |
| `in_last`   | in  | `logic`         | This beat is the last byte of its packet.     |
| `out_valid` | out | `logic`         | Output beat available.                        |
| `out_ready` | in  | `logic`         | Downstream accepts an output beat this cycle. |
| `out_data`  | out | `logic [7:0]`   | Output byte (payload or trailer).             |
| `out_last`  | out | `logic`         | This output beat is a trailer byte.           |

Parameter: `MAX_PAYLOAD` (`int`, ≥ 2) — maximum payload beats per fragment.
Grading uses the default value, 4.

## 3. Stream rules

Both interfaces use a valid/ready handshake: a beat transfers ("is
accepted") on a rising clock edge where valid and ready are both 1.

**Upstream contract (guaranteed by the testbench):** once `in_valid` is
asserted, `in_valid` stays high and `in_data`/`in_last` hold stable until
the beat is accepted. `in_last` is meaningful only while `in_valid` is 1.

**Module obligations:**

- `in_ready` shall be 1 exactly when all of the following hold: `rst` is 0,
  the module is in the **payload phase**, and `out_ready` is 1. In
  particular, `in_ready` must be 0 for the entire trailer phase, and must
  combinationally track `out_ready` during the payload phase. The module
  performs no internal buffering.
- **Payload phase:** the module forwards the input beat combinationally in
  the same cycle — `out_valid` equals `in_valid` and `out_data` equals
  `in_data`. `out_last` is 0 on payload beats.
- **Trailer phase:** `out_valid` is 1 (regardless of `in_valid`),
  `out_data` carries the trailer byte (§5), and `out_last` is 1. The
  trailer byte and `out_valid` hold stable until the trailer is accepted.
- While `rst` is 1, `in_ready` and `out_valid` shall both be 0.

## 4. Fragmentation

The module comes out of reset in the payload phase. Payload beats are
accepted only in the payload phase (per the `in_ready` rule). A fragment
**closes** on the acceptance of a payload beat for which either — or both —
of the following hold:

- the beat carries `in_last = 1`;
- the beat is the `MAX_PAYLOAD`-th accepted payload beat of the current
  fragment.

On the cycle after the closing beat, the module is in the trailer phase and
presents the trailer. After the trailer is accepted, the module returns to
the payload phase.

**Exact-multiple case:** when `in_last` arrives exactly on the
`MAX_PAYLOAD`-th beat, both close conditions coincide. The fragment closes
once, is final (`F = 1` in §5), and exactly **one** trailer is emitted. No
empty fragment or additional trailer follows.

Fragments therefore carry between 1 and `MAX_PAYLOAD` payload bytes. A
1-byte packet produces a 1-byte fragment plus its trailer.

## 5. Trailer

The trailer byte is:

```
trailer = csum XOR (F ? 8'hA5 : 8'h5A)
```

where

- `csum` is the XOR of all payload bytes of **this fragment**, including
  the closing byte, and
- `F` (is-final) is 1 iff the fragment's closing beat carried
  `in_last = 1`.

## 6. Per-fragment state lifecycle

The checksum and payload-beat counter update on each accepted payload beat
and are cleared **after the trailer is accepted** — i.e., on the return to
the payload phase. They are not cleared upon entering the trailer phase,
and not while an unaccepted trailer is stalled by `out_ready`. Cycles where
`in_valid` is low in the middle of a fragment do not disturb them.

## 7. Reset

`rst` is synchronous, active-high, and overrides everything. On a rising
edge with `rst = 1`, the module returns to the payload phase and clears the
checksum, counter, and is-final state. A fragment in progress is abandoned:
**no trailer is emitted for it.** Output gating during reset is specified
in §3.

## 8. Worked example

`MAX_PAYLOAD = 4`. One 5-byte packet `0x10 0x20 0x30 0x40 0x50`;
`out_ready` stalls in cycles 3 and 6. Phase shown is the phase during the
cycle. First-fragment checksum: `0x10^0x20^0x30^0x40 = 0x40`, so its
trailer is `0x40 ^ 0x5A = 0x1A`. Second fragment: `csum = 0x50`, trailer
`0x50 ^ 0xA5 = 0xF5`.

| cyc | in_valid | in_data | in_last | out_ready | phase | in_ready | out_valid | out_data | out_last | transfer |
|-----|----------|---------|---------|-----------|-------|----------|-----------|----------|----------|----------|
| 1   | 1        | 10     | 0       | 1         | PAY   | 1        | 1         | 10       | 0        | beat 1 accepted |
| 2   | 1        | 20     | 0       | 1         | PAY   | 1        | 1         | 20       | 0        | beat 2 accepted |
| 3   | 1        | 30     | 0       | 0         | PAY   | 0        | 1         | 30       | 0        | stalled |
| 4   | 1        | 30     | 0       | 1         | PAY   | 1        | 1         | 30       | 0        | beat 3 accepted |
| 5   | 1        | 40     | 0       | 1         | PAY   | 1        | 1         | 40       | 0        | beat 4 accepted; fragment closes (MAX) |
| 6   | 1        | 50     | 1       | 0         | TRL   | 0        | 1         | 1A       | 1        | trailer stalled |
| 7   | 1        | 50     | 1       | 1         | TRL   | 0        | 1         | 1A       | 1        | trailer accepted |
| 8   | 1        | 50     | 1       | 1         | PAY   | 1        | 1         | 50       | 0        | beat accepted; closes (`in_last`) |
| 9   | 0        | —      | —       | 1         | TRL   | 0        | 1         | F5       | 1        | final trailer accepted |

## 9. Implementation constraints

- Synthesizable SystemVerilog, compatible with Icarus Verilog (`-g2012`).
- No SystemVerilog Assertions (SVA).
- Do not change the module name, parameter name/default, port names,
  directions, or widths.
- Single clock domain. No latches.
