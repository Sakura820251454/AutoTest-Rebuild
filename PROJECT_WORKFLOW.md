# AutoTest 项目流程文档

本文档详细描述了 AutoTest 项目的完整工作流程，包括每个步骤的执行文件、输入输出产物和目的。

---
一旦我所属的文件夹有所变化请更新我

## 项目概述

AutoTest 是一个通用的 **TI C2000 DSP 芯片自动化测试框架**，支持基于 CCS + DSS 的嵌入式软件测试流程。

### 支持的测试类型

- **C 语言工程**（.c 文件）
- **汇编语言工程**（.asm / .s 文件）
- **C++ 工程**（.cpp 文件）
- **算法库测试**（如 FastRTS 等数学函数库）
- **自定义算法测试**
- **驱动程序测试**
- **性能对比测试**（不同优化等级）

### 核心流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AutoTest 完整工作流程                              │
└─────────────────────────────────────────────────────────────────────────────┘

    步骤1: 工程生成          步骤2: 工程构建           步骤3: 测试执行
    ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
    │  生成测试   │    →     │  编译生成   │    →     │  下载运行   │
    │  工程目录   │          │  .out 文件  │          │  导出数据   │
    └─────────────┘          └─────────────┘          └─────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
    source/*.{c,asm}        工程/Debug/*.out          5_result_dat/
    + template/                  ↓                        ↓
                            4_result_out/*.out      summary.csv
                                                    summary.xlsx
```

### 支持的源文件类型

| 扩展名 | 类型 | 说明 |
|--------|------|------|
| `.c` | C 语言源文件 | 标准 C 代码 |
| `.cpp` | C++ 源文件 | C++ 代码 |
| `.asm` | 汇编源文件 | TI 汇编语法 |
| `.s` | 汇编源文件 | GNU 汇编语法 |

---

## 步骤详解

### 步骤 1: 工程生成 (Project Generation)

**目的**: 准备所有测试工程

#### 两种生成模式

通过 `config.json` 中的 `generation.generation_mode` 配置选择：

| 模式 | 配置值 | 适用场景 | 说明 |
|------|--------|----------|------|
| **模板模式** | `"template"` | 所有工程配置相同 | 使用模板工程 + 源文件批量生成 |
| **手动模式** | `"manual"` | 各工程配置不同 | 使用已手动配置好的工程 |

##### 模式 A: TEMPLATE（模板模式）

**适用情况**：所有测试工程的 CCS 配置完全相同，只有工程名和源文件不同

**示例场景**：
- FastRTS 库函数回归测试（55 个用例配置相同）
- 同一算法不同输入参数的批量测试
- 标准单元测试

**所需输入**：
1. `template_dir` - 模板工程目录（标准 CCS 工程）
2. `source_dir` - 源文件目录（.c/.cpp/.asm/.s 文件）

**处理流程**：
```
1. 扫描 source_dir 中的所有源文件
2. 对于每个源文件：
   a. 复制模板工程到 generate_dir
   b. 将源文件复制到工程目录
   c. 替换工程名（.project, .cproject 中的名称）
3. 返回生成的工程列表
```

**输出示例**：
```
generate_dir/
├── FASTRTS_atan_f32/           # 从模板生成
│   ├── .project                 # 工程名已替换为 FASTRTS_atan_f32
│   ├── .cproject
│   ├── FASTRTS_atan_f32.c       # 复制的源文件
│   └── Debug/
│
├── FASTRTS_atan2_f32/          # 从模板生成
│   ├── .project
│   ├── .cproject
│   ├── FASTRTS_atan2_f32.c
│   └── Debug/
│
└── ...
```

##### 模式 B: MANUAL（手动模式）

**适用情况**：各测试工程的 CCS 配置各不相同（编译选项、链接脚本、优化等级等不同）

**示例场景**：
- 不同优化等级的对比测试（-O0 vs -O2 vs -O3）
- 不同内存布局的测试
- 需要特殊链接脚本的测试
- 包含多个源文件的复杂工程

**所需输入**：
1. `generate_dir` - 已配置好的工程目录

**准备工作**（在运行 AutoTest 之前）：
```bash
# 在 CCS 中手动创建和配置工程
# 1. 打开 CCS
# 2. 创建新工程
# 3. 配置编译选项、链接脚本等
# 4. 添加源文件
# 5. 测试编译通过

# 将配置好的工程复制到 generate_dir
xcopy /E /I "D:\CCS_Workspace\custom_opt_o0" "D:\AutoTest_DEMO\3_generate_project\custom_opt_o0"
xcopy /E /I "D:\CCS_Workspace\custom_opt_o2" "D:\AutoTest_DEMO\3_generate_project\custom_opt_o2"
```

**处理流程**：
```
1. 扫描 generate_dir 中的所有工程目录
2. 验证每个工程是有效的 CCS 工程（包含 .project 和 .cproject）
3. 返回验证通过的工程列表
```

**输出示例**：
```
generate_dir/
├── custom_opt_o0/              # 手动配置（-O0 优化）
│   ├── .project
│   ├── .cproject                # 自定义编译选项
│   ├── main.c
│   └── Debug/
│
├── custom_opt_o2/              # 手动配置（-O2 优化）
│   ├── .project
│   ├── .cproject                # 自定义编译选项
│   ├── main.c
│   └── Debug/
│
└── complex_multi_file/         # 手动配置（多文件工程）
    ├── .project
    ├── .cproject
    ├── main.c
    ├── utils.c
    ├── utils.h
    └── Debug/
```

#### 执行文件

- **核心模块**: `src/generator.py` - `ProjectGenerator` 类
- **CLI入口**: `run.py --generate`
- **GUI入口**: 执行面板 → 开始执行（选择"从生成开始"）

#### 配置示例

**TEMPLATE 模式配置**：
```json
{
  "paths": {
    "template_dir": "D:/AutoTest_DEMO/1_project_templete/ccs_insts_test",
    "source_dir": "D:/AutoTest_DEMO/2_source_file",
    "generate_dir": "D:/AutoTest_DEMO/3_generate_project"
  },
  "generation": {
    "generation_mode": "template"
  }
}
```

**MANUAL 模式配置**：
```json
{
  "paths": {
    "template_dir": "D:/AutoTest_DEMO/1_project_templete/ccs_insts_test",
    "source_dir": "D:/AutoTest_DEMO/2_source_file",
    "generate_dir": "D:/AutoTest_DEMO/3_generate_project"
  },
  "generation": {
    "generation_mode": "manual"
  }
}
```

#### 使用建议

1. **TEMPLATE 模式使用流程**：
   ```bash
   # 1. 准备模板工程和源文件
   # template_dir/ - 放置标准 CCS 工程模板
   # source_dir/ - 放置所有 .c/.asm 源文件
   
   # 2. 配置为 template 模式
   # 编辑 config.json: "generation_mode": "template"
   
   # 3. 运行生成
   python run.py -c config.json --generate
   
   # 输出：所有工程从模板批量生成
   ```

2. **MANUAL 模式使用流程**：
   ```bash
   # 1. 在 CCS 中手动配置所有工程
   # 2. 将工程复制到 generate_dir
   xcopy /E /I "D:\CCS_Workspace\project1" "D:\AutoTest_DEMO\3_generate_project\project1"
   xcopy /E /I "D:\CCS_Workspace\project2" "D:\AutoTest_DEMO\3_generate_project\project2"
   
   # 3. 配置为 manual 模式
   # 编辑 config.json: "generation_mode": "manual"
   
   # 4. 运行生成（验证工程）
   python run.py -c config.json --generate
   
   # 输出：验证手动配置的工程
   ```

---

### 步骤 2: 工程构建 (Project Build)

**目的**: 将所有测试工程编译成可执行的 .out 文件

**执行文件**:
- **核心模块**: `src/builder.py` - `ProjectBuilder` 类
- **CLI入口**: `run.py --build`
- **GUI入口**: 执行面板 → 开始执行（选择"从构建开始"）

**输入**:
| 输入项 | 路径/文件 | 说明 |
|--------|-----------|------|
| 配置文件 | `config/config.json` | 包含 ccs_workspace, ccs_executable |
| 测试工程 | `generate_dir/*/` | 步骤1生成的工程目录 |

**处理逻辑**:
```
1. 导入阶段（串行）:
   for each project in generate_dir:
       调用 CCS headless 导入工程到 workspace
       
