# AutoTest 打包成 exe 分发方案（分析与设计）

> 目标：同事**不装 Python**，拿到一个文件夹、解压到自己电脑某处、双击 exe 就能用；源码运行与 exe 运行两种模式行为一致。
> 场景已收敛：**只打包 GUI（`run_gui.py`），不提供 CLI 入口**；不存在多人共用一台机器、不存在共享盘、不存在按人隔离的数据目录。多个同事各自拷贝一份完整包即可。
> 本文只做方案设计，**不涉及任何源码修改**。文中代码块均为"建议改法示意"。

---

## 0. 现状核查结论（只读调研）

### 0.1 入口与调用链

| 入口 | 作用 | 与本次打包的关系 |
|---|---|---|
| [run_gui.py](file:///d:/AutoTest_rebuild/run_gui.py) | GUI 入口（PyQt5） | ✅ **唯一打包入口** |
| [main_window.py](file:///d:/AutoTest_rebuild/gui/main_window.py) | 主窗口，加载配置后立即生成 `full_regr.json` | 打包目标内 |
| [run.py](file:///d:/AutoTest_rebuild/run.py) | CLI 入口（argparse `-c`） | ⚠️ 源码模式仍可用，**打包不考虑** |
| [import_and_run.py](file:///d:/AutoTest_rebuild/scripts/import_and_run.py) | 辅助脚本 | ⚠️ 源码模式仍可用，**打包不考虑** |
| [pipeline.py](file:///d:/AutoTest_rebuild/src/pipeline.py) | 公共流水线，含 `__main__` CLI | ⚠️ 作为库被 GUI 调用；其 `__main__` 打包不考虑 |

### 0.2 代码如何定位目录（关键）

| 用途 | 现状实现 | 打包后是否可用 |
|---|---|---|
| `config` 里的路径 | [config.py](file:///d:/AutoTest_rebuild/src/config.py#L281-L303)：绝对路径直用；相对路径**以配置文件所在目录为基准**（`_base_dir = config_path.parent`） | ✅ 天然兼容，是最健康的一处 |
| DSS 模板 | [executor.py](file:///d:/AutoTest_rebuild/src/executor.py#L74)：`Path(__file__).parent.parent / "templates" / "dss_test.js.tmpl"` | ⚠️ 冻结后 `__file__` 指向 `_internal/src/...`，必须把模板打进包，或改成外部路径 |
| `full_regr.json` | [test_config_generator.py](file:///d:/AutoTest_rebuild/src/test_config_generator.py#L115)：默认 `Path("full_regr.json")` | ❌ 依赖 CWD |
| 结果目录 `results` | [test_config_generator.py](file:///d:/AutoTest_rebuild/src/test_config_generator.py#L63)：`f"results/{ts}/{case}"`；[executor.py](file:///d:/AutoTest_rebuild/src/executor.py#L507) 再 `.resolve()` 转绝对路径传给 JS | ❌ 依赖 CWD |
| 批次日志 `logs/dss` | [executor.py](file:///d:/AutoTest_rebuild/src/executor.py#L190)、[executor.py](file:///d:/AutoTest_rebuild/src/executor.py#L1039) | ❌ 依赖 CWD |
| 程序日志 `logs` | [logger.py](file:///d:/AutoTest_rebuild/src/logger.py#L68)：`Path.cwd() / "logs" / 日期` | ❌ 依赖 CWD |
| 断点续测恢复时间戳 | [execute_panel.py](file:///d:/AutoTest_rebuild/gui/widgets/execute_panel.py#L551-L591)：`Path("results")`、`Path("logs/dss")`、`Path("full_regr.json")` | ❌ 依赖 CWD，且解析假定 `dat_dir` 第一段就是 `results` |
| GUI 用例 dat_dir 兜底 | [pipeline_worker.py](file:///d:/AutoTest_rebuild/gui/workers/pipeline_worker.py#L237) | ❌ 依赖 CWD |
| 汇总报告兜底 | [report_generator.py](file:///d:/AutoTest_rebuild/src/report_generator.py#L49) | ❌ 依赖 CWD |

**结论：`config` 内的路径已经是"配置文件相对"的，问题集中在 5 类写盘目录 + `full_regr.json` + 模板，全部是硬编码的 CWD/包内相对路径。**

### 0.3 写盘需求（必须可写）

- `logs/YYYY-MM-DD/`：运行日志（轮转）
- `logs/dss/<ts>/`：`console_all.log`、`DSS_Batch_*.xml`
- `results/<ts>/<case>/memory/*.dat`、`summary.csv`、`.xlsx`
- `full_regr.json`：GUI 加载/保存配置时重写
- `workspace/`：生成工程 + CCS `.metadata`（会 `rmtree(.metadata)` 重建）
- `4_result_out/`：构建产物收集
- `config/*.json`：GUI `Ctrl+S` 保存时原地写回
- 临时 `.js` 脚本：`tempfile.NamedTemporaryFile(delete=False)` → 留在 `%TEMP%`

### 0.4 subprocess 外部依赖

| 调用 | 位置 | 外部依赖 |
|---|---|---|
| `eclipsec.exe -application ...projectBuild` 构建 | [builder.py](file:///d:/AutoTest_rebuild/src/builder.py) | 本机安装的 CCS 12.1.0+ |
| `eclipsec.exe -application ...runScript` 跑 DSS | [executor.py](file:///d:/AutoTest_rebuild/src/executor.py#L590-L605) | CCS；`eclipsec` 由 `ccs_dss` 路径反推（`dss.bat` 上三级目录 + `eclipse/eclipsec.exe`） |
| `pnputil` / `wmic` / `powershell` 硬件预检 | [hardware_detector.py](file:///d:/AutoTest_rebuild/src/hardware_detector.py#L70-L135) | Windows 自带 |
| `[sys.executable, -m, pip, install, PyQt5]` | [run_gui.py](file:///d:/AutoTest_rebuild/run_gui.py#L35) | ❌ 冻结后 `sys.executable` 是 exe 本身，会"自己启动自己"，必须加 `if not frozen` |

### 0.5 第三方依赖

- 必需：**PyQt5**（GUI）、**numpy**、**pandas**、**openpyxl**（+ `et_xmlfile`，报表用，pandas/openpyxl 在 [report_generator.py](file:///d:/AutoTest_rebuild/src/report_generator.py#L80-L83) 内延迟导入）
- 无 `requirements.txt`；`0_pulgins/` 里是 cp310 的 wheel 和 Python 安装包 → **打包产物不需要它**
- 建议构建环境固定 **Python 3.10 x64**（与 wheel 的 `cp310` 对齐）

---

## 1. 打包方式对比与推荐

| 方案 | 启动速度 | 分发形态 | 升级 | 杀软风险 | 体积 | 结论 |
|---|---|---|---|---|---|---|
| **PyInstaller onedir（推荐）** | 快（1–3s） | 一个文件夹（zip 分发） | 只替换 `exe + _internal`，数据不动 | 中（bootloader 常见误报，可加白名单） | 200–350MB（zip 后 80–120MB） | ✅ 首选 |
| PyInstaller onefile | 慢（每次解压 3–10s 到 `%TEMP%`） | 单个 exe | 整包替换 | 中偏高（自解压行为更像"dropper"） | 同上，运行期翻倍占用 | ⚠️ 备选，仅在"必须一个文件"时 |
| Nuitka standalone | 快 | 文件夹 | 替换目录 | 低（原生编译） | 类似 | 备选，但构建链更重、排障资料少 |
| 便携 Python + `.bat` | 中 | 文件夹 | 替换 runtime | 低 | 大 | 不推荐（等于仍带环境，还多了 bat 入口） |

**推荐：PyInstaller `onedir` + `--windowed`（这是唯一交付形态，不提供 console 变体、不提供 CLI 入口）。**

理由：
1. 本项目是 Qt 桌面程序，onefile 每次启动解压 + Defender 实时扫描，首次体验很差；
2. 分发内容里本来就要带 `1_project_templete / 2_source_file / templates / config`，"一个文件夹"是可接受的交付形态；
3. 现场排障需要看 `logs/`，onedir 目录结构一目了然；
4. 升级只覆盖 `_internal/` 与 exe，历史 `results` 不受影响（onefile 替换单个大文件也更容易被杀软/占用卡住）。

代价：需要打 zip 分发；同事必须解压到**可写目录**再运行（见第 5 节写权限）；`--windowed` 带来的无控制台问题必须按 **3.4** 处理。

---

## 2. 推荐目录树（重点）

设计原则一句话：**exe 只装"程序"，配置与数据一律在外面；所有可写目录都跟着 exe 所在目录走（便携式），整包拷给谁就落在谁电脑的同一处。**

### 2.1 唯一推荐结构（便携式）

解压即用，整个文件夹可放任意盘（**建议全英文路径**）：

```
D:\AutoTest\
├─ AutoTestGUI.exe              # 【打包】唯一的 GUI 程序（windowed）
├─ _internal\                   # 【打包】PyInstaller 运行时（Qt DLL、Python、依赖）
├─ encrypt_flash_dat.py         # 【外置·随包】FLASH 段 dat 加密脚本（勾选"加密 FLASH 段 dat"时调用）
├─ templates\                   # 【外置·随包只读】★不要打进 exe
│  └─ dss_test.js.tmpl          #   现场要改 DSS 脚本时只替换此文件
├─ config\                      # 【外置·随包，可编辑】
│  ├─ config-28335-flash_new.json        # 日常配置（交付只带这四个）
│  ├─ config-28335-sram.json
│  ├─ config-28335-xintf.json
│  ├─ config-fpga-xintf-test.json
│  └─ config.default.json                # 由上述四个派生的交付模板（tools 需按机器改）
├─ 1_project_templete\          # 【外置·随包只读】模板 CCS 工程（体积大，随版本更新）
│  └─ TEST_Fix_ALLINS\
├─ 2_source_file\               # 【外置·随包只读】测试源文件
├─ workspace\          # 【运行期生成·随 exe 定位】CCS 工作空间（含 .metadata）
├─ 4_result_out\                # 【运行期生成·随 exe 定位】构建产物
├─ results\                # 【运行期生成·随 exe 定位】<YYYY-MM-DD-HH-MM>\<case>\memory\*.dat
├─ logs/dss\           # 【运行期生成·随 exe 定位】DSS 批次日志
├─ logs\                        # 【运行期生成·随 exe 定位】logs\<当天日期>\autotest.log
├─ full_regr.json               # 【运行期生成·随 exe 定位】GUI 加载配置时自动生成
└─ README_使用说明.txt
```

说明：
- "随 exe 定位"= 代码里统一解析成 `exe 所在目录/<子目录>`，**与双击时的当前工作目录无关**（快捷方式把"起始位置"设错也不受影响）。
- 不再有 `AutoTestCLI.exe`，也不再分发任何 `.bat` 启动器：唯一入口就是双击 `AutoTestGUI.exe`。
- `0_pulgins/` **不要进分发包**（那是给源码用户离线装 Python/轮子用的），打了只会增大体积并提高杀软扫描命中率。
- 不存在"每人一个数据目录"的设计：每个同事拿到自己那份完整文件夹，目录里就只有他自己的数据。
- **`config/config.json` 不进交付包**（历史遗留，`template_dir` 指向不存在的目录）。交付只带四个日常配置 + `config.default.json`；`run_gui.py` 启动时不自动加载任何配置，不会落到 `config.json` 上。

### 2.2 "哪些打进 exe"一览

| 内容 | 是否打进 exe | 位置 | 说明 |
|---|---|---|---|
| `src/`、`gui/`、`run_gui.py` | ✅ 打进（编译进 `_internal`） | `_internal/` | 随包只读 |
| `templates/dss_test.js.tmpl` | ❌ 默认外置（可同时打进作兜底） | `<程序目录>/templates` | 随包只读，便于现场替换 |
| `encrypt_flash_dat.py` | ⭕ 同时打进 + 外置 | `<程序目录>/encrypt_flash_dat.py` | 外置优先，缺失时才用包内副本；两项都缺则该选项报错 |
| `1_project_templete` | ❌ 外置 | `<程序目录>/1_project_templete` | 随包只读 |
| `2_source_file` | ❌ 外置 | `<程序目录>/2_source_file` | 只读输入 |
| `config/config-28335-*.json`、`config/config.default.json` | ❌ 外置 | `<程序目录>/config` | 只带四个日常配置 + default；`config.json` 分不带走 |
| `workspace`、`4_result_out` | ❌ 外置 | `<程序目录>` | 运行期可写 |
| `results`、`logs/dss`、`logs`、`full_regr.json` | ❌ 外置 | `<程序目录>` | 运行期可写 |
| `0_pulgins` | ❌ 不打包也不分发 | — | — |
| CCStudio（eclipsec/dss.bat/ccxml） | ❌ 不打进 | 本机 CCS 安装路径 | 每台机器自行安装 |

---

## 3. 路径解析改造（重点）

### 3.1 改造原则

只需要**两个根**，不要引入多余抽象：

1. `APP_ROOT`：程序目录（**也是所有数据目录的根**）。源码模式 = 项目根；冻结模式 = `Path(sys.executable).parent`。
2. `BUNDLE_ROOT`：打包资源根。冻结模式 = `sys._MEIPASS`（onedir 下即 `_internal`）；源码模式 = `APP_ROOT`。

规则：
- **可写数据一律写 `APP_ROOT/<子目录>`**，禁止再用 `os.getcwd()` 拼相对路径。
- **资源查找顺序**：`APP_ROOT/<rel>`（外置优先，便于现场改模板）→ `BUNDLE_ROOT/<rel>`（打包兜底）→ 报错。
- `dat_dir` 直接生成**绝对路径**写进 `full_regr.json`，避免"换个工作目录续测就找不到数据"。
- **过渡期兜底**：`run_gui.py` 启动时先 `os.chdir(APP_ROOT)`，这样即使有遗漏的相对路径，exe 双击与源码运行也能对齐（双击 exe 的 CWD 通常是 exe 目录，但快捷方式可改"起始位置"，必须显式 chdir + 后续集中替换）。
- 不引入环境变量、不引入 `--data-root`：没有多人场景，加了只是无用配置项。

### 3.2 建议的 `src/runtime_paths.py`（示意，不落地）

```python
# src/runtime_paths.py —— 所有路径的唯一入口
import sys
from pathlib import Path

def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))

def app_root() -> Path:
    """程序目录，同时也是数据目录的根"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]      # 项目根

def bundle_root() -> Path:
    """打包资源根；源码模式与 app_root 相同"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", app_root()))
    return app_root()

def app_path(rel: str) -> Path:
    """可写数据：一律以 exe/项目根 为基准"""
    return (app_root() / rel).resolve()

def resource_path(rel: str) -> Path:
    """只读资源：外置优先，打包资源兜底"""
    for base in (app_root(), bundle_root()):
        p = base / rel
        if p.exists():
            return p
    return app_root() / rel                        # 交给调用方报"文件不存在"
```

### 3.3 关键改动位置（只列 GUI 实际会走到的路径）

| 序号 | 位置 | 现状 | 改为 |
|---|---|---|---|
| 1 | [executor.py](file:///d:/AutoTest_rebuild/src/executor.py#L74) | `Path(__file__).parent.parent / "templates" / ...` | `resource_path("templates/dss_test.js.tmpl")` |
| 2 | [logger.py](file:///d:/AutoTest_rebuild/src/logger.py#L68) | `Path.cwd() / "logs" / 日期` | `app_path("logs") / 日期` |
| 3 | [executor.py](file:///d:/AutoTest_rebuild/src/executor.py#L190) | `Path("logs/dss") / ts` | `app_path("logs/dss") / ts` |
| 4 | [executor.py](file:///d:/AutoTest_rebuild/src/executor.py#L1039) | `Path("logs/dss")`（清理） | `app_path("logs/dss")` |
| 5 | [test_config_generator.py](file:///d:/AutoTest_rebuild/src/test_config_generator.py#L63) | `f"results/{ts}/{case}"` | `str(app_path("results") / ts / case)`（**绝对路径**，统一 `/`） |
| 6 | [test_config_generator.py](file:///d:/AutoTest_rebuild/src/test_config_generator.py#L115) | `Path("full_regr.json")` | `app_path("full_regr.json")` |
| 7 | [test_config_generator.py](file:///d:/AutoTest_rebuild/src/test_config_generator.py#L159) | 同上（工作空间自动生成分支） | 同上 |
| 8 | [test_config_generator.py](file:///d:/AutoTest_rebuild/src/test_config_generator.py#L183) | `out_file.resolve()` | 保持绝对（无需改） |
| 9 | [report_generator.py](file:///d:/AutoTest_rebuild/src/report_generator.py#L49) | `Path("results") / ts` | `app_path("results") / ts` |
| 10 | [execute_panel.py](file:///d:/AutoTest_rebuild_bak/gui/widgets/execute_panel.py#L552-L579) | 三处 CWD 相对目录 | `app_path(...)`；时间戳解析**保持现有三元写法**（`parts[1] if parts[0]=="results" else parts[-2]`），相对/绝对两种目录形态都能取对 |
| 11 | [pipeline_worker.py](file:///d:/AutoTest_rebuild/gui/workers/pipeline_worker.py#L237) | `f"results/{case.name}"` | `str(app_path("results") / case.name)` |
| 12 | [run_gui.py](file:///d:/AutoTest_rebuild/run_gui.py#L19) | `sys.path.insert` 无条件执行 | 加 `if not is_frozen()`；并在 `main()` 最前 `os.chdir(app_root())` |
| 13 | [run_gui.py](file:///d:/AutoTest_rebuild/run_gui.py#L28-L39) | `--install-deps` 用 `sys.executable -m pip` | 冻结模式下直接禁用该参数（依赖已随包） |
| 14 | [config.py](file:///d:/AutoTest_rebuild_bak/src/config.py#L303) | `_base_dir = config_path.parent` | **保持不变**（正确设计）；四份随包配置的 `paths` 已改成相对路径；`config.json` 不进交付包 |
| 15 | [executor.py](file:///d:/AutoTest_rebuild/src/executor.py#L507) / `:750` | `Path(case["dat_dir"]).resolve()` | 第 5/7 项已产出绝对路径，这里保留 `resolve()` 也无害 |

> `run.py`、`scripts/import_and_run.py`、`src/pipeline.py` 的 `__main__` **不在上表**，它们仍是 CLI 使用的入口，源码模式下继续可用，但打包不考虑（详见 3.7）。

### 3.4 无控制台（`--windowed`）的必做改造（重点）

`--windowed` 后进程没有控制台，`sys.stdout` / `sys.stderr` 为 `None`。这会连带影响日志、第三方库打印、以及异常可见性，**属于必做项，不是可选项**：

| 序号 | 问题 | 现状风险 | 必做改法 |
|---|---|---|---|
| A | [logger.py](file:///d:/AutoTest_rebuild/src/logger.py#L80) 的 `logging.StreamHandler(sys.stdout)` | 无控制台时 stream 为 `None`，`emit` 报错/日志丢失；`ColoredFormatter` 的 ANSI 转义也无意义 | 入口处判断 `if sys.stdout is None: sys.stdout = open(os.devnull, "w")`（同理 `sys.stderr`），再 `setup_logger()`；或给控制台 handler 加 `if sys.stdout is None` 跳过，仅保留文件 handler |
| B | 第三方库/子进程的 stdout 打印 | `pandas`、`openpyxl` 的 warning；`eclipsec/DSS` 的输出 | 子进程已用 `stdout=PIPE`（[builder.py](file:///d:/AutoTest_rebuild/src/builder.py)、[executor.py](file:///d:/AutoTest_rebuild/src/executor.py)），不受影响；库层 warning 交给 logging 文件即可；仍需 A 的 stdout/stderr 兜底 |
| C | 未捕获异常 | GUI 里槽函数抛异常时 `sys.excepthook` 打印到 stderr（`None`）→ 用户只看到"没反应" | 安装自定义 `sys.excepthook`：写 `logs/crash_YYYYMMDD_HHMMSS.log`（traceback + 环境信息），并 `QMessageBox.critical("程序异常", 摘要 + 日志路径)` |
| D | 启动阶段（`QApplication` 创建前）失败 | 例如缺 DLL、config 解析失败 → 无窗口、无提示，双击"闪退" | `run_gui.py` 的 `main()` 用 `try/except BaseException` 包住：先写 `logs/startup_error.log`，再用 `ctypes.windll.user32.MessageBoxW` 弹原生提示（此时 Qt 可能还没起来） |
| E | 业务错误原本靠 print 提示 | windowed 下用户看不到 | 统一改为 `QMessageBox`（GUI 层已有 `error_dialog`、`hardware_error_dialog` 可复用）或写日志 |
| F | `--install-deps` 分支 | 冻结后 `sys.executable -m pip` 会再次启动 exe | 见 3.3 第 13 项：冻结模式禁用 |

> 结论：**`sys.stdout/stderr` 兜底 + 全局 `excepthook` 弹窗 + 启动期原生 MessageBox** 是 `--windowed` 的三件套，必须与路径改造一起做，否则同事遇到的就是"双击没反应/闪退没日志"。

### 3.5 随包配置的写法（四个日常配置 + `config.default.json`）

四个日常配置（`config-28335-flash_new.json`、`config-28335-sram.json`、`config-28335-xintf.json`、`config-fpga-xintf-test.json`）的 `paths` 已改为相对路径（相对配置文件自身，[config.py](file:///d:/AutoTest_rebuild_bak/src/config.py#L303)），解压到任意盘都能用：

```json
{
  "paths": {
    "template_dir": "../1_project_templete\\ccs_insts_test",
    "source_dir": "../2_source_file",
    "generate_dir": "../workspace",
    "result_dir": "../4_result_out",
    "ccs_workspace": "../workspace"
  },
  "tools": {
    "ccs_executable": "C:/ti/ccs1210/ccs/eclipse/eclipsec.exe",
    "ccs_dss": "C:/ti/ccs1210/ccs/ccs_base/scripting/bin/dss.bat",
    "ccxml": "C:/Users/你的名字/ti/CCSTargetConfigurations/f28335_100v2.ccxml"
  }
}
```

- 这四个配置都是 `generation_mode: manual`，生成阶段只校验 `generate_dir` 与 `source_dir`，`template_dir` 不参与，因此它指向的 `ccs_insts_test` 缺失**不影响日常使用**（保留原值，未改目标目录）。
- `tools.*` 保持绝对：CCS 安装路径对多数机器一致，`ccxml` 必须由每台机器改成自己的。
- `config.default.json` 由 `config-28335-flash_new.json` 派生：业务路径相对、`ccxml` 换成占位路径。**占位路径必须是合法 Windows 文件名**（`Path.resolve()` 不接受 `<用户名>` 这类非法字符，会抛 `WinError 123`）。
- `run_gui.py` 启动时**不自动加载**任何配置；同事点"文件 → 打开配置"选择四个之一即可。因此不需要"首次启动复制 config.json"逻辑，`config/config.json` 也不进交付包。

### 3.6 两种运行模式兼容性对照

| 场景 | `APP_ROOT` | `BUNDLE_ROOT` | 数据落点 | 结果 |
|---|---|---|---|---|
| `python run_gui.py`（源码模式） | 项目根 | 项目根 | 项目根 | 与今天行为一致（`results` 就在项目根） |
| 双击 `AutoTestGUI.exe` | exe 所在目录 | `_internal` | exe 所在目录 | 数据与 exe 同级，便携 |
| 从快捷方式启动（"起始位置"乱设） | 仍为 exe 目录 | `_internal` | exe 目录 | 不受 CWD 影响（已集中化 + chdir 兜底） |

> 若只做最小改动、暂不动 11 处硬编码：至少在 `run_gui.py` 入口做 `os.chdir(app_root())`。这能解决 90% 的错位问题；但仍建议按 3.3 全量替换（工作量集中在 5 个文件），否则断点续测等场景仍会错位。

### 3.7 仅 CLI 使用的入口如何处理

以下入口**不打包、不作改动要求**，源码模式继续可用：

- [run.py](file:///d:/AutoTest_rebuild/run.py)：CLI 批量跑，继续用 `python run.py -c config.json`；
- [import_and_run.py](file:///d:/AutoTest_rebuild/scripts/import_and_run.py)：导入已有工程，继续用 `python scripts/import_and_run.py ...`；
- [pipeline.py](file:///d:/AutoTest_rebuild/src/pipeline.py#L238) 的 `main()`：`python -m src.pipeline ...`。

注意：这些入口调用的仍是 [executor.py](file:///d:/AutoTest_rebuild/src/executor.py)、[logger.py](file:///d:/AutoTest_rebuild/src/logger.py) 等公共模块，3.3 的路径改造对它们同样生效（数据会落到项目根，行为不变）。**不要为 CLI 单独做一套路径逻辑**，否则又会分裂成两种模式。

---

## 4. 升级、迁移与整包复制

### 4.1 升级策略
- **程序目录整体替换**：新版本解压后覆盖 `AutoTestGUI.exe` + `_internal/`；`templates/` 有变更才覆盖；`1_project_templete / 2_source_file` 按团队节奏单独更新。
- **绝不覆盖同事已调好的 `config-28335-*.json`**：只发布 `config.default.json`（以及四份配置的原始副本）。
- **数据目录完全不碰**：`3/4/5/6`、`logs`、`full_regr.json` 保留，历史结果可继续查看与续测。
- 建议 exe 加版本号（文件属性 / 关于对话框），便于现场确认同事用的是哪一版。

### 4.2 迁移已有数据
- `results/`、`logs/dss/`、`logs/` 可直接整目录移动到新程序目录下，目录名（时间戳）不变 → 断点续测"按最新目录恢复时间戳"的逻辑仍成立。
- 旧 `full_regr.json` 里的 `dat_dir` 是**相对路径**（`results/<ts>/<case>`）。
  - 最简做法：迁移后删掉旧 `full_regr.json`，让 GUI 重新生成（`load_config` / `save_config` 都会触发 `_generate_test_config`）。
  - 若要保留续测：批量把 `dat_dir` 前缀替换为新 `APP_ROOT/results` 的绝对路径（一次性脚本即可）。
- `workspace`、`4_result_out` 属于可重建产物，迁移时建议清空重建，避免 `.metadata` 残留导致 Eclipse 报错。

### 4.3 "整包复制给别人"的注意点（重要）

把自己的整个文件夹拷给同事，等价于把"你的运行痕迹"一起带过去，必须处理：

1. **分发前清空运行数据**（这些目录/文件都不该带过去）：
   - `results/`：体积最大，且同事点"断点续测"会把**你的**最新时间戳目录当成本次任务继续跑，结果直接写错地方；
   - `logs/dss/`：DSS 批次日志是上一台机器的；
   - `logs/`：含本机绝对路径、用户名等；
   - `full_regr.json`：里面的 `dat_dir`/`out` 全是你的绝对路径；
   - `workspace/`（尤其 `.metadata`）：Eclipse 工作空间元数据带机器指纹，残留会引发构建报错；
   - `4_result_out/`：旧构建产物。
   - 预建**空目录**即可：`workspace / 4_result_out / results / logs/dss / logs`。
2. **config 要重置**：
   - 交付只带四个日常配置 + `config.default.json`，**不要**带 `config.json`（历史遗留、`template_dir` 指向不存在的目录）；
   - 四个配置里的 `tools.ccxml` 是开发机路径，分发前提醒同事改成自己的；不想泄露本人路径就统一换成合法占位路径（如 `C:/Users/你的名字/...`）；
   - 不存在"首次启动自动复制 config.json"的行为：`run_gui.py` 不依赖任何默认配置。
3. **必须保留**：`templates/`、`1_project_templete/`、`2_source_file/`、`_internal/`（漏了 `_internal` 只剩 exe 是完全跑不起来的）。
4. **不要混入构建垃圾**：`.venv-build/`、`build/`、`dist/`、`__pycache__/`、`.pytest_cache/`、`0_pulgins/` 都排除在交付目录外。
5. **复制方式**：整目录复制（保留层级），不要只拷 exe；用 zip 打包可避免复制过程中丢 DLL。
6. **目标机首跑检查**：解压路径可写、路径以英文为主、杀软白名单已加（见第 5 节）。

---

## 5. 可能的坑（打包与运行）

| 类别 | 现象 | 规避 |
|---|---|---|
| **杀软误报** | Defender/360 报 `AutoTestGUI.exe` 为木马/勒索 | ① 用 onedir 不用 onefile；② `--noupx`（UPX 压缩显著提高误报）；③ 交付前提交公司 IT 加白名单/签名；④ 不要把 `python-3.10.0-amd64.exe`、wheel 打进包 |
| **首次启动慢** | 双击后 3–10 秒无反应 | onedir 已显著改善；Defender 实时扫描仍会拖慢首启，首次运行后正常；建议 IT 把程序目录加入排除项 |
| **写权限** | 放 `C:\Program Files` 或只读位置 → 起不来 / 日志为空 / 测试结果写不出 | 必须解压到用户可写目录（`D:\AutoTest`、`%LOCALAPPDATA%`、U 盘） |
| **中文路径** | CCS/Eclipse 对中文 workspace 路径支持差；`.metadata`、DSS 报路径错误；`C:\Users\张三\ti\...ccxml` 也含中文 | 程序目录、数据目录、`1_project_templete`、`workspace` 全部用英文路径；`ccxml` 路径实测通过后再固化到 config |
| **无控制台** | 日志缺失、异常无提示、双击"闪退没反应" | 唯一形态是 `--windowed`，必须落实 **3.4** 的三件套（stdout/stderr 兜底、excepthook 弹窗、启动期原生 MessageBox） |
| **windowed 下 stdout 为 None** | `logging.StreamHandler(sys.stdout)` 在无控制台时 emit 报错/日志丢失 | 见 3.4 A：入口把 `sys.stdout/stderr` 指向 `os.devnull`，或跳过控制台 handler 只保留文件日志 |
| **Qt 插件缺失** | `could not find or load the Qt platform plugin "windows"` | 用 PyInstaller 自带 PyQt5 hook，不要手工裁剪 `platforms/qwindows.dll`；必要时 `--collect-all PyQt5` |
| **缺失隐藏依赖** | 报表导出时才报 `ModuleNotFoundError: openpyxl / et_xmlfile` | spec 里加 `hiddenimports=['openpyxl','et_xmlfile']`（延迟导入容易被漏） |
| **图标** | 默认 Python 图标 | 需要新增 `.ico` 资源并 `--icon`；仓库当前**没有** ico，需要一并准备（属新增资源，非本轮改动） |
| **VC 运行库** | 干净机器提示缺少 `VCRUNTIME140.dll` | 随包附带 VC++ 2015-2022 x64 运行库，或说明由 IT 统一安装 |
| **`%TEMP%` 残留** | `tempfile.NamedTemporaryFile(delete=False)` 的 `.js` 不清理 | onefile 解压目录 + 临时脚本会累积；建议后续加清理（非打包阻塞项） |
| **路径长度** | Eclipse 工程路径 > 260 字符报错 | 程序与数据目录尽量短（如 `D:\AutoTest`） |
| **从网络位置/U 盘直接运行** | 启动卡顿、被 SmartScreen 拦 | 复制到本机本地盘再运行；交付用 zip，先解压后运行 |
| **中文乱码** | `console_all.log` 乱码 | 代码已用二进制写 BOM 规避；保持 DSS 输出 UTF-8 路径不变 |

---

## 6. 打包步骤（建议执行顺序）

### 6.1 构建环境
```powershell
# 固定 Python 3.10 x64，独立 venv，避免把开发机的杂包带进包
py -3.10 -m venv .venv-build
.\.venv-build\Scripts\python -m pip install -U pip
.\.venv-build\Scripts\pip install pyinstaller PyQt5 numpy pandas openpyxl
```

### 6.2 打包命令（唯一入口）
```powershell
# onedir + 无控制台；模板作为兜底一起带上
pyinstaller --noconfirm --clean --onedir --windowed --noupx ^
  --name AutoTestGUI ^
  --add-data "templates;templates" ^
  --hidden-import openpyxl --hidden-import et_xmlfile ^
  run_gui.py
```

- 不再有 `--console` 变体、不再为 `run.py` 出第二个 exe；
- 需要 CLI 的场合走源码模式（`python run.py -c ...`），不属于交付内容。

### 6.3 正式交付（建议 spec + 便携式组装）
- 用 `AutoTestGUI.spec` 固定 `datas / hiddenimports / excludes`（排除 `tkinter`、`matplotlib`、`PyQt5.QtWebEngine*` 等未用模块以减体积）。
- 产出 `dist/AutoTestGUI/` 后，按 **2.1** 的目录树组装发布包：
  - 复制 `AutoTestGUI.exe`、`_internal/`
  - 复制 `templates/`、`1_project_templete/`、`2_source_file/`
  - 复制 `config/` 下四个日常配置 + `config.default.json`（**不带 `config.json`**）
  - 预建**空目录** `workspace / 4_result_out / results / logs/dss / logs`
  - 删除 `full_regr.json`（若存在）
  - 附 `README_使用说明.txt`（含：改 config 的 `tools` 三项、放英文可写路径、异常时看 `logs/`）
- 打 zip 分发；版本号写进 zip 名（如 `AutoTestGUI_v1.2.0_20261109.zip`）。
- 打 zip 前逐项对照 **4.3** 的清理清单，避免把运行数据/绝对路径配置/构建垃圾带出去。

### 6.4 验收清单（必须在**没装 Python 的干净机器**上做）

1. 解压到可写目录，双击 `AutoTestGUI.exe` 能起 GUI，无黑框、无缺 DLL 报错；
2. 启动时不自动加载任何配置；打开四个日常配置之一（如 `config-28335-flash_new.json`），配置面板路径正常显示（相对路径被解析成绝对路径）；
3. 硬件检测可用（`pnputil/powershell` 能调起）；
4. 有 CCS 的机器上：生成 → 构建 → 测试全链路通过，`results/<ts>/<case>/memory/*.dat` 正常落盘；
5. 断点续测能恢复到正确时间戳（验证 `execute_panel` 三处路径改造）；
6. 报表 `.xlsx` 能导出（验证 openpyxl 已打包）；
7. `logs/`、`logs/dss/`、`full_regr.json` 都落在 exe 同级目录，而不是 `%TEMP%` 或 `C:\Windows\System32`；
8. 把快捷方式的"起始位置"改成别的目录再启动 → 数据仍落在 exe 同级（验证不依赖 CWD）；
9. **无控制台专项**：故意让某个用例失败/传入错误 config → 必须弹出错误对话框且 `logs/` 有对应记录，而不是静默退出；
10. 故意在启动阶段制造异常（如临时改坏 config JSON）→ 能看到原生提示框并生成 `logs/startup_error.log`；
11. 放到只读目录运行 → 应给出明确报错/提示，而不是静默失败；
12. 中文用户名机器复测一次（ccxml 路径含中文）；
13. 用 4.3 清理后的"干净交付包"再做一次全流程，确认不依赖开发机的任何残留。

---

## 7. 结论（一页版）

1. **方式**：PyInstaller **onedir + `--windowed`**，唯一入口 `run_gui.py`；不出 CLI、不出 console 变体；不用 onefile（首启慢、误报高），不用 UPX。
2. **目录**：一套便携式结构。exe/`_internal` 只装程序；`templates`、`1_project_templete`、`2_source_file`、`config/`（四个日常配置 + `config.default.json`，不含 `config.json`）外置随包；`3/4/5/6`、`logs`、`full_regr.json` 外置且**跟随 exe 所在目录**；`0_pulgins` 不分发。每个同事一份完整拷贝。
3. **路径**：只保留 `APP_ROOT` + `BUNDLE_ROOT` 两个根，新增唯一入口 `runtime_paths`；资源"外置优先、包内兜底"；数据一律 `app_path(...)`，不再用 `getcwd()`；随包 config 用相对路径，只有 `tools.*` 保持绝对；`run_gui.py` 入口加 `os.chdir(APP_ROOT)` 兜底。不引入 `DATA_ROOT`/环境变量。
4. **无控制台**：必做三件套——`sys.stdout/stderr` 指向 `os.devnull`、全局 `excepthook` 写崩溃日志并弹窗、启动期用原生 `MessageBox` 兜底。
5. **升级/迁移**：程序目录覆盖式升级，config 只发 `.default` 不覆盖，数据目录不动；旧 `full_regr.json` 迁移后重新生成或批量替换 `dat_dir` 前缀。
6. **整包复制**：分发前清空 `results / logs/dss / logs / full_regr.json / workspace(.metadata) / 4_result_out`，config 重置为 default，保留 `templates / 1_project_templete / 2_source_file / _internal`，排除构建垃圾。
7. **坑位**：杀软白名单、不装到 Program Files、全英文短路径、`--windowed` 下 `sys.stdout is None`、openpyxl 隐藏导入、Qt 平台插件、VC 运行库、`0_pulgins` 与 wheel 不要打进包、不要从 U 盘/网络位置直接运行。
8. **CLI 入口**：`run.py` / `import_and_run.py` / `pipeline.__main__` 仅保留源码用法，不作为交付物、不单独改造。
