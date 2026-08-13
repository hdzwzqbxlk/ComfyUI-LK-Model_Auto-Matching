# ComfyUI-LK-Model_Auto-Matching — 项目梳理与基础认知

> 版本基准：v3.6.2（2026-07-24）｜文档生成：2026-07-26
> 目的：为后续迭代建立统一认知。本文档聚焦「架构事实 + 数据管线 + 技术债 + 迭代切入点」，不重复 README/ARCHITECTURE 的营销描述。

---

## 1. 项目定位与价值

ComfyUI 自定义节点（custom_nodes）插件，解决「导入他人工作流后满屏红色 missing model 节点」的痛点：

- **本地匹配（核心）**：扫描本地 `models/` 目录，按文件名 / 变体 / 模糊相似度，把工作流中缺失的模型名替换成本地已有文件。
- **全网结构化搜索（兜底）**：本地没有时，并发搜索 Civitai / HuggingFace / ModelScope / Liblib / CNB 等结构化源（API 按名 + 哈希精确），返回可下载链接；已移除 Google / DuckDuckGo 泛网页搜索。
- **安全确认**：所有改动先弹窗展示 `Original -> New`，用户点确认才生效，不静默改写。

入口：ComfyUI 顶部菜单的 **「LK 🪄 Auto Match」** 按钮（前端在 `js/auto_matcher.js`）。

---

## 2. 系统总览（四层架构）

```
┌──────────────────────────────────────────────────────────┐
│ 前端  js/auto_matcher.js (1117 行)                         │
│  菜单按钮 / 弹窗 / 结果渲染 / MutationObserver 清理        │
└───────────────┬──────────────────────────────────────────┘
                │ HTTP (aiohttp)  /auto-matcher/*
┌───────────────▼──────────────────────────────────────────┐
│ 后端  __init__.py (153 行)  API 路由注册                    │
│  /match  /search  /refresh-index  /save-config            │
│  /validate-config  /get-config                             │
└───────────────┬──────────────────────────────────────────┘
                │ 调用
┌───────────────▼──────────────────────────────────────────┐
│ 核心引擎  core/                                            │
│  scanner.py  文件扫描 + 增量索引 (ModelScanner)            │
│  matcher.py  本地匹配引擎 (ModelMatcher, 5 级策略)         │
│  searcher.py 网络搜索编排 + 各平台 Provider (ModelSearcher)│
│  utils.py    分词/相似度核心 (AdvancedTokenizer)           │
│  database.py SQLite 外部模型库 (ModelDatabase)            │
│  config.py   匹配策略配置 (matcher_config.json)           │
└───────────────┬──────────────────────────────────────────┘
                │ 读写
┌───────────────▼──────────────────────────────────────────┐
│ 数据层                                                       │
│  model_index.json  本地磁盘模型索引 (运行时生成)            │
│  models.db         SQLite 外部模型库 (matcher 用)           │
│  models_db.json    外部模型库 JSON (searcher 用)            │
│  models_db.py      3236 条巨字典 (遗留 / 仅测试)           │
└──────────────────────────────────────────────────────────┘
```

**两条运行时数据路径（关键认知）**：
- 本地匹配走 **SQLite**（`matcher.py` → `database.lookup_modelsdb`）
- 网络搜索走 **JSON**（`searcher.py` → `models_db_reader.find_best_match_in_db`）

---

## 3. 核心数据流

**本地匹配链路（/auto-matcher/match）**：
1. 前端把缺失项 `[{id, node_type, widget_name, current}]` POST 给后端。
2. `ModelMatcher.match()` 先 `_build_index()` 构建倒排索引（带缓存，模型数不变则复用）。
3. 按 `WIDGET_TO_TYPE` 把 widget 名映射到期望模型类型（如 `lora_name -> loras`）。
4. 依次尝试 5 级策略，命中即停：
   - **DB-first**：`database.lookup_modelsdb`（SQLite 语义匹配）
   - **Exact**：全名 / basename 精确命中
   - **Fuzzy**：token 加权 + 格式硬隔离 + 类型严格过滤 + CJK 重叠 bonus
   - **Variant**：核心 token Jaccard（变体识别，如 fp16↔bf16）
   - **Legacy**：RapidFuzz `token_set_ratio` 兜底
