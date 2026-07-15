1) 1_project_templete 此目录下放置 模板工程，模板工程内需将 原始的激励文件删除
2) 2_source_file           此目录下放置 原始激励文件
3) 3_generate_project 此目录下为 根据模板工程和原始激励文件生成的ccs工程，并进行自动import和build
4) 4_result_out           此目录下为遍历工程后的.out文件
5) 5_result_dat           此目录下为运行工程后导出的memory文件
6) 6_result_dat_logs   此目录下存放运行工程和到处memory的log文件
7) config.json            此文件需进行单独配置
8) run.bat                  此文件为一键自动化运行脚本集合

usage：
1. 修改config.json文件，以下为详细说明
  "template_dir"      : "E:/yuwei_work/ti_c2000/280039c/auto_test_v2_251011/1_project_templete/TEST_Fix_ALLINS2",   // 需修改，模板工程路径
  "source_dir"          : "E:/yuwei_work/ti_c2000/280039c/auto_test_v2_251011/2_source_file",                                        // 需修改，原始激励文件路径
  "generate_dir"      : "E:/yuwei_work/ti_c2000/280039c/auto_test_v2_251011/3_generate_project",                               // 需修改，产生ccs工程路径
  "result_dir"           : "E:/yuwei_work/ti_c2000/280039c/auto_test_v2_251011/4_result_out",                                          // 需修改，编译后生成的所有.out文件
  "ccs_executable"  : "E:/ti/ti_software/12.8/ccs/eclipse/eclipsec.exe",                                                                           // 需修改，ccs的eclipse的安装路径
  "ccs_dss"              : "E:/ti/ti_software/12.8/ccs/ccs_base/scripting/bin/dss.bat",                                                          // 需修改，ccs的debug模块的路径
  "ccs_workspace"  : "E:/yuwei_work/ti_c2000/280039c/auto_test_v2_251011/3_generate_project",                               // 需修改，ccs的workspace，可根据修改进行修改
  "ccxml"                : "C:/Users/Administrator/ti/CCSTargetConfigurations/280039c.ccxml",                                         // 需修改，ccs的launch文件路径
  "build_config"      : "Debug",
  "do_generate"     : true,           // 根据需要，是否根据激励文件生成工程
  "do_build"           : true,           // 根据需要修改，是否进行import，和build工程
  "timeout"            : 30000,        // 工程运行超时机制，30s
  "result_addr"       : "0x2",         // 运行工程最后，结果判断的地址
  "success_val"       : "0xCCCC",  // 结果判断的值
  "error_val"           : "0xEEEE",   // 结果判断的值
  "device"              : "Texas Instruments XDS110 USB Debug Probe_0",    // 按照需要进行修改，不同仿真器修改为不同类型
  "cpu"                  : "C28xx_CPU1",   // 根据需要修改
  "cases": [
    {
      "name"   : "xxx",    // 无需修改
      "out"    : "E:/xxx/xxx.out",     // 无需修改
      "dat_dir": "5_result_dat/xxx",     // 无需修改
      "segments": [
        {"name": "M0" ,  "addr": "0x0000", "len": "0x400" , "width": 1},         // 根据需要进行修改，   width 1-16bit  // 目前导出的memory文件为，run完导出的文件
        {"name": "M1" ,  "addr": "0x0400", "len": "0x400" , "width": 1},
        {"name": "LS0",  "addr": "0x8000", "len": "0x800" , "width": 1},
        {"name": "LS1",  "addr": "0x8800", "len": "0x800" , "width": 1},
        {"name": "LS2",  "addr": "0x9000", "len": "0x800" , "width": 1},
        {"name": "LS3",  "addr": "0x9800", "len": "0x800" , "width": 1},
        {"name": "LS4",  "addr": "0xA000", "len": "0x800" , "width": 1},
        {"name": "LS5",  "addr": "0xA800", "len": "0x800" , "width": 1},
        {"name": "LS6",  "addr": "0xB000", "len": "0x800" , "width": 1},
        {"name": "LS7",  "addr": "0xB800", "len": "0x800" , "width": 1},
        {"name": "GS0",  "addr": "0xC000", "len": "0x1000", "width": 1},
        {"name": "GS1",  "addr": "0xD000", "len": "0x1000", "width": 1},
        {"name": "GS2",  "addr": "0xE000", "len": "0x1000", "width": 1},
        {"name": "GS3",  "addr": "0xF000", "len": "0x1000", "width": 1}
      ]
    }
  ]
}


