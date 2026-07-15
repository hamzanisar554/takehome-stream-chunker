`timescale 1ns/1ps
//
// stream_chunker -- implement per docs/spec.md.
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

    // output byte stream (valid/ready, out_last marks the final trailer beat)
    output logic       out_valid,
    input  logic       out_ready,
    output logic [7:0] out_data,
    output logic       out_last
);

    // TODO: implement the chunking / trailer-insertion logic per docs/spec.md.
    // The tie-offs below only keep the skeleton compiling; replace them with
    // your implementation.
    assign in_ready  = 1'b0;
    assign out_valid = 1'b0;
    assign out_data  = '0;
    assign out_last  = 1'b0;

endmodule
