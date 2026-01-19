# Changelog

All notable changes to this project will be documented in this file.

## [1.3.1] - 2026-01-19

### 🔥 Deep Optimization (Core Search)
- **Deep Tokenization Engine**:
  - Automatically splits `CamelCase` and `AlphaNumeric` boundaries (e.g., `wan22Remix` -> `wan 22 Remix`).
  - Solves matching issues for models with complex, concatenated filenames.
- **Progressive Search Strategy**:
  - Implements a 3-stage fall-back system: `Raw Stem` (Precision) -> `Spaced Keywords` (Recall) -> `Deep Tokenization` (Fuzzy).
  - Significantly improves hit rate for both exact matches and obscure/new models.

### 🛠 Fixes & Improvements
- **HuggingFace URL Parsing**: 
  - Fixed a critical bug where repo URLs were truncated to just the username. Now correctly captures `user/repo` for accurate scoring.
- **DuckDuckGo Fallback**:
  - Stabilized HTML scraping to serve as a robust backup when Google Search is rate-limited.
- **GGUF Precision**:
  - Added strict logic to preserve `gguf` keywords in search queries, preventing mix-ups with standard models.

### 💅 UI / UX
- **Clean Interface**: Removed redundant version number from the Settings dialog title for a cleaner look.
- **Unified Versioning**: Synchronized version numbering across Python (`__init__.py`) and JavaScript (`auto_matcher.js`).
