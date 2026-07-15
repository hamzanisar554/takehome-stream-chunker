`timescale 1ns/1ps
//
// stream_chunker -- GOLDEN reference implementation.
// To be completed: implement per docs/spec.md so that the hidden testbench
// passes (see Task_Creation_Walkthrough_V2.txt, Section 2).
// Do not change the module name, parameter, port list, or port directions.
// Synthesizable SystemVerilog only (Icarus Verilog, -g2012). No SVA.
//
module stream_chunker #(
    parameter int MAX_PAYLOAD = 4   // payload beats per fragment; >= 2
) (
    input  logic       clk,
    input  logic       rst,        // synchronous, active-high

    // input byte stream (valid/ready, in_last marks end of packet)
    input  logic       in_valid,
    output logic       in_ready,
    input  logic [7:0] in_data,
    input  logic       in_last,

    // output byte stream (valid/ready, out_last marks trailer beats)
    output logic       out_valid,
    input  logic       out_ready,
    output logic [7:0] out_data,
    output logic       out_last
);

endmodule
