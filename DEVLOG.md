# ComfyUI-LK-Model_Auto-Matching 开发日志

> 最后更新: 2026-02-01 | 版本: v3.1.0

---

## 🚀 v3.1.0 - 本地数据库架构升级 (2026-02-01)

### 🔥 核心架构变革
1.  **SQLite 本地数据库引擎 (`core/database.py`)**:
    -   **抛弃硬编码**: 将原有的 `MODEL_ALIASES` 和 `COMFYUI_POPULAR_MODELS` 字典完全迁移至 `core/data/models.db` (SQLite) 中。
    -   **Schema 设计**: 实现了 `models` (模型实体), `file_hashes` (哈希映射), `aliases` (别名映射) 三表结构，支持更复杂的关联查询。
    -   **优势**: 实现了数据与代码分离，支持动态更新，且查询速度为 O(1)。

2.  **离线索引构建 (`scripts/fetch_top_models.py`)**:
    -   新增脚本支持从 Civitai API 批量拉取热门模型数据并存入本地数据库。
    -   **反爬增强**: `fetch_top_models.py` 集成了 `curl_cffi`，模拟 Chrome 120 指纹，有效绕过 Cloudflare 403 拦截，确保数据获取的稳定性。

3.  **查询逻辑重构 (`core/utils.py`)**:
    -   升级 `lookup_popular_model` 方法，**优先查询本地数据库**。
    -   如果数据库未命中，自动回退到旧版字典匹配，确保兼容性。
    -   自动解析数据库中的 `description` 字段提取 HuggingFace Repo ID。

### 🛠 技术细节
-   **依赖更新**: 引入 `curl_cffi` 用于对抗反爬。
-   **数据迁移**: 实现了 `ModelDatabase.populate_from_json()` 方法，在初始化时自动将旧 JSON 数据迁移至 SQLite。
-   **项目结构**: 新增 `core/data/` 目录用于存放数据库文件。

## 🚀 v3.0.1 - Civitai 哈希匹配与递归搜索 (2026-02-01)

### 🔥 核心改进
1. **Civitai SHA256 哈希精确匹配**:
   - 实现了基于 SHA256 文件哈希的 Civitai 模型匹配算法。
   - 准确率达到 **100%** (针对所有出自 Civitai 的模型)。
   - 调用官方 API: `/api/v1/model-versions/by-hash/{hash}`。

2. **HuggingFace 递归子目录遍历**:
   - 修复了此前无法匹配子路径模型 (如 `LoRAs/rCM/`) 的问题。
   - `HuggingFaceFileSearchProvider` 现在会递归遍历仓库 tree，深度可达 3 层。

3. **UI 体验优化**:
   - **Sticky Close Button**: 修复了搜索结果列表滚动时，右上角关闭按钮 "X" 被遮挡的问题。
   - 现在关闭按钮在滚动时依然固定在右上角。

4. **多轮搜索策略扩展**:
   - 针对 LoRA 模型，自动补全社区常见仓库关键词 (如 `Kijai`, `WanVideo`, `comfy`)。

### 🛠 技术细节
- `searcher.py`: 新增 `CivitaiHashProvider` 类，计算 SHA256 并聚合多轮 HF 搜索结果。
- `js/auto_matcher.js`: 修改 `xBtn.style.position` 为 `sticky`。

---

## 🚀 v3.0.0 - 算法大版本升级 (2026-02-01)

### 🔥 核心改进
1. **HuggingFace Hub API 直接集成**:
   - 彻底废弃依赖 Google 搜索的旧方案。
   - 直接搜索 HF 数据库，极大降低了被封禁 IP 的风险。

2. **反爬策略专项修复**:
   - 移除了所有 Provider 中敏感的 `site:` 搜索语法。
   - 加入了随机请求延迟 (0.2s - 1.5s)，模拟人类行为。

3. **高性能相似度算法**:
   - 全面引入 `rapidfuzz` 库，替换了旧的手写相似度计算逻辑。
   - 处理 10k 次匹配的延迟从分钟级降至毫秒级。

---

## 🚀 v1.4.0 - 搜索精准度优化 (2026-01-22)

### 🔥 核心改进
1. **Provider 优先级重排**:
   - 新顺序: `Civitai → HuggingFace → Liblib(新增) → ModelScope → Google → DuckDuckGo`
   - 高优先级平台返回高分结果时自动跳过低优先级搜索，提升响应速度。

2. **Liblib Provider (新增)**:
   - 新增对 **liblib.art (哩布哩布)** 平台的原生搜索支持。
   - 通过 CSS Selector 解析模型卡片链接，支持中文模型名搜索。

