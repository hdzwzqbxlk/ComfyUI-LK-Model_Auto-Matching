# -*- coding: utf-8 -*-
"""
[v3.6.3] 验证自动索引同步 (Auto-Sync on Match)
不依赖 ComfyUI 运行时：stub folder_paths，用临时目录模拟模型库的增删。
"""
import os
import sys
import time
import types
import shutil
import tempfile
import importlib.util

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE_DIR = os.path.join(PROJECT_ROOT, "core")
sys.path.insert(0, CORE_DIR)  # 让 matcher 的 fallback `from utils import` 可用

# ---- 临时模型库 ----
TMP = tempfile.mkdtemp(prefix="lk_autosync_test_")
LORAS = os.path.join(TMP, "loras")
UNET = os.path.join(TMP, "unet")
os.makedirs(LORAS)
os.makedirs(UNET)

def make_model(path, size_kb=64):
    with open(path, "wb") as f:
        f.write(os.urandom(size_kb * 1024))

make_model(os.path.join(LORAS, "alpha_lora.safetensors"))
make_model(os.path.join(LORAS, "beta_lora.safetensors"))
make_model(os.path.join(UNET, "gamma_unet.gguf"))

# ---- stub folder_paths ----
folder_paths = types.ModuleType("folder_paths")
_PATHS = {
    "loras": [LORAS],
    "unet": [UNET],
}
def get_folder_paths(key):
    return _PATHS.get(key, [])
folder_paths.get_folder_paths = get_folder_paths
sys.modules["folder_paths"] = folder_paths

# ---- 加载 core 子模块（注册空壳包以支持相对导入，并绕过 core/__init__ 的重依赖）----
core_pkg = types.ModuleType("core")
core_pkg.__path__ = [CORE_DIR]
sys.modules["core"] = core_pkg

from core.scanner import ModelScanner
from core.matcher import ModelMatcher

passed = failed = 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}")

try:
    scanner = ModelScanner()
    # 重定向索引镜像到临时目录，避免污染项目根目录
    scanner.index_file = os.path.join(TMP, "model_index.json")
    matcher = ModelMatcher(scanner)

    print("== 1. 初始全量扫描 ==")
    n = scanner.scan_incremental()
    check("扫描到 3 个模型", n == 3)
    check("revision 递增为 1", scanner.revision == 1)

    print("== 2. 首次匹配构建倒排索引 ==")
    items = [{"id": 1, "node_type": "LoraLoader", "widget_name": "lora_name", "current": "alpha_lora.safetensors"}]
    res = matcher.match(items)
    check("匹配到 alpha_lora", len(res) == 1 and res[0]["matched_value"] == "alpha_lora.safetensors")
    check("matcher 记录 revision=1", matcher._built_revision == 1)

    print("== 3. 删一加一（总数不变，旧版数量校验会失效的边界） ==")
    os.remove(os.path.join(LORAS, "beta_lora.safetensors"))
    time.sleep(0.05)
    make_model(os.path.join(LORAS, "delta_lora.safetensors"))
    n = scanner.scan_incremental()
    check("总数仍为 3", n == 3)
    check("revision 递增为 2（集合内容变化）", scanner.revision == 2)

    res = matcher.match([{"id": 2, "node_type": "LoraLoader", "widget_name": "lora_name", "current": "delta_lora.safetensors"}])
    check("新文件 delta_lora 立即可匹配", len(res) == 1)
    res = matcher.match([{"id": 3, "node_type": "LoraLoader", "widget_name": "lora_name", "current": "beta_lora.safetensors"}])
    check("已删除的 beta_lora 不再被引用（模糊兜底属正常行为）",
          not any(m["matched_value"] == "beta_lora.safetensors" for m in res)
          and all(os.path.exists(m["path"]) for m in res))
    check("matcher 重建到 revision=2", matcher._built_revision == 2)

    print("== 4. 无变化时不触发重建（缓存复用） ==")
    n = scanner.scan_incremental()
    check("revision 保持 2（无增删）", scanner.revision == 2)
    matcher.match([{"id": 4, "node_type": "LoraLoader", "widget_name": "lora_name", "current": "alpha_lora.safetensors"}])
    check("matcher 缓存复用（_built_revision 未变）", matcher._built_revision == 2)

    print("== 5. auto_sync 节流与新文件自动收录 ==")
    make_model(os.path.join(LORAS, "epsilon_lora.safetensors"))
    n = scanner.auto_sync()  # 距上次扫描 < 3s，应跳过
    check("auto_sync 节流跳过（新文件暂未收录）", n == 3)
    scanner.data["last_scan"] -= 10  # 模拟超过节流窗口
    n = scanner.auto_sync()
    check("auto_sync 窗口后自动扫描，收录新文件（总数 4）", n == 4)
    res = matcher.match([{"id": 5, "node_type": "LoraLoader", "widget_name": "lora_name", "current": "epsilon_lora.safetensors"}])
    check("epsilon_lora 通过 auto_sync 后可匹配", len(res) == 1)

    print("== 6. 通过 auto_sync 自动擦除（模拟用户删文件后直接点匹配） ==")
    os.remove(os.path.join(LORAS, "alpha_lora.safetensors"))
    scanner.data["last_scan"] -= 10
    n = scanner.auto_sync()
    check("auto_sync 擦除已删文件（总数 3）", n == 3)
    res = matcher.match([{"id": 6, "node_type": "LoraLoader", "widget_name": "lora_name", "current": "alpha_lora.safetensors"}])
    check("被删文件不再被引用",
          not any(m["matched_value"] == "alpha_lora.safetensors" for m in res)
          and all(os.path.exists(m["path"]) for m in res))

finally:
    shutil.rmtree(TMP, ignore_errors=True)

print(f"\n结果: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