CCS 12.1.0 内存导出格式ID映射表：
0 - 8-Bit Hex - TI Style
1 - 8-Bit Hex - C Style
2 - 8-Bit Signed Integer
3 - 8-Bit Unsigned Integer
4 - 8-Bit Binary
5 - Character
6 - Packed Char
7 - 16-Bit Hex - C Style
8 - 16-Bit Hex - TI Style
9 - 16-Bit Signed Integer
10 - 16-Bit Unsigned Integer
11 - 16-Bit Binary
12 - 32-Bit Signed Integer
13 - 32-Bit Unsigned Integer
14 - 32-Bit Hex - C Style
15 - 32-Bit Hex - TI Style
16 - 32-Bit Floating Point
17 - 32-Bit Exponential Float
18 - 32-Bit IEEE Floating Point
19 - 32-Bit IEEE Exp'l Float
20 - 64-Bit Hex - C Style
21 - 64-Bit Hex - TI Style
22 - 64-Bit Floating Point
23 - 64-Bit Exponential Float
因此，如果我想将内存从地址0x0保存为 dat 格式，其中包含 20 条 TI 16 位十六进制格式的记录，我会执行以下作：
debugSession.memory.saveData2（0， 0， 20， “data.dat”， 7， false）;

注意：GUI配置界面中，”导出格式”列已改为下拉框选择，可以直接选择具体的格式名称（如”16-Bit Hex - TI Style”），无需手动输入格式ID。


Flash 项目配置说明：
在配置文件中，可以为每个测试用例添加 “is_flash” 字段来指定是否为 Flash 项目：
  - “is_flash”: true   - 强制启用 Flash 编程（擦除→编程→验证）
  - “is_flash”: false  - 强制禁用 Flash 编程（RAM 项目）
  - 不设置此字段       - 自动判断（根据工程名和内存地址范围）

自动判断策略：
1. 工程名包含 “FLASH” → Flash 项目
2. 内存段地址在 0x3F0000-0x3FFFFF 范围 → Flash 项目
3. 以上都不满足 → RAM 项目

在 GUI 配置界面中，可以通过”Flash 项目”复选框进行三态选择：
- 勾选 = Flash 项目
- 未勾选 = RAM 项目
- 半选状态 = 自动判断（默认）


模板工程生成流程说明：
配置文件中设置 “generation_mode”: “template” 启用模板生成模式。

流程步骤：
1. 准备模板工程（1_project_templete 目录）
   - 包含完整的 CCS 工程结构（.project, .cproject, .cdtbuild 等）
   - 删除或保留需要的源文件

2. 准备源文件（2_source_file 目录）
   - 放置 .asm, .c, .cpp, .s 等源文件
   - 每个源文件将生成一个独立的测试工程

3. 自动生成过程
   - 从模板工程复制整个目录到 3_generate_project
   - 复制源文件到新工程目录
   - 自动替换所有配置文件中的工程名：
     * .project, .cproject, .cdtbuild, .cdtproject
     * artifactName, OUTPUT_FILE, MAP_FILE 等
   - 模板工程名从 .project 文件自动读取（更可靠）

4. 编译工程
   - 自动导入工程到 CCS workspace
   - 并行编译所有工程
   - 复制 .out 文件到 4_result_out 目录

5. 运行测试
   - 读取 .out 文件进行测试
   - 导出内存数据并判断结果


2. 运行run.bat文件