5. 每级都过 `_check_conflicts()`（gguf↔safetensors 硬阻断、I2V↔T2V 互斥、rank 数值互斥等）。
6. 返回 `[{id, original_value, matched_value, path, match_type, type}]`，前端弹窗确认后写回工作流。

**网络搜索链路（/auto-matcher/search）**：
1. 先 `scanner.find_local_file()` 暴力查本地磁盘（未索引也能命中）。
2. 未命中则 `searcher.search()` 按文件名特征**智能路由**优先 Provider，**竞速早停**（score≥0.7 即停）。
3. score<0.85 时用 `find_best_match_in_db`（JSON）兜底。
4. 并发用 `asyncio.as_completed`，网络库统一 `curl_cffi`（chrome124 TLS 伪装）+ `parsel` 解析。

**索引刷新（/auto-matcher/refresh-index）**：`scanner.scan_incremental()` 做双向路径对齐，0 重算 Hash 复用未变文件、识别移动文件、毫秒级擦除已删条目；同时 `matcher.invalidate_index()`。

---

## 4. 模块职责速查

| 文件 | 行数 | 职责 | 关键类/函数 |
|------|------|------|------|
| `core/scanner.py` | 303 | 遍历 `folder_paths` 的 15 类模型目录，增量索引，自愈擦除 | `ModelScanner` / `ModelIndex` / `scan_incremental` / `calculate_fast_hash` / `find_local_file` |
| `core/matcher.py` | 553 | 本地匹配引擎，5 级策略 + 冲突守卫 + 倒排索引 | `ModelMatcher.match` / `_find_exact/fuzzy/variant/legacy_match` / `_check_conflicts` / `_build_index` |
| `core/searcher.py` | 1365 | 网络搜索编排 + 6 个 Provider | `ModelSearcher.search`；`CivitaiProvider`/`HuggingFaceProvider`/`ModelScopeFileSearchProvider`/`LiblibProvider`/`CNBProvider`/`CivitaiHashProvider` |
| `core/utils.py` | 1079 | 分词 + 相似度核心大脑 | `AdvancedTokenizer.tokenize` / `get_core_tokens` / `get_model_format` / `extract_search_terms` / `detect_base_model` / `calculate_similarity`；常量 `NOISE_SUFFIXES`/`PROTECTED_TERMS`/`COMFYUI_POPULAR_MODELS`(197) |
| `core/database.py` | 598 | SQLite 外部模型库管理 | `ModelDatabase`；表 `models`/`file_hashes`/`aliases`/`external_models`；`lookup_modelsdb` / `import_models_db_json` |
| `core/models_db_reader.py` | 100 | 读 `models_db.json`，运行时搜索兜底 | `find_best_match_in_db`（JSON 版，searcher 实际调用） |
| `core/config.py` | 68 | 匹配策略配置加载/合并 | `get_matcher_config` / `override_matcher_config`（读 `core/data/matcher_config.json`） |
| `js/auto_matcher.js` | 1117 | 前端 UI + API 调用 | 菜单按钮、弹窗、确认、复制缺失列表、MutationObserver 残窗清理 |

**两套配置（新人易混）**：
- `envs/config.json`：`civitai_api_key` / `huggingface_token`（给网络搜索用）
- `core/data/matcher_config.json`：匹配开关 + 阈值（db-first、各 cutoff、type 严格度）——由 `core/config.py` 加载，带 `_DEFAULT_CONFIG` 兜底

---

## 5. 数据层全景（最重要的一节）

数据有 **三条来源、三套产物、两条运行路径**，目前存在一致性风险：

