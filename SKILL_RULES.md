# ComfyUI-LK Project Skill Protocol (PSP)

本文件定义了本项目开发过程中必须遵守的 **AI 技能组合使用规则**。旨在防止回归错误、确保代码质量并规范开发流程。

## 1. 核心开发工作流 (Core Workflow)

所有涉及 `core/` 目录 (如 `matcher.py`, `searcher.py`, `scanner.py`) 的修改，必须严格遵循以下技能链：

### 🔴 Phase 1: 故障修复与调试 (Bug Fixes)
**Trigger**: 用户反馈 Bug、测试失败、异常崩溃。
**Required Skills**:
1.  **`systematic-debugging`**:
    *   **必须**先复现问题（编写重现脚本）。
    *   禁止猜测性修复 (No blind fixes)。
2.  **`testing-patterns` (TDD)**:
    *   **必须**在 `scripts/` 下创建或更新验证脚本 (e.g., `verify_critical_paths.py`)。
    *   遵循 "Red-Green-Refactor"：先看到测试失败，再写修复代码，最后验证通过。

### 🟡 Phase 2: 功能开发 (Feature Dev)
**Trigger**: 新增功能 (e.g., 竞速模式, 分类优化)。
**Required Skills**:
1.  **`concise-planning`**:
    *   针对复杂逻辑，先生成原子化的 Task List。
    *   明确“如何验证该功能有效”。
2.  **`python-patterns`**:
    *   使用 Pythonic 的写法 (列表推导式, Set 操作, Type Hints)。
    *   保持 `asyncio` 异步逻辑的清晰性。

### 🟢 Phase 3: 代码提交前 (Pre-Commit)
**Trigger**: 准备 `git verify` 和 `git push`。
**Required Skills**:
1.  **`code-review-checklist` (Self-Check)**:
    *   **Correctness**: 是否处理了边缘情况？(e.g., 文件名相同但分类不同)
    *   **Security**: 变量是否已定义？(防止 `UnboundLocalError`)
    *   **Cleanup**: debug print 是否已删除？
2.  **`clean-code`**:
    *   函数是否过长？(超过 50 行考虑拆分)
    *   变量名是否具有描述性？(`candidate_indices` vs `temp`)

## 2. 特定场景技能映射 (Scenario Mapping)

| 场景 | 必选技能组合 | 关键动作 |
| :--- | :--- | :--- |
| **修改匹配算法** (`matcher.py`) | `testing-patterns` + `code-review-checklist` | **强制运行** `verify_critical_paths.py` |
| **修改网络请求** (`searcher.py`) | `python-patterns` (async) | 检查 Exception Handling 和 Timeout |
| **修改 UI交互** (`auto_matcher.js`) | `javascript-mastery` | 检查 DOM 元素是否存在，避免 `null` 引用 |
| **文档更新** (`README.md`) | `content-creator` (SEO/Copy) | 保持中英文档同步，强调核心卖点 |

## 3. 禁忌 (Anti-Patterns)

*   ❌ **禁止** 在没有运行验证脚本的情况下直接 Push。
*   ❌ **禁止** 在 `try...except` 中吞掉关键错误而不打印 Log。
*   ❌ **禁止** 删除核心变量（如 `candidate_indices`）而不检查引用链。

---
*Created by AI Agent mostly to remind itself not to break things again.*
