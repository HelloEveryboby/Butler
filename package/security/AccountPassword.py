"""
🔐 账号密码管理器 (AccountPassword)
提供安全的账号密码存储、自动登录和强密码生成功能。
采用主密码加密机制，所有数据均通过 AES-256 进行本地加密存储。
"""

import sqlite3
import pyautogui
import time
import sys
import os
import re
import csv
import threading
from getpass import getpass
import bcrypt
import pyperclip
from package.core_utils.log_manager import LogManager
from package.security.crypto_core import SymmetricCrypto

# 初始化日志
logging = LogManager.get_logger(__name__)

class AccountManager:
    # 数据库存储路径，符合系统惯例
    DB_PATH = os.path.join("data", "system_data", "account_manager.db")

    def __init__(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(self.DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()
        self.master_key = None

        # 获取或生成加密盐（用于 PBKDF2 派生 AES 密钥）
        salt_hex = self._get_config("encryption_salt")
        if not salt_hex:
            self.encryption_salt = os.urandom(16)
            self._set_config("encryption_salt", self.encryption_salt.hex())
        else:
            self.encryption_salt = bytes.fromhex(salt_hex)

    def _init_db(self):
        """初始化数据库表结构"""
        # 配置表
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS config (
                                name TEXT PRIMARY KEY,
                                value TEXT
                             )''')
        # 账号表
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS accounts (
                                id INTEGER PRIMARY KEY,
                                username TEXT NOT NULL,
                                password_encrypted TEXT NOT NULL,
                                iv TEXT NOT NULL,
                                category TEXT NOT NULL,
                                website TEXT NOT NULL,
                                notes TEXT DEFAULT '',
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                             )''')
        self.conn.commit()

    def _get_config(self, name):
        self.cursor.execute("SELECT value FROM config WHERE name = ?", (name,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def _set_config(self, name, value):
        self.cursor.execute("INSERT OR REPLACE INTO config (name, value) VALUES (?, ?)", (name, value))
        self.conn.commit()

    def authenticate(self):
        """验证主密码或引导设置主密码"""
        master_hash = self._get_config("master_hash")
        if not master_hash:
            print("\n" + "="*50)
            print("首次运行：请设置主密码 (Master Password)")
            print("⚠️ 请务必记住该密码，丢失后无法找回加密的账号！")
            print("="*50)
            while True:
                p1 = getpass("设置主密码 (至少8位): ")
                if len(p1) < 8:
                    print("❌ 密码太短，请至少输入8位")
                    continue
                p2 = getpass("请再次输入以确认: ")
                if p1 != p2:
                    print("❌ 两次输入不一致")
                    continue
                break

            # 使用 bcrypt 哈希存储主密码，用于身份验证
            hashed = bcrypt.hashpw(p1.encode('utf-8'), bcrypt.gensalt())
            self._set_config("master_hash", hashed.decode('utf-8'))
            # 派生 AES 密钥
            self.master_key = SymmetricCrypto.derive_key(p1, self.encryption_salt)
            print("✅ 主密码设置成功！")
            return True
        else:
            print("\n" + "="*50)
            print("🔐 请输入主密码以解锁管理器")
            print("="*50)
            for i in range(3):
                p = getpass("主密码: ")
                if bcrypt.checkpw(p.encode('utf-8'), master_hash.encode('utf-8')):
                    self.master_key = SymmetricCrypto.derive_key(p, self.encryption_salt)
                    print("✅ 解锁成功")
                    return True
                else:
                    print(f"❌ 密码错误 (剩余尝试次数: {2-i})")
            print("❌ 尝试次数过多，程序退出。")
            return False

    def _encrypt(self, plaintext):
        iv, ct = SymmetricCrypto.encrypt_data(plaintext, self.master_key)
        return iv, ct

    def _decrypt(self, iv, ct):
        try:
            return SymmetricCrypto.decrypt_data(iv, ct, self.master_key)
        except Exception as e:
            logging.error(f"解密失败: {e}")
            return None

    def check_password_strength(self, password):
        """检查密码强度"""
        if len(password) < 8: return "弱 (长度不够)"
        if not re.search(r"\d", password): return "中 (缺少数字)"
        if not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password): return "中 (缺少大小写混合)"
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): return "强 (建议添加特殊字符)"
        return "极强"

    def generate_password(self, length=16):
        """生成随机强密码"""
        import string
        import random
        chars = string.ascii_letters + string.digits + string.punctuation
        return ''.join(random.choice(chars) for _ in range(length))

    def create_account(self):
        print("\n--- 创建新账号 ---")
        username = input("用户名: ")

        while True:
            choice = input("是否生成强密码? (y/n, 默认n): ").lower()
            if choice == 'y':
                password = self.generate_password()
                print(f"生成的密码: {password}")
                confirm = input("使用此密码? (y/n): ").lower()
                if confirm != 'y': continue
            else:
                password = getpass("请输入密码: ")
                strength = self.check_password_strength(password)
                print(f"密码强度: {strength}")
                if len(password) < 8:
                    print("❌ 密码太短，请重试")
                    continue
            break
            
        category = input("分类 (如 社交/工作/银行): ")
        website = input("网站/应用地址 (URL): ")
        notes = input("备注 (可选): ")

        iv, ct = self._encrypt(password)

        try:
            self.cursor.execute("INSERT INTO accounts (username, password_encrypted, iv, category, website, notes) VALUES (?, ?, ?, ?, ?, ?)",
                               (username, ct, iv, category, website, notes))
            self.conn.commit()
            print("✅ 账号信息已安全加密保存")
        except Exception as e:
            print(f"❌ 保存失败: {e}")

    def view_accounts(self, search_term=None):
        query = "SELECT id, username, category, website FROM accounts"
        params = []
        if search_term:
            query += " WHERE username LIKE ? OR category LIKE ? OR website LIKE ?"
            like_term = f"%{search_term}%"
            params = [like_term, like_term, like_term]

        self.cursor.execute(query, params)
        accounts = self.cursor.fetchall()
        if not accounts:
            print("ℹ️ 未找到匹配的账号记录")
            return

        print("\n" + "-"*75)
        print(f"{'ID':<5}{'用户名':<20}{'分类':<15}{'网站':<30}")
        print("-"*75)
        for acc in accounts:
            print(f"{acc[0]:<5}{acc[1]:<20}{acc[2]:<15}{acc[3]:<30}")
        print("-"*75)

        choice = input("\n输入ID查看详情 (或按Enter返回主菜单): ")
        if choice.isdigit():
            self.cursor.execute("SELECT username, password_encrypted, iv, category, website, notes FROM accounts WHERE id=?", (choice,))
            acc = self.cursor.fetchone()
            if acc:
                print("\n" + "="*30)
                print(f"用户名: {acc[0]}")
                print(f"分类: {acc[3]}")
                print(f"网站: {acc[4]}")
                print(f"备注: {acc[5]}")
                print("="*30)
                
                print("\n操作: [1] 复制密码 [2] 显示密码 [Enter] 返回")
                op = input("> ")
                password = self._decrypt(acc[2], acc[1])
                if not password:
                    print("❌ 无法解密密码，可能密钥已损坏。")
                    return

                if op == '1':
                    pyperclip.copy(password)
                    print("✅ 密码已复制到剪贴板，10秒后将自动清除...")
                    def delayed_clear():
                        time.sleep(10)
                        pyperclip.copy("")
                    threading.Thread(target=delayed_clear, daemon=True).start()
                elif op == '2':
                    print(f"🔑 密码: {password}")
                    input("\n按回车键隐藏并返回...")
            else:
                print("❌ 未找到该ID")

    def auto_login(self):
        self.cursor.execute("SELECT id, username, website FROM accounts")
        accounts = self.cursor.fetchall()
        if not accounts:
            print("ℹ️ 暂无账号记录，请先创建。")
            return

        print("\n可用登录账号列表:")
        for i, acc in enumerate(accounts):
            print(f"{i+1}. {acc[1]} (@ {acc[2]})")

        choice = input("\n选择编号进行自动登录 (或按Enter返回): ")
        if choice.isdigit() and 0 < int(choice) <= len(accounts):
            acc_id = accounts[int(choice)-1][0]
            self.cursor.execute("SELECT username, password_encrypted, iv, website FROM accounts WHERE id=?", (acc_id,))
            username, ct, iv, website = self.cursor.fetchone()
            password = self._decrypt(iv, ct)
            if not password:
                print("❌ 解密失败，无法自动登录")
                return

            print(f"\n🚀 准备登录: {username} @ {website}")
            print("⚠️ 重要: 请在5秒内将鼠标焦点点击到目标页面的用户名输入框中！")
            for i in range(5, 0, -1):
                print(f"{i}...", end=" ", flush=True)
                time.sleep(1)
            print("\n正在模拟键盘输入...")

            try:
                # 模拟输入
                pyautogui.write(username, interval=0.05)
                pyautogui.press('tab')
                pyautogui.write(password, interval=0.05)
                pyautogui.press('enter')
                print("✅ 登录指令已发出。")
                logging.info(f"Auto-login triggered for {username} on {website}")
            except Exception as e:
                print(f"❌ 模拟输入时出错: {e}")
        elif choice != "":
            print("❌ 无效选择")

    def delete_account(self):
        username = input("请输入要删除的用户名: ")
        self.cursor.execute("SELECT id FROM accounts WHERE username=?", (username,))
        row = self.cursor.fetchone()
        if row:
            confirm = input(f"⚠️ 警告: 确定要永久删除账号 '{username}' 吗? (y/n): ").lower()
            if confirm == 'y':
                self.cursor.execute("DELETE FROM accounts WHERE id=?", (row[0],))
                self.conn.commit()
                print(f"✅ 账号 '{username}' 已被移除")
        else:
            print("❌ 未找到该用户")

    def update_account(self):
        username = input("请输入要修改的用户名: ")
        self.cursor.execute("SELECT id, category, website, notes FROM accounts WHERE username=?", (username,))
        row = self.cursor.fetchone()
        if not row:
            print("❌ 未找到该用户")
            return
            
        acc_id, cat, web, note = row
        print(f"\n当前信息 - 分类: {cat}, 网站: {web}, 备注: {note}")
        
        new_cat = input(f"新分类 (直接回车保持不变): ") or cat
        new_web = input(f"新网站 (直接回车保持不变): ") or web
        new_note = input(f"新备注 (直接回车保持不变): ") or note
        
        if input("是否需要更改密码? (y/n): ").lower() == 'y':
            new_pwd = getpass("输入新密码: ")
            iv, ct = self._encrypt(new_pwd)
            self.cursor.execute("UPDATE accounts SET category=?, website=?, notes=?, password_encrypted=?, iv=? WHERE id=?",
                               (new_cat, new_web, new_note, ct, iv, acc_id))
        else:
            self.cursor.execute("UPDATE accounts SET category=?, website=?, notes=? WHERE id=?",
                               (new_cat, new_web, new_note, acc_id))
        self.conn.commit()
        print("✅ 信息已成功更新")

    def change_master_password(self):
        print("\n--- 修改主密码 (数据重加密) ---")
        p_current = getpass("请输入当前主密码: ")
        master_hash = self._get_config("master_hash")
        if not bcrypt.checkpw(p_current.encode('utf-8'), master_hash.encode('utf-8')):
            print("❌ 验证失败，无法修改主密码")
            return
            
        while True:
            p1 = getpass("设置新主密码 (至少8位): ")
            if len(p1) < 8:
                print("❌ 密码太短")
                continue
            p2 = getpass("请再次输入以确认: ")
            if p1 != p2:
                print("❌ 两次输入不一致")
                continue
            break
            
        # 重新加密所有账号数据
        self.cursor.execute("SELECT id, password_encrypted, iv FROM accounts")
        all_accounts = self.cursor.fetchall()
        
        new_master_key = SymmetricCrypto.derive_key(p1, self.encryption_salt)
        
        print("正在重新加密所有数据，请勿关闭程序...")
        try:
            for acc_id, ct, iv in all_accounts:
                old_pwd = self._decrypt(iv, ct)
                if old_pwd is None: continue
                
                # 临时替换密钥进行加密
                orig_key = self.master_key
                self.master_key = new_master_key
                new_iv, new_ct = self._encrypt(old_pwd)
                self.master_key = orig_key
                
                self.cursor.execute("UPDATE accounts SET password_encrypted=?, iv=? WHERE id=?", (new_ct, new_iv, acc_id))
            
            # 更新主密码哈希
            new_hashed = bcrypt.hashpw(p1.encode('utf-8'), bcrypt.gensalt())
            self._set_config("master_hash", new_hashed.decode('utf-8'))
            self.master_key = new_master_key
            self.conn.commit()
            print("✅ 主密码修改成功，所有本地数据已完成重加密")
        except Exception as e:
            self.conn.rollback()
            print(f"❌ 修改失败: {e}")
            logging.error(f"Master password change failed: {e}")

    def export_accounts(self):
        print("\n⚠️ 注意: 导出文件将包含明文密码，请在安全的环境下操作。")
        filename = input("请输入导出文件名 (默认 accounts_export.csv): ") or "accounts_export.csv"
        
        self.cursor.execute("SELECT username, category, website, notes, password_encrypted, iv FROM accounts")
        rows = self.cursor.fetchall()
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['用户名', '明文密码', '分类', '网站', '备注'])
                for r in rows:
                    pwd = self._decrypt(r[5], r[4])
                    writer.writerow([r[0], pwd, r[1], r[2], r[3]])
            print(f"✅ 成功导出到: {os.path.abspath(filename)}")
        except Exception as e:
            print(f"❌ 导出失败: {e}")

    def close(self):
        if self.conn:
            self.conn.close()

