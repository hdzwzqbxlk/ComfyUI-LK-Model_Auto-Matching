# 升级计划（Upgrade Plan）— ComfyUI-LK-Model_Auto-Matching

> 版本基准：v3.6.2（2026-07-24）｜计划制定：2026-07-26
> 制定依据：项目目标（README / ARCHITECTURE）+ 基础认知（PROJECT_BRIEF.md）
> 指导框架：全栈开发（fullstack-dev）· 提示词工程（prompt-engineering-expert）· 技能发现（find-skills）
> 配套文档：`PROJECT_BRIEF.md`（架构/技术债）、`ARCHITECTURE.md`（路线图）

---

## 0. 目标对齐：项目目标 → 升级目标

| 项目目标（来自文档） | 升级目标（G*） |
|---|---|
| 自动化匹配，解决红色 missing model | **G1** 提升本地+网络匹配准确率与一致性 |
| 中文/本地化体验、ModelScope/Liblib 权重 | **G2** 中文分词与本地化平台优先 |
| 版本与系列感知（v1↔v2 歧义） | **G3** 语义版本解析 + 模型「族谱」 |
| 模型指纹识别（摆脱文件名） | **G4** 读取 Safetensors header / 哈希云端库 |
| 持续迭代、稳定性 | **G5** 架构治理、可维护性、可测试性 |

本计划按「先打底（G5）→ 再提准（G1/G2/G3）→ 后扩展（G4/体验）」推进。

---

## 1. 全栈架构视角（fullstack-dev 应用）

把插件当作「后端（Python core）+ 前端（JS）+ 数据层」的小型全栈系统来治理，套用其铁律。

### 1.1 当前 vs 目标对照
| fullstack-dev 原则 | 当前状态 | 升级动作 |
|---|---|---|
| 分层：Controller→Service→Repository | ✅ 已基本分层（`__init__.py` 路由 → `matcher/searcher` → `database/scanner`）。但 `__init__.py` 路由内嵌了少量逻辑 | 路由只做解析/校验/调用，业务全在 Service 层 |
| 集中、类型化、fail-fast 配置 | ⚠️ 两套配置：根 `config.json`（token）+ `core/data/matcher_config.json`（策略），分散读取 | 统一为单一配置层，启动时校验 |
| 类型化错误 + 全局处理 | ❌ `__init__.py` 全部 `except Exception as e: print(...)`，无一致错误信封 | 结构化 JSON 日志 + `{error, code, detail}` 信封 |
| 数据迁移纪律 | ⚠️ `database.py` 用 `ALTER TABLE` 静默兼容旧库 | 显式迁移版本号 + 迁移脚本 |
| 前端-后端类型契约 | ❌ 6 个路由与 `js/auto_matcher.js` 字段靠约定（`matched_value/path/match_type/type`） | 建立共享 schema / 类型约定 |

### 1.2 具体应用（见 Phase 1 任务）

---

## 2. 提示工程视角（prompt-engineering-expert 应用）

本项目的「提示」有两层：**(a) 发给搜索引擎的 Query**（`AdvancedTokenizer.extract_search_terms` 构造），**(b) 面向用户的 UI 文案/确认提示**。

### 2.1 搜索 Query = 给搜索引擎的 Prompt
- **结构化查询模板**：为 Google / HF / Civitai 分别定义 query 模板，而非统一拼接。
- **Few-shot 别名示例**：把 `CIVITAI_MAP` / `MODEL_ALIASES` 当作 few-shot 示例固化进检索逻辑，提升「aniwan21 → Wan2.1」类归一化。
- **负向约束**：在 query 中显式排除冲突 token（如搜索 T2V 时排除 `i2v`），对应 `_check_conflicts` 的硬规则。
- **角色/场景化**：若未来引入 LLM 做智能路由，设计 role-based system prompt + few-shot，并配评估用例。

### 2.2 用户侧文案 = 给用户的 Prompt
- 确认弹窗的 `Original → New` 说明、缺失列表复制、错误提示，应映射为人类可读消息（对应 fullstack-dev §12 跨边界错误处理）。
- 避免暴露内部错误（如 `UnboundLocalError`），统一转成友好提示。

---

## 3. 可复用技能盘点（find-skills 结果）

本地已安装、与本次升级相关的技能（**无需远程安装**）：

