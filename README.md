# ComfyUI-LK-Model_Auto-Matching

![GitHub last commit](https://img.shields.io/github/last-commit/hdzwzqbxlk/ComfyUI-LK-Model_Auto-Matching)
![GitHub license](https://img.shields.io/github/license/hdzwzqbxlk/ComfyUI-LK-Model_Auto-Matching)
![Version](https://img.shields.io/badge/version-1.0.0-blue)

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
3.  Restart ComfyUI.

#### Method 2: Update
If you already have it installed, simply navigate to the folder and pull the latest changes:
```bash
cd ComfyUI/custom_nodes/ComfyUI-LK-Model_Auto-Matching
git pull
```

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

*   **⚡ 极速索引引擎 (Smart Indexing)**:
    - 采用本地索引数据库 (`model_index.json`)，匹配速度高达 **毫秒级**。
    - **增量更新**: 点击 "🔄" 按钮仅扫描变动文件，GB 级大模型也能秒级处理。
    - **文件位置感知**: 即使移动了文件或重命名，只要文件内容未变，插件依然能自动识别并更新路径。
*   **🪄 一键魔法修复**: 在菜单栏点击 **"LK 🪄 Auto Match"** 按钮，瞬间完成全图扫描与修复。
*   **🧠 智能模糊匹配算法**: 
    -   **忽略路径差异**: 无论你的模型放在哪个子文件夹，只要文件名对得上就能找到。
    -   **智能识别扩展名**: 自动识别 `.ckpt` 与 `.safetensors` 为同一模型。
    *   **忽略大小写**: 解决不同操作系统间的文件名大小写问题。
*   **🛡️ 安全可靠**: 所有修改在应用前都会弹出详细的对比列表 (`原模型 -> 新模型`)，经你确认后才会执行。
*   **🎨 专属 UI 设计**: 带有醒目的 LK 品牌标识与魔法棒图标，深度适配 ComfyUI深色主题，且不遮挡 LoRA Manager 等其他插件图标。

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
3.  重启 ComfyUI。

#### 方式 2: 更新插件
如果你已经安装了旧版本，请在插件目录下运行更新命令：
```bash
cd ComfyUI/custom_nodes/ComfyUI-LK-Model_Auto-Matching
git pull
```

### 🎮 使用教程
1.  **加载工作流**: 导入任何包含报错（红色节点）的工作流。
2.  **点击修复**: 在顶部菜单栏（通常在 "Queue Prompt" 按钮左侧）找到 **<span style="color: #64b5f6">LK</span> 🪄 Auto Match** 按钮。
3.  **确认方案**: 插件会弹出一个对话框，列出它找到的所有替换方案。
4.  **应用更改**: 点击 **确定 (OK)**，所有红色节点将自动恢复正常。

---
**Created by LK** | Happy Creating! 🎨