3. **中文分词增强 (Chinese Core Extraction)**:
   - 对包含中文的模型名，**优先提取英文核心词**作为首选搜索词。
   - 效果: `哪吒Flux模型_V2.0.safetensors`
     - 首选词: `"哪吒Flux模型_V2.0"` (Liblib/ModelScope 优先)
     - 备选词: `"Flux V2"` (Civitai/HF 兜底)
   - 策略调整: 针对中文模型名，优先保留完整中文名称以确保国内平台搜索准确性，同时保留英文核心词以兼容国际平台。

4. **非模型文件过滤 (Scanner Level)**:
   - 在 `scanner.py` 扫描阶段新增 `VALID_MODEL_EXTENSIONS` 常量。
   - 自动过滤 `.png`, `.txt`, `.mp3` 等非模型文件，避免索引污染。

### 🛠 技术细节
- `searcher.py`: 新增 `LiblibProvider` 类 (L322-385)，重排 `self.providers` 列表。
- `utils.py`: `extract_search_terms()` 增加英文核心提取逻辑 (Phase 2a)。
- `scanner.py`: 新增 `VALID_MODEL_EXTENSIONS` 集合，在 `disk_files` 循环中过滤。

---

## 🚀 v1.3.1 - 深度搜索优化 (2026-01-19)

### 🔥 核心突破
1. **Deep Tokenization (深度分词引擎)**:
   - 针对 `wan22RemixSFW` 这种连写命名，实现了 `CamelCase` 和 `AlphaNumeric` 自动拆分。
   - 效果: `wan22Remix` -> `wan 22 Remix`，完美命中 HuggingFace 仓库。
2. **Progressive Search (渐进式搜索策略)**:
3. **Google Search 修复**:
   - 修复了此前无法抓取 Google 搜索结果中重定向链接 (如 `/url?q=...`) 的 Bug。
   - 现在能够正确提取并匹配 **LiblibAI (哩布哩布)**、**ModelScope (魔搭)** 等平台的链接。
4. **Strict Matching Refinement (严格模式)**:
   - **内容差异惩罚**: 防止 Finetune 模型与 Base 模型误匹配。
     - 效果: `AsianFace F.1` (Finetune) vs `Flux1-dev` (Base) -> **不匹配** (正确)。
   - **GGUF Search Enhancement**:
   - **强制 GGUF 关键字**: 针对 `.gguf` 文件所生成的所有搜索词（包括降级备选相），均强制追加 `gguf`，确保搜索结果精准命中 GGUF 仓库。
   - **Extended Precision Support (全面扩展)**:
     - 基础类型: `Q2_K`, `Q3_K_L`, `Q4_K_M`, `Q5_K_S`, `Q6_K`, `Q8_0` 等。
     - IMatrix 新类型: `IQ1_S`, `IQ2_XXS`, `IQ3_M`, `IQ4_NL` 等。
     - 特殊类型: `SQ`, `TQ` (Ternary), `F16`, `F32`。
     - 所有这些后缀现在都能被 `detect_quantization` 正确识别，并从核心命名中剥离，避免干扰匹配。
6. **Robust Filtering**:
   - 增加文件扩展名过滤器，匹配器将自动忽略非模型文件 (`.mp3`, `.png`, `.txt` 等)，仅处理 `.safetensors`, `.gguf`, `.ckpt` 等有效模型格式。
7. **UI Experience**:
   - 修复设置面板中已保存的 API Key 不显示的问题 (Backend method missing fix)。

### 🛠 问题修复
1. **HuggingFace URL 解析修复**:
   - 之前: `huggingface.co/User/Repo` -> 解析为 `User` (评分失败)。
   - 现在: 解析为 `User/Repo` (评分成功)，可正确索引 Gated 模型。
2. **DuckDuckGo & Google 稳定性增强**:
   - 优化了 HTML 解析逻辑 (CSS Selector)，能够兼容 Google 的动态结果结构。

### 💅 体验优化
- 移除了设置弹窗标题中冗余的版本号显示。

---

## 📁 项目架构

```
ComfyUI-LK-Model_Auto-Matching/
├── __init__.py          # 入口文件，注册 API 路由
├── matcher.py           # 本地模型匹配器
├── scanner.py           # 模型目录扫描器
├── searcher.py          # 网络模型搜索器 (Civitai/HF/ModelScope/Google)
├── utils.py             # 核心工具类 (AdvancedTokenizer, 常量定义)
├── js/
│   └── auto_matcher.js  # 前端 UI (悬浮条、设置对话框)
└── tests/               # 测试文件
```

---

## 🔧 核心组件说明

### 1. `utils.py` - 智能分词与相似度计算

**关键常量:**
- `COMFYUI_POPULAR_MODELS` - 主流模型精确映射表 (60+ 模型)
- `CRITICAL_TERMS` - 功能差异关键词 (严格区分 inpainting/depth/canny 等)
- `NOISE_SUFFIXES` - 技术噪声词 (fp16, pruned, ema 等)
- `VARIANT_SUFFIXES` - 变体后缀 (量化标记、格式后缀)

