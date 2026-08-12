# Frontend ⇄ Backend Field Contract — ComfyUI-LK-Model_Auto-Matching

**Phase 1 · T1.4 (front-end/back-end field contract)** · locked by Architect (Bob)
**Scope:** 6 aiohttp routes in `__init__.py` ↔ `js/auto_matcher.js`
**Sources cited:** `__init__.py` (routes), `js/auto_matcher.js` (consumers), `core/matcher.py`, `core/searcher.py`, `UPGRADE_PLAN.md:105,151`.

> This document is a **lock**, not a proposal. Field names that are already consistent must NOT be renamed. The only backend changes recommended are **additive** (`type` passthrough) and the **shared error envelope**. Green rows are verified-consistent; ⚠️ rows are gaps.

---

## 0. Legend

- **✔ consistent** — backend sends exactly what the frontend reads.
- **⚠ discrepancy** — shape differs from frontend expectation (or plan doc is wrong); see §4.
- **MISSING** — frontend reads a field the backend does not emit.
- All `file:line` citations point at the exact emission / consumption site.

---

## 1. Per-Route Contract Tables

### 1.1 `POST /auto-matcher/match`
**Backend:** `__init__.py:20-44` · **Frontend fetch:** `js:541-547`

**Request body**
| field | type | required | semantics | emitted by frontend (line) |
|---|---|---|---|---|
| `items` | array | yes | missing-model descriptors | `findMissingModels()` → `js:1088-1094` |
| `items[].id` | any | yes | node id | `node.id` (`js:1089`) |
| `items[].node_type` | string | yes | node type | `node.type` (`js:1090`) |
| `items[].widget_name` | string | yes | widget name | `widget.name` (`js:1091`) |
| `items[].current` | string | yes | missing filename | `widget.value` (`js:1092`) |
| `items[].type` | string | **no** | inferred category | `type` local var (`js:1093`) — **backend ignores it** (`matcher.match` reads only id/node_type/widget_name/current, `matcher.py:130-145`) |

**Response** `{ "matches": [ … ] }`
| field | type | required | semantics | example | frontend consumer (line) |
|---|---|---|---|---|---|
| `matches` | array | yes | match results | — | `matchResult.matches \|\| []` (`js:547`) |
| `matches[].id` | any | yes | node id (echo) | `"5"` | `match.id` (`js:1105`) |
| `matches[].node_type` | string | yes | node type (echo) | `"CheckpointLoader"` | echoed, not displayed |
| `matches[].widget_name` | string | yes | widget name (echo) | `"ckpt_name"` | `match.widget_name` (`js:1107`) |
| `matches[].original` | string | yes | the missing filename | `"v1.5.ckpt"` | `m.original` (`js:550,565,770`) |
| `matches[].new_value` | string | yes | replacement path | `"v1.5-pruned.safetensors"` | `m.new_value` (`js:772,1109,1111`) |
| `matches[].match_type` | string | yes | `Exact\|Fuzzy\|Variant\|DB\|Unknown` | `"Exact"` | `m.match_type` (`js:773`) |
| `matches[].type` | string | **MISSING** | model category (for grouping) | `"checkpoints"` | `item.type` in `groupByType(matches)` (`js:722-730`) ⚠ **not sent** (matcher computes it at `matcher.py:214`, route drops it, `__init__.py:32-39`) |
| `matches[].path` | string | **MISSING** | resolved path | — | not consumed by frontend ⚠ harmless |

> ✔ **`new_value` vs the plan's `matched_value`:** `UPGRADE_PLAN.md:106` lists `matched_value` as a field to keep consistent, but the **actual backend uses `new_value`** (mapped from `m["matched_value"]` at `__init__.py:37`) and the **actual frontend reads `m.new_value`** (`js:772`). They are consistent. The plan name is a documentation error — **do NOT rename** `new_value`.

---

### 1.2 `POST /auto-matcher/search`
**Backend:** `__init__.py:46-105` · **Frontend fetch:** `js:590-605`

**Request body**
| field | type | required | semantics | emitted by frontend (line) |
|---|---|---|---|---|
| `items` | array | yes | missing descriptors | `stillMissing` (`js:559-561, 593`) |
| `items[].current` | string | yes | filename to search | `item.current` — backend reads **only** `current` (`__init__.py:64`) |
| `ignore_cache` | bool | no (default false) | bypass search cache | `ignoreCache` (`js:594`) |

**Response** `{ "downloads": [ … ] }`
| field | type | required | semantics | example | frontend consumer (line) |
|---|---|---|---|---|---|
| `downloads` | array | yes | one entry per found item (absent items omitted) | — | `result.downloads \|\| []` (`js:600`) |
| `downloads[].original` | string | yes | the queried filename | `"model.safetensors"` | `d.original` (`js:567,822,835`) |
| `downloads[].result` | object | yes | best online match **or** local-disk marker | — | `d.result.*` |
| `downloads[].type` | string | **MISSING** | category (for grouping) | — | `item.type` in `groupByType(downloadResults)` (`js:793`) ⚠ **not sent** |

