# -*- coding: utf-8 -*-
"""
Vmail 临时邮箱助手
功能：
1. 快速创建 vmail.dev 临时邮箱
2. 自动提取验证码 (OTP) 并复制到剪贴板
3. 后台轮询监控新邮件并提醒
4. 管理临时邮箱历史记录
"""

import os
import json
import time
import re
import threading
import requests
try:
    import pyperclip
except ImportError:
    pyperclip = None
from package.log_manager import LogManager

# 初始化日志
logger = LogManager.get_logger(__name__)

# 全局变量以防止重复启动监控线程
_monitor_thread = None
_monitoring_active = False

class VMailAssistant:
    CONFIG_PATH = "config/vmail_config.json"
    API_BASE = "https://vmail.dev/api/v1"

    def __init__(self, jarvis_app=None):
        self.jarvis_app = jarvis_app
        self.config = self.load_config()
        self.api_key = self.config.get("api_key", "")
        self.active_mailbox = self.config.get("active_mailbox", {})
        self.history = self.config.get("history", [])
        self.last_message_id = None

    def load_config(self):
        """加载配置"""
        if os.path.exists(self.CONFIG_PATH):
            try:
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载配置失败: {e}")
        return {"api_key": "", "active_mailbox": {}, "history": []}

    def save_config(self):
        """保存配置"""
        os.makedirs(os.path.dirname(self.CONFIG_PATH), exist_ok=True)
        config_to_save = {
            "api_key": self.api_key,
            "active_mailbox": self.active_mailbox,
            "history": self.history
        }
        try:
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def set_api_key(self, key):
        self.api_key = key
        self.save_config()

    def get_headers(self):
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def create_mailbox(self):
        """创建新的临时邮箱"""
        if not self.api_key:
            return False, "请先设置 API Key"

        try:
            response = requests.post(f"{self.API_BASE}/mailboxes", headers=self.get_headers(), timeout=10)
            if response.status_code == 201 or response.status_code == 200:
                data = response.json().get("data", {})
                self.active_mailbox = data
                self.history.append(data)
                self.save_config()
                return True, data
            else:
                return False, f"创建失败: {response.text}"
        except Exception as e:
            return False, str(e)

    def list_messages(self, mailbox_id=None):
        """获取邮件列表"""
        mid = mailbox_id or self.active_mailbox.get("id")
        if not mid or not self.api_key:
            return []

        try:
            response = requests.get(f"{self.API_BASE}/mailboxes/{mid}/messages", headers=self.get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json().get("data", [])
            else:
                logger.error(f"获取邮件列表失败: {response.text}")
                return []
        except Exception as e:
            logger.error(f"请求异常: {e}")
            return []

    def get_message_detail(self, message_id, mailbox_id=None):
        """获取邮件详情"""
        mid = mailbox_id or self.active_mailbox.get("id")
        if not mid or not self.api_key:
            return None

        try:
            response = requests.get(f"{self.API_BASE}/mailboxes/{mid}/messages/{message_id}", headers=self.get_headers(), timeout=10)
            if response.status_code == 200:
                return response.json().get("data", {})
            else:
                return None
        except Exception as e:
            logger.error(f"获取详情异常: {e}")
            return None

    def extract_otp(self, text):
        """从文本中提取验证码 (4-6位数字)"""
        if not text:
            return None
        # 寻找 4-6 位连续数字，通常周围有边界
        match = re.search(r'\b(\d{4,6})\b', text)
        return match.group(1) if match else None

    def start_monitoring(self):
        """开始后台监控"""
        global _monitor_thread, _monitoring_active
        if _monitoring_active:
            logger.info("监控已在运行中。")
            return

        _monitoring_active = True
        _monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        _monitor_thread.start()
        logger.info("Vmail 监控线程已启动。")

    def stop_monitoring(self):
        global _monitoring_active
        _monitoring_active = False

    def _monitor_loop(self):
        global _monitoring_active
        logger.info("进入 Vmail 监控循环...")
        while _monitoring_active:
            if not self.active_mailbox:
                time.sleep(10)
                continue

            messages = self.list_messages()
            if messages:
                latest = messages[0]
                if latest.get("id") != self.last_message_id:
                    self.last_message_id = latest.get("id")
                    self._handle_new_message(latest)

            time.sleep(15) # 每15秒轮询一次

    def _handle_new_message(self, msg_summary):
        """处理新邮件"""
        subject = msg_summary.get("subject", "无主题")
        sender = msg_summary.get("from", "未知发件人")

        # 提取验证码
        otp = self.extract_otp(subject)
        detail = None

        if not otp:
            # 如果主题没找到，查详情
            detail = self.get_message_detail(msg_summary.get("id"))
            if detail:
                otp = self.extract_otp(detail.get("text", "") or detail.get("html", ""))

        msg_text = f"收到新邮件来自 {sender}: {subject}"
        if otp:
            if pyperclip:
                msg_text += f"\n提取到验证码: {otp} (已复制到剪贴板)"
                try:
                    pyperclip.copy(otp)
                except Exception as e:
                    logger.error(f"复制到剪贴板失败: {e}")
            else:
                msg_text += f"\n提取到验证码: {otp}"

        if self.jarvis_app:
            self.jarvis_app.speak("收到新的临时邮件通知")
            self.jarvis_app.ui_print(msg_text)
        else:
            print(f"\n🔔 [Vmail] {msg_text}")

    def wait_for_otp(self, timeout=60, poll_interval=5):
        """等待并获取最新的验证码"""
        if not self.active_mailbox:
            return None, "未激活邮箱"

        # 记录当前的最新消息 ID
        initial_messages = self.list_messages()
        last_id = initial_messages[0].get("id") if initial_messages else None

        start_time = time.time()
        logger.info(f"开始等待验证码，超时时间: {timeout}s")

        while time.time() - start_time < timeout:
            msgs = self.list_messages()
            if msgs:
                latest = msgs[0]
                if latest.get("id") != last_id:
                    # 发现新邮件
                    subject = latest.get("subject", "")
                    otp = self.extract_otp(subject)
                    if not otp:
                        detail = self.get_message_detail(latest.get("id"))
                        if detail:
                            otp = self.extract_otp(detail.get("text", "") or detail.get("html", ""))

                    if otp:
                        if pyperclip:
                            try:
                                pyperclip.copy(otp)
                            except:
                                pass
                        return otp, None
                    else:
                        # 虽然有新邮件但没找到验证码，继续更新 last_id 以便检测下一封
                        last_id = latest.get("id")

            time.sleep(poll_interval)

        return None, "等待超时"

def run(*args, **kwargs):
    """扩展运行入口"""
    assistant = VMailAssistant()

    # 如果通过 Jarvis 调用
    jarvis_app = kwargs.get("jarvis_app")
    if jarvis_app:
        assistant.jarvis_app = jarvis_app

    # 简单的交互逻辑
    if not assistant.api_key:
        print("\n" + "="*50)
        print("首次使用 Vmail，请设置 API Key")
        print("您可以从 https://vmail.dev 获取")
        print("="*50)
        key = input("API Key: ").strip()
        if key:
            assistant.set_api_key(key)
        else:
            print("⚠️ 未设置 API Key，功能受限")
            return

    while True:
        print("\n" + "="*50)
        print("📧 Vmail 临时邮箱助手")
        print("="*50)
        if assistant.active_mailbox:
            print(f"当前激活: {assistant.active_mailbox.get('address')}")
        else:
            print("当前无激活邮箱")
        print("-" * 50)
        print("1. 创建新临时邮箱")
        print("2. 查看当前收件箱")
        print("3. 开启后台自动监控")
        print("4. 查看历史邮箱")
        print("5. 等待收验证码 (60s)")
        print("6. 设置 API Key")
        print("0. 返回主菜单")
        print("="*50)

        choice = input("请选择操作 (0-6): ").strip()

        if choice == '1':
            success, res = assistant.create_mailbox()
            if success:
                print(f"✅ 创建成功: {res.get('address')}")
            else:
                print(f"❌ {res}")

        elif choice == '2':
            msgs = assistant.list_messages()
            if not msgs:
                print("📭 收件箱为空")
            else:
                print("\n📬 邮件列表:")
                for i, m in enumerate(msgs):
                    print(f"[{i+1}] {m.get('from')} - {m.get('subject')}")

                msg_idx = input("\n输入编号查看详情 (或按回车返回): ")
                if msg_idx.isdigit() and 0 < int(msg_idx) <= len(msgs):
                    m_id = msgs[int(msg_idx)-1].get("id")
                    detail = assistant.get_message_detail(m_id)
                    if detail:
                        print("-" * 50)
                        print(f"发件人: {detail.get('from')}")
                        print(f"主题: {detail.get('subject')}")
                        print(f"正文: {detail.get('text')}")
                        otp = assistant.extract_otp(detail.get('text', "") or "")
                        if otp:
                            print(f"\n✨ 识别到验证码: {otp}")
                            if pyperclip:
                                try:
                                    pyperclip.copy(otp)
                                    print("已自动复制到剪贴板")
                                except:
                                    pass
                        print("-" * 50)
                    else:
                        print("❌ 获取详情失败")

        elif choice == '3':
            from package.vmail_tool import _monitoring_active
            if not _monitoring_active:
                assistant.start_monitoring()
                print("✅ 已开启后台监控，收到新邮件时将自动提醒并提取验证码。")
            else:
                print("ℹ️ 监控已在运行中")

        elif choice == '4':
            if not assistant.history:
                print("📜 暂无历史记录")
            else:
                for i, h in enumerate(assistant.history):
                    print(f"{i+1}. {h.get('address')} ({h.get('id')})")

        elif choice == '5':
            print("⏳ 正在等待新邮件中的验证码...")
            otp, err = assistant.wait_for_otp(timeout=60)
            if otp:
                print(f"✨ 成功获取验证码: {otp}")
            else:
                print(f"❌ {err}")

        elif choice == '6':
            key = input("新 API Key: ").strip()
            if key:
                assistant.set_api_key(key)
                print("✅ 已更新 API Key")

        elif choice == '0':
            break

if __name__ == "__main__":
    run()
