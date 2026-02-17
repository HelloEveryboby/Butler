import os
import json
import threading
import time

# 尝试获取 Jarvis 全局实例或使用模拟
try:
    from butler.main import Jarvis
except ImportError:
    Jarvis = None

# 音乐库文件路径
MUSIC_LIBRARY_FILE = "music_library.json"

class MusicPlayer:
    def __init__(self, jarvis_app=None):
        self.jarvis = jarvis_app
        self.music_library = self._load_library()
        self.current_song_index = 0
        self.is_playing = False

    def _load_library(self):
        if os.path.exists(MUSIC_LIBRARY_FILE):
            with open(MUSIC_LIBRARY_FILE, "r") as f:
                return json.load(f)
        return []

    def build_library(self):
        print("正在扫描音乐文件...")
        library = []
        # 仅扫描当前目录及子目录，避免全盘扫描过慢
        for root, _, files in os.walk("."):
            for file in files:
                if file.endswith(('.mp3', '.wav', '.ogg')):
                    library.append(os.path.abspath(os.path.join(root, file)))
        self.music_library = library
        with open(MUSIC_LIBRARY_FILE, "w") as f:
            json.dump(library, f)
        return f"扫描完成，找到 {len(library)} 首歌曲。"

    def play(self, index=None):
        if index is not None: self.current_song_index = index % len(self.music_library)
        if not self.music_library: return "库中没有音乐。"

        song = self.music_library[self.current_song_index]
        print(f"播放: {song}")
        # 这里可以使用 pygame 播放
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(song)
            pygame.mixer.music.play()
            self.is_playing = True
            return f"正在播放: {os.path.basename(song)}"
        except Exception as e:
            return f"播放出错: {e}"

    def stop(self):
        try:
            import pygame
            pygame.mixer.music.stop()
            self.is_playing = False
            return "已停止播放。"
        except: return "未在播放。"

def run(*args, **kwargs):
    """Butler 工具接口。"""
    player = MusicPlayer(kwargs.get("jarvis_app"))
    command = kwargs.get("command", "")

    if "扫描" in command or "build" in command:
        return player.build_library()
    elif "停止" in command or "stop" in command:
        return player.stop()
    elif "播放" in command or "play" in command:
        return player.play()

    return "音乐播放器指令：播放, 停止, 扫描"

if __name__ == "__main__":
    # 简单的 CLI 测试
    p = MusicPlayer()
    print(p.build_library())
    print(p.play())
    time.sleep(5)
    print(p.stop())
