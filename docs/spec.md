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
- In payload-forwarding mode, `in_ready` shall be 1 in exactly those
  cycles where a presented payload byte would be accepted, and 0 in every
  other cycle. During tag emission it is 0.
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

The tag is exactly two bytes.

The earlier tag byte is an unsigned 8-bit count of payload bytes that
belong to the piece just ended. `out_last` is 0 on that byte.

The later tag byte is the integrity value of §6. `out_last` is 1 on that
byte and only then.

## 6. Integrity value

The integrity value is an 8-bit frame check of the piece's payload
octets, taken in the order those octets were accepted, after that check
has been masked as specified below. Trailer/count octets are not part of
the checked string.

The frame check is the 8-bit cyclic remainder of that octet string with
these catalog parameters (Rocksoft model): width 8; polynomial `0x07`
(the `x^8` term implicit); init `0x00`; `refin` false; `refout` false;
`xorout` `0x00`. Bits of each octet are consumed most-significant first.

The mask applied to that remainder is selected only by the ending
payload accept: decimal 165 if that accept had `in_last` = 1 (even if it
was also the `MAX_PAYLOAD`-th byte of the piece), decimal 90 otherwise.
Each 1-bit of the mask inverts the corresponding bit of the remainder;
each 0-bit of the mask leaves that remainder bit unchanged. The integrity
byte is the remainder after this masking.

## 7. State that belongs to one piece

The running frame check, the payload count, and whether the ending accept
carried `in_last` describe the piece now in progress. They advance on
each payload accept. They are wiped after the later tag byte is accepted,
before the next piece starts.

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
