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


如 API 文档中所述，使用 memory.getSupportedTypes（） 确定设备上支持的所有格式的 ID。例如，在 CC26xx 设备上，返回的 ID 为：
1-8ti
2-8c

7-16ti
8-16c

14-32ti
15-32c

//0 - 32 位十六进制 - TI 样式
//1 - 32 位十六进制 - C 样式
//2 - 32 位有符号整数
//3 - 32 位无符号整数
//4 - 32 位二进
//5 - 32 位浮点
//6 - 32 位指数浮点
//7 - 16 位十六进制 - TI 样式
//8 - 16 位十六进制 - C 样式
//9 - 16 位有符号整数
//10 - 16 位无符号整数
//11 - 16 位二进制
//12 - 8 位十六进制 - TI 样式
//13 - 8 位十六进制 - C 样式
//14 - 8 位有符号整数
//15 - 8 位无符号整数
//16 - 8 位二进
//17 - 字符
//18 - 64 位十六进制 - TI 样式
//19 - 64 位十六进制 - C 样式
//20 - 64 位有符号整数
//21 - 64 位无符号整数
//22 - 64 位浮点
//23 - 64 位指数浮点
因此，如果我想将内存从地址0x0保存为 dat 格式，其中包含 20 条 TI 16 位十六进制格式的记录，我会执行以下作：
debugSession.memory.saveData2（0， 0， 20， “data.dat”， 7， false）;



2. 运行run.bat文件

