---
description: 推送前检查清单
---

# 推送前检查清单

在推送代码到 GitHub 之前，必须完成以下检查：

## 1. 版本号同步检查
// turbo
确保以下三个位置的版本号一致：
- `__init__.py` 中的 `__version__`
- `js/auto_matcher.js` 中的 `VERSION` 常量  
- `README.md` 中的版本号 badge

## 2. 代码测试
// turbo
检查核心功能是否正常：
```bash
cd g:\AI_Code\ComfyUI-LK-Model_Auto-Matching
uv run python -c "from core.utils import AdvancedTokenizer; print(AdvancedTokenizer.extract_search_terms('test-model-Q4_K_S.gguf'))"
```

## 3. Git 提交
// turbo
```bash
git add -A
git status
git commit -m "描述性提交信息"
git push origin main
```
