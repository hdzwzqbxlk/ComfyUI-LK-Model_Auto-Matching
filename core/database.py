import sqlite3
import os
import json
import logging
import re
from difflib import SequenceMatcher

class ModelDatabase:
    """
    模型数据库管理器 (Phase 2)
    负责管理本地 SQLite 数据库，存储模型信息、哈希和别名。
    """
    def __init__(self, db_path=None):
        if db_path is None:
            # 默认存储在 core/data/models.db
            db_path = os.path.join(os.path.dirname(__file__), 'data', 'models.db')
        
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        directory = os.path.dirname(self.db_path)
        if not os.path.exists(directory):
            os.makedirs(directory)

    def _get_connection(self):
        """获取数据库连接（复用持久连接，WAL 模式）"""
        if not hasattr(self, '_conn') or self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _init_db(self):
        """初始化数据库 Schema"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 1. Models 表：存储规范化模型信息
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,  -- 标准化名称 (e.g., "Flux.1 Dev")
            type TEXT,                  -- Checkpoint, LoRA, VAE
            base_model TEXT,            -- SDXL, SD1.5, Flux
            description TEXT
        )
        ''')

        # 2. File Hashes 表：用于哈希精确匹配
        # 这里使用 hash_sha256 作为主键，防止重复
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_hashes (
            hash_sha256 TEXT PRIMARY KEY,
            model_id INTEGER,
            filename TEXT,              -- 已知的官方文件名 (可选)
            source TEXT,                -- Civitai, HuggingFace
            FOREIGN KEY(model_id) REFERENCES models(id)
        )
        ''')

        # 3. Aliases 表：用于文件名模糊匹配
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS aliases (
            alias TEXT PRIMARY KEY,
            model_id INTEGER,
            is_regex BOOLEAN DEFAULT 0,
            FOREIGN KEY(model_id) REFERENCES models(id)
        )
        ''')

        conn.commit()
        # conn kept alive for reuse

    def add_model(self, name, model_type=None, base_model=None, description=None):
        """添加或获取模型 ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT OR IGNORE INTO models (name, type, base_model, description)
            VALUES (?, ?, ?, ?)
            ''', (name, model_type, base_model, description))
            conn.commit()
            
            # 获取 ID (无论是新插入的还是已存在的)
            cursor.execute('SELECT id FROM models WHERE name = ?', (name,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            pass  # conn kept alive for reuse

    def add_hash(self, sha256, model_id, filename=None, source="User"):
        """添加文件哈希映射"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO file_hashes (hash_sha256, model_id, filename, source)
            VALUES (?, ?, ?, ?)
            ''', (sha256, model_id, filename, source))
            conn.commit()
        finally:
            pass  # conn kept alive for reuse

    def add_alias(self, alias, model_id, is_regex=False):
        """添加模型别名"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO aliases (alias, model_id, is_regex)
            VALUES (?, ?, ?)
            ''', (alias.lower(), model_id, is_regex))
            conn.commit()
        finally:
            pass  # conn kept alive for reuse

    def get_model_by_hash(self, sha256):
        """通过哈希查找模型"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            SELECT m.name, m.type, m.base_model, h.source 
            FROM file_hashes h
            JOIN models m ON h.model_id = m.id
            WHERE h.hash_sha256 = ?
            ''', (sha256,))
            return cursor.fetchone()
        finally:
            pass  # conn kept alive for reuse

    def search_by_filename(self, filename):
        """
        通过文件名查找模型 (Phase 2 Enhanced Implementation)
        支持精确匹配、正则匹配和模糊匹配
        返回: (name, type, base_model, description)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        filename_lower = filename.lower()
        try:
            # 尝试直接匹配 alias (需移除扩展名)
            base_name = os.path.splitext(filename_lower)[0]
            
            cursor.execute('''
            SELECT m.name, m.type, m.base_model, m.description
            FROM aliases a
            JOIN models m ON a.model_id = m.id
            WHERE a.alias = ? AND a.is_regex = 0
            ''', (base_name,))
            
            result = cursor.fetchone()
            if result:
                return result
            
            # 正则匹配 (L3): 尝试所有正则别名
            cursor.execute('''
            SELECT a.alias, m.name, m.type, m.base_model, m.description
            FROM aliases a
            JOIN models m ON a.model_id = m.id
            WHERE a.is_regex = 1
            ''')
            
            regex_results = cursor.fetchall()
            for alias, name, model_type, base_model, description in regex_results:
                try:
                    if re.search(alias, base_name, re.IGNORECASE):
                        return (name, model_type, base_model, description)
                except re.error:
                    # Invalid regex pattern, skip
                    continue
            
            # 模糊匹配: 使用 SequenceMatcher 找到最接近的别名
            cursor.execute('''
            SELECT a.alias, m.name, m.type, m.base_model, m.description
            FROM aliases a
            JOIN models m ON a.model_id = m.id
            WHERE a.is_regex = 0
            ''')
            
            all_aliases = cursor.fetchall()
            best_match = None
            best_score = 0.85  # 模糊匹配阈值
            
            for alias, name, model_type, base_model, description in all_aliases:
                score = SequenceMatcher(None, base_name, alias).ratio()
                if score > best_score:
                    best_score = score
                    best_match = (name, model_type, base_model, description)
            
            return best_match
            
        finally:
            pass  # conn kept alive for reuse

# ... existing code ...

    def populate_from_json(self):
        """从 models_data.json 迁移数据到数据库 (Phase 2 Migration)"""
        json_path = os.path.join(os.path.dirname(self.db_path), 'models_data.json')
        if not os.path.exists(json_path):
            print(f"[DB] JSON data file not found: {json_path}")
            return

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[DB] Error loading JSON: {e}")
            return

        conn = self._get_connection()
        cursor = conn.cursor()
        
        added_models = 0
        added_aliases = 0
        
        try:
            # 1. 迁移 Popular Models
            # 假设这些是 "标准模型"，尽管名字可能还是文件名格式，但在 Phase 3 我们会进一步清理
            popular_models = data.get('popular_models', {})
            for name, repo_id in popular_models.items():
                # 插入模型
                # 推断 base_model (简单的启发式)
                base_model = "Unknown"
                name_lower = name.lower()
                if "sdxl" in name_lower: base_model = "SDXL"
                elif "flux" in name_lower: base_model = "Flux"
                elif "sd1.5" in name_lower or "v1-5" in name_lower: base_model = "SD1.5"
                elif "sd3" in name_lower: base_model = "SD3"
                elif "wan" in name_lower: base_model = "Wan"

                cursor.execute('''
                INSERT OR IGNORE INTO models (name, type, base_model, description)
                VALUES (?, ?, ?, ?)
                ''', (name, "Checkpoint", base_model, f"Repo: {repo_id}"))
                
                # 获取 ID
                cursor.execute('SELECT id FROM models WHERE name = ?', (name,))
                row = cursor.fetchone()
                if row:
                    model_id = row[0]
                    # 添加 Alias (即它自己)
                    cursor.execute('INSERT OR IGNORE INTO aliases (alias, model_id) VALUES (?, ?)', (name.lower(), model_id))
                    # 添加 Hash (暂时没有 SHA256，但我们可以把 Repo ID 存到 description 或其他地方，这里先跳过 file_hashes，因为没有 hash)
                    added_models += 1

            # 2. 迁移 Model Aliases (作为虚拟模型或关联到现有模型?)
            # 目前 model_aliases 只是 缩写 -> 全名 的映射 (e.g. 'sdxl' -> 'stable diffusion xl')
            # 这实际上不应该存为 'models' 表的一行，而是应该作为 全局别名/同义词
            # 但为了 DB 完整性，我们可以把 'Full Name' 存为模型，把 'Abbr' 存为 alias
            aliases_map = data.get('model_aliases', {})
            for abbr, full_name in aliases_map.items():
                # 插入全名作为模型
                cursor.execute('''
                INSERT OR IGNORE INTO models (name, type, base_model, description)
                VALUES (?, ?, ?, ?)
                ''', (full_name, "Concept", "Unknown", "General Concept"))
                
                cursor.execute('SELECT id FROM models WHERE name = ?', (full_name,))
                row = cursor.fetchone()
                if row:
                    model_id = row[0]
                    # 插入缩写作为 alias
                    cursor.execute('INSERT OR IGNORE INTO aliases (alias, model_id) VALUES (?, ?)', (abbr.lower(), model_id))
                    added_aliases += 1

            conn.commit()
            print(f"[DB] Migration complete. Added {added_models} models and {added_aliases} aliases.")
            
        except Exception as e:
            print(f"[DB] Migration failed: {e}")
            conn.rollback()
        finally:
            pass  # conn kept alive for reuse

# 单例实例
db = ModelDatabase()
if __name__ == "__main__":
    # 如果直接运行脚本，执行迁移
    db.populate_from_json()