**关键方法:**
- `AdvancedTokenizer.lookup_popular_model(filename)` - 主流模型快速查找
- `AdvancedTokenizer.calculate_similarity(a, b)` - 综合相似度计算
- `AdvancedTokenizer.extract_search_terms(filename)` - 搜索词提取
- `AdvancedTokenizer.detect_base_model(filename)` - 基座模型检测
- `AdvancedTokenizer.detect_quantization(filename)` - 量化类型检测

### 2. `searcher.py` - 网络搜索引擎

**搜索优先级:**
1. 主流模型快速匹配 (COMFYUI_POPULAR_MODELS)
2. Civitai API
3. HuggingFace API
4. ModelScope HTML 解析
5. Google HTML Scraper (兜底)

**关键方法:**
- `search(filename, ignore_cache)` - 主入口
- `_search_civitai_multi()` - Civitai 多词搜索
- `_search_hf_multi()` - HuggingFace 搜索
- `_search_google_html()` - Google 终极兜底

### 3. `matcher.py` - 本地匹配器

**匹配策略:**
1. 精确匹配 (文件名完全相同)
2. 模糊匹配 (相似度 > 阈值)
3. 格式兼容性检查 (GGUF vs Safetensors)
4. 量化兼容性检查

---

## ✅ 已完成优化 (v1.2.0)

### 主流模型快速匹配
- 添加 `COMFYUI_POPULAR_MODELS` 映射表 (60+ 模型)
- 覆盖: SD1.5, SDXL, SD3.5, Flux, SUPIR, AuraFlow, LTX-2, Mochi, SVD
- 覆盖: 加速 LoRA (Hyper/LCM/TCD/Lightning)
- 覆盖: 文本编码器 (CLIP, T5XXL)

### GGUF 仓库智能匹配
- 仓库名以 `-GGUF` 结尾时，放宽量化检测
- 示例: `qwen-Q4_K_S.gguf` 可匹配 `unsloth/Qwen-GGUF`

### CRITICAL_TERMS 优化
- 移除 `lora`, `video`, `motion`, `animate` (避免误判)
- 保留 `inpainting`, ControlNet 类型 (严格区分)

### 组织名前缀处理
- 自动移除 HF 仓库的组织名 (如 `unsloth/`)

---

## 🎯 待优化方向

### 高优先级
1. **中文模型名支持** - 当前中文分词效果差
2. **更多主流模型覆盖** - 持续扩充映射表
3. **搜索词提取优化** - `Hyper-SDXL-8steps` 提取为 `sdxl lora` 不够精准

### 中优先级
1. **版本号智能匹配** - `v1.0` vs `v2.0` 区分
2. **模型系列识别** - Juggernaut XI vs Juggernaut X
3. **LoRA 与基座模型关联** - LoRA 匹配到对应基座仓库

### 低优先级
1. **缓存持久化** - 搜索结果写入文件缓存
2. **API Key 多平台支持** - HF Token 等

---

## 🛠 常用调试命令

```powershell
# 测试相似度计算
uv run python -c "
from utils import AdvancedTokenizer
score = AdvancedTokenizer.calculate_similarity('flux1-dev.safetensors', 'FLUX.1-dev')
print(f'Score: {score}')
"

# 测试主流模型查找
uv run python -c "
from utils import AdvancedTokenizer
result = AdvancedTokenizer.lookup_popular_model('sd3.5_large.safetensors')
print(f'Result: {result}')
"

# 测试搜索词提取
uv run python -c "
from utils import AdvancedTokenizer
terms = AdvancedTokenizer.extract_search_terms('Hyper-SDXL-8steps-lora.safetensors')
print(f'Terms: {terms}')
"

# 测试完整搜索流程
uv run python -c "
import asyncio
from searcher import ModelSearcher
async def test():
    s = ModelSearcher()
    r = await s.search('flux1-dev.safetensors')
    print(r)
asyncio.run(test())
"
```

---

## 📊 测试结果基准 (v1.2.0)

| 测试类别 | 通过率 |
|---------|-------|
| 主流模型快速查找 | 11/11 (100%) |
| 相似度计算 | 10/14 (71%) |
| 实际搜索流程 | 100% |

**已知限制:**
- `svd_xt_1_1` vs `stable-video-diffusion-img2vid` 相似度低 (0.23) 但被快速查找覆盖
- 中文模型名相似度计算效果差

---

## 🔗 相关链接

- **GitHub**: https://github.com/hdzwzqbxlk/ComfyUI-LK-Model_Auto-Matching
- **ComfyUI 官方示例**: https://comfyanonymous.github.io/ComfyUI_examples/
- **Civitai API**: https://civitai.com/api/v1/models
- **HuggingFace API**: https://huggingface.co/api/models