**`downloads[].result` — Variant A: Local-disk marker** (`scanner.find_local_file` hit, `__init__.py:71-83`)
| field | type | required | semantics | example | consumer (line) |
|---|---|---|---|---|---|
| `source` | string const | yes | **exactly** `"Local Disk (Unindexed)"` | `"Local Disk (Unindexed)"` | `d.result.source === "Local Disk (Unindexed)"` (`js:817`) ⚠ **exact-string contract** |
| `name` | string | yes | `"Found Locally"` | `"Found Locally"` | `d.result.name` (`js:823`) |
| `filename` | string | yes | original filename | `"model.safetensors"` | not consumed |
| `url` | string | yes | `""` (no download) | `""` | not consumed in local branch |
| `pageUrl` | string | yes | `""` | `""` | not consumed in local branch |
| `score` | number | yes | `1.0` | `1.0` | not consumed in local branch |
| `local_path` | string | yes | absolute path on disk | `"/models/x.safetensors"` | `d.result.local_path` (`js:824`) |
| `description` | string | yes | hint text | `"File exists on disk..."` | `d.result.description` (`js:823`) |

**`downloads[].result` — Variant B: Online best-match** (`searcher.search()` → `result_list[0]`, `__init__.py:99`, `searcher.py:1483`)
| field | type | required | semantics | example | consumer (line) |
|---|---|---|---|---|---|
| `source` | string | yes | provider label | `"HuggingFace (Exact File)"` / `"Civitai (Native)"` | `d.result.source` (`js:837,856`) |
| `name` | string | yes | model name/label | `"Repo/model"` | `d.result.name` (`js:840`) |
| `filename` | string | yes\* | base filename | `"model.safetensors"` | not consumed (⚠ `\*` `db_fallback` at `searcher.py:1361-1367` omits `filename`) |
| `url` | string | yes | direct download URL | `"https://..."` | `d.result.url` (`js:842`) |
| `pageUrl` | string | yes | model page URL | `"https://..."` | `d.result.pageUrl` (`js:858`) |
| `score` | number | yes | 0..1 similarity | `0.92` | `d.result.score === 1.0` badge (`js:838`) |

> ✔ Online `result` union shape (all providers emit `{source,name,filename,url,pageUrl,score}`, `+hash_match` for `CivitaiHashProvider`, `searcher.py:147-155,241-248,287-294,671-678,875-882,1025-1032,1086-1093,1189-1196,1248-1255`): **consistent** with what the frontend reads. Only `filename` is unused — leaving it is fine.

---

### 1.3 `POST /auto-matcher/refresh-index`
**Backend:** `__init__.py:107-115` · **Frontend:** `js:184-207`

| direction | field | type | required | semantics | consumer (line) |
|---|---|---|---|---|---|
| resp | `status` | string | yes | `"ok"` | `data.status === "ok"` (`js:193`) |
| resp | `count` | int | yes | models indexed | `data.count` (`js:194`) |
| err | `error` | string | yes | flat raw message | `data.error` (`js:196`) — ⚠ see §2 envelope |

Request: POST, no body.

---

### 1.4 `POST /auto-matcher/save-config`
**Backend:** `__init__.py:117-125` · **Frontend:** `js:489-500`

| direction | field | type | required | semantics | consumer (line) |
|---|---|---|---|---|---|
| req | `civitai_api_key` | string | yes | key to persist | `js:491-493` |
| resp | `status` | string | yes | `"ok"` | ignored by frontend (`js:489-500`) |

✔ consistent (frontend does not depend on any specific response field).

---

### 1.5 `POST /auto-matcher/validate-config`
**Backend:** `__init__.py:127-136` · **Frontend:** `js:435-445`

| direction | field | type | required | semantics | consumer (line) |
|---|---|---|---|---|---|
| req | `civitai_api_key` | string | yes | key to test | `js:437` |
| resp | `valid` | bool | yes | key validity | `result.valid` (`js:441`) |
| resp | `message` | string | yes | human-readable status | `result.message` (`js:442,444`) |

✔ consistent.

---

### 1.6 `GET /auto-matcher/get-config`
**Backend:** `__init__.py:138-148` · **Frontend:** `js:11-15, 379-386`

| direction | field | type | required | semantics | consumer (line) |
|---|---|---|---|---|---|
| resp | `version` | string | yes | plugin version | `config.version` (`js:13`) |
| resp | `civitai_api_key` | string | no | stored key (absent if empty) | `config.civitai_api_key` (`js:381`) |
| resp | *(other config keys)* | any | no | full `config.json` dump (`searcher.get_config`) | not consumed by frontend |

