# ComfyUI-LK-Model_Auto-Matching 开发日志

> 最后更新: 2026-01-19 | 版本: v1.3.1

---

## 🚀 v1.3.1 - 深度搜索优化 (2026-01-19)

### 🔥 核心突破
1. **Deep Tokenization (深度分词引擎)**:
   - 针对 `wan22RemixSFW` 这种连写命名，实现了 `CamelCase` 和 `AlphaNumeric` 自动拆分。
   - 效果: `wan22Remix` -> `wan 22 Remix`，完美命中 HuggingFace 仓库。
2. **Progressive Search (渐进式搜索策略)**:
   - 自动执行三级回退搜索: `Raw Stem` (精准) -> `Spaced` (常规) -> `Deep Token` (模糊)。
   - 大幅提升了冷门和复杂命名模型的召回率。

### 🛠 问题修复
1. **HuggingFace URL 解析修复**:
   - 之前: `huggingface.co/User/Repo` -> 解析为 `User` (评分失败)。
   - 现在: 解析为 `User/Repo` (评分成功)，可正确索引 Gated 模型。
2. **DuckDuckGo 稳定性增强**:
   - 优化了 HTML 解析逻辑，作为 Google 的强力兜底方案。

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
