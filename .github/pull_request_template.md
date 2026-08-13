<!--
  LK 项目结构化 PR 描述模板（与 pr-delivery 技能一致）。
  自动化交付会由 pr-delivery 从真实 git 状态填充下列槽位；手写 PR 也请尽量补全，
  尤其「路径映射 / 工作链 / 状态证明 / 构建门禁」。
-->

## 变更概要
<!-- 一句话说明这个 PR 做了什么、为什么 -->

## 关联
- 基分支：`main`
- 交付分支：`<!-- 你的分支名，如 t25-local-first-match -->`
- 关联任务：`<!-- T2.5 / 无 -->`

## 类型
- [ ] feat  - 新功能
- [ ] fix   - 缺陷修复
- [ ] refactor - 工程 / 重构
- [ ] docs  - 文档
- [ ] chore - 构建 / 依赖 / 辅助

## 路径映射（真实文件清单）
> 来源：`git diff --stat <merge-base> HEAD`

```
<!-- 粘贴 git diff --stat 输出 -->
```

## 工作链（commit 序列）
> 来源：`git log --oneline <merge-base>..HEAD`

```
<!-- 粘贴 git log --oneline 输出，含 hash -->
```

## 变更点
<!-- 逐文件说明改了什么、为什么（代码不揭示的背景） -->
-

## 最终状态证明
- `git status`：`<!-- clean / 改动列表 -->`
- 自 base 起 commit 数：`<!-- git rev-list --count -->`
- 分支 tip：`<!-- git rev-parse HEAD -->`
- 构建 / 测试门禁：`<!-- pytest 结果 -->`

## 构建门禁（Push Gate）
- [ ] pytest 回归套件零失败
- 自测步骤：`<!-- 命令 -->`

## 残留标注
<!-- 未合入的后续项 / 暂缓的优化，如无填「无」 -->

## 记忆归档
- PR：https://github.com/hdzwzqbxlk/ComfyUI-LK-Model_Auto-Matching/pull/<!-- 号 -->
- 合入方式：squash（待合 / 已合）
- 通道选择原因：`<!-- github MCP 403 / gh 超时 / curl+GCM token -->`
- 远端分支清理：`<!-- 合入后删 -->`
