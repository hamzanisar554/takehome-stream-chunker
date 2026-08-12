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

    // output byte stream (valid/ready, out_last marks the final trailer beat)
    output logic       out_valid,
    input  logic       out_ready,
    output logic [7:0] out_data,
    output logic       out_last
);

    typedef enum logic {
        PAYLOAD,
        TRAILER
    } state_t;

    state_t state;

    logic [7:0] crc;
    logic [7:0] payload_count;
    logic       is_final;
    logic       trailer_check;

    // CRC-8 polynomial: x^8 + x^2 + x + 1
    function automatic logic [7:0] crc_next(
        input logic [7:0] crc_in,
        input logic [7:0] data
    );
        logic [7:0] c;
        integer i;

        begin
            c = crc_in;

            for (i = 7; i >= 0; i = i - 1) begin
                if (c[7] ^ data[i])
                    c = {c[6:0], 1'b0} ^ 8'h07;
                else
                    c = {c[6:0], 1'b0};
            end

            crc_next = c;
        end
    endfunction

    always_comb begin
        in_ready  = 1'b0;
        out_valid = 1'b0;
        out_data  = 8'h00;
        out_last  = 1'b0;

        if (!rst) begin
            case (state)

                PAYLOAD: begin
                    in_ready  = out_ready;
                    out_valid = in_valid;
                    out_data  = in_data;
                end

                TRAILER: begin
                    out_valid = 1'b1;

                    if (!trailer_check) begin
                        out_data = payload_count;
                        out_last = 1'b0;
                    end
                    else begin
                        if (is_final)
                            out_data = crc ^ 8'hA5;
                        else
                            out_data = crc ^ 8'h5A;

                        out_last = 1'b1;
                    end
                end

            endcase
        end
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            state         <= PAYLOAD;
            crc           <= 8'h00;
            payload_count <= 8'h00;
            is_final      <= 1'b0;
            trailer_check <= 1'b0;
        end
        else begin
            case (state)

                PAYLOAD: begin
                    if (in_valid && in_ready) begin
                        crc <= crc_next(crc, in_data);
                        payload_count <= payload_count + 1'b1;

                        if (in_last ||
                            (payload_count == MAX_PAYLOAD - 1)) begin
                            is_final      <= in_last;
                            trailer_check <= 1'b0;
                            state         <= TRAILER;
                        end
                    end
                end

                TRAILER: begin
                    if (out_valid && out_ready) begin
                        if (!trailer_check) begin
                            trailer_check <= 1'b1;
                        end
                        else begin
                            state         <= PAYLOAD;
                            crc           <= 8'h00;
                            payload_count <= 8'h00;
                            is_final      <= 1'b0;
                            trailer_check <= 1'b0;
                        end
                    end
                end

                default: begin
                    state         <= PAYLOAD;
                    crc           <= 8'h00;
                    payload_count <= 8'h00;
                    is_final      <= 1'b0;
                    trailer_check <= 1'b0;
                end

            endcase
        end
    end

endmodule