✔ consistent. `__version__ = "3.6.2"` (`__init__.py:11`) matches JS default `PROJECT_VERSION = "3.6.2"` (`js:4`).

---

## 2. Error Envelope Spec

**Current state (verified):** every route does `return web.json_response({"error": str(e)}, status=500)` (`__init__.py:44,105,115,125,136,148`). Flat `{error}` with a **raw exception string** (leaks stack/tracebacks/paths) and **no `code`/`detail`**.

**Required envelope (backward-compatible):** keep `error` as a **string** because the shipped frontend concatenates `data.error` directly at `js:196` (`"更新失败: " + data.error`). Changing it to an object would print `[object Object]`. Add `code` + `detail` as siblings.

```json
{
  "error":  "<human-readable, SAFE message — no stack/trace/path>",
  "code":   "MATCH_FAILED",
  "detail": "<optional server-only debug info; NEVER shown to user>"
}
```

### 2.1 Recommended HTTP status per error class
| code | HTTP | when |
|---|---|---|
| `VALIDATION_ERROR` | 400 | malformed / missing request body or field |
| `MATCH_FAILED` | 500 | `matcher.match()` raised |
| `SEARCH_FAILED` | 502 | all providers failed / upstream unreachable |
| `INDEX_REFRESH_FAILED` | 500 | `scanner.scan_incremental()` / `matcher.invalidate_index()` raised |
| `CONFIG_SAVE_FAILED` | 500 | `searcher.save_config()` raised |
| `CONFIG_VALIDATE_FAILED` | 502 | Civitai reachability/network error during key validation |
| `CONFIG_LOAD_FAILED` | 500 | `searcher.get_config()` raised |
| `INTERNAL_ERROR` | 500 | fallback / unexpected |

### 2.2 Shared helper (add once, near top of `__init__.py`)
```python
from aiohttp import web

class ErrorCode:
    VALIDATION_ERROR       = "VALIDATION_ERROR"
    MATCH_FAILED           = "MATCH_FAILED"
    SEARCH_FAILED          = "SEARCH_FAILED"
    INDEX_REFRESH_FAILED   = "INDEX_REFRESH_FAILED"
    CONFIG_SAVE_FAILED     = "CONFIG_SAVE_FAILED"
    CONFIG_VALIDATE_FAILED = "CONFIG_VALIDATE_FAILED"
    CONFIG_LOAD_FAILED     = "CONFIG_LOAD_FAILED"
    INTERNAL_ERROR         = "INTERNAL_ERROR"

def error_response(code: str, message: str, detail: str | None = None, status: int = 500):
    """
    Consistent error envelope. `error` stays a STRING for backward compat with
    js/auto_matcher.js:196. `code`/`detail` are additive. `message` must be
    user-safe; `detail` is server-only and must NOT reach the UI.
    """
    body = {"error": message, "code": code}
    if detail is not None:
        body["detail"] = detail
    return web.json_response(body, status=status)
```
Usage: replace each `except Exception as e: … return web.json_response({"error": str(e)}, status=500)` with e.g.
`return error_response(ErrorCode.MATCH_FAILED, "模型匹配失败，请稍后重试。", detail=str(e))`.
**Success shapes are untouched.**

---

## 3. Frontend Field-Mapping (backend field → JS property)

| backend response field | JS variable / property | line |
|---|---|---|
| `match.matches` | `matchResult.matches` | `js:547` |
| `match.matches[].id` | `m.id` (in `applyFixes`) | `js:1105` |
| `match.matches[].widget_name` | `m.widget_name` | `js:1107` |
| `match.matches[].original` | `m.original` | `js:550,565,770` |
| `match.matches[].new_value` | `m.new_value` | `js:772,1109,1111` |
| `match.matches[].match_type` | `m.match_type` | `js:773` |
| `match.matches[].type` | `item.type` (groupByType) — **not emitted** | `js:722-730` |
| `search.downloads` | `result.downloads` | `js:600` |
| `search.downloads[].original` | `d.original` | `js:567,822,835` |
| `search.downloads[].type` | `item.type` (groupByType) — **not emitted** | `js:793` |
| `search.downloads[].result.source` | `d.result.source` | `js:817,837,856` |
| `search.downloads[].result.name` | `d.result.name` | `js:823,840` |
| `search.downloads[].result.description` | `d.result.description` | `js:823` |
| `search.downloads[].result.local_path` | `d.result.local_path` | `js:824` |
| `search.downloads[].result.score` | `d.result.score` | `js:838` |
| `search.downloads[].result.url` | `d.result.url` | `js:842` |
| `search.downloads[].result.pageUrl` | `d.result.pageUrl` | `js:858` |
| `refresh.status` | `data.status` | `js:193` |
| `refresh.count` | `data.count` | `js:194` |
| `refresh.error` | `data.error` | `js:196` |
| `validate.valid` | `result.valid` | `js:441` |
| `validate.message` | `result.message` | `js:442,444` |
| `getconfig.version` | `config.version` | `js:13` |
| `getconfig.civitai_api_key` | `config.civitai_api_key` | `js:381` |