2. 构建阶段（并行）:
   with ThreadPoolExecutor(max_workers=4):
       for each project:
           调用 CCS headless 构建工程
           复制 .out 文件到 result_dir
```

**CCS Headless 命令**:
```bash
# 导入工程
eclipsec.exe -noSplash -data <workspace> \
    -application com.ti.ccstudio.apps.importProject \
    -ccs.location <project_path> \
    -ccs.autoBuild false

# 构建工程
eclipsec.exe -noSplash -data <workspace> \
    -application com.ti.ccstudio.apps.buildProject \
    -ccs.projects <project_name> \
    -ccs.configuration Debug
```

**输出产物**:
```
generate_dir/                    # CCS 工作空间
├── test_algorithm_c/
│   └── Debug/
│       └── test_algorithm_c.out  # 构建产物（留在原处）
├── test_driver_asm/
│   └── Debug/
│       └── test_driver_asm.out
└── ...

result_dir/                      # 例如: D:/AutoTest_rebuild/4_result_out
├── test_algorithm_c.out         # 复制的构建产物
├── test_driver_asm.out
└── ...
```

---

### 步骤 3: 配置生成 (Config Generation)

**目的**: 扫描所有 .out 文件，生成完整的测试配置

**执行文件**:
- **核心模块**: `src/executor.py` - `TestExecutor.generate_test_config()`
- **调用时机**: 测试执行前自动调用

**输入**:
| 输入项 | 路径/文件 | 说明 |
|--------|-----------|------|
| 配置文件 | `config/config.json` | 模板配置 |
| .out 文件 | `workspace/**/*.out` | 步骤2生成的可执行文件 |

**处理逻辑**:
```python
outs = sorted(workspace.rglob('*.out'))  # 递归查找所有 .out 文件
for out_file in outs:
    case_name = out_file.stem
    dat_dir = f'5_result_dat/{timestamp}/{case_name}'
    cases.append({
        'name': case_name,
        'out': str(out_file),
        'dat_dir': dat_dir,
        'segments': [...]  # 内存段配置
    })
