# -*- coding: utf-8 -*-
"""
T2.3 测试补齐 — Provider 解析逻辑锁定（零联网，全 mock）

覆盖范围（UPGRADE_PLAN Phase 2 / T2.3）：
  - CivitaiHashProvider    : SHA256 哈希命中 / 404 / 文件不存在 / 坏 JSON
  - CivitaiProvider        : 文本搜索命中 / 403 / 坏 JSON / 空结果
  - HuggingFaceProvider    : 文本搜索命中 / 空结果
  - HuggingFaceFileSearchProvider (纯逻辑，不联网) :
        _get_weighted_tokens / _extract_keywords / _search_in_tree / _is_match
  - DuckDuckGoProvider._parse_link (纯函数) : 各平台 URL 判定
  - ModelScopeFileSearchProvider : mock API + 文件树，端到端解析
  - CNBProvider            : mock 搜索页 HTML，解析 repo 链接
  - LiblibProvider         : mock 搜索页 HTML，解析 /modelinfo/ 链接

设计要点：
  - 所有 HTTP 请求被 MockAsyncSession 拦截，绝不触网。
  - 在 import searcher 之后 patch searcher.AsyncSession，使各 Provider 实例化时
    拿到 Mock，而非真实 curl_cffi.AsyncSession。
  - 关于 LiblibProvider：它依赖解析静态 HTML 中的 /modelinfo/ 链接；真实 liblib.art
    搜索页为 JS 动态渲染，静态链接大概率缺失（T2.4 待重写为 API/页面解析）。
    本测试仅锁定「给定含 /modelinfo/ 链接的 HTML 时能正确解析」这一逻辑本身。
"""

import sys
import os
import json
import asyncio
import tempfile
from unittest import mock

# 把仓库根加入 path，允许 `from core import searcher`
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# searcher 本身不 import folder_paths/server，但依赖链（utils 等）可能；保险 stub。
sys.modules.setdefault('folder_paths', mock.MagicMock())
sys.modules.setdefault('server', mock.MagicMock())

import unittest  # noqa: E402

from core import searcher  # noqa: E402


# --------------------------------------------------------------------------- #
# Mock 基础设施：拦截 curl_cffi AsyncSession                                  #
# --------------------------------------------------------------------------- #
class FakeResponse:
    """模拟 curl_cffi Response：.status_code / .text / .json()"""
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self._text = text
        self._json = json_data

    @property
    def text(self):
        return self._text

    def json(self):
        if self._json is None:
            raise ValueError("no json payload")
        return self._json


class MockAsyncSession:
    """可替换 searcher.AsyncSession 的假会话。

    行为完全由类级 _default_responder 决定，每次请求时实时读取，
    避免实例化时机与 set_responder 的顺序问题。
    """
    _default_responder = None

    def __init__(self, *args, **kwargs):
        self.requests = []

    @classmethod
    def set_responder(cls, responder):
        cls._default_responder = responder

    @classmethod
    def reset(cls):
        cls._default_responder = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kwargs):
        self.requests.append(("GET", url))
        return self._respond(url, "GET", kwargs)

    async def post(self, url, data=None, json=None, **kwargs):
        self.requests.append(("POST", url))
        return self._respond(url, "POST", kwargs)

    async def put(self, url, json=None, **kwargs):
        self.requests.append(("PUT", url))
        return self._respond(url, "PUT", kwargs)

    def _respond(self, url, method, kwargs):
        r = MockAsyncSession._default_responder
        if r is not None:
            return r(url, method, kwargs)
        return FakeResponse(200, "", {})


def responder_from_routes(routes):
    """routes: list[(url_substring, FakeResponse)]，按出现顺序匹配，首个命中生效。"""
    def responder(url, method, kwargs):
        for sub, resp in routes:
            if sub in url:
                return resp
        return FakeResponse(404, "", {})
    return responder


# 在 import 之后、任何 Provider 实例化之前，替换 AsyncSession
searcher.AsyncSession = MockAsyncSession


