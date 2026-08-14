# Changelog

## [Unreleased]
### Fixed
- **Matcher 本地匹配优先 (T2.5, PR #3, 已合入 `main@8ebeb8c`)**: 将 DB-first（外部知识库 / 网络匹配）从 `match()` 首位移至 Legacy 之后，本地索引候选池（`model_index.json`，含 ComfyUI 默认路径 + 自定义路径）优先匹配。消除"本地有精确文件却被外部标准名抢答"的错配——实测 13 个硬错归零、全通道 DB 命中从 72 降至 1。网络匹配优化（量化 / 代际后缀冲突约束）按指示暂缓。
- **本地匹配核心词覆盖率硬门槛 + 在线源优先级 (Matcher / Searcher Bugfix)**: 修复 `minimax_music3_dit_fp16` 被误匹配到本地 `sam3.1.multiplex_fp16` 的问题。
  - **本地匹配严格化**: 新增「核心身份词覆盖率」硬门槛（`core_coverage_min=0.6`，目标核心词数 ≥ `core_min_tokens=2` 时强制），技术后缀（`fp16`/`fp8`/`bf16`/`safetensors` 等）不计入核心词，无法单独支撑一次匹配；Fuzzy 的 `W_NOISE` 由 `0.1` 降至 `0.05`，`fuzzy_score_cutoff` 60→65、`legacy_score_cutoff` 75→80，使本地匹配更保守。`flux1-dev`↔`flux1-dev-fp8` 等正常变体匹配不受影响。
  - **在线源优先级与组件过滤**: `searcher` 新增 `source_preference`（主模型优先 HuggingFace / ModelScope / CNB 等官方国内镜像）并对默认 Provider 顺序重排；新增组件类别过滤，主模型请求剔除 `text_encoder` / `vae` / `clip` / `dav` 等组件候选（如 `minimax_music3_text_encoder_*`、`minimax_music3_dav`），避免主模型被同名组件抢答。
  - **配置语义澄清**: `use_db_first` 更名为 `use_db_fallback`（语义明确为「本地完全无匹配才回退 DB」），`matcher_config.json` 同步更新；DB 回退仍仅在本地四层全失配后启用。
- **LiblibProvider 重写 (T2.4, PR #2, 已合入 `main@899880b`)**: 改用 Liblib 内部 JSON API（`api2.liblib.art`），改进模型检索与匹配精度；新增 `regression_tests/provider_check.py` 回归校验锁定重写后行为。

### Added
- **标准化研发流程与文档**: 新增项目级技能 `lk-dev-standard`、仓库 `CONTRIBUTING.md`、`.github/pull_request_template.md`，并将 `CHANGELOG.md` 顶部改为 Keep a Changelog 风格的 `Unreleased` 段。PR 机械步骤统一委托 `pr-delivery` 技能（真实 git 状态提取 + 三级降级 + 合入自动清分支）。
- **网络模型匹配轻量化可行性计划**: 新增 `docs/MODEL_MATCHING_FEASIBILITY.md`——深度调研类同项目（ComfyUI-Manager / Civitai API 集成 / Comfy-Org 官方管线等 8+1）、国内镜像生态（hf-mirror / ModelScope / TUNA / Liblib / Civitai）、分层精准匹配架构（L0 本地 → L1 注册表 → L2 确定性镜像 → L3 Civitai API → L4 兜底）与 P1–P7 路线图；评估 ModelScope 重要等级由 L4 提级至 L2（国内首选镜像，与 hf-mirror 并列）。
- **镜像感知 URL 重写（路线图 P2-L2 / P3 核心）**: 新增 `core/mirror.py`（`rewrite_hf_url` / `rewrite_modelscope_url`），将 HuggingFace / ModelScope 下载 URL 路由到用户配置的镜像端点（`HF_ENDPOINT` / `MODELSCOPE_ENDPOINT`，含环境变量 `LK_HF_ENDPOINT` / `LK_MODELSCOPE_ENDPOINT`）。接入 `models_db_reader._enrich_info`、`database._enrich_external_info` 与 Kijai 兜底、`searcher` 的 HF 精确文件匹配与 ModelScope 直链。**端点未配置时原样透传，对既有行为零改变**；CN 用户设 `HF_ENDPOINT=https://hf-mirror.com` 即走国内镜像。新增 `tests/test_mirror.py` 覆盖透传 / 重写 / 非目标域不动。

### Changed
- **移除 Google / DuckDuckGo 泛网页搜索（路线图 P6）**: 删除 `core/searcher.py` 的 `GoogleOmniProvider` / `DuckDuckGoProvider` 两个泛搜兜底 Provider 及其在 provider 链与中文优先级路由中的引用；同步清理死配置 `config.py` / `matcher_config.json` 的 `google` 键、`regression_tests/provider_check.py` 的 `TestDuckDuckGoParseLink`、以及 AGENTS / README / ARCHITECTURE / PROJECT_BRIEF 的对应描述。以结构化 API 源（Civitai / HuggingFace / ModelScope / Liblib / CNB）替代脆弱的搜索引擎抓取。**Shakker.ai 暂不可达（已核实明确事实，非仅取舍）**: 其为 liblibai 姊妹站（favicon 托管于 `liblibai-web-static.liblib.cloud/shakker/`），模型检索接口 `https://www.shakker.ai/api/www/model/search`（POST）与 `getByUuid` 对独立客户端（含 `curl_cffi` Chrome 124 指纹、带页面 `webid` cookie）一致返回 500（反爬 / 服务端令牌保护，与 TLS 指纹、cookie、请求体字段均无关），且 `/models` 为 SSR 空壳（原始 HTML 无 `modelinfo` 链接）——即**无干净的公开搜索 API 可用**。Shakker 仅曾由泛搜顺带覆盖，移除后不再作为在线匹配源；短期内不新增 `ShakkerProvider`（避免部署即 500 的空壳，违背"轻量不脆弱"原则）。

## [3.6.2] - 2026-07-24
### Optimized
- **Zero-Hashing Fast Alignment**: Implemented bi-directional path set alignment in `scan_incremental()`. Cleans deleted models in 15ms without re-computing hashes for existing files.

## [3.6.1] - 2026-07-24
### Added
- **Official Specs Alignment**: Full support for latest ComfyUI folders (`diffusion_models`, `text_encoders`) and new widget names (`diffusion_model`, `text_encoder_name`, `unet_name`).

### Fixed & Improved
- **CJK Precision Matching**: Added 2-Gram sliding window tokenization and CJK character overlap scoring bonus.
- **Index Self-Healing**: Automatically cleans physically deleted model entries during `load_index()` and runtime `get_all_models()`.

## [3.6.0] - 2026-07-24
### Fixed
- **Search API Scope Bug**: Fixed `UnboundLocalError` in `/auto-matcher/search` route when returning unindexed local files.

### Optimized
- **Inverted Index Caching**: Added lazy index building (`_index_built`) in `ModelMatcher`. Reduces matching latency from ~55ms to ~7.3ms (7.6x speedup) for large libraries.
- **Index Invalidation**: Linked index invalidation to `/auto-matcher/refresh-index` to ensure cache accuracy on disk changes.

## [3.5.7] - 2026-02-08
### Fixed
- **Strict Type Enforcement**: Implemented strict type checking in Fuzzy/Legacy matching. Now, if a widget expects a `Checkpoint`, any `LoRA` candidates are immediately disqualified, preventing cross-type mismatches.
- **UI Residue Cleaner**: Introduced `MutationObserver` to monitor the modal's lifecycle. This ensures the floating close button is instantly removed even when the modal is closed via background click.
- **Type Display**: Fixed a bug where match results were missing the `type` field, causing them to appear as "UNKNOWN" in the UI.

## [3.5.6] - 2026-02-07
### Fixed
- **Deep Path Normalization**: Added a final layer of path normalization in the Matcher to ensure all output paths (including those from legacy indices or hardcoded databases) use the correct system separator.

## [3.5.5] - 2026-02-04
### Fixed
- **Path Separator**: Fixed incorrect path separator (using `/` instead of `\`) when displaying matched models in Windows environments.

### Fixed
- **Civitai Provider**: Fixed persistent `403 Forbidden` errors by removing manual `User-Agent` rotation that conflicted with `curl_cffi` TLS fingerprinting. System now uses native Chrome 124 attributes.

## [3.5.3] - 2026-02-02
### Fixed
- **DuckDuckGo Provider**: Fixed critical `UnboundLocalError` caused by incorrect variable scope for `platform`.
- **Frontend Stability**: Added safety checks in `auto_matcher.js` to prevent crashes when search results miss the `source` field.
- **Shakker Parsing**: Improved URL parsing for Shakker models in general search results.

## [3.5.2] - 2026-02-02
### Added
- **CNB.cool Integration**: Full support for CNB model search with optimized name matching and relevance checks.
- **Smart Tokenizer**: Enhanced handling for non-standard naming (e.g., `aniWan` -> `ani wan`).
- **Short Smart Term Strategy**: Prioritizes short, tokenized terms to avoid timeout issues with long filenames.
- **Network Stabilization**: Global timeout configuration (20s) in `BaseProvider` to prevent premature failures on slow connections.
- **Verification Suite**: Added `scripts/final_system_verify.py` for full system integrity validation.

### Fixed
- Fixed `KeyError: 0` in verification scripts when no results are found.
- Fixed `curl` resolution timeouts by correctly propagating network config.
- Fixed `CNBProvider` repo ID variable scope issue.

### Added
- **Smart Weighted Tokenizer**: Implemented intelligent filename parsing that correctly handles:
    - Version numbers (e.g., `Wan2.1` -> `Wan`, `2.1`).
    - Model sizes (e.g., `14B`, `7B`).
    - Protected technical terms (`T2V`, `I2V`, `v4`).
- **Weighted Intersection Matching**: New matching engine that prioritizes core tokens (Name + Version + Size) over fuzzy string similarity, solving failures with generic filenames in specific repos.
- **Dynamic Repository Discovery**: 
    - Automatically discovers official repositories (e.g., `Wan-AI`, `nvidia`) via Hugging Face API based on keywords.
    - Repository-aware matching: Uses the repository name as context when matching files.
- **Deep Network Camouflage (Phase 3)**:
    - Upgraded network engine to impersonate `chrome124`.
    - Implemented random User-Agent rotation to bypass Civitai/Cloudflare blocking.
- **Special Case Normalization (Phase 3)**:
    - Added rule for `Wan21` -> `Wan 2.1` to handle non-standard version naming (`aniWan21...`).

### Fixed
- Fixed matching failure for `Wan_2.1_T2V_14B_rCM.safetensors` due to tokenizer splitting errors.
- Fixed inability to match files with generic names (e.g., `model.safetensors`) when they reside in correctly named repositories.
- Fixed tokenization for `14BFp` -> `14B Fp` (Model size stuck to suffix).


## [v3.3.2] - 2026-02-02
### 🧠 深度算法优化 (基于 204 个模型样本)
- **CamelCase 智能分词**: `DasiwaWAN22` → `Dasiwa WAN 22`
- **版本号归一化**: `wan21`, `Wan2_1`, `wan2-1` → `wan2.1`
- **别名映射表**: 25+ 条缩写映射 (zimg→z-image, infinitetalk→wan2.1等)
- **精确映射表**: 60+ 条常用模型→HuggingFace仓库映射
- **Provider 智能路由**: 中文模型优先 Liblib/ModelScope，FLUX/Wan/Qwen 优先 HuggingFace

### 📊 覆盖模型系列
- FLUX (~25), Wan (~15), Qwen (~20), Z-Image (~10)
- LTX (~10), SD/SDXL (~20), ControlNet (~25), 中文模型 (~15)

### 🎯 预期效果
- 精确匹配率: 30% → **>80%**
- 模糊匹配准确率: 50% → **>90%**

## [v3.3.1] - 2026-02-02
### ⚡ 极限性能优化
- **单轮全量并发**: 取消多轮串行搜索，只用最优搜索词一次并发所有 Provider
- **超时压缩**: 全局超时从 15s 降至 3s (Fast-Fail)
- **删除 DDG 延迟**: 移除 0.3-1.0s 随机延迟
- **早停阈值降低**: 从 0.85 降至 0.7，更快返回结果

### 🎯 预期效果
- 从 10-60 秒降至 **≤3 秒**

## [v3.3.0] - 2026-02-02
### 🚀 HuggingFace 搜索深度优化
- **并发目录遍历**: 使用 `asyncio.gather` 同时扫描多个子目录
- **智能剪枝**: 仅扫描与目标文件名相关的目录 (70-80% 剪枝率)
- **仓库结构缓存**: 5 分钟 TTL, 重复搜索直接命中
- **早停机制**: 找到精确匹配立即返回，取消其他任务
- **优先仓库检测**: Kijai/WanVideo_comfy 等社区仓库优先扫描

### ⚡ 性能提升
- 从分钟级降至 **3-5 秒**

## [v3.2.0] - 2026-02-02
### 🎯 精准度大幅提升
- **硬格式阻断**: `.safetensors` 与 `.gguf` 彻底互斥，消除跨格式错误匹配
- **乘法惩罚机制**: 格式不匹配直接归零，不再是弱扣分
- **格式分区索引**: 预过滤候选池，减少 50-70% 无效比较

### ⚡ 性能优化
- 倒排索引按格式分区，加速匹配循环
- 预编译正则表达式，减少重复编译开销

## [v3.1.4] - 2026-02-02
### Changed
- **UX**: Added a friendly reminder to update local index for best performance (once every 24h).
- **UX**: Added "Copy Missing List" button to the results dialog for easy sharing.
- **Perf**: Optimized internal regex compilation for faster matching loops.
- **Core**: Verified and optimized concurrent/multi-threaded execution for external search providers.

## [v3.1.3] - 2026-02-012

### ⚡ Performance & Accuracy
*   **RapidFuzz Integration**: Replaced standard `difflib` with SIMD-accelerated `rapidfuzz`. Matching performance improved by **50-100x**.
*   **Legacy Conflict Guard**: Fixed a critical leak where fallback string matching (Legacy Mode) bypassed safety checks (e.g., I2V matching T2V). Now all matching strategies enforce strict conflict rules.
*   **Anti-Detect**: Upgraded Civitai/Liblib scraper fingerprint to `chrome124` to reduce 403 errors.

### 📚 Documentation
*   **Refactor**: Consolidated `DEVLOG.md` into `CHANGELOG.md` for a single source of truth.
*   **Architecture**: Renamed Whitepaper to `ARCHITECTURE.md` and linked it in README.

## [3.1.2] - 2026-02-02

### 🧠 Algorithm
*   **Deep Conflict Guard**: Implemented strict token conflict checking to prevent invalid cross-matches:
    *   **I2V vs T2V**: Strictly isolated.
    *   **Rank Awareness**: Now checks numeric values in filenames (`rank83` vs `rank128`).
    *   **Category Logic**: VAEs will no longer match Checkpoints.
*   **Variant Optimization**: Applied conflict logic to all matching strategies (Exact, Fuzzy, Variant).

## [3.1.1] - 2026-02-02

### ⚡ Optimization
*   **Async Hashing**: Offloaded heavy SHA256 calculation for Civitai matching to a background thread, preventing UI freezes when processing large checkpoints.
*   **Modular Architecture**: Refactored `matcher.py` into atomic methods (`_find_exact_match`, `_find_fuzzy_match`, etc.) for better maintainability and debugging.

### 🛡️ Stability
*   **Bug Fix**: Resolved `UnboundLocalError` in fuzzy matching logic where candidate indices were not initialized.
*   **Protocol**: Established `qa-protocol` workflow to enforce TDD and strict code review for core modules.
*   **Tests**: Added persistent verification scripts (`scripts/verify_*.py`) to CI/CD pipeline.

## [3.1.0] - 2026-01-30
### 🔥 Core Architecture
*   **Local SQLite Database**: Replaced hardcoded dictionaries with `core/data/models.db` (SQLite) for O(1) queries and dynamic updates.
*   **Offline Indexing**: Added `scripts/fetch_top_models.py` to fetch top Civitai models into local DB.
*   **Anti-Bot**: Integrated `curl_cffi` to bypass Cloudflare 403 on Civitai/Liblib.

## [3.0.1] - 2026-01-25
### ✨ Features
*   **Civitai Hash Matching**: Implemented SHA256 based matching for 100% accuracy on Civitai models.
*   **Recursive Search**: HuggingFace provider now searches subdirectories (up to depth 3).
*   **UI Fix**: Fixed "Close Button" being obscured by content (Sticky positioning).

## [3.0.0] - 2026-01-20
### 🚀 Major Algorithm Update
*   **Direct API Integration**: Replaced Google Scraping with direct HuggingFace Hub API calls for stability.
*   **RapidFuzz**: Replaced custom similarity logic with `rapidfuzz` library, reducing matching time from minutes to milliseconds.
*   **Race Mode**: Concurrent searching across multiple providers (Civitai, HF, Liblib) with "fastest win" strategy.

## [1.4.0] - 2026-01-15
### 🌐 Platform Support
*   **Liblib Support**: Added native search provider for Liblib.art.
*   **Chinese Optimization**: Improved tokenizer to extract English core terms from Chinese filenames (e.g. "哪吒Flux" -> "Flux").
*   **Filtering**: Added strict file extension filtering in Scanner.

## [1.3.1] - 2026-01-10
### 🧠 Deep Tokenization
*   **Smart Splitting**: Handles camelCase and alphanumeric concatenation (e.g. `wan22Remix` -> `wan 22 Remix`).
*   **GGUF Support**: Enhanced quantization detection (`Q4_K_M`, `IQ4_NL`) and matching logic.

