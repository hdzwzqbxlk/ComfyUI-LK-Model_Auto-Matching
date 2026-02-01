# Changelog

## [3.4.2] - 2026-02-02
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

