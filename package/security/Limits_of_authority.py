import hashlib
import getpass
import time
import json
import os
import base64
import functools
import argparse
from typing import Dict, Any, Optional
from package.log_manager import LogManager
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes

# 初始化日志
logger = LogManager.get_logger(__name__)

class AuthorityManager:
    """权限管理类，负责用户验证、权限校验和文件完整性检查"""

    DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "authority_config.json")
    DEFAULT_HASH_STORAGE_FILE = os.path.join(os.path.dirname(__file__), "file_hashes.json")
    DEFAULT_AUDIT_LOG = "audit.log"

    def __init__(self, config_path: str = None, hash_storage_path: str = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.hash_storage_path = hash_storage_path or self.DEFAULT_HASH_STORAGE_FILE

        self.permissions = {}
        self.operations = {}
        self.users = {}
        self.session_timeout = 1800
        self.user_sessions = {}

        self._load_config()
        self._init_hash_storage()

    def _load_config(self):
        """加载或初始化配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.permissions = config.get("permissions", {})
                    self.operations = config.get("operations", {})
                    self.users = config.get("users", {})
                    self.session_timeout = config.get("session_timeout", 1800)
                logger.info(f"成功加载配置文件: {self.config_path}")
            except Exception as e:
                logger.error(f"加载配置文件出错: {e}")
                self._apply_defaults()
        else:
            logger.warning(f"配置文件不存在，正在应用默认设置: {self.config_path}")
            self._apply_defaults()
            self._save_config()

    def _apply_defaults(self):
        """应用默认权限和操作设置"""
        self.permissions = {
            "普通用户": 1,
            "受限操作": 2,
            "高级操作": 3,
            "查看配置": 2,
            "高级查看": 3
        }
        self.operations = {
            "查看数据": 1,
            "修改配置": 2,
            "核心操作": 3,
            "写入文件": 2,
            "查看配置": 2
        }
        # 默认用户 (注意：实际使用时应通过 set_password 重新设置)
        self.users = {}
        self.session_timeout = 1800

    def _save_config(self):
        """保存当前配置到文件"""
        config = {
            "permissions": self.permissions,
            "operations": self.operations,
            "users": self.users,
            "session_timeout": self.session_timeout
        }
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            logger.info(f"配置已保存到: {self.config_path}")
        except Exception as e:
            logger.error(f"保存配置文件出错: {e}")

    def _init_hash_storage(self):
        """初始化文件哈希存储"""
        if not os.path.exists(self.hash_storage_path):
            try:
                with open(self.hash_storage_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
            except Exception as e:
                logger.error(f"初始化哈希存储文件出错: {e}")

    def _hash_password(self, password: str, salt: bytes = None) -> tuple:
        """使用 PBKDF2 进行加盐哈希"""
        if salt is None:
            salt = get_random_bytes(16)
        # 使用 100,000 次迭代
        key = PBKDF2(password, salt, dkLen=32, count=100000)
        return salt, key

    def set_user_password(self, username: str, password: str, permission_level: int):
        """设置或更新用户密码及权限"""
        salt, key_hash = self._hash_password(password)
        self.users[username] = {
            "salt": base64.b64encode(salt).decode('utf-8'),
            "key_hash": base64.b64encode(key_hash).decode('utf-8'),
            "permission": permission_level
        }
        self._save_config()
        logger.info(f"用户 '{username}' 密码已设置")

    def verify_user(self, username: str, password: str) -> bool:
        """验证用户凭据"""
        user_info = self.users.get(username)
        if not user_info:
            return False
        
        salt = base64.b64decode(user_info["salt"])
        stored_hash = base64.b64decode(user_info["key_hash"])
        
        _, current_hash = self._hash_password(password, salt)
        return current_hash == stored_hash

    def update_session(self, username: str):
        """更新用户会话"""
        self.user_sessions[username] = time.time()

    def is_session_valid(self, username: str) -> bool:
        """检查会话是否有效"""
        if username not in self.user_sessions:
            return False
        return (time.time() - self.user_sessions[username]) < self.session_timeout

    def log_audit(self, username: str, operation: str, status: str):
        """记录审计日志"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] 用户: {username}, 操作: {operation}, 状态: {status}\n"

        # 同时记录到系统日志和专门的审计文件
        logger.info(f"AUDIT: {log_entry.strip()}")
        try:
            with open(self.DEFAULT_AUDIT_LOG, "a", encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"写入审计日志出错: {e}")

    def calculate_file_hash(self, file_path: str) -> Optional[str]:
        """计算文件的 SHA256 哈希值"""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(8192)
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except FileNotFoundError:
            logger.warning(f"文件未找到: {file_path}")
            return None
        except Exception as e:
            logger.error(f"计算文件哈希时出错: {e}")
            return None

    def verify_file_integrity(self, file_path: str) -> bool:
        """验证文件完整性"""
        current_hash = self.calculate_file_hash(file_path)
        if current_hash is None:
            return False

        try:
            with open(self.hash_storage_path, 'r', encoding='utf-8') as f:
                hashes = json.load(f)
        except Exception as e:
            logger.error(f"读取哈希存储出错: {e}")
            return False

        stored_hash = hashes.get(file_path)
        
        if stored_hash is None:
            logger.info(f"文件 {file_path} 首次使用，正在保存哈希值")
            hashes[file_path] = current_hash
            try:
                with open(self.hash_storage_path, 'w', encoding='utf-8') as f:
                    json.dump(hashes, f, indent=4)
                return True
            except Exception as e:
                logger.error(f"保存初始哈希出错: {e}")
                return False
        
        if current_hash == stored_hash:
            logger.info(f"文件 '{file_path}' 完整性验证通过")
            return True
        else:
            logger.warning(f"文件 '{file_path}' 完整性受损!")
            return False

    def check_permission(self, username: str, required_level: int) -> bool:
        """检查用户权限"""
        if username not in self.users:
            logger.warning(f"未找到用户: {username}")
            return False

        user_level = self.users[username].get("permission", 0)

        if self.is_session_valid(username):
            if user_level >= required_level:
                return True
            else:
                logger.warning(f"用户 '{username}' 权限等级不足 (拥有: {user_level}, 需要: {required_level})")
                print(f"权限不足: 用户 {username} 的级别为 {user_level}，但此操作需要级别 {required_level}。")
                return False

        print(f"用户 {username} 的会话已过期或不存在，需要验证身份。")
        password = getpass.getpass("请输入密钥: ")
        
        if self.verify_user(username, password):
            if user_level >= required_level:
                self.update_session(username)
                return True
            else:
                logger.warning(f"用户 '{username}' 验证成功但权限不足 (拥有: {user_level}, 需要: {required_level})")
                print("权限不足")
                return False
        else:
            logger.warning(f"用户 '{username}' 密钥验证失败")
            print("密钥无效")
            return False

# 创建单例实例
authority_manager = AuthorityManager()

def require_permission(operation_name):
    """权限控制装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(username, *args, **kwargs):
            required_level = authority_manager.operations.get(operation_name)
            if required_level is None:
                logger.error(f"未知操作: {operation_name}")
                return None
                
            if authority_manager.check_permission(username, required_level):
                authority_manager.log_audit(username, operation_name, "执行")
                return func(username, *args, **kwargs)
            else:
                authority_manager.log_audit(username, operation_name, "拒绝")
                return None
        return wrapper
    return decorator

# --- 操作函数 ---

@require_permission("查看数据")
def view_data(username, file_path):
    if authority_manager.verify_file_integrity(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = file.read()
                print(f"文件内容:\n{data}")
                return True
        except Exception as e:
            print(f"读取文件时出错: {e}")
            return False
    else:
        print("由于完整性检查失败，无法查看数据。")
        return False

@require_permission("修改配置")
def modify_config(username):
    print(f"用户 {username} 正在修改配置...")
    # 实际逻辑在此处添加
    return True

@require_permission("核心操作")
def core_operation(username):
    print(f"用户 {username} 正在执行核心操作...")
    # 实际逻辑在此处添加
    return True

# --- CLI 工具函数 ---

def print_operations():
    print("\n可用操作及其所需权限级别：")
    print("=" * 40)
    # 反向映射权限级别到名称
    level_to_name = {v: k for k, v in authority_manager.permissions.items()}
    for op, level in authority_manager.operations.items():
        p_name = level_to_name.get(level, "未知")
        print(f"- {op:10} : {p_name} (级别 {level})")

def login():
    """登录并建立会话"""
    username = input("用户名: ")
    password = getpass.getpass("密码: ")
    
    if authority_manager.verify_user(username, password):
        authority_manager.update_session(username)
        logger.info(f"用户 '{username}' 登录成功")
        print(f"登录成功! 欢迎 {username}")
        return username
    else:
        logger.warning(f"用户 '{username}' 登录失败")
        print("登录失败: 用户名或密码错误")
        return None

def run():
    """Butler 系统加载入口"""
    main()

def main():
    """CLI 主循环"""
    parser = argparse.ArgumentParser(description="权限控制系统管理工具")
    parser.add_argument("--add-user", nargs=3, metavar=("USERNAME", "PASSWORD", "LEVEL"), help="添加或更新用户")
    parser.add_argument("--list-users", action="store_true", help="列出所有用户 (仅用户名)")
    args = parser.parse_args()

    if args.add_user:
        username, password, level = args.add_user
        authority_manager.set_user_password(username, password, int(level))
        print(f"用户 '{username}' 已创建/更新。")
        return

    if args.list_users:
        print("当前系统用户：")
        for user in authority_manager.users:
            print(f"- {user}")
        return

    logger.info("权限控制系统启动")
    
    # 检查是否需要初始化默认用户
    if not authority_manager.users:
        print("检测到系统未配置用户，正在初始化默认用户...")
        authority_manager.set_user_password("admin", "admin_key", 3)
        authority_manager.set_user_password("operator", "operator_key", 2)
        print("已创建默认用户: admin/admin_key, operator/operator_key")
    
    current_user = login()
    if not current_user:
        return
    
    while True:
        print("\n--- 权限控制系统菜单 ---")
        print("1. 查看可用操作")
        print("2. 查看文件内容")
        print("3. 修改系统配置")
        print("4. 执行核心任务")
        print("5. 查看审计日志 (需高级权限)")
        print("6. 用户管理 (需高级权限)")
        print("7. 退出")
        
        choice = input("> ")
        
        if choice == "1":
            print_operations()
        elif choice == "2":
            path = input("输入文件路径: ")
            view_data(current_user, path)
        elif choice == "3":
            modify_config(current_user)
        elif choice == "4":
            core_operation(current_user)
        elif choice == "5":
            if authority_manager.users.get(current_user, {}).get("permission", 0) >= 3:
                try:
                    if os.path.exists(AuthorityManager.DEFAULT_AUDIT_LOG):
                        with open(AuthorityManager.DEFAULT_AUDIT_LOG, 'r', encoding='utf-8') as f:
                            print("\n--- 最近 20 条审计日志 ---")
                            lines = f.readlines()
                            for line in lines[-20:]:
                                print(line.strip())
                    else:
                        print("审计日志文件不存在。")
                except Exception as e:
                    print(f"读取审计日志出错: {e}")
            else:
                print("权限不足。")
        elif choice == "6":
            if authority_manager.users.get(current_user, {}).get("permission", 0) >= 3:
                new_user = input("用户名: ")
                new_pwd = getpass.getpass("密码: ")
                new_level = input("级别 (1-3): ")
                authority_manager.set_user_password(new_user, new_pwd, int(new_level))
                print(f"用户 {new_user} 已更新。")
            else:
                print("权限不足，无法管理用户。")
        elif choice == "7":
            print("正在退出...")
            break
        else:
            print("无效输入，请重试")

if __name__ == "__main__":
    main()
