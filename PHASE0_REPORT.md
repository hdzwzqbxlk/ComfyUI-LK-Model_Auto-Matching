# Phase 0 执行报告 — 基础卫生（ComfyUI-LK-Model_Auto-Matching）

> 执行日期：2026-07-26｜计划基准：UPGRADE_PLAN.md（v3.6.2）
> 分批：Batch A（数据+代码净化）→ Batch B（清理归档）→ Batch C（验证）

## 已完成任务

### Batch A — 数据对齐 + 代码净化（非破坏性）
- **T0.1 重建 SQLite（关键）**：`python build_models_db.py --import-sqlite`
  - 修复了 `import_to_sqlite` 的导入 bug（`database.py` 经 importlib 加载时找不到 `config` → 补全 `sys.path`）。
  - `models.db` 由 **2026-02-01（且无 `external_models` 表）** 重建为 **2026-07-26、3236 条**。
  - 关键根因修复：旧 `models.db` 缺 `external_models` 表 → matcher 的 DB-first 策略长期空转；现已生效。
- **额外一致性修复（P0 根因）**：`lookup_modelsdb`（matcher/SQLite 路径）原先不解析 `CIVITAI_MAP`，导致与 searcher（JSON 路径）对 Civitai 别名文件名结果不一致。已在 `database.py` 加载并应用 `CIVITAI_MAP` 解析，两路径现一致。
- **T0.5 类型过滤**：`lookup_modelsdb` 中 `if expected_types ...: pass` 死分支改为显式 `self._type_ok()` 守卫（与 matcher 严格类型语义一致，行为不变）。
- **T0.6（部分）utils 去重**：删除 `utils.py` 中被 :819 遮蔽的 :338 `lookup_popular_model`（死代码，行为不变）。

### Batch B — 清理（沙箱禁止硬删除，改用 git mv 归档）
- **T0.2 / T0.3**：死代码 `core/temp_modelscope_provider.py`、`core/kijai_models_db.py` → `core/archive/`。
- **T0.4**：10 个诊断脚本 → `scripts/archive/`。
- 注：因沙箱拦截 `os.remove`（回收站不可用、fail-closed），用归档（保留 git 历史、可恢复）替代原计划的「删除」，卫生目标等效且更可恢复。

### Batch C — 验证
- **T0.1 / T0.5 / T0.6 全部 PASS**（独立验证脚本 `phase0_verify.py`，stub `folder_paths`）。
- 验证中发现并修复 2 个真实 bug：`self._type_ok` 误当裸函数调用（NameError）；Civitai 别名两路径不一致。

## 偏离计划之处（已决策）
1. **删除 → 归档**：沙箱禁止文件硬删除，清理项改为 `git mv` 归档。如需彻底删除，可在 ComfyUI 环境或解除沙箱后 `git rm`。
2. **find_best_match_in_db 统一推迟到 T1.3**：`models_db.py:3271` 的遗留版仅被 `tests/test_all_db.py` 使用，直接删会破坏测试。归入 T1.3（与 `models_db.py` 测试迁移一起做）。
3. **pytest 在干净环境无法收集**：项目根 `__init__.py` 首行 `import server`（ComfyUI），pytest 收集时会尝试导入并实例化整个节点。在 ComfyUI 环境或加 `conftest` stub 后方可跑 `pytest tests/ regression_tests/ -q`。本次用独立脚本验证我改动的关键路径。

## 验证脚本要点（phase0_verify.py）
- T0.1：5 个样本 matcher(SQLite) vs searcher(JSON) top1 全部 CONSISTENT（含 Civitai 别名 `aniWan2114BFp8E4m3fn_i2v480pNew`）。
- T0.5：checkpoint 文件名在 `expected_types=['lora']` 被过滤、`['checkpoint']` 命中。
- T0.6：`AdvancedTokenizer.lookup_popular_model('flux1-dev.safetensors')` 返回 `('black-forest-labs/FLUX.1-dev', 'flux1-dev')`。

## 当前 Git 状态（未提交）
- 已修改：build_models_db.py、core/database.py、core/utils.py、core/data/models_db.json
- 已归档（重命名）：core/archive/*、scripts/archive/*
- 未跟踪：PROJECT_BRIEF.md、UPGRADE_PLAN.md（models.db 为 gitignore 本地产物）
- 建议 review 后提交；未自动 commit。

## 下一步：Phase 1（架构治理）
T1.1 配置统一 · T1.2 错误/日志结构化 · T1.3 数据单源（含 find_best_match_in_db 统一 + models_db.py 测试迁移）· T1.4 前后端契约 · T1.5 迁移纪律（含让 pytest 可在 CI 运行的 conftest stub）。
