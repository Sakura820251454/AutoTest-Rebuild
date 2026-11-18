# 回归测试（tests）

无硬件、无板卡、无 CCS 编译条件下的自动化回归集。目的：改完代码后一条命令确认既有功能没被破坏。

- 只使用标准库 `unittest` 与项目已有的 PyQt5，没有新增依赖。
- 只新增/修改 `tests/` 下的文件；`src/`、`gui/` 的缺陷修复走独立提交，不用测试代偿。
- 每个用例使用独立临时目录，结束即删除；不写真实配置文件，不写 `_packaging/release`，不运行 PyInstaller。

## 怎么跑

在项目根目录（`d:\AutoTest_rebuild_bak`）执行：

```powershell
# 全量回归（推荐，日常只需要这一条）
python tests\run_checks.py

# 只跑某个模块（调试时用）
python tests\run_checks.py tests.test_config_parse

# 也可以直接用 unittest
python -m tests.test_config_parse
python -m unittest tests.test_gui_config_panel -v
```

输出每个用例一行 `[PASS] / [FAIL] / [ERROR] / [SKIP]`，末尾给出总数、通过数、失败数、错误数、跳过数与耗时。
全部通过时退出码为 `0`，任何失败/错误退出码为 `1`，可直接接 CI 或批处理。

GUI 用例自动设置 `QT_QPA_PLATFORM=offscreen`，不会弹窗、不会阻塞。

## 覆盖范围

| 测试模块 | 覆盖的既有功能 |
| --- | --- |
| `test_runtime_paths.py` | `is_frozen/app_root/bundle_root/app_path/resource_path/to_posix/path_key`；源码模式与冻结模式两套语义（冻结状态用 monkeypatch 模拟） |
| `test_config_parse.py` | 新旧两种配置格式、字段缺失走默认值、相对路径按配置文件目录解析、`${VAR}`/`%VAR%` 展开、`generate_dir` 与 `ccs_workspace` 单一真源、用例继承全局段/判定、注释键处理、`validate()` 成功与失败分支 |
| `test_config_save.py` | 程序目录内写相对路径、目录外写绝对路径、统一正斜杠、注释保留、保存后重新加载路径语义不变、用例 `dat_dir` 转正斜杠 |
| `test_test_config_generator.py` | 扫描 `.out` 生成 `full_regr.json`、无产物返回 None 且不落盘、优先使用配置内用例、`dat_dir` 为绝对正斜杠、`is_flash/segments/result_check` 传递 |
| `test_config_field_guard.py` | 以 dataclass 字段为真源断言 `PipelineWorker._config_to_dict()` 不漏字段；全字段哨兵值经"Config → 临时 JSON → Config.load"逐字段值与类型比对；`results_dir` 自定义绝对路径专项往返 |
| `test_executor_postprocess.py` | `_post_process_dat_files` 剥新旧 CCS 文件头、幂等、普通数据不误伤；`_copy_case_projects` 过滤中间文件、旧文件清理、无工程根时安全返回、开关关闭时不复制 |
| `test_flash_encrypt.py` | 进程内加载根目录 `encrypt_flash_dat.py`、`FLASH0~3.dat` 产出与行数、输入不被改写、回读校验、解密还原一致、文件缺失/行数错误/脚本缺失的失败分支 |
| `test_executor_flash_integration.py` | 按用例/子目录去重加密、`encrypt_status` 成功/失败/跳过、缺失 `FLASH.dat` 记录失败、RAM 用例跳过 |
| `test_executor_results.py` | `_read_case_result` 成功/失败/异常状态与两列旧格式、耗时缺失、耗时非整数/带单位/空串/负数/超大值时仅丢耗时且状态照常；`_collect_results` 汇总匹配、时间戳目录缺失、summary 缺失/空/不完整；`_find_last_completed_batch` 全完成、首批失败、有目录无 summary、中间批次不完整时的续测起点 |
| `test_generator.py` | 模板模式按源文件批量生成、模板名读取与回退、工程名/产物名在各配置文件中的替换、工程名含 `& < > "` 时按 XML 转义且生成后可被 `ET.parse` 解析、原有实体不二次转义、模板本身损坏时报失败而不是静默成功、目标已存在时跳过与 `clean=True` 重建、模板/源目录与 `.cproject` 缺失、手动模式工程校验 |
| `test_report_generator.py` | 未开加密 CSV 两列、开加密三列、`dat_dir` 缺失时回落到结果根目录、空结果不生成文件 |
| `test_gel_config.py` | `tools.gel_file` 空/有值与相对/绝对往返、空值零介入、`<device><cpu>` 注入内容与临时文件清理、文件缺失与无法注入的中文三段式报错、ccxml 已声明 GEL 的来源描述；离线 DSS `openSession` 查询已登记 GEL 确认 CCS 接受注入结果 |
| `test_gui_config_panel.py` | 生成模式切换时模板/源文件两行显隐、加密开关与回读校验联动、字段加载/回读往返（结果目录、隐藏兼容字段）、Flash 三态 |
| `test_gui_execute_panel.py` | 断点续测复选框联动起始批次、从配置结果目录恢复最新时间戳、旧 `5_result_dat` 兼容、无结果返回 None |
| `test_stop_semantics.py` | 停止后剩余用例标记 `Skipped` 并只通知一次、跳过用例不参与 FLASH 加密且不计失败、停止时 `run_all` 全量跳过且无加密失败；结束摘要区分"已停止/测试完成"、成功/失败/跳过口径、失败原因直显；点击停止立即显示"正在停止…"、停止收尾期间不被覆盖、正常结束仍显示"执行完成" |
| `test_gui_usability.py` | 启动配置优先级（`-c` → `config/config.json` → 上次使用 → 空态）；错误文案三段式且 JSON/文件类异常中文化、不含 traceback；日志页 HTML 转义、多行不粘连、级别过滤与内存上限；未加载配置时开始执行/开始检测禁用并带 tooltip、配置页空态引导；执行失败错误条与结果目录提示、停止不算错误；用例表 dat 目录解析与复制路径；worker 日志真实级别（失败 ERROR / 成功 INFO / 跳过 WARNING） |