def display_menu():
    print("\n" + "="*50)
    print("🔐 账号密码管理器 (AccountManager V2.0)")
    print("="*50)
    print(" 1. 自动登录 (模拟键盘输入)")
    print(" 2. 查看/复制账号 (包含搜索)")
    print(" 3. 创建新账号 (支持随机强密码)")
    print(" 4. 修改账号信息")
    print(" 5. 删除已有账号")
    print(" 6. 修改主密码 (数据重加密)")
    print(" 7. 导出账号数据 (CSV)")
    print(" 8. 生成随机强密码")
    print(" 0. 退出程序")
    print("="*50)

def run(*args, **kwargs):
    """Butler 系统扩展调用入口"""
    manager = AccountManager()
    try:
        if not manager.authenticate():
            return

        while True:
            display_menu()
            choice = input("请选择操作 (0-8): ")
            
            if choice == '0':
                print("👋 已安全退出管理器")
                break
            elif choice == '1':
                manager.auto_login()
            elif choice == '2':
                search = input("输入关键词搜索 (直接回车查看全部): ")
                manager.view_accounts(search)
            elif choice == '3':
                manager.create_account()
            elif choice == '4':
                manager.update_account()
            elif choice == '5':
                manager.delete_account()
            elif choice == '6':
                manager.change_master_password()
            elif choice == '7':
                manager.export_accounts()
            elif choice == '8':
                length = input("密码长度 (默认16): ") or 16
                pwd = manager.generate_password(int(length) if str(length).isdigit() else 16)
                print(f"\n生成的随机强密码: {pwd}")
                pyperclip.copy(pwd)
                print("✅ 已复制到剪贴板")
            else:
                print("⚠️ 无效选择，请重新输入")
    except KeyboardInterrupt:
        print("\n👋 强制退出")
    finally:
        manager.close()

if __name__ == "__main__":
    run()