| 技能（本机名） | 对应中文 | 在本计划中的用途 |
|---|---|---|
| `fullstack-dev` | 全栈开发 | 架构治理、配置/错误/契约（Phase 1） |
| `prompt-engineering-expert` | 提示词工程专家 | 搜索 Query 与 UI 文案优化（Phase 3） |
| `diagnose` | 诊断 | 升级中排查硬 bug / 性能回归 |
| `grill-me` | 计划确认 | 执行前与用户对齐 Phase 范围与取舍 |
| `excalidraw-diagram` | 架构图 | 可视化路线图/数据流（可配本文档） |
| `impeccable` | 前端打磨 | Phase 3 前端 UI 精细化 |

> 注：`全栈开发`/`提示词工程专家` 在本环境以英文目录名 `fullstack-dev` / `prompt-engineering-expert` 存储，调用时须用英文名。

---

## 4. 分阶段升级路线图（核心交付）

### Phase 0 — 基础卫生（低风险、高回报，约 1–2 天）
**目标（G5）**：消除数据不一致与死代码，建立可重复构建。

- **T0.1 重建 SQLite（P0）**
  - 动作：`python build_models_db.py --import-sqlite`（将 `models.db` 2026-02-01 对齐到 `models_db.json` 2026-07-26）。
  - 验收：`matcher.lookup_modelsdb` 与 `searcher.find_best_match_in_db` 对同一组样本返回一致的 top1；`models.db` mtime 刷新。
- **T0.2 删除死代码 `core/temp_modelscope_provider.py`**
  - 理由：全工程无 import；且 `super().__init__()` 缺 `import BaseProvider` → `NameError`。
- **T0.3 下线 `core/kijai_models_db.py`**
  - 理由：`find_best_match_in_kijai` 无任何引用（searcher 已在 `models_db_reader` 自行实现 civitai→Kijai 兜底）。删除或正式接入。
- **T0.4 归档诊断脚本**
  - 动作：`scripts/` 下 `diag_/explore_/inspect_/verify_/test_cnb/test_tokenizer` 共 10 个移入 `scripts/archive/`。
- **T0.5 修 `lookup_modelsdb` 类型过滤空分支（P1）**
  - 位置：`core/database.py` 约 :374 与 :403 的 `if expected_types ...: pass` 空体 → 真正实现类型过滤，与 matcher 严格类型语义一致。
- **T0.6 合并 `utils.py` 重复 `lookup_popular_model`（:338 vs :819）** 与 **两套 `find_best_match_in_db`**（统一到 `models_db_reader`）。
  - 执行记录（2026-07-26）：`utils.py` 重复已合并（删 :338 被 :819 遮蔽的死代码）；`find_best_match_in_db` 统一**推迟至 T1.3**，与 `models_db.py` 测试迁移一并处理（直接删遗留版会破坏 `tests/test_all_db.py`）。

**里程碑 M1 验收**：`pytest tests/ regression_tests/ -q` 全绿；SQLite 与 JSON 内容对齐；仓库无死代码文件。

### Phase 1 — 架构治理（约 3–5 天）
**目标（G5）**：配置/日志/契约/单数据源，为持续迭代打底（fullstack-dev 视角）。

- **T1.1 配置统一（fullstack-dev §2）**
  - 合并根 `config.json` 与 `core/data/matcher_config.json` 为单一配置层；集中读取、启动校验（fail-fast）、类型转换在配置层完成。
- **T1.2 错误处理与日志（fullstack-dev §3/§7）**
  - `__init__.py` 的 `print` 改为结构化 JSON 日志（带 request_id 风格上下文）；定义 `AppError` 风格错误层次与一致响应信封 `{error, code, detail}`；不向客户端暴露堆栈。
- **T1.3 数据单源（最关键，G1 一致性）**
  - 确立 `build_models_db.py` 为唯一数据源；让 matcher 与 searcher **共用同一份**外部模型库（建议都读 `models_db.json`，或都走重建后的 SQLite），消除双路径不一致。
  - 将测试从 `core/models_db.py`（3236 条遗留巨字典）改引 `models_db_reader`。
- **T1.4 前后端契约（fullstack-dev §5/§12）**
  - 在 `__init__.py` 6 个路由与 `js/auto_matcher.js` 间建立共享字段约定（手写 typed contract / JSON schema），保证 `matched_value/path/match_type/type` 等字段前后端一致；前端错误映射到用户可读消息。
- **T1.5 SQLite 迁移纪律（fullstack-dev §4）**
  - `database.py` 的 `ALTER TABLE` 兼容逻辑改为显式迁移版本号 + 可重放迁移脚本。

