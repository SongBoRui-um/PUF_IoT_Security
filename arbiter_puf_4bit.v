// 4-bit arbiter PUF core with a real two-path race.
//
// Interface:
//   puf_trigger   : HPS writes 0, sets challenge, then writes 1 to launch one race.
//   puf_challenge : 4-bit challenge, held stable before trigger rising edge.
//   puf_status[0] : sampled response bit.
//   puf_status[1] : done bit. Goes high when response is valid.
//
// Important:
//   The arbiter register is intentionally clocked by the bottom race path.
//   Isolate this block with SDC false paths and preserve/keep attributes.

module arbiter_puf_4bit (
    input  wire       clk_50,
    input  wire       reset_n,
    input  wire       puf_trigger,
    input  wire [3:0] puf_challenge,
    output wire [1:0] puf_status
);

    (* preserve, noprune *) reg trigger_q1 = 1'b0;
    (* preserve, noprune *) reg trigger_q2 = 1'b0;
    wire trigger_re;

    always @(posedge clk_50 or negedge reset_n) begin
        if (!reset_n) begin
            trigger_q1 <= 1'b0;
            trigger_q2 <= 1'b0;
        end else begin
            trigger_q1 <= puf_trigger;
            trigger_q2 <= trigger_q1;
        end
    end

    assign trigger_re = trigger_q1 & ~trigger_q2;

    (* preserve, noprune *) reg [3:0] challenge_latched = 4'b0000;
    (* preserve, noprune *) reg launch_top = 1'b0;
    (* preserve, noprune *) reg launch_bottom = 1'b0;
    (* preserve, noprune *) reg busy = 1'b0;
    (* preserve, noprune *) reg done = 1'b0;

    (* keep, noprune *) wire t0, b0;
    (* keep, noprune *) wire t1, b1;
    (* keep, noprune *) wire t2, b2;
    (* keep, noprune *) wire t3, b3;

    puf_switch_box sb0 (
        .in_top(launch_top),
        .in_bottom(launch_bottom),
        .challenge(challenge_latched[0]),
        .out_top(t0),
        .out_bottom(b0)
    );

    puf_switch_box sb1 (
        .in_top(t0),
        .in_bottom(b0),
        .challenge(challenge_latched[1]),
        .out_top(t1),
        .out_bottom(b1)
    );

    puf_switch_box sb2 (
        .in_top(t1),
        .in_bottom(b1),
        .challenge(challenge_latched[2]),
        .out_top(t2),
        .out_bottom(b2)
    );

    puf_switch_box sb3 (
        .in_top(t2),
        .in_bottom(b2),
        .challenge(challenge_latched[3]),
        .out_top(t3),
        .out_bottom(b3)
    );

    // The arbiter: bottom path is the race clock, top path is sampled data.
    (* preserve, noprune *) reg raw_response = 1'b0;
    always @(posedge b3) begin
        raw_response <= t3;
    end

    (* preserve, noprune *) reg b3_s1 = 1'b0;
    (* preserve, noprune *) reg b3_s2 = 1'b0;
    (* preserve, noprune *) reg raw_s1 = 1'b0;
    (* preserve, noprune *) reg raw_s2 = 1'b0;
    (* preserve, noprune *) reg response = 1'b0;

    always @(posedge clk_50 or negedge reset_n) begin
        if (!reset_n) begin
            challenge_latched <= 4'b0000;
            launch_top <= 1'b0;
            launch_bottom <= 1'b0;
            busy <= 1'b0;
            b3_s1 <= 1'b0;
            b3_s2 <= 1'b0;
            raw_s1 <= 1'b0;
            raw_s2 <= 1'b0;
            response <= 1'b0;
            done <= 1'b0;
        end else begin
            b3_s1 <= b3;
            b3_s2 <= b3_s1;
            raw_s1 <= raw_response;
            raw_s2 <= raw_s1;

            if (!trigger_q1) begin
                launch_top <= 1'b0;
                launch_bottom <= 1'b0;
                busy <= 1'b0;
                done <= 1'b0;
            end else if (trigger_re) begin
                challenge_latched <= puf_challenge;
                launch_top <= 1'b1;
                launch_bottom <= 1'b1;
                busy <= 1'b1;
                done <= 1'b0;
            end else if (busy && b3_s2) begin
                response <= raw_s2;
                done <= 1'b1;
                busy <= 1'b0;
            end
        end
    end

    assign puf_status = {done, response};

endmodule

module puf_switch_box (
    input  wire in_top,
    input  wire in_bottom,
    input  wire challenge,
    output wire out_top,
    output wire out_bottom
);
    (* keep, noprune *) wire straight_top;
    (* keep, noprune *) wire cross_top;
    (* keep, noprune *) wire straight_bottom;
    (* keep, noprune *) wire cross_bottom;

    assign straight_top = in_top & ~challenge;
    assign cross_top = in_bottom & challenge;
    assign out_top = straight_top | cross_top;

    assign straight_bottom = in_bottom & ~challenge;
    assign cross_bottom = in_top & challenge;
    assign out_bottom = straight_bottom | cross_bottom;
endmodule
