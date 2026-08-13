# `stream_chunker` — Functional Specification

## 1. Purpose

This module is a single-clock cut-and-tag adapter. Packets arrive as a
byte stream. The adapter slices each packet into pieces no longer than
`MAX_PAYLOAD` bytes, forwards every payload byte with no extra cycle of
delay, and after each piece emits a two-byte tag that a downstream
parser can use to recover piece length and an integrity check.

Reset is synchronous and active-high.

## 2. Ports

Do not rename, resize, or reverse any port. Do not rename the module or
the parameter.

| Name        | Dir | Width     | Role |
|-------------|-----|-----------|------|
| `clk`       | in  | 1         | Rising-edge clock. |
| `rst`       | in  | 1         | Synchronous reset, active high. |
| `in_valid`  | in  | 1         | Upstream is offering a byte. |
| `in_ready`  | out | 1         | This module consumes that byte this cycle. |
| `in_data`   | in  | 8         | Offered payload byte. |
| `in_last`   | in  | 1         | Offered byte is the last byte of its packet. Valid only while `in_valid` is 1. |
| `out_valid` | out | 1         | This module is offering a byte. |
| `out_ready` | in  | 1         | Downstream consumes that byte this cycle. |
| `out_data`  | out | 8         | Offered byte (payload or tag). |
| `out_last`  | out | 1         | Offered byte is the last byte of the current piece's tag. |

`MAX_PAYLOAD` is an integer parameter, default 4, minimum 2. Hidden
grading uses the default.

## 3. Handshake

A transfer happens only on a rising edge where that interface's valid and
ready are both 1. Call that an **accept**.

The testbench promises: after `in_valid` rises, it stays 1 and
`in_data`/`in_last` do not change until the byte is accepted.

This module promises:

- It never stores a payload byte to replay later. While it is forwarding
  payload, the byte it offers on `out_*` is the byte currently offered on
  `in_*`, in that same cycle. Therefore it may accept a payload byte only
  if downstream is willing to accept an output byte in that same cycle.
- `in_ready` is 1 only when a payload accept is actually allowed (see
  §4). During tag emission it is 0.
- During tag emission it holds `out_valid` high and keeps `out_data`
  unchanged until that tag byte is accepted.

## 4. When a piece ends

After reset the module is forwarding payload. Payload accepts are legal
only in that mode.

The current piece **ends** on the payload accept for which either of
these is true (both at once still ends one piece, not two):

- `in_last` is 1 on that accepted byte, or
- that accept is the `MAX_PAYLOAD`-th payload accept of the piece.

The cycle after that ending accept, the module is emitting the tag. After
the tag's last byte is accepted, it returns to forwarding payload.

## 5. Tag format

The tag is exactly two bytes, in this order.

**Count byte (first).** Unsigned 8-bit count of payload bytes that belong
to the piece just ended. `out_last` is 0.

**Integrity byte (second).** `out_last` is 1. Its value is specified in
§6.

## 6. Integrity byte

Let `N` be the count from §5. Let `ended_packet` be true iff the piece
ended because the accepted byte had `in_last` = 1 (including the case
where that byte was also the `MAX_PAYLOAD`-th byte).

Compute an 8-bit frame check over the piece's payload bytes **only**, in
the order they were accepted. Do not include `N` in that check. The
algorithm is CRC-8 with generator `x^8 + x^2 + x + 1`, initial value 0,
input processed most-significant bit first, no reflected bits, and no
constant mixed into the remainder after the last bit. Call the resulting
byte `C`.

If `ended_packet` is true, the integrity byte is `C` with every bit that
differs from `8'hA5` flipped (i.e. XOR). If `ended_packet` is false, use
`8'h5A` in place of `8'hA5`.

## 7. State that belongs to one piece

The running frame check, the payload count, and `ended_packet` describe
the piece now in progress. They advance on each payload accept. They are
wiped after the integrity byte is accepted, before the next piece starts.

## 8. Reset

While `rst` is 1 it wins over §3–§7: both `in_ready` and `out_valid` are
0, so neither side accepts. On a rising edge with `rst` = 1 the module
goes back to payload-forwarding and wipes the per-piece state of §7. Any
unfinished piece, including one already in the middle of its tag, is
dropped; leftover tag bytes must not appear after reset.

## 9. Coding limits

Synthesizable SystemVerilog for Icarus Verilog (`-g2012`). No SVA. One
clock, no latches. The skeleton's module name, parameter, and ports stay
exactly as given.
