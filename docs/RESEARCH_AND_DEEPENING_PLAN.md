# 深化方案（调研驱动）— ComfyUI-LK-Model_Auto-Matching

> 编写：2026-08-12　｜　依据：agent-reach 调研（ComfyUI 官方文档 + 同类插件实现）
> 配套：`UPGRADE_PLAN.md`（原路线图）、`docs/FRONTEND_BACKEND_CONTRACT.md`（契约锁）

本方案把 Phase 1 收尾（T1.5）与 Phase 2（准确率，核心目标 G1/G2/G3）结合调研结论具体化。
调研来源：ComfyUI 官方文档（docs.comfy.org / deepwiki folder_paths）、ComfyUI-Model Linker、
comfyui-modelsearchandload、ComfyUI-ModelResolver、comfyui_model_installer。

---

## 1. 调研关键发现

### 1.1 ComfyUI 官方规范（必须对齐）
- **模型类型 taxonomy（规范集合）**：`checkpoints / loras / vae / text_encoders /
  diffusion_models(=unet) / clip_vision / controlnet / style_models / embeddings /
  upscale_models / vae_approx / hypernetworks / photomaker / diffusers / gligen /
  detection / frame_interpolation / ipadapter`
- **`folder_paths` API**：`add_model_folder_path / get_folder_paths / get_filename_list /
  get_full_path`；搜索路径 = 默认 `models/<type>` + `extra_model_paths.yaml` + 各 custom node
  注册的目录（如 Kijai 的 `detection/`）。子目录相对路径会被保留。
- **原生 Missing Models 弹窗是开放集成点**：Model Linker / Model Installer 都往弹窗注入按钮，
  走 `installModelsApi({file_hash, filename, save_path, url})`。这意味着我们的下载落盘路径
  必须对齐官方 folder 名，否则用户刷新后仍红。

### 1.2 同类插件的已验证模式（直接可借鉴）
| 模式 | 出处 | 对我们的意义 |
|---|---|---|
| **版本感知匹配**：区分 `wan2.1↔wan2.2`、`v1↔v2`；评分=70% token 相似+30% 字符相似；归一化 `_-.`；按类别收敛 | ComfyUI-Model Linker | 直接对应 T2.2，是中文/版本歧义的最高收益项 |
| **curated 已知模型库**：`known_models.json` = `{文件名:{folder,url,source,size}}`，folder 键遵循 ComfyUI 约定，可编辑 | comfyui-modelsearchandload | 对应我们 `external_models` / `models_db.json`，缺「size」「folder」字段与可编辑入口 |
| **多层搜索链**：curated → HF 仓库名 → HF README 全文 → 兜底伞仓（Kijai/WanVideo_comfy 等） | comfyui-modelsearchandload | 对应 T2.4 Provider 修复与搜索排序 |
| **置信度分层**（100/90-99/70-89/<70）驱动 UI 自动解析 vs 人工确认 | Model Linker / Installer | 前端应据 score 分层展示（我们已有 score，缺分层 UI） |
| **智能 folder 路由 + 同盘 hardlink 去重 + API token 仅服务端存储（掩码预览）** | modelsearchandload / Installer | 下载落盘与密钥安全规范 |
| **网络搜索 Query 模板化**：per-provider 不同 query，而非统一拼接 | 本项目原计划 T3.1 | 对应搜索质量 |

---

## 2. 当前插件差距分析（Gap）

| 能力 | 现状（database.py / matcher / searcher） | 竞品水平 | 差距 |
|---|---|---|---|
| 版本感知 | 无；`wan2.1` 与 `wan2.2` token 重叠高，易误配 | 显式版本号识别、区分主次版本 | **高**（T2.2） |
| 评分框架 | 临时拼凑：token Jaccard + alias + normalized + base_model 加权 + rapidfuzz 兜底 | 70/30 token+char 加权、归一化分隔符、类别收敛 | 中（T2.2 顺带重构评分） |
| 中文分词 | `features.chinese_tokenization: True` 已开，但 `AdvancedTokenizer` 未引入 jieba/CJK 2-gram | 中文模型名（ModelScope/Liblib）占比高 | 中（T2.1） |
| folder 路由 | `type` 靠文件名启发式推断（lora/vae/...），无 `folder_paths` 对齐、无 `size` | 严格对齐官方 folder + 同盘去重 | 高（T2.2/下载落盘） |
| Provider 真实逻辑 | Liblib 依赖 JS 静态链接（大概率失效）；ModelScope/CNB/DDG 逻辑薄弱 | 多层搜索链 + README 全文 | 高（T2.4） |
| 置信度 UI | 返回 score，但前端无分层（100/90/70）决策 | 分层自动/人工 | 中（T3 UI，可前移） |
| 迁移纪律 | T1.5 已完成：显式版本号 + 可重放迁移 ✅ | — | 已补 |

---

## 3. T1.5 SQLite 迁移纪律（已实施 ✅）

`core/database.py` 改造：
- 新增 `schema_migrations(version, applied_at, description)` 版本表。
- `MIGRATIONS = [(1, ...), (2, ...)]`：v1 建基础表（external_models 仅核心列）；v2 带 PRAGMA 守卫地
  加 `normalized_name/alias/type/base_model/family/tokens` 六列 + 索引。每个迁移函数幂等。