```

**输出产物**:
```
full_regr.json                   # 完整测试配置
{
  "ccxml": "...",
  "device": "...",
  "cpu": "...",
  "timeout": 45000,
  "result_addr": "0x7625",
  "success_val": "0xCCCC",
  "error_val": "0xEEEE",
  "cases": [
    {
      "name": "test_algorithm_c",
      "out": "D:/.../test_algorithm_c.out",
      "dat_dir": "5_result_dat/2026-03-16-10-30/test_algorithm_c",
      "segments": [...]
    },
    ...
  ]
}
```

---

### 步骤 4: 硬件预检测 (Hardware Pre-check)

**目的**: 快速检测 XDS100 调试器是否连接，避免 DSS 超时等待

**执行文件**:
- **新版**: `src/hardware_detector.py` - `HardwareDetector` 类
- **调用时机**: 每批测试执行前自动调用

**检测方式**:
| 系统 | 检测方法 | 说明 |
|------|----------|------|
| Windows | pnputil / wmic / PowerShell | 检查 USB 设备 VID/PID |
| Linux | lsusb | 检查 USB 设备 |

**输出**:
- 检测结果: `(是否连接, 详细信息)`
- 如果未连接，提前终止测试并提示用户

---

### 步骤 5: 测试执行 (Test Execution)

**目的**: 将程序下载到目标板运行，导出内存数据，检查测试结果

**执行文件**:
- **核心模块**: `src/executor.py` - `TestExecutor` 类
- **配置生成**: `src/test_config_generator.py` - `generate_test_config()` 函数
- **报告生成**: `src/report_generator.py` - `generate_summary_report()` 函数
- **DSS模板**: `templates/dss_test.js.tmpl`
- **CLI入口**: `run.py --test`
- **GUI入口**: 执行面板 → 开始执行（选择"仅测试"）

**输入**:
| 输入项 | 路径/文件 | 说明 |
|--------|-----------|------|
| 测试配置 | `full_regr.json` | 步骤3生成的配置 |
| .out 文件 | `workspace/**/*.out` | 可执行文件 |
| DSS 执行器 | `ccs_dss` | CCS DSS 脚本执行器 |

**新增功能**:
- **硬件连接检测**: 批次执行前后检测硬件连接状态
- **断点续测**: 支持从指定批次继续执行
- **硬件错误恢复**: 检测到连接中断时弹出恢复对话框
- **断连自动重连**: 配置 `auto_resume=true` 时自动重试，无需手动干预
- **可配置重试策略**: `max_retries`（最大重试次数）、`retry_delay`（重试间隔）
- **多时间点内存导出**: 支持 after_load/before_run/after_run 三个时间点
- **多种结果判断方式**: breakpoint（断点地址）、memory（内存值）、expression（表达式）
- **FLASH项目支持**: 自动检测FLASH项目，配置编程选项，使用restart()代替reset()

**处理逻辑**:
```
1. 分批处理（每批 N 个用例）:
   batches = split_cases(cases, batch_size=10)
   
