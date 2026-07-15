# `stream_chunker` — Functional Specification

## 1. Overview

`stream_chunker` segments a byte stream of packets into fragments of at
most `MAX_PAYLOAD` payload beats and inserts a two-beat trailer after each
fragment. Payload beats pass through combinationally (zero latency); each
trailer occupies exactly two extra output beats. Single clock domain;
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
| `out_last`  | out | `logic`         | This output beat is the final beat of its fragment's trailer. |

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
  the module is in the **payload phase**, and `out_ready` is 1.
- **Payload phase:** the module forwards the input beat combinationally in
  the same cycle — `out_valid` equals `in_valid` and `out_data` equals
  `in_data`. `out_last` is 0 on payload beats.
- **Trailer phase:** `out_valid` is 1 (regardless of `in_valid`) and
  `out_data` carries the current trailer beat (§5). The two trailer beats
  are emitted in §5's order; each trailer beat and `out_valid` hold stable
  until that beat is accepted. `out_last` is 1 on the check beat and 0 on
  the length beat.
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
presents the first trailer beat. After the trailer's check beat is
accepted, the module returns to the payload phase.

## 5. Trailer

Each fragment is followed by a two-beat trailer, emitted in this order:

1. **Length beat:** `out_data` carries the number of payload beats of this
   fragment, as an unsigned 8-bit value (1 … `MAX_PAYLOAD`). `out_last`
   is 0.
2. **Check beat:** `out_data` carries `crc XOR (F ? 8'hA5 : 8'h5A)`, and
   `out_last` is 1.

where

- `F` (is-final) is 1 iff the fragment's closing beat carried
  `in_last = 1`, and
- `crc` is the CRC-8 of all payload bytes of **this fragment**, including
  the closing byte, defined below.

**CRC-8.** Polynomial `x^8 + x^2 + x + 1` (`8'h07`), initial value
`8'h00`, most-significant-bit-first, no input or output reflection, no
final XOR. The CRC register starts at `8'h00` for each fragment and
consumes the fragment's payload bytes in acceptance order. Each payload
byte `b` updates the 8-bit register `crc` as follows:

- `crc = crc XOR b`; then
- eight times: if bit 7 of `crc` is 1, `crc = (crc << 1) XOR 8'h07`,
  otherwise `crc = crc << 1` (shifts are 8-bit; the shifted-out bit is
  discarded).

## 6. Per-fragment state lifecycle

The CRC register and payload-beat counter update on each accepted payload
beat and are cleared **after the trailer's check beat is accepted** — i.e.,
on the return to the payload phase.

## 7. Reset

`rst` is synchronous, active-high, and overrides everything. On a rising
edge with `rst = 1`, the module returns to the payload phase and clears the
CRC register, counter, and is-final state. A fragment in progress is
abandoned: **no further trailer beats are emitted for it.** Output gating
during reset is specified in §3.

## 8. Implementation constraints

- Synthesizable SystemVerilog, compatible with Icarus Verilog (`-g2012`).
- No SystemVerilog Assertions (SVA).
- Do not change the module name, parameter name/default, port names,
  directions, or widths.
- Single clock domain. No latches.