- `run_migrations()` 只应用未记录的版本；`get_schema_version()` 返回最高版本；`migrate()` 公开入口。
- 验证：`regression_tests/migration_check.py`（全新库→最新版本 / 幂等重放 / 遗留库安全升级且数据不丢 /
  MIGRATIONS 最高版本==`SCHEMA_VERSION`）。
- 下次加列/改表 = 追加 `(3, ...)` 迁移函数并 `SCHEMA_VERSION=3`，无需再碰 `ALTER TABLE`。

---

## 4. Phase 2 深化设计（受调研启发）

### 4.1 T2.2 版本与族谱感知（**优先级最高**，推荐首做）
- **版本号归一化器**：从文件名抽取语义版本 `v1.0`/`2.1`/`14B`/`fp8`/`scaled` 等，拆分为
  `(base, major, minor, variant, quant, size)` 维度。`wan2.1` vs `wan2.2` 在主版本维度不同 → 强降权。
- **复用 `features.version_aware` 开关**：`core/config.py` 已预留 `version_aware: False`，
  翻为 `True` 即启用；评分层读取该开关，默认关闭以保证回归稳定，按开关逐步放开。
- **评分重构为 70/30**：`score = 0.7 * token_jaccard + 0.3 * char_similarity`，并归一化 `_-.`；
  版本维度冲突时整体乘惩罚系数（借鉴 Model Linker 的「版本号被误当扩展名」bug 修复）。
- **类别收敛**：`expected_types` 已存在，强化「只在同 type 内比较」，避免 LoRA 误配 Checkpoint。
- **族谱库**：`MODELS_DB` 已含 `family` 字段；补 `Juggernaut vN` / `Flux.1 [dev/schnell]` 等演进映射，
  作为同族加分、跨代降权。
- **验收**：新增 `tests/`(gitignored) 与 `regression_tests/` 用例覆盖 `wan2.1 vs wan2.2`、`Flux.1-dev vs schnell`、
  `SD1.5-pruned vs v1-5`；版本歧义用例通过率 100%。

### 4.2 T2.1 中文分词增强
- `utils.AdvancedTokenizer` 引入轻量中文方案（jieba 或自研 CJK 2-gram），增强中英边界切分。
- 覆盖 ModelScope/Liblib 中文模型样本（如「麦橘超然」「玄武」等中文权重命名）。
- 验收：中文模型名匹配率提升，单独用例集。

### 4.3 T2.4 Provider 修复
- 重写 `LiblibProvider`：去掉失效的 JS 静态链接，改 API/页面解析（curl_cffi chrome124 伪装已在位）。
- `ModelScope/CNB/DDG`：补真实逻辑或 mock，对齐「多层搜索链」思路（curated→仓库名→README 全文→兜底伞仓）。

### 4.4 T2.3 测试补齐
- `CivitaiHashProvider` 哈希匹配、`HuggingFaceFileSearchProvider` 并发扫描、各 Provider 真实/ mock 逻辑。
- 双路径一致回归（matcher vs searcher 同输入同输出）已随 T1.3 建立，持续加固。

### 4.5 folder 路由（下载落盘，跨 Phase 2/3）
- 下载时按官方 taxonomy 选 folder；落盘前查 `folder_paths.get_folder_paths(type)` 与同盘已有同名同尺寸文件 → hardlink 去重。
- API token（Civitai/HF）仅服务端存储，前端只收掩码预览（已在 T1.4 错误信封安全设计内体现）。

---

## 5. 优先级与首步建议

| 顺序 | 任务 | 收益 | 风险 | 依赖 |
|---|---|---|---|---|
| 1 | **T2.2 版本/族谱感知**（翻 `version_aware`） | 最高，直接解决 wan2.x / Flux 歧义 | 中（评分改动需回归） | T1.5 ✅、T0.5 ✅ |
| 2 | T2.4 Provider 修复（Liblib 优先） | 高，恢复失效源 | 中（反爬） | T1.3 ✅ |
| 3 | T2.1 中文分词 | 中高（中文权重场景） | 低 | — |
| 4 | T2.3 测试补齐 | 保障长期 | 低 | 上述 |

**首步推荐**：先做 T2.2（版本/族谱感知），因为它收益最高、配置开关已就绪、且竞品（Model Linker）已验证
「版本号敏感 + 70/30 加权」是正确方向。实施前会先出短方案（评分公式 + 版本维度定义 + 测试用例）交你过目。

---

## 6. 复用与风险

- **复用**：`features.version_aware` 开关、`external_models` 表与 `MODELS_DB.family`、`expected_types` 类型过滤、
  `regression_tests/` 测试范式、`build_models_db.py --import-sqlite` 离线重建（CI 防 SQLite 陈旧）。
- **风险**：评分改动可能引入回归 → 以「开关默认关 + 增量用例」控制；Provider 反爬 → curl_cffi 已就位，改 Liblib 时重新验证 TLS 指纹。