2. 为每批生成 DSS JS 脚本:
   js_script = generate_js_template(config)
   
3. 调用 DSS 执行:
   dss.bat temp_script.js
   
4. DSS 脚本内部流程:
   a. 连接目标板 (XDS100v3)
   b. 加载 .out 文件
   c. 根据配置在不同时间点导出内存段
   d. 设置断点（Right/IDLE 或自定义标签）
   e. 运行程序
   f. 检查结果（断点地址/内存值/表达式）
   g. 写入 summary.csv
   
5. 失败重试机制:
   a. 检测连接错误（CONNECTION_LOST_DETECTED）
   b. 自动重试（最多 max_retries 次）
   c. 重试间隔 retry_delay 秒
   d. 重试耗尽后才弹窗手动干预
```

**DSS 脚本核心逻辑**:
```javascript
// templates/dss_test.js.tmpl
function runTestCase(testCfg) {
    // 1. 判断是否需要 FLASH 编程
    var needFlashProgram = (testCfg.out.toUpperCase().indexOf("FLASH") >= 0);
    
    // 2. 加载程序
    session.memory.loadProgram(testCfg.out);
    
    // 3. FLASH项目特殊处理
    if (needFlashProgram) {
        // 配置FLASH编程选项：擦除 → 编程 → 验证
        session.flash.options.setString("FlashOperations", "Erase, Program, Verify");
        // 重启目标，使PC重新定位到程序入口
        session.target.restart();
    }
    
    // 4. 根据配置导出内存段
    var exportCfg = getExportConfig(testCfg.export_points);
    if (exportCfg.when === "after_load") {
        exportMemorySegments(testCfg, exportCfg.subdir);
    }
    
    // 5. 设置断点并运行
    // ...
    
    // 6. 检查结果（支持多种方式）
    if (testCfg.result_check.method === "breakpoint") {
        result = checkResultByBreakpoint(testCfg, pc);
    } else if (testCfg.result_check.method === "memory") {
        result = checkResultByMemory(testCfg);
    } else if (testCfg.result_check.method === "expression") {
        result = checkResultByExpression(testCfg);
    }
    
    // 7. 写入结果
    summary.write(testCfg.case_name + "," + result + "\n");
}
```

**输出产物**:
```
5_result_dat/                    # 测试数据输出
└── 2026-03-16-10-30/           # 时间戳目录
    ├── summary.csv             # 汇总结果
    │   test_algorithm_c,Success
    │   test_driver_asm,Error
    │   ...
    ├── summary.xlsx            # 彩色 Excel 报告
    │   （成功=绿色，失败=红色）
    ├── test_algorithm_c/       # C语言工程结果
    │   ├── summary.csv
    │   └── memory/
    │       ├── M0.dat
    │       ├── M1.dat
    │       └── ...
    └── ...

6_result_dat_logs/              # DSS 执行日志
└── 2026-03-16-10-30/
    ├── console_all.log         # 控制台输出
    └── DSS_Batch_*.xml         # DSS 详细日志
