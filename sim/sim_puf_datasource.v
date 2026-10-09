`timescale 1ns / 1ps
// ======================================================================================
// File Name:    sim_puf_datasource.v
// Description:  面向电力 IoT 零信任框架的大规模 PUF 工艺偏差行为级仿真数据源生成器
//               (支持温度漂移、电压抖动与高斯随机延迟引入)
// ======================================================================================

module sim_puf_datasource;

    // 仿真控制信号
    reg         clk;
    reg         trigger;
    reg  [3:0]  challenge;
    
    // 环境变异性因子 (用于支撑论文第三章的环境鲁棒性评估)
    real        env_temperature; // 模拟温度: 25.0度(常温), 85.0度(高温)
    real        env_voltage;     // 模拟电压: 1.2V(标准), 1.08V(电压跌落)
    
    // 随机数种子，用于生成高斯分布
    integer     seed_path_a;
    integer     seed_path_b;
    integer     seed_noise;
    
    // 内部计算延迟线
    real        delay_u[0:3]; // 上路每级的固有工艺偏差
    real        delay_d[0:3]; // 下路每级的固有工艺偏差
    
    // 赛跑时间累加器
    real        time_upper;
    real        time_lower;
    
    // 最终输出响应
    reg         puf_response;
    
    // 文件句柄，用于直接导出 CSV 数据集
    integer     csv_file;
    integer     dev_id;
    integer     chal_idx;
    
    // ===================================================================
    // 1. 初始化物理工艺偏差 (高斯分布模拟：均值为1.0ns，标准差为0.05ns)
    // ===================================================================
    initial begin
        clk = 0;
        trigger = 0;
        challenge = 0;
        
        // 赋予初始种子值（确保每次运行或不同设备 ID 种子不同）
        seed_path_a = 12345;
        seed_path_b = 67890;
        seed_noise  = 55555;
        
        // 打开用于算法训练和分析的 CSV 数据集文件
        csv_file = $fopen("puf_sim_dataset.csv", "w");
        // 写入符合电力物联网及安全标准的数据集表头
        $fdisplay(csv_file, "Device_ID,Challenge_Dec,Temperature,Voltage,Time_Upper,Time_Lower,Response");
        
        $display("[INFO] 开始生成基于微观工艺偏差的行为级 PUF 仿真数据集...");
    end

    // 时钟发生器（50MHz 采样率控制）
    always #10 clk = ~clk;

    // ===================================================================
    // 2. 核心物理仿真逻辑：计算 4-bit 挑战下的累积延迟
    // ===================================================================
    task evaluate_puf(
        input integer id, 
        input [3:0] chal, 
        input real temp, 
        input real volt, 
        output out_bit,
        output real t_up,
        output real t_dn
    );
        integer i;
        real base_delay;
        real temp_coefficient;
        real volt_coefficient;
        real random_jitter;
        begin
            // 基础传播延迟 (基准 1.0 ns)
            base_delay = 1.0;
            
            // 物理环境一阶效应：温度升高延迟增大，电压降低延迟增大
            temp_coefficient = 1.0 + (temp - 25.0) * 0.002; 
            volt_coefficient = 1.0 - (volt - 1.2) * 0.15;
            
            time_upper = 0.0;
            time_lower = 0.0;
            
            // 逐级计算选择器（Mux）延迟
            for (i = 0; i < 4; i = i + 1) begin
                // 利用高斯分布产生该芯片特定的、不可克隆的微观延迟差异
                delay_u[i] = $dist_normal(seed_path_a, 1000, 50) / 1000.0; // 均值1.0, 标准差0.05
                delay_d[i] = $dist_normal(seed_path_b, 1000, 50) / 1000.0;
                
                // 引入随时间动态变化的电力热电磁干扰噪声 (高斯白噪声微扰: 均值0, 标准差0.01ns)
                random_jitter = $dist_normal(seed_noise, 0, 10) / 1000.0;
                
                // 依据 Mux 级联逻辑，Challenge 决定路径切换
                if (chal[i] == 1'b0) begin
                    time_upper = time_upper + (delay_u[i] * temp_coefficient * volt_coefficient) + random_jitter;
                    time_lower = time_lower + (delay_d[i] * temp_coefficient * volt_coefficient) - random_jitter;
                end else begin
                    // Challenge = 1 时，上下路径发生交叉
                    time_upper = time_lower + (delay_u[i] * temp_coefficient * volt_coefficient) + random_jitter;
                    time_lower = time_upper + (delay_d[i] * temp_coefficient * volt_coefficient) - random_jitter;
                end
            end
            
            // 仲裁器（D-FF）根据两路到达的先后顺序锁定响应
            if (time_upper < time_lower)
                out_bit = 1'b1; // 上路快，输出1
            else
                out_bit = 1'b0; // 下路快，输出0
                
            t_up = time_upper;
            t_dn = time_lower;
        end
    endtask

    // ===================================================================
    // 3. 自动化数据集轮询生成（模拟 50 个异构终端，全组合环境变异）
    // ===================================================================
    real out_t_up, out_t_dn;
    reg  out_b;
    
    initial begin
        // 等待系统稳定
        #100;
        
        // 循环虚拟生成 50 块异构电力物联网终端芯片 (Device ID: 1 到 50)
        for (dev_id = 1; dev_id <= 50; dev_id = dev_id + 1) begin
            
            // 为每块芯片更换不同的内部制造种子，保证个体唯一性
            seed_path_a = seed_path_a + dev_id * 7;
            seed_path_b = seed_path_b + dev_id * 13;
            
            // 遍历 16 种所有的 4-bit 挑战组合 (Challenge 0000 到 1111)
            for (chal_idx = 0; chal_idx < 16; chal_idx = chal_idx + 1) begin
                challenge = chal_idx[3:0];
                
                // 场景 A：模拟电力系统常温、标准电压下的注册指纹 (25°C, 1.2V)
                evaluate_puf(dev_id, challenge, 25.0, 1.20, out_b, out_t_up, out_t_dn);
                puf_response = out_b;
                $fdisplay(csv_file, "%d,%d,25.0,1.20,%f,%f,%d", dev_id, challenge, out_t_up, out_t_dn, puf_response);
                #20;
                
                // 场景 B：模拟高负荷变电站恶劣环境——高温、电压跌落下的运行指纹 (85°C, 1.08V)
                evaluate_puf(dev_id, challenge, 85.0, 1.08, out_b, out_t_up, out_t_dn);
                puf_response = out_b;
                $fdisplay(csv_file, "%d,%d,85.0,1.08,%f,%f,%d", dev_id, challenge, out_t_up, out_t_dn, puf_response);
                #20;
            end
        end
        
        // 完成数据采集，安全关闭文件描述符
        $fclose(csv_file);
        $display("[SUCCESS] 硬件指纹数据集生成成功！已存盘为 'puf_sim_dataset.csv'。");
        $display("[INFO] 总共为 50 个设备生成了 %d 组标准 CRP 指纹样本。", 50 * 16 * 2);
        $finish;
    end

endmodule