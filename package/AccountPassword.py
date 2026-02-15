"""
账号密码管理器。支持自动登录、账号创建、密码修改、数据导出及强密码生成等功能。
"""
import sqlite3
import pyautogui
import time
import sys
import os
import re
from getpass import getpass
import bcrypt
from package.log_manager import LogManager
import pyperclip  # 新增剪贴板功能

logging = LogManager.get_logger(__name__)

# 初始化数据库连接
conn = sqlite3.connect('account_manager.db', check_same_thread=False)
cursor = conn.cursor()

# 创建用户表结构，添加 website 字段
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    category TEXT NOT NULL,
                    website TEXT NOT NULL,
                    notes TEXT DEFAULT ''
                 )''')
conn.commit()

# 自动登录功能
def auto_login():
    cursor.execute("SELECT id, username, category, website FROM users")
    accounts = cursor.fetchall()

    if accounts:
        print("\n" + "="*50)
        print("可用账号列表:")
        print("-"*50)
        for i, account in enumerate(accounts):
            print(f"{i+1}. {account[1]} [{account[2]}] - {account[3]}")
        print("="*50 + "\n")

        choice = input("请输入要自动登录的账号编号 (0返回主菜单): ")

        if choice.strip() == "" or choice == "0":
            return False  # 用户跳过自动登录

        try:
            account_id = accounts[int(choice) - 1][0]  # 获取选择的账号ID
        except (ValueError, IndexError):
            print("⚠️ 无效的选择，请重试。")
            return False  # 无效选择后跳过自动登录

        cursor.execute("SELECT username, password, website FROM users WHERE id = ?", (account_id,))
        user = cursor.fetchone()

        if user:
            username, hashed_password, website = user
            
            # 显示登录提示
            print(f"\n即将登录: {username} @ {website}")
            print("请确保:")
            print("1. 浏览器窗口已打开并位于前台")
            print("2. 焦点在登录页面的用户名输入框")
            print("3. 等待5秒后开始自动输入...")
            time.sleep(5)
            
            password = getpass(f"请输入密码以自动登录 (或按Enter跳过): ")
            
            if not password:
                print("已跳过自动登录")
                return False

            # 验证密码
            if bcrypt.checkpw(password.encode('utf-8'), hashed_password):
                print(f"\n🚀 自动登录 {username} 到 {website}...")
                
                # 记录日志
                logging.info(f"用户 {username} 登录了网站 {website}")
                
                # 更可靠的输入方式
                pyautogui.write(username, interval=0.05)
                pyautogui.press('tab')
                pyautogui.write(password, interval=0.05)
                pyautogui.press('enter')
                
                print("\n✅ 登录操作已完成，程序将在5秒后退出...")
                time.sleep(5)
                sys.exit()  # 登录完成后退出程序
            else:
                print("🔒 密码错误，无法自动登录。")
                return False  # 密码错误后跳过自动登录
        else:
            print("❌ 无法找到指定用户。")
            return False  # 用户未找到后跳过自动登录
    else:
        print("ℹ️ 没有找到任何账号，无法自动登录。")
        return False  # 没有账号时跳过自动登录

# 创建新账号
def create_account():
    logging.info("Attempting to create a new account")
    print("\n" + "="*50)
    print("创建新账号")
    print("="*50)
    
    while True:
        username = input("请输入用户名 (至少3个字符): ")
        
        if len(username) < 3:
            print("❌ 用户名长度必须大于3个字符")
            continue
            
        # 检查用户名是否已存在
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            print("❌ 用户名已存在，请选择其他用户名")
            continue
            
        break
    
    while True:
        password = getpass("请输入密码 (至少8个字符): ")
        
        if len(password) < 8:
            print("❌ 密码长度必须至少8个字符")
            continue
            
        confirm_password = getpass("请再次输入密码: ")
        
        if password != confirm_password:
            print("❌ 两次输入的密码不一致")
            continue
            
        break
    
    # 对密码进行加密
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    category = input("请输入账号分类 (如: 社交媒体/工作/娱乐): ")
    
    while True:
        website = input("请输入网站地址 (如 https://example.com): ")
        # 简单的URL验证
        if not re.match(r'https?://.+', website):
            print("⚠️ 网址格式可能不正确，建议以http://或https://开头")
            choice = input("是否继续? (y/n): ").lower()
            if choice != 'y':
                continue
        break
    
    notes = input("请输入备注信息 (可选): ")

    try:
        cursor.execute("INSERT INTO users (username, password, category, website, notes) VALUES (?, ?, ?, ?, ?)", 
                       (username, hashed_password, category, website, notes))
        conn.commit()
        print("\n✅ 账号创建成功!")
        print(f"用户名: {username}")
        print(f"分类: {category}")
        print(f"网站: {website}")
    except sqlite3.IntegrityError:
        print("❌ 创建账号时发生错误")

# 修改密码
def change_password():
    logging.info("Attempting to change a password")
    print("\n" + "="*50)
    print("修改密码")
    print("="*50)
    
    username = input("请输入用户名: ")
    cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()

    if user:
        user_id, hashed_password = user
        
        # 验证当前密码
        current_password = getpass("请输入当前密码: ")
        if not bcrypt.checkpw(current_password.encode('utf-8'), hashed_password):
            print("❌ 当前密码错误")
            return
            
        while True:
            new_password = getpass("请输入新密码 (至少8个字符): ")
            if len(new_password) < 8:
                print("❌ 密码长度必须至少8个字符")
                continue
                
            confirm_password = getpass("请再次输入新密码: ")
            if new_password != confirm_password:
                print("❌ 两次输入的密码不一致")
                continue
                
            break
            
        new_hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_hashed_password, user_id))
        conn.commit()
        print(f"\n✅ {username} 的密码修改成功!")
    else:
        print("❌ 未找到指定用户名")

# 修改账号信息
def update_account():
    logging.info("Attempting to update an account")
    print("\n" + "="*50)
    print("修改账号信息")
    print("="*50)
    
    username = input("请输入要修改的用户名: ")
    cursor.execute("SELECT id, category, website, notes FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()

    if user:
        user_id, current_category, current_website, current_notes = user
        
        print(f"\n当前信息:")
        print(f"1. 分类: {current_category}")
        print(f"2. 网站: {current_website}")
        print(f"3. 备注: {current_notes}")
        print(f"4. 返回")
        
        while True:
            choice = input("\n请选择要修改的项目 (1-4): ")
            
            if choice == '1':
                new_category = input("请输入新的账号分类: ")
                cursor.execute("UPDATE users SET category = ? WHERE id = ?", (new_category, user_id))
                conn.commit()
                print("✅ 分类修改成功!")
                
            elif choice == '2':
                new_website = input("请输入新的网站地址: ")
                cursor.execute("UPDATE users SET website = ? WHERE id = ?", (new_website, user_id))
                conn.commit()
                print("✅ 网站地址修改成功!")
                
            elif choice == '3':
                new_notes = input("请输入新的备注: ")
                cursor.execute("UPDATE users SET notes = ? WHERE id = ?", (new_notes, user_id))
                conn.commit()
                print("✅ 备注修改成功!")
                
            elif choice == '4':
                break
                
            else:
                print("❌ 无效选择")
    else:
        print("❌ 未找到指定用户名")

# 复制密码到剪贴板
def copy_password():
    logging.info("Attempting to copy a password")
    print("\n" + "="*50)
    print("复制密码")
    print("="*50)
    
    username = input("请输入用户名: ")
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    
    if result:
        hashed_password = result[0]
        password = getpass("请输入密码以验证: ")
        
        if bcrypt.checkpw(password.encode('utf-8'), hashed_password):
            # 解密并复制到剪贴板
            pyperclip.copy(password)
            print("\n✅ 密码已复制到剪贴板，10秒后自动清除...")
            
            # 10秒后清除剪贴板
            time.sleep(10)
            pyperclip.copy('')
            print("剪贴板已清除")
        else:
            print("❌ 密码错误")
    else:
        print("❌ 未找到指定用户名")

# 删除指定的账号
def delete_account():
    logging.info("Attempting to delete an account")
    print("\n" + "="*50)
    print("删除账号")
    print("="*50)
    
    username = input("请输入要删除的用户名: ")
    cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()

    if user:
        user_id, hashed_password = user
        password = getpass("请输入密码以确认删除: ")

        if bcrypt.checkpw(password.encode('utf-8'), hashed_password):
            confirm = input(f"⚠️ 确定要永久删除 {username} 吗? (y/n): ").lower()
            if confirm == 'y':
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                print(f"✅ 账号 {username} 已成功删除。")
        else:
            print("❌ 密码错误")
    else:
        print("❌ 未找到指定用户名")

# 查看账号
def view_accounts():
    logging.info("Viewing accounts")
    print("\n" + "="*50)
    print("查看账号")
    print("="*50)
    print("1. 查看所有账号")
    print("2. 按分类查看")
    print("3. 搜索账号")
    print("4. 返回")
    
    choice = input("请选择查看方式: ")
    
    if choice == '1':
        cursor.execute("SELECT id, username, category, website FROM users")
        accounts = cursor.fetchall()
        
        if accounts:
            print("\n" + "-"*70)
            print(f"{'ID':<5}{'用户名':<20}{'分类':<15}{'网站':<30}")
            print("-"*70)
            for account in accounts:
                print(f"{account[0]:<5}{account[1]:<20}{account[2]:<15}{account[3]:<30}")
            print("-"*70 + "\n")
        else:
            print("ℹ️ 没有找到任何账号")
            
    elif choice == '2':
        category = input("请输入要查看的分类: ")
        cursor.execute("SELECT username, website FROM users WHERE category = ?", (category,))
        accounts = cursor.fetchall()
        
        if accounts:
            print(f"\n分类 '{category}' 下的账号:")
            print("-"*50)
            for account in accounts:
                print(f"用户名: {account[0]}")
                print(f"网站: {account[1]}")
                print("-"*50)
        else:
            print(f"ℹ️ 分类 '{category}' 下没有找到账号")
            
    elif choice == '3':
        search_term = input("请输入搜索关键词: ")
        cursor.execute("SELECT username, category, website FROM users WHERE username LIKE ? OR website LIKE ? OR category LIKE ?", 
                      (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        accounts = cursor.fetchall()
        
        if accounts:
            print("\n搜索结果:")
            print("-"*50)
            for account in accounts:
                print(f"用户名: {account[0]}")
                print(f"分类: {account[1]}")
                print(f"网站: {account[2]}")
                print("-"*50)
        else:
            print("ℹ️ 没有找到匹配的账号")

# 导出账号数据
def export_accounts():
    logging.info("Exporting accounts")
    print("\n" + "="*50)
    print("导出账号数据")
    print("="*50)
    
    filename = input("请输入导出文件名 (默认为 accounts_export.csv): ") or "accounts_export.csv"
    
    try:
        cursor.execute("SELECT username, category, website, notes FROM users")
        accounts = cursor.fetchall()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("用户名,分类,网站,备注\n")
            for account in accounts:
                f.write(f"{account[0]},{account[1]},{account[2]},{account[3]}\n")
        
        print(f"✅ 账号数据已导出到 {filename}")
        print(f"文件路径: {os.path.abspath(filename)}")
    except Exception as e:
        print(f"❌ 导出失败: {str(e)}")

# 生成强密码
def generate_password():
    logging.info("Generating a new password")
    print("\n" + "="*50)
    print("生成强密码")
    print("="*50)
    
    import random
    import string
    
    length = input("请输入密码长度 (默认12): ") or 12
    try:
        length = int(length)
        if length < 8:
            length = 8
    except:
        length = 12
        
    chars = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(chars) for _ in range(length))
    
    print(f"\n生成的密码: {password}")
    pyperclip.copy(password)
    print("✅ 密码已复制到剪贴板")

# 处理用户选择
def process_choice(choice):
    choice = choice.lower()
    
    if choice in ['登录', 'login']:
        auto_login()
    elif choice in ['创建', 'create', 'new']:
        create_account()
    elif choice in ['修改密码', 'changepass']:
        change_password()
    elif choice in ['修改', 'update', 'edit']:
        update_account()
    elif choice in ['复制密码', 'copy']:
        copy_password()
    elif choice in ['删除', 'delete', 'remove']:
        delete_account()
    elif choice in ['查看', 'view', 'list']:
        view_accounts()
    elif choice in ['导出', 'export']:
        export_accounts()
    elif choice in ['生成密码', 'generate']:
        generate_password()
    elif choice in ['退出', 'exit', 'quit']:
        print("👋 退出程序。")
        sys.exit()
    else:
        print("⚠️ 无效的选择，请重试。")

# 显示主菜单
def display_menu():
    print("\n" + "="*50)
    print("🔐 账号密码管理器")
    print("="*50)
    print("1. 自动登录账号")
    print("2. 创建新账号")
    print("3. 修改密码")
    print("4. 修改账号信息")
    print("5. 复制密码到剪贴板")
    print("6. 删除账号")
    print("7. 查看账号")
    print("8. 导出账号数据")
    print("9. 生成强密码")
    print("0. 退出程序")
    print("="*50)

# 主菜单
def AccountPassword():
    logging.info("AccountPassword tool started")
    while True:
        display_menu()
        choice = input("请选择操作 (0-9): ")

        # 语音控制选项
        if choice == '语音控制':
            print("\n🎤 请说出您的命令...")
            command = takecommand()
            if command:
                print(f"识别到的命令: {command}")
                process_choice(command)
            else:
                print("❌ 未识别到命令")
            continue
        
        # 文字输入处理
        try:
            choice = int(choice)
        except ValueError:
            print("⚠️ 请输入有效数字")
            continue
            
        if choice == 0:
            print("👋 退出程序。")
            sys.exit()
        elif choice == 1:
            auto_login()
        elif choice == 2:
            create_account()
        elif choice == 3:
            change_password()
        elif choice == 4:
            update_account()
        elif choice == 5:
            copy_password()
        elif choice == 6:
            delete_account()
        elif choice == 7:
            view_accounts()
        elif choice == 8:
            export_accounts()
        elif choice == 9:
            generate_password()
        else:
            print("⚠️ 无效的选择，请重试。")

def run(**kwargs):
    """
    启动账号密码管理器。
    """
    # 程序启动时尝试自动登录
    try:
        print("="*50)
        print("🔐 正在启动账号密码管理器...")
        print("="*50)

        # 创建必要的目录
        os.makedirs("exports", exist_ok=True)

        if not auto_login():  # 如果自动登录失败或跳过，启动主菜单
            AccountPassword()
    finally:
        conn.close()  # 确保数据库连接在程序结束时关闭
        print("✅ 数据库连接已关闭")

if __name__ == "__main__":
    run()
