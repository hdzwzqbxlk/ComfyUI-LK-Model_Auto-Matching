import copy
import json
import os

_DEFAULT_CONFIG = {
    "db": {
        "enabled": True,
        "exact_score": 1.0,
        "basename_score": 0.99,
        "semantic_min_score": 0.35,
        "fuzzy_score_cutoff": 80,
    },
    "matching": {
        "use_db_first": True,
        "use_exact_match": True,
        "use_fuzzy_match": True,
        "use_variant_match": True,
        "use_legacy_match": True,
        "fuzzy_score_cutoff": 60.0,
        "variant_score_cutoff": 0.9,
        "legacy_score_cutoff": 75,
    },
}

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "matcher_config.json")
_CONFIG = None


def _merge_config(base, override):
    merged = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_matcher_config(path=None):
    config_path = path or _CONFIG_PATH
    config = copy.deepcopy(_DEFAULT_CONFIG)
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            config = _merge_config(config, payload)
        except Exception:
            pass
    return config


def get_matcher_config():
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = load_matcher_config()
    return _CONFIG


def override_matcher_config(config):
    global _CONFIG
    _CONFIG = _merge_config(_DEFAULT_CONFIG, config)
    return _CONFIG


def reset_matcher_config():
    global _CONFIG
    _CONFIG = None
    return get_matcher_config()
