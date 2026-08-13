# 贡献指南（Contributing）

本指南是本仓库标准化研发流程的**应用版**。完整规范见项目级技能 `lk-dev-standard`
（`~/.workbuddy/skills/lk-dev-standard` 或本项目 `.workbuddy/skills/lk-dev-standard`）；
PR 的机械步骤（建 / 合 / 清分支）一律走 `pr-delivery` 技能。

## 1. 环境
- Python 3.12+，依赖见 `requirements.txt` / `pyproject.toml`。
- 本机 git 命令通过 **pwsh MCP** 执行（宿主 GCM 已配密钥，无需额外登录）。
- 测试：`python -m pytest`（合入前必须全绿）。

## 2. 分支
- 从 `main` 切，合回 `main`（squash）。
- **扁平分支名**：`t2.4-liblib-api`、`fix-matcher-cjk`。**不要**用 `feat/xxx` 嵌套名
  （会导致 ref 写不出、HEAD unborn）。
- 一个任务一个分支；跨任务拆独立 PR。

## 3. 提交（Conventional Commits）
```
<type>(<scope>): <subject> (T2.5)

<body：为什么改，而非怎么改>

<footer：Fixes #123 / BREAKING CHANGE: / Co-Authored-By: ...>
```
- type：`feat` `fix` `refactor` `docs` `test` `chore` `perf` `ci` `build`
- subject：祈使句、首字母大写、无句号、≤70 字，结尾带任务标签。
- **版本号铁律**：修复 / 小优化走 **PATCH**；仅大功能 / 架构调整升 **MINOR**；breaking 升 **MAJOR**。
  不要随意跳版本号。

## 4. PR
- 描述**来自真实 git 状态**（pr-delivery 自动提取），结构见
  `.github/pull_request_template.md`：路径映射 / 工作链 / 状态证明 / 构建门禁 / 残留标注 / 记忆归档。
- **squash** 合入；合并后远端分支自动清理。
- 早开 draft 验方向 + CI，再转 Ready。

## 5. 测试与门禁（Push Gate）
- 合并前 `pytest` 必绿，否则退回修复、绝不开 PR。
- 交付报告贴出构建 / 测试退出码作为状态证明。

## 6. 版本与变更日志
- SemVer，补丁号优先。
- `CHANGELOG.md` 顶部保留 `## [Unreleased]` 段；用户可见变更（feat/fix/perf/breaking）必写。
- 发版时把 `Unreleased` 归入新版本号段并标注日期。

## 7. 文档
- `ARCHITECTURE.md`（架构）/ `README.md`（用法）/ `CHANGELOG.md`（变更）/ 本文件（流程）。
- 改了行为，顺手更新对应文档与 CHANGELOG。

## 红线
- 100% 中文注释与文档（标识符英文）。
- 禁 `any` 类型注解。
- 验证闭环（测试不过不交付）。
- 本机命令走 pwsh MCP，禁用 Bash 沙箱做 git / 构建。