以下环节**不在自动回归范围**，按人工清单验证：[MANUAL_CHECKS.md](MANUAL_CHECKS.md)。

- 真实 `eclipsec` 编译（工程生成已由 `test_generator.py` 用合成模板覆盖）
- DSS/JTAG 连板执行、硬件超时与重试
- 板上真实 `FLASH.dat` 的端到端加密
- 打包后 exe 的冻结模式冒烟

## 本次基线

- 用例总数：268，通过 268，失败 0，错误 0，跳过 0（含离线 DSS GEL 验收，依赖本机 CCS 12.10）
- 单次全量耗时：约 12.8 秒（Windows，Python 3.9.12 32 位）

## 配置字段守卫

`test_config_field_guard.py` 针对"GUI 内存 Config → 临时 JSON → 重新 load 时字段被吞掉"这一类缺陷：

- `FieldCompletenessTest` 用 `dataclasses.fields()` 枚举 `PathConfig/BuildConfig/TestConfig/ResultCheck/MemorySegment/ExportPoint/TestCase`，断言 `_config_to_dict()` 产出的 dict 覆盖同名字段（`PathConfig` 的工具路径在 `tools` 分组中匹配）。
- `ValueRoundtripTest` 给每个字段塞与默认值不同的哨兵值，走完整往返后逐字段比对**值与类型**，既抓漏写也抓隐式类型改写。
- `ResultsDirRegressionTest` 锁定 `results_dir` 自定义绝对路径不会被解析成临时目录的相对默认值。

新增配置字段时不需要改测试：只要字段属于上述 dataclass，守卫会自动要求 `_config_to_dict()` 写入它。若确有字段必须刻意不写，在 `DELIBERATE_OMISSIONS` 中以 `(分组, 字段名): "理由"` 登记，`test_omission_list_is_documented` 会强制理由非空。

## 已知观察（未修改源码，不阻塞回归）

1. `src/test_config_generator.py` 的 `_generate_from_cases` 对配置内 `case.dat_dir` 原样透传，未做 `to_posix`。当 `dat_dir` 本身是反斜杠写法时，产出 JSON 会出现反斜杠；正常链路由本工具生成或 `Config.save()` 保存时已是正斜杠，因此未计为失败。若要让"dat_dir 一律正斜杠"成为硬约束，在该分支补一次 `to_posix` 即可。
2. `src/executor.py` 的 `_should_copy_project_file` 在 `.settings` 分支之前先过滤 `.prefs`，所以 `.settings/org.eclipse.core.resources.prefs` 不会被复制（`.settings` 分支只对非 `.prefs` 文件生效）。工程复制后 Eclipse 的源文件编码等偏好不会随工程走。
3. `src/flash_encrypt.py` 成功文案固定为 `FLASH0~3.dat`，实际实例数由根脚本 `N_INST` 决定；当前 `N_INST=4`，无实际影响。
4. `src/executor.py` 的 `_collect_results` 当前**没有任何生产调用点**（全仓仅测试调用），疑似历史遗留；其行为还有两处静默：summary 为空时返回空列表而不是逐用例 `NoResult`；summary 中缺少某用例时该用例直接从结果中消失。对应 `test_empty_summary_yields_no_results`、`test_incomplete_summary_only_returns_listed_cases`。
5. `src/generator.py` 的替换清单不含通用 `name="..."` 属性（只处理 `<name>`、`<project>`、`artifactName`、`projectName`、`.out/.map/.com.ti`）。当前真实模板的 `.cproject` 使用 `${ProjName}` 宏，因此暂无影响；若换用带 `name="工程名"` 属性的模板，该属性不会被改写。
6. `src/generator.py` 目标目录已存在且 `clean=False` 时返回 `success=True` 且 `error="目录已存在，跳过"`。跳过语义与成功标志混用，上层若只看 `success` 会误以为工程已重新生成。对应 `test_existing_project_is_skipped_when_clean_false`。

## 新增用例约定

- 继承 `tests.helpers.TempTestCase`，通过 `self.tmp` / `self.make_dir()` / `self.write_text()` 使用临时目录，不要把任何产物写到工程目录。
- 构造配置用 `make_config_dict()/make_config()`，需要模拟 `app_root()` 时用 `mock.patch`，不要真的修改工程内配置文件。
- 只读引用真实资源（如 `templates/dss_test.js.tmpl`、`encrypt_flash_dat.py`）是允许的。
- 新增模块命名 `test_*.py`，`run_checks.py` 会自动发现。
- 发现疑似缺陷时：先写能复现的用例；若确认是真实缺陷且不在本次修改范围，记录到本文件"已知观察"，不要改 `src/`。
