import os
import sys

# 尝试导入 folder_paths, 如果不在 ComfyUI 环境下则创建一个 Mock 对象以方便测试
try:
    import folder_paths
except ImportError:
    class MockFolderPaths:
        def get_filename_list(self, folder_name):
            return []
        def get_folder_paths(self, folder_name):
            return []
    folder_paths = MockFolderPaths()

class ModelScanner:
    def __init__(self):
        self.known_types = ["checkpoints", "loras", "vae", "controlnet", "upscale_models", "embeddings", "clip", "unet"]
        
    def scan_all_models(self):
        """
        扫描所有已知类型的模型目录，返回一个字典：
        {
            "checkpoints": ["model1.ckpt", "subfolder/model2.safetensors", ...],
            "loras": [...]
        }
        """
        all_models = {}
        for folder_type in self.known_types:
            try:
                files = folder_paths.get_filename_list(folder_type)
                if files:
                    all_models[folder_type] = files
            except Exception as e:
                print(f"[AutoModelMatcher] Warning: Could not scan {folder_type}: {e}")
                
        return all_models

    def get_full_path(self, folder_type, filename):
        """
        获取模型的完整路径 (用于调试或高级匹配)
        """
        try:
            return folder_paths.get_full_path(folder_type, filename)
        except:
            return None
