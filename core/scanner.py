import os
import hashlib
import json
import time
import folder_paths

# 定义要扫描的模型类型 (对应 folder_paths 中的 key)
MODEL_TYPES = {
    "checkpoints": "checkpoints",
    "loras": "loras",
    "vae": "vae",
    "controlnet": "controlnet",
    "upscale_models": "upscale_models",
    "embeddings": "embeddings",
    "clip": "clip",
    "unet": "unet",
    "clip_vision": "clip_vision",
    "style_models": "style_models",
    "diffusers": "diffusers"
}

# 有效模型文件扩展名 (用于过滤非模型文件)
VALID_MODEL_EXTENSIONS = {
    '.safetensors', '.ckpt', '.pt', '.pth', '.bin', 
    '.gguf', '.onnx', '.pkl', '.sft'
}

HASH_VERSION = 1  # 索引结构版本，不兼容时升级

class ModelIndex:
    def __init__(self):
        # 索引文件路径 (保存在项目根目录，即 core 的上级目录)
        self.index_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "model_index.json")
        self.data = {
            "version": HASH_VERSION,
            "last_scan": 0,
            "models": {} # { unique_hash: { path, filename, type, size, mtime } }
        }
        self.load_index()

    def load_index(self):
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                    if saved_data.get("version") == HASH_VERSION:
                        self.data = saved_data
                    else:
                        print("[AutoMatch] Index version mismatch, rebuilding...")
            except Exception as e:
                print(f"[AutoMatch] Failed to load index: {e}")

    def save_index(self):
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[AutoMatch] Failed to save index: {e}")

    def calculate_fast_hash(self, filepath):
        """
        计算快速哈希：Size + MTime + First 1MB + Last 1MB (MD5)
        足以区分大部分模型文件，且速度极快
        """
        try:
            stat = os.stat(filepath)
            file_size = stat.st_size
            mtime = stat.st_mtime
            
            # 基础指纹
            fingerprint = f"{file_size}-{mtime}"
            
            # 读取头尾数据进行哈希 (避免仅靠元数据冲突)
            md5 = hashlib.md5()
            md5.update(fingerprint.encode('utf-8'))
            
            with open(filepath, 'rb') as f:
                # Read first 1MB
                chunk = f.read(1024 * 1024)
                md5.update(chunk)
                
                # Check for last 1MB
                if file_size > 1024 * 1024:
                    f.seek(-1024 * 1024, 2)
                    chunk = f.read(1024 * 1024)
                    md5.update(chunk)
            
            return md5.hexdigest()
        except Exception as e:
            print(f"[AutoMatch] Hash error {filepath}: {e}")
            return None

    def scan_incremental(self):
        """
        执行增量扫描
        """
        start_time = time.time()
        print("[AutoMatch] Starting incremental scan...")
        
        current_models_on_disk = set()
        new_or_updated_count = 0
        
        # 1. 扫描磁盘
        for type_key, folder_key in MODEL_TYPES.items():
            # 获取该类型下的所有文件名 (folder_paths.get_filename_list 返回的是相对路径 list)
            try:
                # ComfyUI 方法: get_filename_list
                filenames = folder_paths.get_filename_list(folder_key)
                if not filenames:
                    print(f"[AutoMatch] No models found for type: {type_key} (folder: {folder_key})")
                    continue
                
                print(f"[AutoMatch] Scanning {len(filenames)} files for {type_key}...")

                for filename in filenames:
                    # 获取绝对路径
                    full_path = folder_paths.get_full_path(folder_key, filename)
                    if not full_path:
                        continue
                    
                    # 记录该路径存在
                    current_models_on_disk.add(full_path)
                    
                    # 检查是否需要更新索引
                    # 我们使用 full_path 作为 lookup key 来检查是否已索引 (为了快速检测变化)
                    # 但存储时使用 hash 作为 key
                    
                    # 为了高效，我们需要反向查找: Path -> Hash
                    # 但因为 JSON 结构是 Hash -> Info，我们需要先遍历一遍建立临时映射?
                    # 为了增量快，我们在内存中维护 Path -> Info 的映射会更好?
                    # 暂且用简单的遍历查找 (优化点)
                    # 或者，我们在 data 中存一个 "paths" 辅助字典?
                    pass 

            except Exception as e:
                print(f"[AutoMatch] Error creating file list for {type_key}: {e}")
                continue

        # 优化: 重构数据结构以支持 Path-Key 查找?
        # 不，用户要求 "模型位置变动也能感应到"，这意味着 Identity 是 Hash。
        # 如果 v1.5 从 A 移到 B。
        # 1. A 消失 -> Scan 发现 A 不在 disk。
        # 2. B 出现 -> Scan 发现 B 是新文件。
        # 3. 计算 B 的 Hash -> 发现 Hash 等于原来的 A。
        # 4. 更新条目: Hash 不变，Path 变了。
        
        # 实现逻辑:
        # A. 构建 disk_files_map: { full_path: { type, filename, mtime, size } }
        disk_files = {}
        for type_key, folder_key in MODEL_TYPES.items():
            try:
                filenames = folder_paths.get_filename_list(folder_key)
                if not filenames: continue
                for filename in filenames:
                    full_path = folder_paths.get_full_path(folder_key, filename)
                    if not full_path or not os.path.exists(full_path): continue
                    
                    # 过滤非模型文件 (图片、音频、文本等)
                    _, ext = os.path.splitext(full_path)
                    if ext.lower() not in VALID_MODEL_EXTENSIONS:
                        continue
                    
                    stat = os.stat(full_path)
                    disk_files[full_path] = {
                        "type": type_key,
                        "filename": filename,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime
                    }
            except:
                pass

        # B. 遍历现有索引，标记移除和保持
        # existing_index: { hash: info }
        # 我们需要识别:
        # 1. 路径匹配且 mtime/size 匹配 -> 保持 (Keep)
        # 2. 路径匹配但 mtime/size 变了 -> 需要重算 Hash (Dirty)
        # 3. 路径在索引有但在 disk_files 无 -> 可能是移动了或删除了 (Lost)
        
        # 为了处理移动，我们需要 careful。
        
        next_models = {} # 新的 models 字典
        
        # 建立 path -> hash 的映射以便快速查找
        path_to_hash = {}
        for h, info in self.data["models"].items():
            path_to_hash[info["path"]] = h

        # 处理磁盘文件
        for path, meta in disk_files.items():
            file_hash = None
            
            # Case 1: 路径在索引中存在
            if path in path_to_hash:
                old_hash = path_to_hash[path]
                old_info = self.data["models"].get(old_hash)
                
                # Check consistency
                if old_info and old_info["size"] == meta["size"] and abs(old_info["mtime"] - meta["mtime"]) < 1.0:
                    # 完全没变
                    file_hash = old_hash
                    # 更新 entry (直接复用 old_info)
                    next_models[file_hash] = old_info
                    continue
                else:
                    # 变了 (Modified), 重算 hash
                    file_hash = self.calculate_fast_hash(path)
                    new_or_updated_count += 1
            else:
                # Case 2: 新路径 (New File or Moved File)
                file_hash = self.calculate_fast_hash(path)
                new_or_updated_count += 1
            
            if file_hash:
                # 更新/添加到新索引
                next_models[file_hash] = {
                    "path": path,
                    "filename": meta["filename"],
                    "type": meta["type"],
                    "size": meta["size"],
                    "mtime": meta["mtime"],
                    "hash": file_hash # 冗余存储方便
                }

        # 3. 替换索引
        self.data["models"] = next_models
        self.data["last_scan"] = time.time()
        self.save_index()
        
        elapsed = time.time() - start_time
        print(f"[AutoMatch] Scan finished in {elapsed:.2f}s. Total: {len(next_models)}, Updated: {new_or_updated_count}")
        return len(next_models)

    def get_all_models(self):
        return self.data["models"].values()

class ModelScanner(ModelIndex):
    pass