---

## 4. Discrepancy + Change List for the Engineer

### 4a. Backend response tweaks (minimal, correctness-first)
| # | finding | action | risk | backward-compat |
|---|---|---|---|---|
| D1 | Plan names field `matched_value`; actual backend uses `new_value`, frontend reads `new_value` (`__init__.py:37`, `js:772`) | **No change — keep `new_value`.** Fix the plan doc wording. | none | ✔ |
| D2 | `/match` omits `type` (matcher computes it, `matcher.py:214`); `groupByType(matches)` falls back to `"unknown"` (`js:722-730,743`) | **Recommended (additive):** pass `type` through in the results loop, `__init__.py:32-39` → add `"type": m.get("type", "unknown")`. | low | ✔ adds a field |
| D3 | `/search` `downloads[]` omits `type`; `groupByType(downloadResults)` falls back to `"unknown"` (`js:793`) | **Optional:** read `item.get("type")` (`__init__.py:64`) and attach `type` to both the local-disk object (`71-83`) and the online object (`97-100`). | low | ✔ adds a field |
| D4 | Online `result` from `db_fallback` (`searcher.py:1361-1367`) omits `filename`; all other providers include it | **No change** — frontend never reads `result.filename`. Note for completeness only. | none | ✔ |
| D5 | Local-disk `source` string `"Local Disk (Unindexed)"` is an exact-match branch in JS (`js:817`) | **No change** — lock the literal; do not reword. | none | ✔ |
| D6 | Error envelope leaks raw exception; `match`/`search` errors are **silently swallowed** (no HTTP-status check in `js:546,599`) | Adopt §2 envelope (keep `error` as string). Frontend error UX hardening is a separate T3.2 task. | low | ✔ |

### 4b. Shared error-envelope helper
Add `ErrorCode` + `error_response(...)` (§2.2) once near the top of `__init__.py`. Replace all 6 `except` blocks' `web.json_response({"error": str(e)}, status=500)` with `error_response(ErrorCode.<X>, "<safe msg>", detail=str(e))`. **Success responses are unchanged — the shipped `js/auto_matcher.js` keeps working.**

### 4c. Contract test assertions (committed as `regression_tests/contract_check.py`, runs via `python regression_tests/contract_check.py`)

> 注意：`tests/` 与全局 `test_*.py` 均被 `.gitignore` 忽略，故契约测试命名为 `contract_check.py`（不带 `test_` 前缀）以便入库锁死契约。
1. **match** — POST `{"items":[{id,node_type,widget_name,current}]}` → `200`, body has `matches` array; each item has `id,node_type,widget_name,original,new_value,match_type` (assert `new_value` present, **not** `matched_value`). If D2 implemented, assert `type` present.
2. **search (local)** — for a filename that exists on disk but not in index → `downloads[0].result.source == "Local Disk (Unindexed)"` and `result.local_path` is truthy, `result.url == ""`.
3. **search (online)** — mock `searcher.search` to return `[{source,name,filename,url,pageUrl,score}]` → assert `downloads[0].result` carries `source,name,url,pageUrl,score`; assert frontend-read fields exist (no `result.filename` dependency).
4. **refresh-index** — `200`, `status=="ok"`, `count` is int.
5. **save-config** — `200`, `status=="ok"`.
6. **validate-config** — POST `{"civitai_api_key":""}` → `valid==False`; valid key mock → `valid==True`, `message` is str.
7. **get-config** — `200`, `version` is str and equals `__version__`.
8. **error envelope** — force a route exception → assert body has `error` (string), `code` (in `ErrorCode` set); assert `error` is NOT the raw traceback substring (e.g. `"Traceback"` absent). Assert HTTP status matches the class table in §2.1.
9. **No rename regression** — grep-free assertion: response JSON keys for `match` must equal `{"matches"}` wrapper with item keys exactly `{id,node_type,widget_name,original,new_value,match_type[,type]}` — `matched_value` must be absent.

---

## 5. Assumptions
- `searcher.search()` is assumed to always return a **list** (`[best_match]` or `[]`, `searcher.py:1483,1487`); the `return None` at `searcher.py:1328` only fires on empty filename, which the route guards via `if not filename: continue` (`__init__.py:65`). So `result_list[0]` at `__init__.py:99` is safe.
- Only `version` and `civitai_api_key` are contractually consumed from `get-config`; other config keys are passthrough.
- No code was modified; this document is descriptive + a change list only (per task constraints).