```

---

## 目录结构示例

```
d:\AutoTest_rebuild/
├── 1_project_templete/          # 模板工程目录（TEMPLATE模式使用）
│   └── ccs_insts_test/          # 标准CCS工程模板
│       ├── .project
│       ├── .cproject
│       └── ...
│
├── 2_source_file/               # 源文件目录（TEMPLATE模式使用）
│   ├── algorithm.c              # C语言测试代码
│   ├── driver.asm               # 汇编测试代码
│   └── ...
│
├── 3_generate_project/          # 生成的工程目录（已从版本控制移除）
│   ├── test_algorithm_c/        # 【TEMPLATE】生成的C工程
│   ├── test_driver_asm/         # 【TEMPLATE】生成的汇编工程
│   └── ...
│
├── 4_result_out/                # 构建产物目录
│   ├── test_algorithm_c.out
│   └── ...
│
├── 5_result_dat/                # 测试结果目录（已从版本控制移除）
│   └── 2026-03-16-10-30/
│       ├── summary.csv
│       └── ...
│
├── 6_result_dat_logs/           # 日志目录（已从版本控制移除）
│   └── ...
│
├── config/                      # 配置文件目录
│   ├── config.json              # 主配置文件
│   ├── config-28335.json        # F28335 RAM配置
│   ├── config-28335-flash.json  # F28335 FLASH配置
│   ├── config-28335-sram.json   # F28335 SRAM配置
│   ├── config-28335-xintf.json  # F28335 XINTF配置
│   └── config-test.json         # 测试配置
│
└── templates/                   # 模板文件
    └── dss_test.js.tmpl         # DSS脚本模板
```

---

## 入口脚本汇总

### 入口脚本汇总

### CLI 命令行入口

| 脚本 | 功能 | 用法 |
|------|------|------|
| `run.py` | 主入口 | `python run.py -c config.json` |
| `run.py --generate` | 只生成工程 | `python run.py -c config.json --generate` |
| `run.py --build` | 只构建工程 | `python run.py -c config.json --build` |
| `run.py --test` | 只执行测试 | `python run.py -c config.json --test` |
| `run.py --resume` | 断点续传 | `python run.py -c config.json --resume` |
| `run.py --steps test --start-batch N` | 从指定批次测试 | `python run.py -c config.json --steps test --start-batch 2` |

### GUI 图形界面入口

| 脚本 | 功能 | 用法 |
|------|------|------|
| `run_gui.py` | 启动 GUI | `python run_gui.py` |
| `run_gui.py -c` | 启动并加载配置 | `python run_gui.py -c config.json` |
| `run_gui.py --install-deps` | 自动安装依赖 | `python run_gui.py --install-deps` |

---

## 配置文件说明

### 主配置文件

**文件**: `config/config.json`

```json
{
  "_comment": "AutoTest 配置文件 - 支持C/ASM/CPP多种工程类型",
  
  "paths": {
    "template_dir": "D:/AutoTest_rebuild/1_project_templete/ccs_insts_test",
    "source_dir": "D:/AutoTest_rebuild/2_source_file",
    "generate_dir": "D:/AutoTest_rebuild/3_generate_project",
    "result_dir": "D:/AutoTest_rebuild/4_result_out",
    "ccs_workspace": "D:/AutoTest_rebuild/3_generate_project"
  },
  
  "tools": {
    "ccs_executable": "C:/ti/ccs1210/ccs/eclipse/eclipsec.exe",
    "ccs_dss": "C:/ti/ccs1210/ccs/ccs_base/scripting/bin/dss.bat",
    "ccxml": "C:/Users/你的用户名/ti/CCSTargetConfigurations/280039.ccxml"
  },
  
  "build": {
    "build_config": "Debug",
    "build_timeout": 600,
    "max_build_threads": 4,
    "do_generate": true,
    "do_build": true
  },

  "generation": {
    "generation_mode": "template"
  },
  
  "test": {
    "test_timeout": 45000,
    "test_batch_size": 10,
    "result_addr": "0x7625",
    "success_val": "0xCCCC",
    "error_val": "0xEEEE",
    "device": "Texas Instruments XDS100v3 USB Debug Probe_0",
    "cpu": "C28xx_CPU1",
    "auto_resume": true,
    "max_retries": 5,
    "retry_delay": 10
  },
  
  "result_check": {
    "method": "breakpoint",
    "success_label": "Right",
    "fail_label": "IDLE"
  },
  
  "memory_segments": {
    "segments": [
      {"name": "M0", "addr": "0x0000", "len": "0x200", "width": 15},
      {"name": "M1", "addr": "0x0400", "len": "0x200", "width": 15},
      {"name": "LS0", "addr": "0x8000", "len": "0x400", "width": 15},
      {"name": "LS1", "addr": "0x8800", "len": "0x400", "width": 15},
      {"name": "LS2", "addr": "0x9000", "len": "0x400", "width": 15},
      {"name": "LS3", "addr": "0x9800", "len": "0x400", "width": 15},
      {"name": "LS4", "addr": "0xa000", "len": "0x400", "width": 15},
      {"name": "LS5", "addr": "0xa800", "len": "0x400", "width": 15},
      {"name": "LS6", "addr": "0xb000", "len": "0x400", "width": 15},
      {"name": "LS7", "addr": "0xb800", "len": "0x400", "width": 15},
      {"name": "GS0", "addr": "0xc000", "len": "0x800", "width": 15},
      {"name": "GS1", "addr": "0xd000", "len": "0x800", "width": 15},
      {"name": "GS2", "addr": "0xe000", "len": "0x800", "width": 15},
      {"name": "GS3", "addr": "0xf000", "len": "0x800", "width": 15}
    ],
    "export_points": [
      {"when": "after_run", "enabled": true, "subdir": "Memory"}
    ]
  }
}
```

---

## 完整流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              完整流程图                                      │
└─────────────────────────────────────────────────────────────────────────────┘

[开始]
  │
  ▼
┌─────────────────┐
│ 读取配置文件     │ ← config/config.json
│ (config.py)      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 步骤1: 工程生成 (generator.py)           │
│                                         │
│  generation_mode = "template"            │
│    ├─ 读取 template_dir 模板工程         │
│    ├─ 扫描 source_dir 源文件             │
│    └─ 批量生成工程到 generate_dir        │
│                                         │
│  generation_mode = "manual"              │
│    └─ 验证 generate_dir 中的手动工程     │
│                                         │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ 步骤2: 工程构建  │────→│ 输出: .out 文件  │
│ (builder.py)     │     │ result_dir/*.out│
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ 步骤3: 配置生成  │────→│ 输出: 测试配置   │
│ (executor.py)    │     │ full_regr.json  │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ 步骤4: 测试执行  │────→│ 输出: 测试结果   │
│ (executor.py)    │     │ 5_result_dat/*  │
│                 │     │ summary.csv     │
│                 │     │ summary.xlsx    │
└────────┬────────┘     └─────────────────┘
         │
         ▼
[结束]
```

