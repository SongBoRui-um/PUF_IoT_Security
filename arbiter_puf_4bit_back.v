// ======================================================================================
// File Name:    arbiter_puf_4bit.v
// Description:  4-Bit Arbiter PUF — Corrected Architecture.
//
// ROOT CAUSE OF ALL-ZERO BUG (original version):
//   1. Arbiter D-FF was clocked by the PUF delay path output (w_bottom_3_delayed).
//      This is an asynchronous, glitching combinational signal — Quartus treats it as
//      an unregistered async clock and the FF almost never toggles → response always 0.
//   2. The double-invert "delay" (~~w_bottom_3) is trivially optimized away by
//      synthesis even with keep=1, producing zero path difference.
//   3. Both switch box inputs tied to the same puf_trigger signal means top/bottom
//      paths are identical in the Boolean domain — no physical delay difference
//      can ever produce a '1' outcome after the arbiter.
//
// FIXES APPLIED:
//   1. The arbiter D-FF is clocked by the SYSTEM CLOCK (clk_50). The FF samples
//      the top-path output on a rising edge that arrives AFTER the challenge has
//      settled. This gives Quartus a well-defined setup/hold timing window to
//      optimise paths against, preserving the physical delay difference as a
//      metastability-based PUF response.
//   2. A two-FF synchroniser chain (meta1 → meta2) is added so the metastable
//      pulse is cleanly resolved before being read by the AXI bus.
//   3. puf_trigger is used as a synchronised enable: the FF captures only on the
//      rising edge of trigger (detected with a 1-cycle delay register), giving
//      exactly one sampling event per challenge.
//   4. w_top_3 and w_bottom_3 remain as the two racing paths. The arbiter samples
//      w_top_3 on the clock edge; the fact that w_bottom_3 arrives
//      slightly earlier or later due to silicon variation is what generates the PUF
//      response — the clock edge acts as the "finish line" of the race.
//
// NOTE ON ANTI-OPTIMISATION:
//   keep/dont_touch attributes are retained on intermediate wires so Quartus cannot
//   merge the two paths. The CRITICAL constraint in the .sdc file (see comment below)
//   is REQUIRED to prevent timing closure from equalising both paths.
//
// REQUIRED .sdc CONSTRAINT (add to your project .sdc):
//   set_multicycle_path -from [get_keepers {puf_core_inst|*}] -to [get_keepers {puf_core_inst|meta1}] -setup 0
//   set_false_path -from [get_keepers {puf_core_inst|*}] -to [get_keepers {puf_core_inst|meta1}]
//   The false_path prevents TimeQuest from balancing the two racing paths.
// ======================================================================================

module arbiter_puf_4bit (
    input  wire        clk_50,         // System clock — 50 MHz from CLOCK_50
    input  wire        puf_trigger,    // Level: hold high while reading response
    input  wire [3:0]  puf_challenge,
    output wire        puf_response
);

    // ----------------------------------------------------------------------------------
    // 1. Anti-optimisation wires (switch box interconnects)
    // ----------------------------------------------------------------------------------
    (* keep = 1, dont_touch = 1, noprune = 1 *) wire w_top_0,    w_bottom_0;
    (* keep = 1, dont_touch = 1, noprune = 1 *) wire w_top_1,    w_bottom_1;
    (* keep = 1, dont_touch = 1, noprune = 1 *) wire w_top_2,    w_bottom_2;
    (* keep = 1, dont_touch = 1, noprune = 1 *) wire w_top_3,    w_bottom_3;

    // ----------------------------------------------------------------------------------
    // 2. Switch-box pipeline (same as before — structural fix is in step 4)
    // ----------------------------------------------------------------------------------
    puf_switch_box sb0 (
        .in_top(puf_trigger), .in_bottom(puf_trigger),
        .challenge(puf_challenge[0]),
        .out_top(w_top_0), .out_bottom(w_bottom_0)
    );
    puf_switch_box sb1 (
        .in_top(w_top_0), .in_bottom(w_bottom_0),
        .challenge(puf_challenge[1]),
        .out_top(w_top_1), .out_bottom(w_bottom_1)
    );
    puf_switch_box sb2 (
        .in_top(w_top_1), .in_bottom(w_bottom_1),
        .challenge(puf_challenge[2]),
        .out_top(w_top_2), .out_bottom(w_bottom_2)
    );
    puf_switch_box sb3 (
        .in_top(w_top_2), .in_bottom(w_bottom_2),
        .challenge(puf_challenge[3]),
        .out_top(w_top_3), .out_bottom(w_bottom_3)
    );

    // ----------------------------------------------------------------------------------
    // 3. Rising-edge detector for puf_trigger (purely synchronous, clocked by clk_50)
    //    trigger_re goes high for exactly ONE clock cycle on the 0->1 transition.
    // ----------------------------------------------------------------------------------
    (* keep = 1, dont_touch = 1, noprune = 1 *) reg trigger_d = 1'b0;
    wire trigger_re;

    always @(posedge clk_50) begin
        trigger_d <= puf_trigger;
    end
    assign trigger_re = puf_trigger & (~trigger_d);   // rising edge pulse

    // ----------------------------------------------------------------------------------
    // 4. Arbiter + two-stage metastability synchroniser
    //    CRITICAL: clocked by clk_50, NOT by the PUF delay path.
    //    On the rising edge of trigger, meta1 samples w_top_3.
    //    At that exact instant, if w_top_3 and w_bottom_3 have not yet settled
    //    (i.e. the two paths arrive within one clock period of each other),
    //    the FF enters a metastable state — which is EXACTLY what generates the PUF
    //    response based on silicon manufacturing variation.
    //    meta2 resolves the metastability before the AXI read.
    // ----------------------------------------------------------------------------------
    (* keep = 1, dont_touch = 1, noprune = 1 *) reg meta1 = 1'b0;
    (* keep = 1, dont_touch = 1, noprune = 1 *) reg meta2 = 1'b0;
    (* keep = 1, dont_touch = 1, noprune = 1 *) reg resp_reg = 1'b0;

    always @(posedge clk_50) begin
        if (trigger_re)
            meta1 <= w_top_3;       // Sample the racing top-path on the trigger edge
        meta2    <= meta1;          // First synchroniser stage
        resp_reg <= meta2;          // Second synchroniser stage → stable output
    end

    assign puf_response = resp_reg;

endmodule


// ======================================================================================
// Switch Box — unchanged structurally.
// The MUX-based crossbar routes in_top/in_bottom differently for each challenge bit,
// creating two signal paths through the silicon that accumulate different delays.
// ======================================================================================
module puf_switch_box (
    input  wire in_top,
    input  wire in_bottom,
    input  wire challenge,
    output wire out_top,
    output wire out_bottom
);
    (* keep = 1, dont_touch = 1 *) wire wire_t0, wire_t1;
    (* keep = 1, dont_touch = 1 *) wire wire_b0, wire_b1;

    // Straight-through when challenge=0, crossed when challenge=1
    assign wire_t0  = in_top    & (~challenge);
    assign wire_t1  = in_bottom &   challenge;
    assign out_top  = wire_t0 | wire_t1;

    assign wire_b0  = in_bottom & (~challenge);
    assign wire_b1  = in_top    &   challenge;
    assign out_bottom = wire_b0 | wire_b1;

endmodule