**里程碑 M2 验收**：单配置入口；错误/日志结构化；matcher 与 searcher 同源；契约文档存在且测试覆盖。

### Phase 2 — 匹配准确率提升（约 1–2 周，核心目标 G1/G2/G3）
- **T2.1 中文分词增强（G2）**：`utils.AdvancedTokenizer` 引入 jieba/轻量方案（ARCHITECTURE Phase1），增强 CJK 2-gram 与中英边界切分；补 `tests/` 中文模型样本。
- **T2.2 版本与系列感知（G3）**：实现语义版本解析 + 模型「族谱」库（Juggernaut 各版本演进等）；依赖 T0.5 已生效的严格类型过滤。
- **T2.3 测试补齐**：覆盖 `CivitaiHashProvider` 哈希匹配、`HuggingFaceFileSearchProvider` 真实并发扫描、`ModelScope/CNB/Liblib/DDG` 真实网络逻辑（mock 或 stub）。
- **T2.4 Provider 修复**：重写 `LiblibProvider`（当前依赖 JS 静态链接，大概率失效）为 API/页面解析；`ModelScope/CNB/DDG` 补真实逻辑或 mock。

**里程碑 M3 验收**：中文模型匹配率 >90%（对标 ARCHITECTURE 预期）；版本歧义用例通过；新增测试覆盖上述 Provider。

### Phase 3 — 体验与扩展（持续，G4 + 提示工程/UI）
- **T3.1 搜索 Query 优化（prompt-engineering §2.1）**：重构 `extract_search_terms`，per-provider 查询模板 + few-shot 别名 + 负向约束。
- **T3.2 用户侧文案优化（prompt-engineering §2.2 + fullstack-dev §12）**：确认弹窗说明、缺失列表复制、错误提示人类可读。
- **T3.3 前端打磨（`impeccable` skill）**：`js/auto_matcher.js` 加载态/错误态/无障碍/深色模式一致性。
- **T3.4（可选）LLM 路由系统提示**：若引入 LLM 做智能路由，设计 role-based + few-shot system prompt，配评估用例。
- **T3.5 模型指纹识别（G4，长期）**：读取 Safetensors header + 计算 SHA256/BLAKE3，建立云端哈希库，摆脱纯文件名依赖（ARCHITECTURE Phase3）。

---

## 5. 执行顺序、里程碑与关键路径

```
关键路径：T0.1 重建SQLite → T1.3 数据单源 → T2 准确率提升
（数据一致性是后续一切的前提）

M1 (1–2d)  Phase 0   卫生+数据对齐+死代码
M2 (3–5d)  Phase 1   架构治理（配置/日志/契约/单源）
M3 (1–2w)  Phase 2   准确率（中文/版本/Provider/测试）
M4 (持续)   Phase 3   体验/扩展/指纹
```
- 建议 M1 之前用 `grill-me` 与用户对齐 Phase 范围与取舍；用 `excalidraw-diagram` 把本路线图画成一张可视化图贴在仓库。
- CI 建议：每次发布前跑 `python build_models_db.py --import-sqlite` + `pytest`，防止 SQLite 再次陈旧。

---

## 6. 风险与回滚

| 风险 | 缓解 / 回滚 |
|---|---|
| `fetch_models_db.py` 重建需联网抓 HF API | SQLite 重建（`import_models_db_json`）只依赖本地 `models_db.json`，**无需联网**；JSON 已是最新，可离线完成 T0.1 |
| Provider 反爬（Cloudflare） | `curl_cffi` chrome124 伪装已就位；改 Liblib 时需重新验证 TLS 指纹 |
| 前后端字段变更（T1.4） | 必须同步改 `js/auto_matcher.js`，并用契约文档 + 测试锁死 |
| 数据单源切换引入回归 | T1.3 后补「双路径一致」回归测试（matcher vs searcher 同输入同输出） |
| 误删 `models_db.py` 致测试失败 | 先改测试引用 `models_db_reader`，再删巨字典 |

---

## 7. 下一步建议
1. 先执行 **Phase 0（T0.1–T0.6）**——风险最低、收益最高，可直接动手。
2. 动手前用 `grill-me` 确认 Phase 1 的配置合并方案（是否保留两套 config 语义）。
3. 需要我把本路线图用 `excalidraw-diagram` 画成一张可视化架构/里程碑图吗？可直接说。
