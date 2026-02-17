import os
import time
import json
import threading
import logging
import glob
from typing import Optional, Callable
from dotenv import load_dotenv
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class VoiceService:
    def __init__(self, on_command_received: Callable[[str], None], ui_print_func: Callable):
        self.on_command_received = on_command_received
        self.ui_print = ui_print_func
        self.is_listening = False
        self.voice_mode = 'offline'  # 'offline' or 'online'
        self.engine = None
        self.speech_recognizer = None
        self.tts_mode = 'auto' # 'auto', 'azure', 'local'

        base_dir = os.path.dirname(__file__)
        self.ACTIVATION_SOUND_FILE = os.path.join(base_dir, "resources", "activate.wav")

    def speak(self, text: str):
        """执行文本转语音，优先使用 Azure，失败则回退到 pyttsx3。"""
        if not text: return

        azure_key = os.getenv("AZURE_SPEECH_KEY")
        if (self.tts_mode == 'azure' or self.tts_mode == 'auto') and azure_key:
            if self._speak_azure(text):
                return

        self._speak_local(text)

    def _speak_azure(self, text: str) -> bool:
        """使用 Azure 语音合成。"""
        try:
            import azure.cognitiveservices.speech as speechsdk
            speech_key = os.getenv("AZURE_SPEECH_KEY")
            service_region = os.getenv("AZURE_SERVICE_REGION", "chinaeast2")

            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
            # 设置中文女声
            speech_config.speech_synthesis_voice_name = "zh-CN-XiaoxiaoNeural"

            speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
            result = speech_synthesizer.speak_text_async(text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return True
            else:
                logger.warning(f"Azure TTS failed: {result.reason}")
                return False
        except Exception as e:
            logger.error(f"Azure TTS Error: {e}")
            return False

    def _speak_local(self, text: str):
        """使用本地 pyttsx3 语音合成。"""
        try:
            import pyttsx3
            if not self.engine:
                self.engine = pyttsx3.init()
                # 尝试设置中文语音
                voices = self.engine.getProperty('voices')
                for voice in voices:
                    if 'chinese' in voice.name.lower() or 'zh' in voice.id.lower():
                        self.engine.setProperty('voice', voice.id)
                        break

            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            self.ui_print(f"本地音频处理(TTS)出错: {e}", tag='error')
            logger.warning(f"Could not use pyttsx3 for TTS: {e}")

    def play_activation_sound(self):
        """播放唤醒音。"""
        if not os.path.exists(self.ACTIVATION_SOUND_FILE):
            logger.info("Activation sound file not found, skipping sound.")
            return

        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(self.ACTIVATION_SOUND_FILE)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.quit()
        except Exception as e:
            logger.warning(f"Could not play activation sound: {e}")

    def start_listening(self):
        if self.is_listening:
            return
        self.is_listening = True
        target_loop = self._offline_listen_loop if self.voice_mode == 'offline' else self._online_listen_loop
        self.listen_thread = threading.Thread(target=target_loop)
        self.listen_thread.daemon = True
        self.listen_thread.start()

    def stop_listening(self):
        self.is_listening = False

    def set_voice_mode(self, mode: str):
        if mode in ['online', 'offline'] and self.voice_mode != mode:
            self.voice_mode = mode
            if self.is_listening:
                self.stop_listening()
                self.start_listening()
            return True
        return False

    def _find_vosk_model(self):
        """查找本地 Vosk 模型，优先匹配中文。"""
        models = glob.glob("vosk-model-*")
        if not models:
            return None
        # 优先返回带 'cn' 或 'chinese' 的模型
        for m in models:
            if 'cn' in m.lower() or 'chinese' in m.lower():
                return m
        return models[0]

    def _offline_listen_loop(self):
        porcupine_access_key = os.getenv("PICOVOICE_ACCESS_KEY")
        vosk_model_path = self._find_vosk_model()

        if not porcupine_access_key or not vosk_model_path:
            self.ui_print("离线语音环境不完整：缺失 PICOVOICE_ACCESS_KEY 或 Vosk 模型。", tag='error')
            self.ui_print("请运行 'package/voice_setup.py' 自动配置环境。", tag='system_message')
            self.is_listening = False
            return

        try:
            from pvrecorder import PvRecorder
            import pvporcupine
            from vosk import Model, KaldiRecognizer

            # 兼容不同操作系统的唤醒词路径
            try:
                keyword_paths = [pvporcupine.KEYWORD_PATHS["jarvis"]]
                porcupine = pvporcupine.create(access_key=porcupine_access_key, keyword_paths=keyword_paths)
            except Exception:
                # 备选：如果默认 keyword_paths 失败，尝试内置
                porcupine = pvporcupine.create(access_key=porcupine_access_key, keywords=["jarvis"])

            vosk_model = Model(vosk_model_path)
            self.ui_print(f"离线语音引擎就绪 (模型: {vosk_model_path})，监听 'Jarvis'...", tag='system_message')

            while self.is_listening:
                recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
                recorder.start()
                try:
                    while self.is_listening:
                        pcm = recorder.read()
                        if porcupine.process(pcm) >= 0:
                            self.play_activation_sound()
                            break
                finally:
                    recorder.stop()
                    recorder.delete()

                if not self.is_listening: break

                # 开始指令识别
                recognizer = KaldiRecognizer(vosk_model, 16000)
                cmd_recorder = PvRecorder(device_index=-1, frame_length=512)
                cmd_recorder.start()

                self.ui_print("正在聆听指令...", tag='system_message')

                silence_frames = 0
                try:
                    while self.is_listening:
                        pcm = cmd_recorder.read()
                        if recognizer.AcceptWaveform(bytes(pcm)):
                            result = json.loads(recognizer.Result()).get("text", "")
                            if result:
                                # 处理识别出的文字（Vosk 有时会在中文间加空格，这里去掉）
                                result = result.replace(" ", "")
                                self.ui_print(f"识别到指令: {result}", tag='user_input')
                                self.on_command_received(result)
                            break
                        else:
                            partial = json.loads(recognizer.PartialResult()).get("partial", "")
                            if not partial:
                                silence_frames += 1
                            else:
                                silence_frames = 0

                        if silence_frames > 60: # 约 2 秒静音自动结束
                            break
                finally:
                    cmd_recorder.stop()
                    cmd_recorder.delete()

        except Exception as e:
            self.ui_print(f"离线语音循环出错: {e}", tag='error')
            logger.error(f"Offline Voice Loop Error: {e}")
        finally:
            self.is_listening = False

    def _online_listen_loop(self):
        try:
            import azure.cognitiveservices.speech as speechsdk
            speech_key = os.getenv("AZURE_SPEECH_KEY")
            service_region = os.getenv("AZURE_SERVICE_REGION", "chinaeast2")
            if not speech_key: raise ValueError("Azure Key missing")

            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
            speech_config.speech_recognition_language = "zh-CN"
            self.speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config)

            def recognized_cb(evt):
                if evt.result.text:
                    clean_text = evt.result.text.strip().rstrip('。')
                    self.ui_print(f"识别到指令 (在线): {clean_text}", tag='user_input')
                    self.on_command_received(clean_text)

            self.speech_recognizer.recognized.connect(recognized_cb)
            self.speech_recognizer.start_continuous_recognition()
            self.ui_print("在线语音识别已启动...", tag='system_message')

            while self.is_listening:
                time.sleep(0.5)

            self.speech_recognizer.stop_continuous_recognition()
        except Exception as e:
            self.ui_print(f"在线语音错误: {e}", tag='error')
            logger.error(f"Online Voice Error: {e}")
        finally:
            self.is_listening = False