**来源（SOURCE）**
- `comfy_gguf_models.json`（3067 条，2026-02-02）：由 `fetch_models_db.py` 调 HuggingFace API 抓取 Comfy-Org/City96/bartowski/mradermacher/MaziyarPanahi 生成。
- `kijai_all_models.txt`（193 行，手工维护的 Kijai/WanVideo 列表）。

**产物（BUILD）** — 由 `build_models_db.py` 串起来：
```
comfy_gguf_models.json + kijai_all_models.txt
        │  build_models_db.py (write_json)
        ▼
core/data/models_db.json   (890KB, 2026-07-26)  ← searcher 运行时读
        │  build_models_db.py --import-sqlite
        ▼
core/data/models.db        (45KB,  2026-02-01)  ← matcher 运行时读 (lookup_modelsdb)
```

**遗留产物（LEGACY，易踩坑）**
- `core/models_db.py`（3236 条，780KB，2026-07-24）：同名仓库的**另一个**全量字典，由旧/外部管线生成，**运行时并未被 matcher/searcher 引用**，仅 `tests/test_all_db.py` 引用其内部的 `find_best_match_in_db`。

**结论 / 风险**
1. ⚠️ **`models.db`（SQLite）比 `models_db.json` 旧约 5 个月**，且 matcher 走 SQLite、searcher 走 JSON —— 两者可能给出不一致的匹配结果。这是当前最该先处理的数据隐患。
2. 存在两条并行「知识库」：`build_models_db.py` 管线（运行时）与 `models_db.py` 巨字典（遗留/测试），无单一事实源，易漂移。

**修复动作**：发布/CI 中执行 `python build_models_db.py --import-sqlite` 重建 SQLite；评估 `models_db.py` 是否可下线（把测试改引 `models_db_reader`）。

---

## 6. 技术债与风险清单（按优先级）

### P0 — 阻塞一致性，优先修
- **[数据] SQLite 陈旧且双路径不一致**：`models.db` 2026-02-01 vs `models_db.json` 2026-07-26。matcher(SQLite) 与 searcher(JSON) 可能结果冲突。→ 跑 `--import-sqlite` 重建，并固化进发布流程。

### P1 — 正确性 / 死代码
- **[死代码] `core/temp_modelscope_provider.py`**：全工程无 import；且自身有 bug（`super().__init__()` 但没 `import BaseProvider` → `NameError`）。直接删除。
- **[死代码] `core/kijai_models_db.py`**：`find_best_match_in_kijai` 无任何引用（searcher 自行在 `models_db_reader` 实现 civitai→Kijai 兜底）。删除或正式接入。
- **[Bug] `database.lookup_modelsdb` 类型过滤失效**：`core/database.py` 约 :374 与 :403 处 `if expected_types ...: pass` 为空体，`expected_types` 永远不生效（与 matcher 的严格类型过滤语义不一致）。
- **[重复] `utils.py` 中 `lookup_popular_model` 定义两次**（:338 与 :819），第二个覆盖第一个，导致第一个含的 DB 查询分支沦为死代码、可能丢失逻辑。合并为单一实现。
- **[重复] 两套 `find_best_match_in_db`**：`models_db.py:3271`（内存字典，仅测试）与 `models_db_reader.py:42`（JSON，运行时）。逻辑重复、易漂移。统一到 `models_db_reader`。

### P2 — 卫生 / 可维护性
- **[归档] `scripts/` 下 10 个诊断/探索脚本**：`diag_modelscope.py` / `explore_modelscope.py` / `inspect_modelscope_sdk.py` / `verify_*.py` / `test_cnb.py` / `test_tokenizer.py` 带探索性质，建议移入 `scripts/archive/` 或 `tools/`，避免污染仓库根。
- **[散落死代码]**：`database.py:197` 残留 `# ... existing code ...`；未用 import（`logging`/`uuid`/`random`）；`HuggingFaceFileSearchProvider._extract_keywords` 末行不可达 `return`。（`GoogleOmniProvider._parse_link` 对 HF 仅取 owner 名 一项已于 P6 移除 GoogleOmniProvider / DuckDuckGoProvider 时解决）
- **[测试分散]** 测试在 `tests/`（8 文件）与 `regression_tests/`（1 文件）两个目录，确认 pytest 能同时发现两者。