# --------------------------------------------------------------------------- #
# 测试套件                                                                     #
# --------------------------------------------------------------------------- #
class TestCivitaiHashProvider(unittest.TestCase):
    def setUp(self):
        MockAsyncSession.reset()

    def _provider(self):
        return searcher.CivitaiHashProvider({})

    def _run(self, filename, original):
        """用 mock 替代真实文件 IO（避免 Windows 临时文件独占锁），只验证 API 解析。"""
        with mock.patch.object(searcher.CivitaiHashProvider, 'calculate_sha256', return_value='0' * 64), \
             mock.patch('os.path.exists', return_value=True):
            return asyncio.run(self._provider().search_by_hash(filename, original))

    def test_hash_hit(self):
        """200 命中：正确解析 modelId / model.name / version name / downloadUrl。"""
        payload = {
            "modelId": 123456,
            "model": {"name": "DreamShaper XL"},
            "name": "v1.0",
            "downloadUrl": "https://civitai.com/api/download/models/999",
        }
        MockAsyncSession.set_responder(lambda u, m, k: FakeResponse(200, "", payload))
        results = self._run("dreamshaperxl.safetensors", "dreamshaperxl.safetensors")
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["source"], "Civitai (Hash Match)")
        self.assertEqual(r["name"], "DreamShaper XL - v1.0")
        self.assertEqual(r["url"], "https://civitai.com/api/download/models/999")
        self.assertEqual(r["pageUrl"], "https://civitai.com/models/123456")
        self.assertTrue(r["hash_match"])

    def test_hash_404(self):
        """404：模型非 Civitai 来源，应返回空列表。"""
        MockAsyncSession.set_responder(lambda u, m, k: FakeResponse(404, "", {}))
        results = self._run("unknown.safetensors", "unknown.safetensors")
        self.assertEqual(results, [])

    def test_file_not_found(self):
        """文件不存在：不发起任何请求，直接返回空。"""
        with mock.patch('os.path.exists', return_value=False):
            results = asyncio.run(
                self._provider().search_by_hash("__no_such_file__.safetensors", "x.safetensors")
            )
        self.assertEqual(results, [])

    def test_bad_json(self):
        """200 但响应体非 JSON：解析异常应被吞掉，返回空。"""
        MockAsyncSession.set_responder(lambda u, m, k: FakeResponse(200, "<html>oops</html>", None))
        results = self._run("x.safetensors", "x.safetensors")
        self.assertEqual(results, [])


class TestCivitaiProvider(unittest.TestCase):
    def setUp(self):
        MockAsyncSession.reset()

    def test_search_hit(self):
        payload = {
            "items": [
                {
                    "name": "Juggernaut XL",
                    "id": 777,
                    "modelVersions": [
                        {
                            "name": "v9",
                            "id": 888,
                            "files": [
                                {"name": "juggernautXL_v9.safetensors",
                                 "downloadUrl": "https://civitai.com/api/download/models/1"}
                            ],
                        }
                    ],
                }
            ]
        }
        MockAsyncSession.set_responder(lambda u, m, k: FakeResponse(200, "", payload))
        results = asyncio.run(
            searcher.CivitaiProvider({}).search("juggernaut", "juggernautXL_v9.safetensors")
        )
        self.assertTrue(any(r["source"] == "Civitai (Native)" for r in results))

    def test_search_403(self):
        MockAsyncSession.set_responder(lambda u, m, k: FakeResponse(403, "", {}))
        results = asyncio.run(
            searcher.CivitaiProvider({}).search("q", "f.safetensors")
        )
        self.assertEqual(results, [])

    def test_search_bad_json(self):
        MockAsyncSession.set_responder(lambda u, m, k: FakeResponse(200, "not json", None))
        results = asyncio.run(
            searcher.CivitaiProvider({}).search("q", "f.safetensors")
        )
        self.assertEqual(results, [])

    def test_search_empty(self):
        MockAsyncSession.set_responder(lambda u, m, k: FakeResponse(200, "", {"items": []}))
        results = asyncio.run(
            searcher.CivitaiProvider({}).search("q", "f.safetensors")
        )
        self.assertEqual(results, [])


class TestHuggingFaceProvider(unittest.TestCase):
    def setUp(self):
        MockAsyncSession.reset()

    def test_search_hit(self):
        payload = [
            {"modelId": "Comfy-Org/sdxl-vae"},
            {"modelId": "stabilityai/stable-diffusion-xl-base-1.0"},
        ]
        MockAsyncSession.set_responder(lambda u, m, k: FakeResponse(200, "", payload))
        results = asyncio.run(
            searcher.HuggingFaceProvider({}).search("sdxl", "sdxl_vae.safetensors")
        )
        self.assertTrue(any(r["source"] == "HuggingFace" for r in results))

    def test_search_empty(self):
        MockAsyncSession.set_responder(lambda u, m, k: FakeResponse(200, "", []))
        results = asyncio.run(
            searcher.HuggingFaceProvider({}).search("q", "f.safetensors")
        )
        self.assertEqual(results, [])


