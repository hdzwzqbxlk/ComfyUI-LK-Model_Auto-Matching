"""
Configuration constants for ComfyUI-LK-Model_Auto-Matching
Centralized magic numbers and thresholds for easy tuning
"""

class MatcherConfig:
    """Matching algorithm thresholds and weights"""
    
    # Matching thresholds
    EXACT_MATCH_THRESHOLD = 1.0
    FUZZY_MATCH_THRESHOLD = 60.0
    VARIANT_MATCH_THRESHOLD = 0.9
    LEGACY_MATCH_THRESHOLD = 75.0
    
    # Scoring weights
    W_ANCHOR = 10.0      # Weight for anchor tokens (flux, sdxl, etc.)
    W_VERSION = 5.0      # Weight for version numbers
    W_NORMAL = 1.0      # Weight for normal tokens
    W_NOISE = 0.1        # Weight for noise suffixes
    
    # Type consistency bonus
    TYPE_MATCH_BONUS = 30.0
    
    # CJK character overlap bonus
    CJK_BONUS_MULTIPLIER = 25.0
    
    # Format multiplier
    FORMAT_MATCH_MULTIPLIER = 1.0
    FORMAT_MISMATCH_MULTIPLIER = 0.0


class SearcherConfig:
    """Search provider thresholds and timeouts"""
    
    # Network timeouts (seconds)
    DEFAULT_TIMEOUT = 20
    CIVITAI_TIMEOUT = 20
    HUGGINGFACE_TIMEOUT = 20
    GOOGLE_TIMEOUT = 15
    
    # Score thresholds
    MIN_FILE_SCORE = 0.35
    MIN_NAME_SCORE = 0.35
    MIN_COMBINED_SCORE = 0.35
    HIGH_CONFIDENCE_SCORE = 0.9
    
    # Search limits
    MAX_RESULTS_PER_PROVIDER = 5
    MAX_CIVITAI_RESULTS = 20
    MAX_HUGGINGFACE_REPOS = 8
    
    # Cache settings
    TREE_CACHE_TTL = 300  # 5 minutes
    HASH_CACHE_MAX_SIZE = 100
    
    # Circuit breaker
    CIRCUIT_BREAKER_THRESHOLD = 3  # errors before disabling provider


class DatabaseConfig:
    """Database matching thresholds"""
    
    # Fuzzy matching threshold
    FUZZY_MATCH_THRESHOLD = 0.85
    
    # Connection settings
    CONNECTION_TIMEOUT = 30


# Load user overrides from config.json if available
def load_user_config():
    """Load user configuration overrides from config.json"""
    import os
    import json
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    user_config = {}
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                user_config = data.get("thresholds", {})
        except Exception:
            pass
    
    # Apply user overrides if present
    if user_config:
        if "fuzzy_match_threshold" in user_config:
            MatcherConfig.FUZZY_MATCH_THRESHOLD = user_config["fuzzy_match_threshold"]
        if "variant_match_threshold" in user_config:
            MatcherConfig.VARIANT_MATCH_THRESHOLD = user_config["variant_match_threshold"]
        if "min_score" in user_config:
            SearcherConfig.MIN_FILE_SCORE = user_config["min_score"]
    
    return user_config


# Initialize user config on import
load_user_config()