---

## 7. 测试覆盖现状

**已覆盖（tests/）**
- `test_matcher`：精确 / 模糊匹配
- `test_variants`：核心 token / 变体 / 关键术语
- `test_format_strict`：gguf↔safetensors 格式硬隔离
- `test_quantization`：量化 / 精度互斥
- `test_semantic`：base_model 与兼容（Flux Dev/Schnell 等）
- `test_algorithm`：HF 加权分词 / 动态仓库发现 / aniwan 归一化
- `test_all_db`：Kijai / Comfy-Org / GGUF 精确 + civitai 映射（走 `models_db.py`）
- `test_searcher`：`extract_search_terms` / `calculate_similarity` / 噪声 / ModelScope stub

**明显未覆盖**
- `CivitaiHashProvider` 哈希精确匹配
- `HuggingFaceFileSearchProvider` 真实并发目录扫描
- `ModelScopeFileSearchProvider` / `CNBProvider` / `LiblibProvider` 真实网络逻辑（仅 stub 或需 mock）
- `database.lookup_modelsdb`（含失效的类型过滤分支）
- SQLite 迁移路径（`ALTER TABLE` 兼容旧库）
- `ModelSearcher` 智能路由与竞速早停
- `temp_modelscope_provider`（本就死代码，无需覆盖）

**建议**：迭代 P0/P1 修复项时，优先补 `lookup_modelsdb` 类型过滤、SQLite 重建脚本、双路径一致的回归测试。

---

## 8. 后续迭代切入点与建议

**短期（基础卫生，低风险高收益）**
1. 重建 SQLite：`python build_models_db.py --import-sqlite`，验证 matcher 与 searcher 结果一致。
2. 删除 `temp_modelscope_provider.py`、`kijai_models_db.py`（确认无引用后）。
3. 归档 `scripts/` 诊断脚本到 `scripts/archive/`。
4. 合并 `utils.py` 重复的 `lookup_popular_model`；修 `lookup_modelsdb` 空类型过滤分支。
5. 统一两套 `find_best_match_in_db` 到 `models_db_reader`。

**中期（一致性 / 正确性）**
6. 确立**单一数据源**：建议以 `build_models_db.py` 管线为准，评估下线 `models_db.py` 巨字典（测试改引 JSON reader）。
7. 让 matcher 与 searcher 共用同一份外部模型库（要么都走 JSON，要么都走 SQLite），消除双路径不一致。
8. 完善 `LiblibProvider`（当前依赖 JS 静态链接，大概率已失效）。

**长期（路线图，已载于 ARCHITECTURE.md）**
9. 中文分词增强（jieba / 轻量方案）、ModelScope/Liblib 权重提升、Civitai 镜像源。
10. 语义版本解析 + 模型「族谱」库（v1↔v2 歧义）。
11. 模型指纹识别（读取 Safetensors header + SHA256/BLAKE3 云端哈希库），摆脱纯文件名依赖。

---

## 附：快速上手命令

```bash
# 重新生成 JSON + 重建 SQLite（发布前必跑）
python build_models_db.py --import-sqlite

# 运行测试
pytest tests/ regression_tests/ -q

# 本地索引增量刷新由插件菜单按钮触发（/auto-matcher/refresh-index）
```

> 注：运行需处于 ComfyUI 环境（`folder_paths`、`server` 为 ComfyUI 内置模块，不在 requirements.txt 中）。纯逻辑（matcher/utils/tokenizer）可在独立环境用 pytest 验证。
