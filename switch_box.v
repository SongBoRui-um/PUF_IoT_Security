// switch_box.v
module switch_box (
    input  wire in_top,       
    input  wire in_bottom,    
    input  wire challenge,    
    output wire out_top,      
    output wire out_bottom    
);
    // 增加 noprune 锁，确保两条物理多路选择路径绝对独立、不被交叉合并
    (* keep = 1, dont_touch = 1, noprune = 1 *) wire mux_top_out;
    (* keep = 1, dont_touch = 1, noprune = 1 *) wire mux_bottom_out;

    assign mux_top_out    = (challenge == 1'b0) ? in_top    : in_bottom;
    assign mux_bottom_out = (challenge == 1'b0) ? in_bottom : in_top;

    assign out_top    = mux_top_out;
    assign out_bottom = mux_bottom_out;
endmodule