# `stream_chunker` — Functional Specification

## 1. Overview

`stream_chunker` segments a byte stream of packets into fragments of at
most `MAX_PAYLOAD` payload beats and appends a trailer after each fragment.
Single clock domain; synchronous, active-high reset.

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
| `out_last`  | out | `logic`         | Final beat of the current fragment's trailer. |

Parameter: `MAX_PAYLOAD` (`int`, ≥ 2) — maximum payload beats per fragment.

## 3. Stream rules

Both interfaces use a valid/ready handshake: a beat transfers ("is
accepted") on a rising clock edge where valid and ready are both 1.

**Upstream contract (guaranteed by the testbench):** once `in_valid` is
asserted, `in_valid` stays high and `in_data`/`in_last` hold stable until
the beat is accepted. `in_last` is meaningful only while `in_valid` is 1.

**Module obligations:**

- The module performs no internal buffering. A payload beat is forwarded
  combinationally in the same cycle it is presented — during the payload
  phase, `out_valid` equals `in_valid` and `out_data` equals `in_data` —
  and consequently a payload beat can be accepted only in a cycle where
  the downstream can take it in that same cycle.
- `in_ready` shall be 1 in exactly those cycles where a payload beat would
  be accepted if one were presented (§4 governs which cycles those are).
- **Trailer phase:** `out_valid` is 1 and `out_data` carries the current
  trailer beat (§5). Each trailer beat and `out_valid` hold stable until
  that beat is accepted.

## 4. Fragmentation

The module comes out of reset in the payload phase. Payload beats are
accepted only in the payload phase. A fragment **closes** on the
acceptance of a payload beat for which either — or both — of the following
hold:

- the beat carries `in_last = 1`;
- the beat is the `MAX_PAYLOAD`-th accepted payload beat of the current
  fragment.

On the cycle after the closing beat, the module is in the trailer phase and
presents the first trailer beat. After the trailer's check beat is
accepted, the module returns to the payload phase.

## 5. Trailer

Each fragment is followed by a trailer of two beats.

The **length beat** is presented first. Its `out_data` is the number of
payload beats belonging to this fragment, encoded as an unsigned 8-bit
integer. `out_last` is 0.

The **check beat** is presented next. Let `L` be the length-beat value.
Let `F` be 1 iff the fragment's closing beat carried `in_last = 1`. Let
`R` be the residue defined below, taken over the fragment's payload
bytes **followed by** the octet `L`. The check beat's `out_data` is `R`
combined by bitwise XOR with the trailer seed: `8'hA5` when `F` is 1,
otherwise `8'h5A`. `out_last` is 1.

**Residue.** Treat the octets that enter the residue — the payload bytes
in acceptance order, then `L` — as the coefficient sequence of a
polynomial `M(x)` over GF(2), most significant bit first, the first
octet's most significant bit being the highest-order coefficient. `R`
is the byte whose bits, most significant first, are the coefficients of
the degree-7…0 terms of the remainder of `x^8 · M(x)` divided by
`G(x) = x^8 + x^2 + x + 1` over GF(2).

## 6. Per-fragment state lifecycle

The payload-beat counter updates on each accepted payload beat. The
residue is that of §5 for the current fragment. After the check beat is
accepted, the residue, the counter, and `F` are cleared.

## 7. Reset

`rst` is synchronous, active-high, and overrides everything: while it
is asserted, `in_ready` and `out_valid` are 0, and no beat is accepted
on either interface. On a rising edge with `rst = 1`, the module returns
to the payload phase and clears the residue, counter, and `F`. A fragment
in progress is abandoned: no further trailer beats are emitted for it.

## 8. Implementation constraints

- Synthesizable SystemVerilog, compatible with Icarus Verilog (`-g2012`).
- No SystemVerilog Assertions (SVA).
- Do not change the module name, parameter name/default, port names,
  directions, or widths.
- Single clock domain. No latches.
