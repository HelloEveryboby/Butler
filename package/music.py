"""
音乐播放器工具。支持扫描本地文件、搜索歌曲、播放列表展示以及简单的播放控制。
"""
import os
import json
try:
    from jarvis.jarvis import takecommand
except ImportError:
    takecommand = None
from playsound import playsound

# 音乐库文件路径
MUSIC_LIBRARY_FILE = "music_library.json"

# 音乐播放器函数
def music_player():
    music_library = []

    # 从文件中加载音乐库
    def load_music_library():
        try:
            with open(MUSIC_LIBRARY_FILE, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    # 保存音乐库到文件
    def save_music_library():
        with open(MUSIC_LIBRARY_FILE, "w") as f:
            json.dump(music_library, f)

    # 遍历整个文件系统以查找音乐文件
    def build_music_library():
        for root, _, files in os.walk("/"):
            for file in files:
                if file.endswith(('.mp3', '.wav', '.ogg')):
                    music_library.append(os.path.join(root, file))

    # 加载音乐库，如果文件不存在则构建
    music_library = load_music_library()
    if not music_library:
        print("正在构建音乐库，这可能需要一些时间...")
        build_music_library()
        save_music_library()
        print("音乐库构建完成！")

    current_song_index = 0

    def play_music(song_index):
        try:
            playsound(music_library[song_index])
            print(f"正在播放: {music_library[song_index]}")
        except Exception as e:
            print(f"无法播放音乐文件 {music_library[song_index]}: {e}")

    def next_song():
        nonlocal current_song_index
        current_song_index = (current_song_index + 1) % len(music_library)
        play_music(current_song_index)

    def previous_song():
        nonlocal current_song_index
        current_song_index = (current_song_index - 1) % len(music_library)
        play_music(current_song_index)

    def show_playlist():
        for index, song in enumerate(music_library):
            print(f"{index + 1}. {os.path.basename(song)}")

    def search_song(keyword):
        for index, song in enumerate(music_library):
            if keyword.lower() in os.path.basename(song).lower():
                print(f"找到歌曲: {song}")
                play_music(index)
                return
        print("未找到匹配的歌曲。")
        
    def text_input_control():
        global current_song_index
        while True:
            user_input = input("请输入命令 (播放, 下一首, 上一首, 搜索 <关键词>, 播放列表, 退出): ").strip()
            if user_input:
                if "播放" in user_input:
                    play_music(current_song_index)
                elif "下一首" in user_input:
                    next_song()
                elif "上一首" in user_input:
                    previous_song()
                elif "搜索" in user_input:
                    keyword = user_input.split("搜索")[-1].strip()
                    search_song(keyword)
                elif "播放列表" in user_input:
                    show_playlist()
                elif "退出" in user_input:
                    print("音乐播放器已退出。")
                    break
                else:
                    print("未知命令，请重新输入。")

    def voice_input_control():
        global current_song_index
        while True:
            try:
                command = takecommand()
                if command:
                    if "播放" in command:
                        play_music(current_song_index)
                    elif "下一首" in command:
                        next_song()
                    elif "上一首" in command:
                        previous_song()
                    elif "搜索" in command:
                        keyword = command.split("搜索")[-1].strip()
                        search_song(keyword)
                    elif "播放列表" in command:
                        show_playlist()
                    elif "切换到文字输入模式" in command or command == "1":
                        print("已切换到文字输入模式")
                        return
                    elif "退出" in command:
                        print("音乐播放器已退出。")
                        break
                    else:
                        print("未知命令，请重新输入。")
            except Exception as e:
                print(f"发生错误: {e}")
                
    # 初始设置
    use_voice_input = True if takecommand else False

    while True:
        if use_voice_input:
            voice_input_control()
        else:
            text_input_control()

        # 切换输入模式
        print("输入 '1' 切换到文字输入模式, 输入 '2' 切换到语音输入模式:")
        user_input = input().strip()
        if user_input == "1":
            use_voice_input = False
            print("已切换到文字输入模式")
        elif user_input == "2":
            use_voice_input = True
            print("已切换到语音输入模式")
        else:
            print("未知命令，请重新输入。")

def run(**kwargs):
    """
    启动音乐播放器。
    """
    music_player()

if __name__ == "__main__":
    run()