---

## 故障排查

### 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| E1001 配置文件不存在 | 路径错误 | 检查 -c 参数路径 |
| E1003 模板工程不存在 | template_dir 错误 | 确认模板工程路径 |
| E2002 源文件错误 | source_dir 中没有支持的文件 | 确保目录中有 .c/.cpp/.asm/.s 文件 |
| E3001 CCS 未找到 | CCS 路径错误 | 检查 ccs_executable 配置 |
| E3003 构建失败 | 代码错误或配置问题 | 查看 logs/ 目录下的详细日志 |
| E4001 DSS 未找到 | DSS 路径错误 | 检查 ccs_dss 配置 |
| E4005 测试超时 | 程序死循环或断点未触发 | 检查测试代码，增加 timeout |
| E4007 DSS 模板不存在 | 模板文件丢失 | 检查 templates/dss_test.js.tmpl |
| 连接丢失 | USB断开或目标板断电 | 检查硬件连接，启用 auto_resume 自动重连 |
| FLASH编程失败 | FLASH配置错误 | 检查项目名是否包含"FLASH"，确认FLASH配置 |

### 日志位置

```
logs/YYYY-MM-DD/autotest.log    # 主日志
logs/YYYY-MM-DD/*.log           # 各模块日志
6_result_dat_logs/YYYY-MM-DD-HH-MM/console_all.log  # DSS 控制台输出（UTF-8 BOM编码）
```

---

## 版本说明

- **v2.2.0** (增强版本): 可配置内存导出时机和结果判断方式，断连自动重连重试，FLASH项目支持
- **v2.1.0** (GUI版本): 图形化界面，硬件预检测，测试断点续测，实时状态显示
- **v2.0.0** (重构版本): 模块化架构，统一配置，完善日志，支持两种明确的生成模式
- **v1.0.0** (原始版本): 基础功能实现，仅支持 ASM 文件

---

## 相关文档

| 文档 | 说明 |
|------|------|
| `README.md` | 项目主文档，快速开始和配置说明 |
| `src/README.md` | 核心代码模块文档 |
| `gui/README.md` | GUI模块文档 |

---

*文档生成时间: 2026-03-18*
*更新说明: 添加GUI入口、硬件预检测流程、断点续测功能*
*最后更新: 2026-07-10*
*更新内容: 添加可配置内存导出时机、多种结果判断方式、断连自动重连、FLASH项目支持、新增配置文件*
