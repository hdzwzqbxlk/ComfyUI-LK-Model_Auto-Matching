# ComfyUI-LK-Model_Auto-Matching
**[English](#english) | [中文](#chinese)**

---

<a name="english"></a>
## 🇬🇧 English

### Introduction
**ComfyUI-LK-Model_Auto-Matching** is a ComfyUI custom node extension designed to solve the common headache of broken model paths when loading workflows from others.

When you import a workflow, the model paths (Checkpoints, LoRAs, VAEs, etc.) often point to the original author's specific folders, which might not exist on your machine. This plugin automatically scans your local models and intelligently matches them to the missing nodes in the workflow, saving you from manually re-selecting every single model.

### Key Features
*   **One-Click Fix**: Adds an "Auto Match Models" button to the ComfyUI menu.
*   **Smart Detection**: Automatically identifies model widgets in the current workflow that have invalid values.
*   **Exact Match**: Matches files with the same name, ignoring folder structures.
*   **Fuzzy Match**: Intelligently matches files even if they have slightly different names (e.g., `v1.5-pruned.ckpt` matching `v1.5-pruned.safetensors`, ignoring extensions and case).
*   **Safe**: Requires user confirmation before applying any changes.

### Installation
1.  Navigate to your ComfyUI custom nodes directory:
    ```bash
    cd ComfyUI/custom_nodes/
    ```
2.  Clone this repository:
    ```bash
    git clone https://github.com/YourUsername/ComfyUI-LK-Model_Auto-Matching.git
    ```
3.  Restart ComfyUI.

### Usage
1.  Load any workflow that has missing models (nodes showing red or errors).
2.  Click the **"Auto Match Models"** button in the top menu bar.
3.  The plugin will scan and present a list of proposed fixes.
4.  Click **OK** to apply the changes.

### Version History
*   **v1.0.0** (2026-01-17)
    *   Initial release.
    *   Implemented Model Scanner and Matcher backend.
    *   Added Frontend UI for auto-detection and fixing.
    *   Support for Checkpoints, LoRAs, VAE, ControlNet, CLIP, UNET.

---

<a name="chinese"></a>
## 🇨🇳 中文

### 简介
**ComfyUI-LK-Model_Auto-Matching** 是一个 ComfyUI 自定义节点扩展，旨在解决加载他人工作流时模型路径不匹配的常见痛点。

当你导入别人的工作流时，其中的模型路径（Checkpoints, LoRAs, VAEs 等）通常指向原作者的特定文件夹，这些路径在你本地可能并不存在。本插件可以自动扫描你的本地模型库，并智能匹配工作流中丢失的模型，让你无需再一次次手动重新选择。

### 主要功能
*   **一键修复**: 在 ComfyUI 菜单栏添加 "Auto Match Models" 按钮。
*   **智能检测**: 自动识别当前工作流中值无效的模型组件。
*   **精确匹配**: 忽略文件夹结构，只要文件名相同即可匹配。
*   **模糊匹配**: 即使文件名略有差异也能智能识别（例如：忽略 `.ckpt` 和 `.safetensors` 的扩展名差异，忽略大小写）。
*   **安全**: 在应用任何更改前都会弹出确认框供用户审核。

### 安装说明
1.  进入你的 ComfyUI 自定义节点目录：
    ```bash
    cd ComfyUI/custom_nodes/
    ```
2.  克隆本仓库：
    ```bash
    git clone https://github.com/YourUsername/ComfyUI-LK-Model_Auto-Matching.git
    ```
3.  重启 ComfyUI。

### 使用方法
1.  加载任何包含丢失模型（节点显示红色或报错）的工作流。
2.  点击顶部菜单栏的 **"Auto Match Models"** 按钮。
3.  插件将扫描并弹出一个建议修复列表。
4.  点击 **确定 (OK)** 应用更改。

### 版本历史
*   **v1.0.0** (2026-01-17)
    *   首次发布。
    *   实现后端模型扫描与匹配逻辑。
    *   添加前端 UI，支持自动检测与一键修复。
    *   支持 Checkpoints, LoRAs, VAE, ControlNet, CLIP, UNET 等多种模型类型。
