from .interpreter import Interpreter

# ANSI escape codes for colors
class colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def main_loop():
    """
    与本地解释器交互的主命令行循环。
    """
    print(f"{colors.HEADER}{colors.BOLD}欢迎使用本地解释器命令行界面{colors.ENDC}")
    print("输入 'exit' 退出。")

    interpreter = Interpreter()
    if not interpreter.is_ready:
        print(f"{colors.FAIL}无法初始化解释器。正在退出。{colors.ENDC}")
        return

    while True:
        try:
            user_input = input(f"{colors.BOLD}>>> {colors.ENDC}")
            if user_input.lower().strip() == 'exit':
                print(f"{colors.WARNING}正在退出...{colors.ENDC}")
                break

            result = interpreter.run(user_input)

            print(f"{colors.OKBLUE}--- 结果 ---{colors.ENDC}")
            print(result)
            print(f"{colors.OKBLUE}------------{colors.ENDC}\n")

        except KeyboardInterrupt:
            print(f"\n{colors.WARNING}正在退出...{colors.ENDC}")
            break
        except Exception as e:
            print(f"{colors.FAIL}主循环中发生关键错误: {e}{colors.ENDC}")
            break

if __name__ == '__main__':
    # We also need to refine the 'thinking' output from the other modules
    # for a truly clean run. For this MVP, we'll accept their print statements.
    main_loop()
