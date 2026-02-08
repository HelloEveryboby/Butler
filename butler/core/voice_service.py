import os
import time
import json
import threading
import logging
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

        base_dir = os.path.dirname(__file__)
        self.ACTIVATION_SOUND_FILE = os.path.join(base_dir, "resources", "activate.wav")

    def speak(self, text: str):
        """Perform text-to-speech."""
        try:
            import pyttsx3
            if not self.engine:
                self.engine = pyttsx3.init()
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            self.ui_print(f"音频处理(TTS)出错: {e}", tag='error')
            logger.warning(f"Could not initialize or use pyttsx3 for TTS: {e}")

    def play_activation_sound(self):
        """Plays a sound to indicate wake word detection."""
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

    def _offline_listen_loop(self):
        porcupine_access_key = os.getenv("PICOVOICE_ACCESS_KEY")
        vosk_model_path = "vosk-model-small-en-us-0.15"

        if not porcupine_access_key or not os.path.exists(vosk_model_path):
            self.ui_print("离线语音环境配置不完整，请检查 PICOVOICE_ACCESS_KEY 和 Vosk 模型。", tag='error')
            self.is_listening = False
            return

        try:
            from pvrecorder import PvRecorder
            import pvporcupine
            from vosk import Model, KaldiRecognizer

            keyword_paths = [pvporcupine.KEYWORD_PATHS["jarvis"]]
            porcupine = pvporcupine.create(access_key=porcupine_access_key, keyword_paths=keyword_paths)
            vosk_model = Model(vosk_model_path)

            self.ui_print("离线语音引擎已就绪，正在监听 'Jarvis'...", tag='system_message')

            while self.is_listening:
                recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
                recorder.start()
                while self.is_listening:
                    pcm = recorder.read()
                    if porcupine.process(pcm) >= 0:
                        self.play_activation_sound()
                        recorder.stop()
                        break
                if not self.is_listening: break

                recognizer = KaldiRecognizer(vosk_model, 16000)
                cmd_recorder = PvRecorder(device_index=-1, frame_length=512)
                cmd_recorder.start()

                silence_frames = 0
                while self.is_listening:
                    pcm = cmd_recorder.read()
                    if recognizer.AcceptWaveform(bytes(pcm)):
                        result = json.loads(recognizer.Result()).get("text", "")
                        if result:
                            self.ui_print(f"识别到指令: {result}", tag='user_input')
                            self.on_command_received(result)
                        break
                    elif not json.loads(recognizer.PartialResult()).get("partial", ""):
                        silence_frames += 1
                    else:
                        silence_frames = 0
                    if silence_frames > 30: break
                cmd_recorder.stop()

        except Exception as e:
            self.ui_print(f"离线语音错误: {e}", tag='error')
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
                    self.ui_print(f"识别到指令 (在线): {evt.result.text}", tag='user_input')
                    self.on_command_received(evt.result.text)

            self.speech_recognizer.recognized.connect(recognized_cb)
            self.speech_recognizer.start_continuous_recognition()
            while self.is_listening: time.sleep(0.5)
            self.speech_recognizer.stop_continuous_recognition()
        except Exception as e:
            self.ui_print(f"在线语音错误: {e}", tag='error')
        finally:
            self.is_listening = False