class TestHuggingFaceFileSearchLogic(unittest.TestCase):
    """HFFileSearch 的纯逻辑（不创建 session、不触网）。

    v3.7.0 已修复：
      1) repo 上下文过度匹配 → 改为文件必须有 50%+ 核心重叠，repo 仅弥补
      2) T2V/I2V 不区分 → 新增 regex-based type conflict HARD gate（在 fuzzy 之前）
    """

    def setUp(self):
        self.p = searcher.HuggingFaceFileSearchProvider({})

    def test_weighted_tokens(self):
        toks = self.p._get_weighted_tokens("Wan2.1-T2V-14B.safetensors")
        token_set = {t["token"] for t in toks}
        self.assertIn("14b", token_set)
        self.assertIn("t2v", token_set)

    def test_extract_keywords(self):
        kws = self.p._extract_keywords("Wan2.1-T2V-14B.safetensors")
        self.assertTrue(all(len(k) > 1 for k in kws))

    def test_search_in_tree_hit(self):
        tree = {"files": ["Wan2.1-T2V-14B.safetensors"], "dirs": {}}
        res = self.p._search_in_tree(
            tree, "Wan-AI/Wan2.1-T2V-14B",
            self.p._extract_keywords("Wan2.1-T2V-14B.safetensors"),
            "Wan2.1-T2V-14B.safetensors",
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["score"], 0.98)
        self.assertEqual(res["source"], "HuggingFace (Exact File)")

    def test_search_in_tree_miss_unrelated_repo(self):
        # 不相关仓库 + 不相关文件 → None
        tree = {"files": ["unrelated_model.safetensors"], "dirs": {}}
        res = self.p._search_in_tree(
            tree, "SomeOrg/UnrelatedRepo",
            self.p._extract_keywords("Wan2.1-T2V-14B.safetensors"),
            "Wan2.1-T2V-14B.safetensors",
        )
        self.assertIsNone(res)

    def test_is_match_exact(self):
        # 完全匹配（同仓库同名）
        self.assertTrue(
            self.p._is_match(
                "Wan2.1-T2V-14B.safetensors",
                "wan2.1-t2v-14b.safetensors",
                "wan2.1-t2v-14b",
                repo_id="Wan-AI/Wan2.1-T2V-14B",
            )
        )

    def test_is_match_variant_same_repo(self):
        # 同仓库变体（fp16）→ 应通过（有 100% 核心重叠）
        self.assertTrue(
            self.p._is_match(
                "Wan2.1-T2V-14B-fp16.safetensors",
                "wan2.1-t2v-14b.safetensors",
                "wan2.1-t2v-14b",
                repo_id="Wan-AI/Wan2.1-T2V-14B",
            )
        )

    def test_is_match_repo_overmatch_fixed(self):
        # [v3.7.0 fix] 同仓库内不相关文件 → False（旧版因 repo 名并入会误判 True）
        self.assertFalse(
            self.p._is_match(
                "unrelated_model.safetensors",
                "wan2.1-t2v-14b.safetensors",
                "wan2.1-t2v-14b",
                repo_id="Wan-AI/Wan2.1-T2V-14B",
            )
        )

    def test_is_match_type_conflict_i2v_t2v(self):
        # [v3.7.0 fix] I2V vs T2V 类型冲突 → False（旧版 fuzzy 短路会误判 True）
        self.assertFalse(
            self.p._is_match(
                "Wan2.1-I2V-14B.safetensors",
                "wan2.1-t2v-14b.safetensors",
                "wan2.1-t2v-14b",
            )
        )

    def test_is_match_type_conflict_i2v_t2v_with_repo(self):
        # [v3.7.0 fix] 即使在同一仓库，I2V vs T2V 也应被 type gate 拦截
        self.assertFalse(
            self.p._is_match(
                "Wan2.1-I2V-14B.safetensors",
                "wan2.1-t2v-14b.safetensors",
                "wan2.1-t2v-14b",
                repo_id="Wan-AI/Wan2.1-T2V-14B",
            )
        )

    def test_is_match_core_missing(self):
        # 目标文件无任何核心词 → 失败
        self.assertFalse(
            self.p._is_match(
                "tiny_model.safetensors",
                "wan2.1-t2v-14b.safetensors",
                "wan2.1-t2v-14b",
                repo_id="SomeOrg/UnrelatedRepo",
            )
        )


