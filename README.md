# AutoTest - TI C2000 DSP 自动化测试框架

## 项目简介

AutoTest 是一个用于 **Texas Instruments C2000 系列 DSP 芯片**（如 TMS320F280039C）的 **通用自动化测试框架**，支持基于 CCS + DSS 的嵌入式软件测试流程。

### 主要功能

- **工程自动生成**：从模板工程批量生成测试工程
- **并行构建**：多线程并行构建 CCS 工程
- **自动化测试**：通过 DSS 脚本自动执行测试并导出内存数据
- **结果报告**：自动生成 CSV 和彩色 Excel 测试报告

### 适用场景

- **算法库测试**：FastRTS 等数学函数库的回归测试
- **功能验证**：嵌入式软件功能测试和验证
- **性能测试**：不同优化等级下的性能对比测试
- **内存分析**：测试过程中的内存数据导出和分析

### 测试示例

框架可用于测试各类 DSP 算法，例如：
- 三角函数：`sin`, `cos`, `atan`, `atan2`, `sincos`
- 指数对数：`exp`, `log`, `pow`
- 数学运算：`sqrt`, `isqrt`, `div`

支持多种优化等级（o0 ~ o4）的对比测试。

***

## 目录结构

```
d:\AutoTest_rebuild/
├── src/                         # 核心代码模块
│   ├── __init__.py              # 模块初始化
│   ├── config.py                # 配置管理
│   ├── logger.py                # 日志管理
│   ├── exceptions.py            # 自定义异常
│   ├── generator.py             # 工程生成
│   ├── builder.py               # 工程构建
│   ├── executor.py              # 测试执行
│   ├── pipeline.py              # 流水线管理
│   └── hardware_detector.py     # 硬件预检测
│
├── gui/                         # 图形界面模块
│   ├── main_window.py           # 主窗口
│   ├── widgets/                 # 界面组件
│   │   ├── config_panel.py      # 配置面板
│   │   ├── hardware_panel.py    # 硬件检测面板
│   │   ├── execute_panel.py     # 执行面板
│   │   ├── log_panel.py         # 日志面板
│   │   ├── case_table.py        # 用例表格
│   │   ├── path_selector.py     # 路径选择器
│   │   └── status_indicator.py  # 状态指示器
│   ├── workers/                 # 工作线程
│   │   ├── pipeline_worker.py   # 流水线工作线程
│   │   └── hardware_checker.py  # 硬件检测线程
│   ├── dialogs/                 # 对话框
│   │   ├── about_dialog.py      # 关于对话框
│   │   ├── error_dialog.py      # 错误对话框
│   │   └── hardware_error_dialog.py  # 硬件错误对话框
│   └── utils/                   # 工具函数
│       └── validators.py        # 输入验证
│
├── config/                      # 配置文件目录
│   └── config.json              # 主配置文件
│
├── templates/                   # 模板文件
│   └── dss_test.js.tmpl         # DSS 脚本模板
│
├── 0_pulgins/                   # 离线依赖包
│   ├── python-3.10.0-amd64.exe
│   ├── numpy-*.whl
│   ├── pandas-*.whl
│   └── openpyxl-*.whl
│
├── logs/                        # 日志输出目录
├── run.py                       # CLI主入口脚本
├── run_gui.py                   # GUI主入口脚本
└── README.md                    # 项目说明
```

***

## 快速开始

### 环境要求

- **Python**: 3.10+
- **CCS**: Code Composer Studio 12.1.0+
- **目标硬件**: TI C2000 DSP 开发板（如 TMS320F280039C）
- **调试器**: XDS100v3 或兼容调试器

### 安装依赖

```bash
# 方式一：使用离线包安装（推荐）
# 离线包位于 0_pulgins/ 目录

# 方式二：在线安装
pip install numpy pandas openpyxl
```

### 配置文件

编辑 `config/config.json`，配置你的环境：

```json
{
  "paths": {
    "template_dir": "D:/AutoTest_DEMO/1_project_templete/ccs_insts_test",
    "source_dir": "D:/AutoTest_DEMO/2_source_file",
    "generate_dir": "D:/AutoTest_DEMO/3_generate_project",
    "result_dir": "D:/AutoTest_DEMO/4_result_out",
    "ccs_workspace": "D:/AutoTest_DEMO/3_generate_project"
  },
  "tools": {
    "ccs_executable": "C:/ti/ccs1210/ccs/eclipse/eclipsec.exe",
    "ccs_dss": "C:/ti/ccs1210/ccs/ccs_base/scripting/bin/dss.bat",
    "ccxml": "C:/Users/你的用户名/ti/CCSTargetConfigurations/280039.ccxml"
  },
  "build": {
    "build_config": "Debug",
    "build_timeout": 600,
    "max_build_threads": 4
  },
  "test": {
    "test_timeout": 45000,
    "test_batch_size": 10,
    "device": "Texas Instruments XDS100v3 USB Debug Probe_0",
    "cpu": "C28xx_CPU1"
  }
}
```

