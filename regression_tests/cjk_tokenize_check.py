"""T2.1 中文分词增强回归测试。

验证：
  1. _segment_cjk 正向最大匹配：词典词切分、OOV 单字兜底、非中文原样返回
  2. tokenize 在 chinese_tokenization 开启时产出中文词（如「动漫」「大模型」），
     关闭时回退到既有 2-gram 行为（严格兼容）
  3. extract_search_terms 在开启时：(a) 中文词级空格切分；(b) 中文→英文别名扩展
  4. 生产开关 core/data/matcher_config.json 的 features.chinese_tokenization == true

遵循 version_aware_check.py 的隔离范式：stub folder_paths / server，使用托管 venv 运行。
设计取舍：零外部依赖（不引入 jieba），内置精简中文模型词典，可由 models_data.json 覆盖。
"""
import os
import sys
import json
import unittest
from unittest.mock import MagicMock

# 隔离 stub：core 模块在导入链中可能触及 folder_paths / server
sys.modules['folder_paths'] = MagicMock()

import types as _types
_server_stub = _types.ModuleType("server")
_server_ps = MagicMock()
_server_routes = MagicMock()


def _identity_decorator(_path):
    def _wrap(fn):
        return fn
    return _wrap


_server_routes.post.side_effect = _identity_decorator
_server_routes.get.side_effect = _identity_decorator
_server_ps.instance.routes = _server_routes
_server_stub.PromptServer = _server_ps
sys.modules['server'] = _server_stub

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'core'))

from core import config as config_module
from core.utils import AdvancedTokenizer


def setUpModule():
    # 确保 T2.1 开关在测试期间生效；测试结束还原缓存
    config_module.override_config({
        'features': {'chinese_tokenization': True},
        'matching': {'use_db_fallback': False},  # 隔离到内存匹配路径
    })


def tearDownModule():
    config_module.reset_config()


class TestSegmentCJK(unittest.TestCase):
    def test_dict_word_segmentation(self):
        """正向最大匹配：连续中文应切成词典词。"""
        self.assertEqual(AdvancedTokenizer._segment_cjk("动漫大模型"), ["动漫", "大模型"])
        self.assertEqual(AdvancedTokenizer._segment_cjk("写实动漫"), ["写实", "动漫"])
        self.assertEqual(AdvancedTokenizer._segment_cjk("动漫风格"), ["动漫", "风格"])

    def test_oov_single_char_fallback(self):
        """词典未覆盖的中文应回退到单字。"""
        # 「漫画风」均不在词典：应切成单字
        self.assertEqual(AdvancedTokenizer._segment_cjk("漫画风"), ["漫", "画", "风"])

    def test_non_cjk_passthrough(self):
        """非中文（英文/数字）应原样返回，不做切分。"""
        self.assertEqual(AdvancedTokenizer._segment_cjk("SDXL动漫"),
                         ["S", "D", "X", "L", "动漫"])
        self.assertEqual(AdvancedTokenizer._segment_cjk("wan2.1"), ["w", "a", "n", "2", ".", "1"])

    def test_empty_and_mixed(self):
        self.assertEqual(AdvancedTokenizer._segment_cjk(""), [])
        # 中文 + 英文混合：中文词 + 英文逐字符
        self.assertEqual(AdvancedTokenizer._segment_cjk("动漫Real"), ["动漫", "R", "e", "a", "l"])


class TestTokenizeCJK(unittest.TestCase):
    def test_word_tokens_when_enabled(self):
        """开启时 tokenize 应产出中文词（含「大模型」整词）。"""
        tokens = AdvancedTokenizer.tokenize("写实动漫大模型.safetensors")
        self.assertIn("动漫", tokens)
        self.assertIn("大模型", tokens, "开启中文分词应产出整词「大模型」")

    def test_fallback_when_disabled(self):
        """关闭时回退到 2-gram：不应产出整词「大模型」，但保留二元组「大模/模型」。"""
        config_module.override_config({
            'features': {'chinese_tokenization': False},
            'matching': {'use_db_fallback': False},
        })
        try:
            tokens = AdvancedTokenizer.tokenize("写实动漫大模型.safetensors")
            self.assertNotIn("大模型", tokens, "关闭时不应产出整词「大模型」")
            # 既有 2-gram 行为仍应保留相邻二元组
            self.assertTrue(
                {"大模", "模型"}.intersection(tokens),
                "关闭时仍应保留相邻 2-gram 二元组")
        finally:
            config_module.reset_config()

    def test_gate_flag(self):
        self.assertTrue(AdvancedTokenizer._cjk_enabled())
        config_module.override_config({
            'features': {'chinese_tokenization': False},
            'matching': {'use_db_fallback': False},
        })
        try:
            self.assertFalse(AdvancedTokenizer._cjk_enabled())
        finally:
            config_module.reset_config()


class TestSearchTermsCJK(unittest.TestCase):
    def test_word_spaced_and_alias_expansion(self):
        """开启时：中文名应产出词级空格搜索词 + 中文→英文别名。"""
        terms = AdvancedTokenizer.extract_search_terms("写实动漫大模型.safetensors")
        joined = " ".join(terms)
        # 词级切分：应出现「动漫」与「大模型」相邻的空格词
        self.assertTrue(
            any("动漫" in t and "大模型" in t for t in terms),
            "应产出中文词级切分搜索词，实际: %s" % terms)
        # 中文→英文别名扩展（国际平台兜底）
        self.assertTrue(
            any("anime" in t.lower() for t in terms),
            "应产出中文→英文别名（anime），实际: %s" % terms)

    def test_alias_expansion_explicit(self):
        """中文→英文别名：动漫→anime，风格→style。"""
        terms = AdvancedTokenizer.extract_search_terms("动漫风格模型.safetensors")
        self.assertTrue(
            any("anime" in t.lower() and "style" in t.lower() for t in terms),
            "应产出 anime style 别名，实际: %s" % terms)

    def test_cjk_latin_boundary_preserved(self):
        """开启时「动漫Flux.1」应产出词级切分 / 中英空格的搜索词（原始全名保留属正常）。"""
        terms = AdvancedTokenizer.extract_search_terms("动漫Flux.1.safetensors")
        lowered = [t.lower() for t in terms]
        # T2.1 应产出中文词级 + 中英空格的变体（如「动漫 flux」）
        self.assertTrue(
            any("动漫 flux" in t for t in lowered),
            "应产出中文词级切分且中英空格的搜索词，实际: %s" % terms)
        # F.1 归一化应生效（出现 flux）
        self.assertTrue(
            any("flux" in t for t in lowered),
            "F.1 应归一化为 flux，实际: %s" % terms)


class TestProductionFlag(unittest.TestCase):
    def test_chinese_tokenization_enabled_in_config(self):
        cfg_path = os.path.join(ROOT, 'core', 'data', 'matcher_config.json')
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        self.assertTrue(
            cfg.get('features', {}).get('chinese_tokenization', False),
            "生产配置 core/data/matcher_config.json 必须开启 features.chinese_tokenization")


if __name__ == '__main__':
    unittest.main(verbosity=2)
