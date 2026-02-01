# Changelog

## [3.1.1] - 2026-02-02

### ⚡ Optimization
*   **Async Hashing**: Offloaded heavy SHA256 calculation for Civitai matching to a background thread, preventing UI freezes when processing large checkpoints.
*   **Modular Architecture**: Refactored `matcher.py` into atomic methods (`_find_exact_match`, `_find_fuzzy_match`, etc.) for better maintainability and debugging.

### 🛡️ Stability
*   **Bug Fix**: Resolved `UnboundLocalError` in fuzzy matching logic where candidate indices were not initialized.
*   **Protocol**: Established `qa-protocol` workflow to enforce TDD and strict code review for core modules.
*   **Tests**: Added persistent verification scripts (`scripts/verify_*.py`) to CI/CD pipeline.

## [3.1.0] - 2026-01-30
*   Initial release of Database Backend and Race Mode Search.
