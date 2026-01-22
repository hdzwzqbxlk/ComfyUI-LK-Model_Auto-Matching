# ComfyUI-LK-Model_Auto-Matching 技术白皮书

> **版本**: 1.3.1 (2026-01)  
> **状态**: 稳定 / 持续迭代  
> **维护者**: LK Team

---

## 1. 项目概览 (Project Overview)

**ComfyUI-LK-Model_Auto-Matching** 是一个专为 ComfyUI 设计的智能模型匹配与修复系统。它旨在解决用户在导入第三方工作流（Workflow）时，因本地模型文件名与工作流中记录的名称不一致，导致出现大量红色 "missing model" 报错的痛点。

### 核心价值
- **自动化匹配 (Auto-Matching)**: 基于语义和模糊匹配算法，自动寻找本地已有的同名或变体模型。
- **全网聚合搜索 (Omni-Search)**: 本地缺失时，自动从 Civitai, HuggingFace, ModelScope 等主流平台搜索下载链接。
- **智能兼容性 (Smart Compatibility)**: 识别量化版本 (FP16 vs FP8)、格式差异 (Safetensors vs GGUF)，防止错误替换。

---

## 2. 系统架构 (System Architecture)

项目采用模块化设计，核心由四大组件构成：

```mermaid
graph TD
    User[ComfyUI 用户] -->|加载工作流/点击匹配| UI[JS Frontend (auto_matcher.js)]
    UI -->|API请求| Backend[Python Backend (__init__.py)]
    
    subgraph Core Engine
        Backend --> Matcher[本地匹配器 (matcher.py)]
        Backend --> Searcher[网络搜索器 (searcher.py)]
        
        Matcher -->|索引构建| Scanner[文件扫描器 (scanner.py)]
        Matcher & Searcher -->|分词与相似度| Utils[核心工具库 (utils.py)]
    end
    
    Searcher -->|API/Scraping| External[外部模型源]
    External --> Civitai
    External --> HuggingFace
    External --> ModelScope
    External --> Google/DDG
```

### 模块说明
| 模块 | 职责 | 关键技术 |
| :--- | :--- | :--- |
| **Scanner** | 遍历 ComfyUI `models/` 目录 | 递归扫描, 路径缓存 |
| **Matcher** | 寻找本地最佳替代模型 | 倒排索引, 格式校验, 变体推断 |
| **Searcher** | 网络搜索模型信息 | 异步并发 (AsyncIO), 浏览器指纹模拟 (curl_cffi) |
| **Utils** | 提供分词、清洗、评分算法 | Deep Tokenization, 加权 Jaccard, 正则引擎 |

---

## 3. 核心技术实现 (Implementation Logic)

### 3.1 智能分词引擎 (Deep Tokenization)
位于 `core/utils.py` 的 `AdvancedTokenizer` 类是整个系统的核心大脑。它不仅仅是简单的字符串分割，还通过多层处理实现了“语义理解”。

- **Pipeline 流程**:
    1.  **Normalization**: 统一大小写，标准化符号 (将 `F.1` 归一化为 `Flux 1`)。
    2.  **CJK Segmentation (中文优化)**: 正则分离中文字符与英数字符，解决中文模型名粘连问题 (如 `人脸F.1` -> `人脸 F 1`)。
    3.  **De-Noising (去噪)**: 剥离技术后缀（`fp16`, `pruned`, `gguf`, `repack`），提取模型“核心名”。
    4.  **Pattern Recognition**: 识别特定术语（`sdxl`, `lora`, `controlnet`）并赋予保护权重。

### 3.2 多维相似度算法 (Multi-Dimensional Similarity)
系统摒弃了单一的 Levenshtein 距离，采用多层级判定策略：

1.  **架构排斥 (Architecture Guard)**: 
    - 优先检测基座模型 (Base Model Detection)。
    - **规则**: 若 Model A 是 `SDXL`，Model B 是 `SD1.5`，即使名字相似度 99%，得分为 0 (直接拒绝)。
    - **逻辑**: 通过 `detect_base_model()` 实现，涵盖 SD1.5, SDXL, SD3, Flux, Pony, Hunyuan 等。

2.  **兼容性检查 (Compatibility Check)**:
    - **Flux 互斥**: `Dev` 版本不能匹配 `Schnell` 版本。
    - **SDXL 互斥**: `Base` 不能匹配 `Refiner`。
    - **格式隔离**: `.gguf` 文件绝不匹配 `.safetensors`，除非是纯搜索模式。

3.  **混合相似度 (Hybrid Score)**:
    - 结合 `Rapidfuzz` (如果可用) 和 `Jaccard Similarity`。
    - 对包含中文的模型名赋予特殊权重。

### 3.3 全网聚合搜索 (Omni-Search Provider)
针对模型分散在不同平台的现状，实现了 `GoogleOmniProvider` 和专用 API Provider。

- **渐进式搜索策略 (Progressive Strategy)**:
    - **Attempt 1**: 搜索原始文件名 (Raw Stem) -> 命中率高，特别是 Google。
    - **Attempt 2**: 搜索清洗后的空格分隔名 (Spaced) -> 适合通用搜索。
    - **Attempt 3+**: 搜索深层分词结果 (Deep Tokenized) -> 解决 `wan2.1` 这种复杂命名。
- **GGUF 优化**:
    - 针对 GGUF 模型，搜索词自动追加 `gguf` 关键字。
    - 自动识别 HuggingFace 的 `-GGUF` 仓库后缀 pattern。
- **反爬虫技术**:
    - 使用 `curl_cffi` 库模拟 `Chrome 120` 的 TLS 指纹和 HTTP2 特征，有效绕过 Cloudflare 验证。

---

## 4. 技术路线与依赖 (Tech Stack)

### 核心依赖
- **Python 3.10+**: 核心逻辑。
- **curl_cffi**: 高级 HTTP 客户端，支持指纹模拟 (替代传统的 requests/aiohttp)。
- **rapidfuzz** (Optional): 高性能字符串匹配库，比 standard library 快 10-100 倍。
- **parsel**: 强大的 HTML/XML 解析库 (基于 lxml)，用于 Google/DuckDuckGo 结果提取。

### 依赖文件规范
项目严格遵循 `requirements.txt` 管理依赖，并建议使用 `uv` 进行环境锁定：
```bash
uv pip install -r requirements.txt
```

---

## 5. 未来演进规划 (Roadmap)

基于当前架构和 `DEVLOG`，后续迭代将聚焦于以下方向：

### Phase 1: 深度中文与本地化 (Near Term)
- **目标**: 让国内用户体验无缝化。
- **计划**:
    - [ ] 引入 `jieba` 或轻量级中文分词库，优化中文模型名匹配。
    - [ ] 增强 ModelScope 和 Liblib 的搜索权重。
    - [ ] 支持 Civitai 镜像源配置。

### Phase 2: 版本与系列感知 (Mid Term)
- **目标**: 解决 `v1.0` vs `v2.0` 的匹配歧义。
- **计划**:
    - [ ] 实现语义版本号解析 (Semantic Versioning Parser)。
    - [ ] 建立模型“族谱”数据库 (Family Tree)，理解 `Juggernaut` 各版本演进关系。

### Phase 3: 模型指纹识别 (Long Term)
- **目标**: 摆脱文件名依赖。
- **计划**:
    - [ ] 读取模型 Header (Safetensors metadata)。
    - [ ] 计算文件哈希 (SHA256/BLAKE3) 并建立云端哈希库。

---

_本文档由 Antigravity 自动生成，归档于项目根目录_
