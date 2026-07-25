# ComfyUI-LK-Model_Auto-Matching

![GitHub last commit](https://img.shields.io/github/last-commit/hdzwzqbxlk/ComfyUI-LK-Model_Auto-Matching)
![Version](https://img.shields.io/badge/Version-v3.6.3-blue.svg)

**[English](#english) | [中文说明](#chinese)**

---

<a name="english"></a>
## 🇬🇧 English

### Introduction
**ComfyUI-LK-Model_Auto-Matching** is a powerful ComfyUI extension designed to solve the annoying "missing model" errors (red nodes) when loading shared workflows. 

Instead of manually re-selecting every single Checkpoint, LoRA, or VAE, this plugin acts as a **Magic Wand 🪄** to scan your local library and intelligently match them to the workflow's requirements.

### ✨ Key Features

*   **🪄 Magic One-Click Fix**: Just look for the **"LK 🪄 Auto Match"** button in your ComfyUI menu. Click it, and let the magic happen.
*   **🧠 Intelligent Fuzzy Matching**: 
    *   Matches exact filenames regardless of folder structure.
    *   Smartly handles differences like `v1-5-pruned.ckpt` vs `v1-5-pruned.safetensors`.
    *   Case-insensitive matching.
*   **🛡️ Safety First**: The plugin **never** changes anything silently. It presents a clear confirmation dialog showing exactly what will be changed (`Original -> New`).
*   **🎨 Premium UI**: Optimized user interface with clear "LK" branding and dark mode support.
*   **⚡ Non-Intrusive**: intelligently places itself in the menu without breaking other extensions (like LoRA Manager).

### 📂 Supported Model Types
The plugin automatically detects and matches the following model types:
*   ✅ **Checkpoints** (Stable Diffusion, SDXL, Flux, etc.)
*   ✅ **LoRAs**
*   ✅ **VAE**
*   ✅ **ControlNet**
*   ✅ **Upscale Models** (ESRGAN, SwinIR, etc.)
*   ✅ **CLIP**
*   ✅ **UNET**
*   ✅ **Embeddings**

### 📦 Installation

#### Method 1: Git Clone (Recommended)
1.  Navigate to your ComfyUI `custom_nodes` directory:
    ```bash
    cd ComfyUI/custom_nodes/
    ```
2.  Clone this repository:
    ```bash
    git clone https://github.com/hdzwzqbxlk/ComfyUI-LK-Model_Auto-Matching.git
    ```
3.  **Install Dependencies**:
    ```bash
    cd ComfyUI-LK-Model_Auto-Matching
    pip install -r requirements.txt
    ```
4.  Restart ComfyUI.

#### Method 2: Update
If you already have it installed, simply navigate to the folder and pull the latest changes:
```bash
cd ComfyUI/custom_nodes/ComfyUI-LK-Model_Auto-Matching
git pull
pip install -r requirements.txt
```

### 🚀 Advanced Features (New in v3.0)
*   **Database-Driven Matching**: The system now uses a high-performance local SQLite database (`core/data/models.db`) for instant and accurate lookups, reducing reliance on slow network searches.
*   **Offline Indexing**: You can populate your local database with thousands of popular Civitai models to make the matcher even smarter.
    *   **How to use**:
        ```bash
        python scripts/fetch_top_models.py
        ```
        This script fetches the top downloaded models from Civitai and adds them to your local index.

### 🎮 Usage Guide
1.  **Load a Workflow**: Open a workflow that contains missing models (nodes highlighting in red).
2.  **Click Auto Match**: Find the button labeled **<span style="color: #64b5f6">LK</span> 🪄 Auto Match** in the top menu bar (near the Queue button).
3.  **Review Changes**: A popup will show you the proposed matches.
4.  **Confirm**: Click **OK** to apply the fixes instantly.

---

<a name="chinese"></a>
## 🇨🇳 中文说明

### 简介
**ComfyUI-LK-Model_Auto-Matching** 是一款专为解决 ComfyUI "模型路径丢失" 痛点而生的插件。

当你加载别人的工作流时，满屏的红色报错节点不再是噩梦。本插件就像一根 **魔法棒 🪄**，能自动扫描你本地所有的模型文件，并智能匹配工作流中缺失的模型，让你彻底告别繁琐的手动纠错。

### ✨ 核心亮点

*   **🧠 智能全域匹配 (Smart Global Matching)**
    - **多级匹配策略**: 依次尝试 精确路径 -> 文件名匹配 -> 模糊相似度 -> **交叉变体匹配**。
    - **交叉变体识别**: 自动识别同模型的不同版本（如 `bf16` vs `fp16`, `Q4_K_M` vs `Q5_K_M`），大幅提高 Workflow 兼容性。
    - **严格格式卫士**: 强制文件类型隔离（如 `GGUF` 不会匹配 `Safetensors`），杜绝模型加载报错。

*   **🚀 极速数据库模式 (New)**
    - **本地 SQLite 引擎**: 采用全新的数据库架构取代旧版字典，提供毫秒级精确查询。
    - **离线索引构建**: 支持一键获取 Civitai 热门模型数据，构建强大的本地知识库，不再依赖实时网络。

*   **🔍 全网聚合搜索 (All-Network Aggregation)**
    - **竞速模式 (Race Mode)**: 同时并发请求 Civitai, HuggingFace, Liblib, ModelScope，毫秒级响应。
    - **API 优先**: 优先使用官方 API 进行精确检索（支持 Civitai Hash, HF File Search）。
    - **兜底保障**: 当垂直网站无结果时，自动调用 Google/DuckDuckGo 进行全网补漏。

*   **🛡️ 安全可靠**
    - **零依赖**: 纯 Python 实现，无需复杂环境配置。
    - **隐私保护**: 仅发送模型名称进行搜索，不上传任何图像或敏感数据。
    *   **非侵入式 UI**: 深度适配 ComfyUI 界面，带有醒目的 LK 品牌标识，且不遮挡其他插件。

### 📂 支持的模型类型
全面覆盖 ComfyUI 常用模型节点：
*   ✅ **大模型 (Checkpoints)**
*   ✅ **LoRA / LyCORIS**
*   ✅ **VAE**
*   ✅ **ControlNet**
*   ✅ **放大模型 (Upscale Models)**
*   ✅ **CLIP**
*   ✅ **UNET**
*   ✅ **Embeddings**

### 📦 安装与更新

#### 方式 1: Git 克隆 (推荐)
1.  进入你的 ComfyUI `custom_nodes` 目录：
    ```bash
    cd ComfyUI/custom_nodes/
    ```
2.  克隆本仓库：
    ```bash
    git clone https://github.com/hdzwzqbxlk/ComfyUI-LK-Model_Auto-Matching.git
    ```
3.  **安装依赖**：
    ```bash
    cd ComfyUI-LK-Model_Auto-Matching
    pip install -r requirements.txt
    ```
4.  重启 ComfyUI。

#### 方式 2: 更新插件
如果你已经安装了旧版本，请在插件目录下运行更新命令：
```bash
cd ComfyUI/custom_nodes/ComfyUI-LK-Model_Auto-Matching
git pull
pip install -r requirements.txt
```

### 🚀 高级功能 (v3.0 新增)
*   **离线索引增强**: 想要更强大的本地匹配能力？运行以下脚本即可自动从 Civitai 获取流行模型数据并存入本地数据库：
    ```bash
    python scripts/fetch_top_models.py
    ```
    (提示：该脚本会自动绕过部分反爬验证，建议定期运行以保持数据库最新)

*   **技术架构**: 深度算法解析请参阅 [ARCHITECTURE.md](ARCHITECTURE.md)。

### 🎮 使用教程
1.  **加载工作流**: 导入任何包含报错（红色节点）的工作流。
2.  **点击修复**: 在顶部菜单栏（通常在 "Queue Prompt" 按钮左侧）找到 **<span style="color: #64b5f6">LK</span> 🪄 Auto Match** 按钮。
3.  **确认方案**: 插件会弹出一个对话框，列出它找到的所有替换方案。
4.  **应用更改**: 点击 **确定 (OK)**，所有红色节点将自动恢复正常。

---
**Created by LK** | Happy Creating! 🎨