### 运行测试

#### 命令行方式 (CLI)

```bash
# 执行全部步骤（生成 -> 构建 -> 测试）
python run.py -c config/config.json

# 只执行工程生成
python run.py -c config/config.json --generate

# 只执行工程构建
python run.py -c config/config.json --build

# 只执行测试
python run.py -c config/config.json --test

# 断点续传（跳过已完成的步骤）
python run.py -c config/config.json --resume

# 测试断点续测（从指定批次继续）
python run.py -c config/config.json --steps test --start-batch 2
```

#### 图形界面方式 (GUI)

```bash
# 启动 GUI
python run_gui.py

# 启动 GUI 并加载指定配置
python run_gui.py -c config/config.json

# 自动安装依赖并启动
python run_gui.py --install-deps
```

***

## 配置说明

### 路径配置 (`paths`)

| 字段              | 说明         | 示例                     |
| --------------- | ---------- | ---------------------- |
| `template_dir`  | CCS 模板工程目录 | `D:/project/template`  |
| `source_dir`    | 测试源文件目录    | `D:/project/source`    |
| `generate_dir`  | 生成的工程输出目录  | `D:/project/generated` |
| `result_dir`    | 构建产物存放目录   | `D:/project/result`    |
| `ccs_workspace` | CCS 工作空间   | `D:/project/generated` |

### 工具配置 (`tools`)

| 字段               | 说明                        |
| ---------------- | ------------------------- |
| `ccs_executable` | CCS 命令行工具路径（eclipsec.exe） |
| `ccs_dss`        | DSS 脚本执行器路径（dss.bat）      |
| `ccxml`          | 目标芯片配置文件                  |

### 构建配置 (`build`)

| 字段                  | 说明          | 默认值     |
| ------------------- | ----------- | ------- |
| `build_config`      | 构建配置名称      | `Debug` |
| `build_timeout`     | 单个工程构建超时（秒） | `600`   |
| `max_build_threads` | 最大并行构建线程数   | `4`     |
| `do_generate`       | 是否执行工程生成    | `true`  |
| `do_build`          | 是否执行工程构建    | `true`  |

### 工程生成配置 (`generation`)

| 字段              | 说明                      | 默认值       |
| --------------- | ----------------------- | --------- |
| `generation_mode` | 生成模式: `template` 或 `manual` | `template` |

- **template 模式**: 从模板工程 + 源文件批量生成测试工程
- **manual 模式**: 使用已手动配置好的工程（直接放在 generate_dir 中）

### 测试配置 (`test`)

| 字段                | 说明           | 默认值          |
| ----------------- | ------------ | ------------ |
| `test_timeout`    | 单个测试用例超时（毫秒） | `45000`      |
| `test_batch_size` | 每批执行的测试用例数   | `10`         |
| `result_addr`     | 测试结果存放地址     | `0x7625`     |
| `success_val`     | 测试成功标志值      | `0xCCCC`     |
| `error_val`       | 测试失败标志值      | `0xEEEE`     |
| `device`          | 调试器名称        | -            |
| `cpu`             | CPU 核名称      | `C28xx_CPU1` |

### 内存段配置 (`memory_segments`)

用于导出测试数据到 .dat 文件：

| 段名      | 起始地址          | 长度         | 用途     |
| ------- | ------------- | ---------- | ------ |
| M0      | 0x0000        | 0x200      | M0 RAM |
| M1      | 0x0400        | 0x200      | M1 RAM |
| LS0-LS7 | 0x8000-0xB800 | 0x400 each | LS RAM |
| GS0-GS3 | 0xC000-0xF000 | 0x800 each | GS RAM |

***

## 工作流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        AutoTest 工作流程                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: 工程生成                                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ 模板工程      │ +  │ 源文件        │ →  │ 测试工程      │       │
│  │ template_dir │    │ source_dir   │    │ generate_dir │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: 工程构建                                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ 导入 CCS     │ →  │ 并行构建     │ →  │ 收集 .out    │       │
│  │ Workspace    │    │ (多线程)     │    │ 构建产物     │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: 测试执行                                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ 生成 DSS     │ →  │ 连接目标板   │ →  │ 加载程序     │       │
│  │ JS 脚本      │    │ XDS100v3     │    │ .out 文件    │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ 设置断点     │ →  │ 运行测试     │ →  │ 检查结果     │       │
│  │ LAST_CMP     │    │ (超时监控)   │    │ 0xCCCC/EEEE  │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────┐    ┌──────────────┐                           │
│  │ 导出内存段   │ →  │ 生成报告     │                           │
│  │ M0/M1/LS/GS  │    │ CSV + Excel  │                           │
│  └──────────────┘    └──────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