class TestDuckDuckGoParseLink(unittest.TestCase):
    """_parse_link 是纯函数，直接验证各平台 URL 判定。"""

    def setUp(self):
        self.p = searcher.DuckDuckGoProvider({})

    def test_civitai(self):
        meta = self.p._parse_link("https://civitai.com/models/123", "wan")
        self.assertEqual(meta["source"], "Civitai (DDG)")

    def test_huggingface(self):
        meta = self.p._parse_link("https://huggingface.co/user/repo", "wan")
        self.assertEqual(meta["source"], "HuggingFace (DDG)")

    def test_cnb(self):
        meta = self.p._parse_link("https://cnb.cool/ai-models/author/repo", "wan")
        self.assertEqual(meta["source"], "CNB (DDG)")

    def test_modelscope(self):
        meta = self.p._parse_link("https://modelscope.cn/models/abc", "wan")
        self.assertEqual(meta["source"], "ModelScope (DDG)")

    def test_liblib(self):
        meta = self.p._parse_link("https://www.liblib.art/modelinfo/xyz", "wan")
        self.assertEqual(meta["source"], "Liblib (DDG)")

    def test_shakker(self):
        meta = self.p._parse_link("https://www.shakker.ai/models/abc", "wan")
        self.assertEqual(meta["source"], "Shakker (DDG)")

    def test_unknown_returns_none(self):
        meta = self.p._parse_link("https://example.com/foo", "wan")
        self.assertIsNone(meta)


class TestModelScopeSearch(unittest.TestCase):
    def setUp(self):
        MockAsyncSession.reset()

    def test_search_hit(self):
        search_payload = {
            "Success": True,
            "Data": {"Model": {"Models": [
                {"Path": "Wan-AI", "Name": "Wan2.1-T2V-14B"}
            ]}},
        }
        file_tree = {
            "Data": {"Files": [
                {"Path": "Wan2.1-T2V-14B.safetensors", "Type": "blob"}
            ]}
        }
        routes = [
            ("/repo/files", FakeResponse(200, "", file_tree)),
            ("/dolphin/models", FakeResponse(200, "", search_payload)),
        ]
        MockAsyncSession.set_responder(responder_from_routes(routes))
        results = asyncio.run(
            searcher.ModelScopeFileSearchProvider({}).search(
                "wan2.1 t2v 14b", "Wan2.1-T2V-14B.safetensors"
            )
        )
        self.assertTrue(any(r["source"] == "ModelScope (Direct)" for r in results))


class TestCNBSearch(unittest.TestCase):
    def setUp(self):
        MockAsyncSession.reset()

    def test_search_hit(self):
        html = (
            '<html><body>'
            '<a href="/ai-models/black-forest-labs/FLUX.1-schnell">FLUX.1 schnell</a>'
            '<a href="/ai-models/some/other">other</a>'
            '</body></html>'
        )
        MockAsyncSession.set_responder(
            lambda u, m, k: FakeResponse(200, html, None)
        )
        results = asyncio.run(
            searcher.CNBProvider({}).search("flux", "FLUX.1-schnell.safetensors")
        )
        self.assertTrue(any(r["source"] == "CNB" for r in results))
        hit = [r for r in results if r["source"] == "CNB"][0]
        self.assertEqual(hit["name"], "black-forest-labs/FLUX.1-schnell")


class TestLiblibSearch(unittest.TestCase):
    def setUp(self):
        MockAsyncSession.reset()

    def test_parse_modelinfo_links(self):
        """锁定：给定含 /modelinfo/ 链接的 HTML，能正确解析出模型条目。

        注意：真实 liblib.art 搜索页为 JS 动态渲染，静态链接大概率缺失
        （T2.4 待重写为 API/页面解析）。此测试仅验证解析逻辑本身不被回归破坏。
        """
        html = (
            '<html><body>'
            '<a href="/modelinfo/Wan2.1-T2V-14B">Wan2.1 T2V 14B</a>'
            '<a href="/modelinfo/AnotherModel">Another</a>'
            '</body></html>'
        )
        MockAsyncSession.set_responder(
            lambda u, m, k: FakeResponse(200, html, None)
        )
        results = asyncio.run(
            searcher.LiblibProvider({}).search("Wan2.1", "Wan2.1-T2V-14B.safetensors")
        )
        self.assertTrue(any(r["source"] == "Liblib" for r in results))
        hit = [r for r in results if r["source"] == "Liblib"][0]
        self.assertEqual(hit["name"], "Wan2.1-T2V-14B")


if __name__ == "__main__":
    unittest.main(verbosity=2)
