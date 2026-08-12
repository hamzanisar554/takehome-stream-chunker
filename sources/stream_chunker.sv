`timescale 1ns/1ps

module stream_chunker #(
    parameter int MAX_PAYLOAD = 4
) (
    input  logic       clk,
    input  logic       rst,

    input  logic       in_valid,
    output logic       in_ready,
    input  logic [7:0] in_data,
    input  logic       in_last,

    output logic       out_valid,
    input  logic       out_ready,
    output logic [7:0] out_data,
    output logic       out_last
);

    typedef enum logic [1:0] {
        PAYLOAD,
        LENGTH,
        CHECK
    } state_t;

    state_t state;

    logic [7:0] crc;
    logic [7:0] payload_count;
    logic       is_final;

    // CRC-8, polynomial x^8 + x^2 + x + 1 (0x07).
    // MSB first, initial value 0, no final XOR.
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

    // Output side is combinational. Payload data is passed through
    // without any internal buffering.
    always_comb begin
        in_ready  = 1'b0;
        out_valid = 1'b0;
        out_data  = 8'h00;
        out_last  = 1'b0;

        if (!rst) begin
            case (state)

                PAYLOAD: begin
                    // A payload byte can only be accepted when the
                    // downstream is ready in the same cycle.
                    in_ready  = out_ready;
                    out_valid = in_valid;
                    out_data  = in_data;
                end

                LENGTH: begin
                    in_ready  = 1'b0;
                    out_valid = 1'b1;
                    out_data  = payload_count;
                    out_last  = 1'b0;
                end

                CHECK: begin
                    in_ready  = 1'b0;
                    out_valid = 1'b1;

                    if (is_final)
                        out_data = crc ^ 8'hA5;
                    else
                        out_data = crc ^ 8'h5A;

                    out_last = 1'b1;
                end

                default: begin
                    in_ready  = 1'b0;
                    out_valid = 1'b0;
                    out_data  = 8'h00;
                    out_last  = 1'b0;
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
        end
        else begin
            case (state)

                PAYLOAD: begin
                    if (in_valid && in_ready) begin
                        crc <= crc_next(crc, in_data);
                        payload_count <= payload_count + 1'b1;

                        // Close the fragment either at in_last or when
                        // the maximum payload size is reached.
                        if (in_last ||
                            (payload_count == MAX_PAYLOAD - 1)) begin
                            is_final <= in_last;
                            state    <= LENGTH;
                        end
                    end
                end

                LENGTH: begin
                    if (out_valid && out_ready) begin
                        state <= CHECK;
                    end
                end

                CHECK: begin
                    if (out_valid && out_ready) begin
                        state         <= PAYLOAD;
                        crc           <= 8'h00;
                        payload_count <= 8'h00;
                        is_final      <= 1'b0;
                    end
                end

                default: begin
                    state         <= PAYLOAD;
                    crc           <= 8'h00;
                    payload_count <= 8'h00;
                    is_final      <= 1'b0;
                end

            endcase
        end
    end

endmodule