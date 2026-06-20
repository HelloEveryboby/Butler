# -*- coding: utf-8 -*-
"""
邮箱助手 - 轻松管理多个邮箱账户
功能：
1. 支持多个邮箱账户管理
2. 发送邮件（支持中文主题和内容）
3. 接收未读邮件
4. 保存邮件附件
5. 拉黑发件人（标记不想看到的发件人）
"""

import os
import json
import imaplib
import email
import time
import datetime
import re
from dateutil import parser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header, decode_header
import smtplib
from email.utils import formataddr

class EmailAssistant:
    
    def __init__(self):
        """初始化邮箱助手"""
        self.load_config()
        self.current_account_index = 0
        self.update_account_info()
        self.blacklist = self.load_blacklist()  # 加载黑名单
        print(f"✨ 邮箱助手已启动，当前账户: {self.email}")
        print(f"已加载 {len(self.blacklist)} 个黑名单发件人")
        
    def load_config(self):
        """加载邮箱配置文件"""
        try:
            with open("email_config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
            print("✅ 邮箱配置加载成功")
        except FileNotFoundError:
            print("⚠️ 未找到配置文件 email_config.json，请创建配置文件")
            self.create_default_config()
        except json.JSONDecodeError:
            print("⚠️ 配置文件格式错误，请检查JSON格式")
            exit(1)
            
    def create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            "accounts": [
                {
                    "name": "我的QQ邮箱",
                    "email": "your_email@qq.com",
                    "password": "your_password",
                    "imap_server": "imap.qq.com",
                    "imap_port": 993,
                    "smtp_server": "smtp.qq.com",
                    "smtp_port": 465,
                    "smtp_ssl": True
                },
                {
                    "name": "我的163邮箱",
                    "email": "your_email@163.com",
                    "password": "your_password",
                    "imap_server": "imap.163.com",
                    "imap_port": 993,
                    "smtp_server": "smtp.163.com",
                    "smtp_port": 465,
                    "smtp_ssl": True
                }
            ]
        }
        
        with open("email_config.json", "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=4)
        print("📝 已创建默认配置文件 email_config.json，请修改为您的账户信息")
        exit(0)
        
    def load_blacklist(self):
        """加载黑名单"""
        try:
            if os.path.exists("blacklist.json"):
                with open("blacklist.json", "r", encoding="utf-8") as f:
                    return json.load(f).get(self.email, [])
        except:
            pass
        return []
        
    def save_blacklist(self):
        """保存黑名单"""
        try:
            all_blacklists = {}
            if os.path.exists("blacklist.json"):
                with open("blacklist.json", "r", encoding="utf-8") as f:
                    all_blacklists = json.load(f)
            
            all_blacklists[self.email] = self.blacklist
            
            with open("blacklist.json", "w", encoding="utf-8") as f:
                json.dump(all_blacklists, f, ensure_ascii=False, indent=4)
            print(f"✅ 黑名单已保存 ({len(self.blacklist)} 个发件人)")
        except Exception as e:
            print(f"❌ 保存黑名单失败: {str(e)}")
            
    def update_account_info(self):
        """更新当前账户信息"""
        account = self.config["accounts"][self.current_account_index]
        self.account_name = account.get("name", "未命名账户")
        self.email = account["email"]
        self.password = account["password"]
        self.imap_server = account["imap_server"]
        self.imap_port = account["imap_port"]
        self.smtp_server = account["smtp_server"]
        self.smtp_port = account["smtp_port"]
        self.smtp_ssl = account.get("smtp_ssl", True)
        self.blacklist = self.load_blacklist()  # 切换账户时重新加载黑名单
         
    def list_accounts(self):
        """列出所有可用账户"""
        print("\n📋 可用邮箱账户:")
        for i, account in enumerate(self.config["accounts"]):
            prefix = "→ " if i == self.current_account_index else "  "
            print(f"{prefix}[{i}] {account.get('name', '未命名账户')} - {account['email']}")
    
    def switch_account(self):
        """切换邮箱账户"""
        self.list_accounts()
        try:
            index = int(input("\n请输入要切换的账户编号: "))
            if 0 <= index < len(self.config["accounts"]):
                self.current_account_index = index
                self.update_account_info()
                print(f"\n✅ 已切换到账户: {self.account_name} ({self.email})")
                print(f"当前黑名单: {len(self.blacklist)} 个发件人")
            else:
                print("⚠️ 无效的账户编号")
        except ValueError:
            print("⚠️ 请输入有效的数字")
    
    def decode_header(self, header):
        """解码邮件头信息"""
        if header is None:
            return ""
            
        try:
            decoded = decode_header(header)
            result = []
            for part, encoding in decoded:
                if isinstance(part, bytes):
                    if encoding:
                        result.append(part.decode(encoding))
                    else:
                        # 尝试常用编码
                        try:
                            result.append(part.decode('utf-8'))
                        except:
                            try:
                                result.append(part.decode('gbk'))
                            except:
                                result.append(part.decode('iso-8859-1', 'ignore'))
                else:
                    result.append(part)
            return ''.join(result)
        except Exception as e:
            print(f"⚠️ 解码邮件头出错: {e}")
            return str(header)

    def get_sender(self, msg):
        """获取发件人信息"""
        from_header = msg.get("From")
        return self.decode_header(from_header) if from_header else "未知发件人"
    
    def extract_email_address(self, sender):
        """从发件人信息中提取邮箱地址"""
        # 匹配 <email@domain.com> 格式
        match = re.search(r'<([^>]+)>', sender)
        if match:
            return match.group(1).lower()
        
        # 匹配纯邮箱地址
        if re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', sender):
            return sender.lower()
        
        # 无法提取，返回原始信息
        return sender

    def get_subject(self, msg):
        """获取邮件主题"""
        subject_header = msg.get("Subject", "无主题")
        return self.decode_header(subject_header)

    def get_date(self, email_msg):
        """获取邮件日期"""
        try:
            return parser.parse(email_msg.get("date"))
        except:
            return datetime.datetime.now()

    def save_attachments(self, msg, download_folder="attachments"):
        """保存邮件附件"""
        if not os.path.exists(download_folder):
            os.makedirs(download_folder)
            
        attachment_count = 0
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue    
            if part.get('Content-Disposition') is None:
                continue   
                
            filename = part.get_filename()
            if bool(filename):
                filename = self.decode_header(filename)
                filepath = os.path.join(download_folder, filename)
                with open(filepath, 'wb') as f:
                    f.write(part.get_payload(decode=True))
                print(f"📎 附件已保存: {filepath}")
                attachment_count += 1
                
        return attachment_count

    def fetch_unread_emails(self, mark_read=False, limit=5):
        """获取未读邮件"""
        print(f"\n📥 正在检查 {self.email} 的未读邮件...")
        msgs = []
        try:
            # 使用SSL连接
            if self.imap_port == 993:
                conn = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            else:
                conn = imaplib.IMAP4(self.imap_server, self.imap_port)
                
            conn.login(self.email, self.password)
            conn.select('INBOX', readonly=(not mark_read))
            
            # 搜索未读邮件
            status, messages = conn.search(None, '(UNSEEN)')
            if status != 'OK' or not messages[0]:
                print("🎉 没有未读邮件")
                return []
                
            email_ids = messages[0].split()
            total_emails = len(email_ids)
            if limit:
                email_ids = email_ids[:limit]
                
            print(f"发现 {total_emails} 封未读邮件，正在加载前 {len(email_ids)} 封...")
            
            # 获取邮件
            for i, num in enumerate(email_ids):
                print(f"正在加载邮件 {i+1}/{len(email_ids)}...")
                status, data = conn.fetch(num, '(RFC822)')
                if status == 'OK' and data and data[0]:
                    msg = email.message_from_bytes(data[0][1])
                    
                    # 检查发件人是否在黑名单中
                    sender = self.get_sender(msg)
                    email_address = self.extract_email_address(sender)
                    
                    if email_address in self.blacklist:
                        print(f"⛔ 已跳过黑名单发件人: {email_address}")
                        continue
                        
                    msgs.append(msg)
            
            print(f"✅ 成功加载 {len(msgs)} 封未读邮件 (已过滤 {total_emails - len(msgs)} 封黑名单邮件)")
            return msgs
        except Exception as e:
            print(f"❌ 邮件获取失败: {str(e)}")
            return []
        finally:
            try:
                conn.close()
                conn.logout()
            except:
                pass

    def display_emails(self, emails):
        """显示邮件列表"""
        if not emails:
            print("没有邮件可显示")
            return
            
        print("\n📬 邮件列表:")
        for i, msg in enumerate(emails):
            print(f"\n【{i+1}】")
            sender = self.get_sender(msg)
            email_address = self.extract_email_address(sender)
            
            # 标记黑名单发件人
            blacklist_marker = "⛔" if email_address in self.blacklist else "👤"
            print(f"{blacklist_marker} 发件人: {sender}")
            print(f"📧 邮箱地址: {email_address}")
            print(f"📝 主题: {self.get_subject(msg)}")
            print(f"📅 日期: {self.get_date(msg).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 显示邮件内容
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True)
                    try:
                        # 尝试UTF-8解码
                        body_text = body.decode('utf-8')
                    except:
                        try:
                            # 尝试GBK解码
                            body_text = body.decode('gbk')
                        except:
                            # 尝试ISO-8859-1解码
                            body_text = body.decode('iso-8859-1', 'ignore')
                    
                    # 显示前200个字符
                    preview = body_text[:200].replace('\n', ' ').replace('\r', '')
                    if len(body_text) > 200:
                        preview += "..."
                    print(f"📄 内容: {preview}")
                    break

    def send_email(self, subject, message, receiver):
        """发送邮件"""
        print(f"\n✉️ 准备发送邮件到: {receiver}")
        print(f"主题: {subject}")
        print(f"内容预览: {message[:100]}{'...' if len(message) > 100 else ''}")
        
        # 确认发送
        confirm = input("\n确认发送邮件? (y/n): ").lower()
        if confirm != 'y':
            print("❌ 邮件发送已取消")
            return False
        
        # 创建邮件
        msg = MIMEMultipart()
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = formataddr((self.email, self.email))
        msg['To'] = receiver
        msg.attach(MIMEText(message, "plain", "utf-8"))            

        try:
            # 根据配置选择SSL或普通连接
            if self.smtp_ssl:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()  # 启动TLS加密
                
            server.login(self.email, self.password)
            server.sendmail(self.email, [receiver], msg.as_string())
            print(f"✅ 邮件发送成功至: {receiver}")
            return True
        except smtplib.SMTPAuthenticationError:
            print("❌ 认证失败：用户名或密码不正确")
        except smtplib.SMTPRecipientsRefused:
            print("❌ 收件人地址被拒绝：请检查收件人邮箱是否正确")
        except smtplib.SMTPSenderRefused:
            print("❌ 发件人地址被拒绝：请检查发件人邮箱配置")
        except smtplib.SMTPDataError as e:
            print(f"❌ 邮件内容被拒绝: {e}")
        except Exception as e:
            print(f"❌ 邮件发送失败: {str(e)}")
        finally:
            try:
                server.quit()
            except:
                pass
        
        return False

    def manage_blacklist(self):
        """管理黑名单"""
        while True:
            print("\n" + "=" * 50)
            print("🚫 黑名单管理")
            print("=" * 50)
            print(f"当前账户: {self.email}")
            print(f"黑名单数量: {len(self.blacklist)}")
            print("=" * 50)
            print("1. 添加发件人到黑名单")
            print("2. 从黑名单中移除发件人")
            print("3. 查看当前黑名单")
            print("4. 清空黑名单")
            print("5. 返回主菜单")
            print("=" * 50)
            
            try:
                choice = input("请选择操作 (1-5): ")
                
                if choice == '1':
                    email_address = input("\n请输入要添加到黑名单的邮箱地址: ").strip().lower()
                    if email_address and '@' in email_address:
                        if email_address not in self.blacklist:
                            self.blacklist.append(email_address)
                            self.save_blacklist()
                            print(f"✅ 已添加 {email_address} 到黑名单")
                        else:
                            print(f"⚠️ {email_address} 已在黑名单中")
                    else:
                        print("⚠️ 请输入有效的邮箱地址")
                        
                elif choice == '2':
                    if not self.blacklist:
                        print("⚠️ 黑名单为空")
                        continue
                        
                    print("\n当前黑名单:")
                    for i, addr in enumerate(self.blacklist):
                        print(f"{i+1}. {addr}")
                    
                    try:
                        index = int(input("\n请输入要移除的邮箱编号: ")) - 1
                        if 0 <= index < len(self.blacklist):
                            removed = self.blacklist.pop(index)
                            self.save_blacklist()
                            print(f"✅ 已从黑名单中移除: {removed}")
                        else:
                            print("⚠️ 无效的编号")
                    except ValueError:
                        print("⚠️ 请输入有效的数字")
                        
                elif choice == '3':
                    if not self.blacklist:
                        print("✅ 黑名单为空")
                    else:
                        print("\n当前黑名单:")
                        for i, addr in enumerate(self.blacklist):
                            print(f"{i+1}. {addr}")
                            
                elif choice == '4':
                    if self.blacklist:
                        confirm = input("\n确定要清空黑名单吗? (y/n): ").lower()
                        if confirm == 'y':
                            self.blacklist = []
                            self.save_blacklist()
                            print("✅ 黑名单已清空")
                    else:
                        print("⚠️ 黑名单已为空")
                        
                elif choice == '5':
                    break
                    
                else:
                    print("⚠️ 请选择有效的选项 (1-5)")
                    
            except KeyboardInterrupt:
                print("\n返回黑名单管理菜单")
                continue

def main_menu():
    """主菜单"""
    print("\n" + "=" * 50)
    print("📧 邮箱助手主菜单")
    print("=" * 50)
    print("1. 发送邮件")
    print("2. 查看未读邮件")
    print("3. 切换邮箱账户")
    print("4. 黑名单管理")
    print("5. 退出程序")
    print("=" * 50)
    
    try:
        choice = input("请选择操作 (1-5): ")
        return choice
    except KeyboardInterrupt:
        print("\n👋 感谢使用，再见！")
        exit(0)

def send_email_flow(assistant):
    """发送邮件流程"""
    print("\n📝 撰写新邮件")
    
    # 获取收件人
    receiver = input("收件人邮箱: ").strip()
    if not receiver:
        print("⚠️ 收件人不能为空")
        return
        
    # 获取邮件主题
    subject = input("邮件主题: ").strip()
    if not subject:
        print("⚠️ 邮件主题不能为空")
        return
        
    # 获取邮件内容
    print("\n请输入邮件内容 (输入'END'单独一行结束):")
    lines = []
    while True:
        try:
            line = input()
            if line == 'END':
                break
            lines.append(line)
        except EOFError:
            break
    message = "\n".join(lines)
    
    if not message:
        print("⚠️ 邮件内容不能为空")
        return
        
    # 发送邮件
    assistant.send_email(subject, message, receiver)

def view_unread_emails(assistant):
    """查看未读邮件流程"""
    emails = assistant.fetch_unread_emails()
    if not emails:
        return
        
    assistant.display_emails(emails)
    
    # 邮件操作选项
    while True:
        print("\n邮件操作:")
        print("1. 查看完整邮件内容")
        print("2. 保存附件")
        print("3. 将发件人加入黑名单")
        print("4. 返回主菜单")
        
        try:
            choice = input("请选择操作 (1-4): ")
            if choice == '1':
                try:
                    index = int(input("请输入邮件编号: ")) - 1
                    if 0 <= index < len(emails):
                        print("\n完整邮件内容:")
                        print("-" * 50)
                        for part in emails[index].walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True)
                                try:
                                    print(body.decode('utf-8'))
                                except:
                                    try:
                                        print(body.decode('gbk'))
                                    except:
                                        print(body.decode('iso-8859-1', 'ignore'))
                        print("-" * 50)
                    else:
                        print("⚠️ 无效的邮件编号")
                except ValueError:
                    print("⚠️ 请输入有效的数字")
            elif choice == '2':
                try:
                    index = int(input("请输入邮件编号: ")) - 1
                    if 0 <= index < len(emails):
                        count = assistant.save_attachments(emails[index])
                        print(f"✅ 保存了 {count} 个附件")
                    else:
                        print("⚠️ 无效的邮件编号")
                except ValueError:
                    print("⚠️ 请输入有效的数字")
            elif choice == '3':
                try:
                    index = int(input("请输入邮件编号: ")) - 1
                    if 0 <= index < len(emails):
                        sender = assistant.get_sender(emails[index])
                        email_address = assistant.extract_email_address(sender)
                        
                        print(f"\n确定将以下发件人加入黑名单吗?")
                        print(f"发件人: {sender}")
                        print(f"邮箱地址: {email_address}")
                        
                        confirm = input("\n确认加入黑名单? (y/n): ").lower()
                        if confirm == 'y':
                            if email_address not in assistant.blacklist:
                                assistant.blacklist.append(email_address)
                                assistant.save_blacklist()
                                print(f"✅ 已添加 {email_address} 到黑名单")
                            else:
                                print(f"⚠️ {email_address} 已在黑名单中")
                    else:
                        print("⚠️ 无效的邮件编号")
                except ValueError:
                    print("⚠️ 请输入有效的数字")
            elif choice == '4':
                break
            else:
                print("⚠️ 请选择有效的选项 (1-4)")
        except KeyboardInterrupt:
            print("\n返回邮件操作菜单")
            continue

def main():
    """主程序"""
    print("\n" + "=" * 50)
    print("📧 欢迎使用邮箱助手")
    print("=" * 50)
    print("提示: 首次使用请编辑 email_config.json 配置您的邮箱账户")
    print("=" * 50)
    
    try:
        assistant = EmailAssistant()
        
        while True:
            choice = main_menu()
            
            if choice == '1':
                send_email_flow(assistant)
            elif choice == '2':
                view_unread_emails(assistant)
            elif choice == '3':
                assistant.switch_account()
            elif choice == '4':
                assistant.manage_blacklist()
            elif choice == '5':
                print("\n👋 感谢使用邮箱助手，再见！")
                break
            else:
                print("⚠️ 请选择有效的选项 (1-5)")
                
    except KeyboardInterrupt:
        print("\n👋 感谢使用，再见！")
    except Exception as e:
        print(f"\n❌ 程序发生错误: {str(e)}")

if __name__ == '__main__':
    main()