***

## 输出结果

### 目录结构

```
5_result_dat/                   # 测试数据输出
└── 2026-03-16-10-30/          # 时间戳目录
    ├── summary.csv            # 汇总结果
    ├── summary.xlsx           # 彩色 Excel 报告
    ├── FASTRTS_atan_f32/      # 各用例结果
    │   ├── summary.csv
    │   └── memory/
    │       ├── M0.dat
    │       ├── M1.dat
    │       └── ...
    └── ...

logs/                           # 日志输出
└── 2026-03-16/                # 按日期分目录
    ├── autotest.log           # 主日志
    └── ...

6_result_dat_logs/              # DSS 执行日志
└── 2026-03-16-10-30/
    ├── console_all.log        # 控制台输出
    └── DSS_*.xml              # DSS 日志
```

### 结果报告格式

**CSV 格式：**

```
FASTRTS_atan_f32,Success
FASTRTS_atan_f32_o0,Success
FASTRTS_sin_f32,Error
...
```

**Excel 报告：**

- 带序号、测试用例名、状态列
- 成功用绿色背景标记
- 失败用红色背景标记
- 自适应列宽

***

## 错误诊断

### 错误码说明

| 错误码范围 | 类别       |
| ----- | -------- |
| 1xxx  | 配置相关错误   |
| 2xxx  | 工程生成相关错误 |
| 3xxx  | 工程构建相关错误 |
| 4xxx  | 测试执行相关错误 |
| 5xxx  | 日志相关错误   |

### 常见错误及解决方案

| 错误码   | 错误信息       | 解决方案                |
| ----- | ---------- | ------------------- |
| E1001 | 配置文件不存在    | 检查配置文件路径是否正确        |
| E1002 | 配置验证失败     | 检查配置字段值是否有效         |
| E1003 | 路径配置错误     | 确保所有目录和文件都存在        |
| E2001 | 模板工程不存在    | 检查 template\_dir 配置 |
| E3001 | CCS 未找到    | 检查 CCS 安装路径配置       |
| E3004 | 构建超时       | 增加 build\_timeout 值 |
| E4001 | DSS 执行器不存在 | 检查 CCS DSS 路径配置     |
| E4005 | 测试超时       | 增加 test\_timeout 值  |

### 日志查看

```bash
# 查看主日志
cat logs/2026-03-16/autotest.log

# 查看 DSS 执行日志
cat 6_result_dat_logs/2026-03-16-10-30/console_all.log
```

***

***

## 开发指南

### 核心模块说明

| 模块                   | 功能             |
| -------------------- | -------------- |
| `config.py`          | 配置加载、验证、路径解析   |
| `logger.py`          | 日志初始化、格式化、文件管理 |
| `exceptions.py`      | 自定义异常类和错误码     |
| `generator.py`       | 工程生成逻辑         |
| `builder.py`         | 工程导入和构建逻辑      |
| `executor.py`        | 测试执行和结果收集      |
| `pipeline.py`        | 流水线管理和步骤编排     |
| `hardware_detector.py` | 硬件预检测（USB设备检测） |

### GUI模块说明

| 模块                        | 功能           |
| ------------------------- | ------------ |
| `main_window.py`          | GUI主窗口       |
| `widgets/config_panel.py` | 配置编辑面板      |
| `widgets/hardware_panel.py` | 硬件检测面板    |
| `widgets/execute_panel.py` | 测试执行面板     |
| `widgets/log_panel.py`    | 日志显示面板      |
| `workers/pipeline_worker.py` | 流水线后台线程 |
| `workers/hardware_checker.py` | 硬件检测线程  |

### 扩展测试用例

1. 在 `source_dir` 中添加新的源文件（.asm 或 .c）
2. 运行 `python run.py -c config/config.json`
3. 新的测试工程会自动生成和测试

***

## 版本历史

### v2.1.0 (GUI版本)

- 图形化界面 (PyQt5)
- 硬件预检测功能
- 测试断点续测支持
- 实时用例状态显示
- 硬件连接错误自动检测和恢复

### v2.0.0 (重构版本)

- 模块化代码架构
- 统一配置管理
- 完善的日志系统
- 详细的错误诊断
- 断点续传支持
- DSS 模板分离

### v1.0.0 (原始版本)

- 基础测试功能
- 批量工程生成
- 并行构建
- DSS 测试执行

***

## 许可证

内部项目，仅供团队使用。
