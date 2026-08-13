# AGENTS.md — ComfyUI-LK-Model_Auto-Matching · AI 入口（SSOT）

> 本文件是**所有 AI Agent / 大模型进入本项目的唯一入口（Single Source of Truth）**。
> 任何自动化助手在开始改动代码或文档前，**必须先读本文 + `docs/` 下对应文档**。
> 根目录严禁新建 `.md`；根仅允许 `AGENTS.md`（AI 入口 SSOT）、`README.md`（用法）。其余文档一律归类到 `docs/`（含 `CHANGELOG`）。

## 0. 项目简介
ComfyUI 自定义节点（custom_nodes）插件，自动匹配 / 修复导入他人工作流时的 "missing model" 红色节点。

- **本地匹配（核心）**：扫描本地 `models/` 目录，按文件名 / 变体 / 模糊相似度，把工作流中缺失的模型名替换成本地已有文件。
- **全网搜索（兜底）**：本地没有时，并发搜索 Civitai / HuggingFace / ModelScope / Liblib / Google / DuckDuckGo，返回可下载链接。
- **安全确认**：所有改动先弹窗展示 `Original -> New`，用户点确认才生效，不静默改写。
- **存储**：本地 SQLite（`core/data/models.db`）+ JSON 载荷，由 `build_models_db.py` 从 `data/samples/` 源数据构建。

## 1. 路由索引（AI 上下文地图）
| 你需要… | 读这个 |
|------|------|
| 系统架构 / 模块划分 / 数据流 | `docs/ARCHITECTURE.md` |
| 项目梳理 / 架构事实 / 技术债 / 迭代切入点 | `docs/PROJECT_BRIEF.md` |
| 升级路线图 / 目标对齐 | `docs/UPGRADE_PLAN.md` |
| 统一分散配置设计方案（密钥 / 策略分层） | `docs/T1.1_CONFIG_DESIGN.md` |
| Phase 0 卫生执行报告 | `docs/PHASE0_REPORT.md` |
| 贡献流程 / 分支规范 / PR 步骤 | `docs/CONTRIBUTING.md` |
| 版本 / 变更记录（Keep a Changelog） | `docs/CHANGELOG.md` |
| 前端契约 / 深入研究计划 | `docs/FRONTEND_BACKEND_CONTRACT.md`、`docs/RESEARCH_AND_DEEPENING_PLAN.md` |

## 2. 代码修改规范（速览）
- **语言**：中文 UI 文本与代码注释；仅物理路径 / API 变量名 / 技术专有名词保留原样。
- **配置真源（三层，绝不混淆）**：
  - ① 用户密钥 `envs/config.json`（`{civitai_api_key, huggingface_token}`，**被 .gitignore 忽略，含密钥，禁提交**）；
  - ② 策略 `core/data/matcher_config.json`（已提交，生产开关在此）；
  - ③ 运行时索引 `envs/model_index.json`（被 .gitignore 忽略，首次扫描生成）。
  - 优先级：环境变量 > ② > ①。密钥**绝不**并入已提交单文件。
- **路径约定**：用户态文件统一在 `envs/`（密钥 + 运行时索引）；源数据 / 样本在 `data/samples/`；文档统一在 `docs/`。
- **推送前置门禁（Push Gate）**：分支 + PR（PR 机械步骤走 `pr-delivery` 技能），禁止直推 `main`；合入前须**同时满足**：① 测试全绿；② **文档完善自检**——核对 `docs/` 与本次改动一致、路由索引（§1）已同步、`CHANGELOG` 的 `[Unreleased]` 段已补、根目录无新增 `.md`，方可推送 / 开 PR。
- **本机命令通道**：git / 构建类命令一律走 **pwsh MCP**，不在 Bash 沙箱执行。

## 3. 文档自愈与更新指令（Self-Maintenance Protocol）
> 对**所有** AI 助手生效。每次改动代码后，同步维护 `docs/`：

- 新增 / 修改核心匹配 / 搜索 / 索引逻辑 → 核对并更新 `docs/ARCHITECTURE.md`、`docs/PROJECT_BRIEF.md`（技术债 / 切入点）。
- 配置分层变更 → 同步 `docs/T1.1_CONFIG_DESIGN.md`。
- 流程 / 分支 / PR 变更 → 同步 `docs/CONTRIBUTING.md`。

### 3.1 禁止污染根目录
- 任何设计说明、方案讨论、计划书，**一律**存放于 `docs/`，**严禁在根目录新建 `.md`**。
- 根目录仅允许长期稳定存在的：`AGENTS.md`（AI 入口 SSOT）、`README.md`（用法）。

### 3.2 任务结束审查（DoD 之一）
- 每次完成开发任务后，校验 `docs/` 文档与实际代码一致；发现漂移先改文档，再交付。
- 文档改动随代码在同一分支 / PR 提交。

## 4. 快速上手
```bash
cd ComfyUI/custom_nodes/ComfyUI-LK-Model_Auto-Matching
pip install -r requirements.txt
python build_models_db.py --import-sqlite   # 构建本地 SQLite 索引（读取 data/samples/ 源数据）
# 重启 ComfyUI，菜单栏点 "LK 🪄 Auto Match"
```
> 用户密钥写入 `envs/config.json`（参考 `docs/T1.1_CONFIG_DESIGN.md`）。本机命令优先走 pwsh MCP。
