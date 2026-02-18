import os
import time
import json
import threading
import tempfile
from typing import Optional, Callable
from dotenv import load_dotenv
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class VoiceService:
    def __init__(self, on_command_received: Callable[[str], None], ui_print_func: Callable, on_status_change: Optional[Callable[[bool], None]] = None):
        self.on_command_received = on_command_received
        self.ui_print = ui_print_func
        self.on_status_change = on_status_change
        self.is_listening = False
        self.voice_mode = 'online'  # Default to online since offline is removed
        self.client = None

        load_dotenv()
        self._init_baidu_client()

        base_dir = os.path.dirname(__file__)
        self.ACTIVATION_SOUND_FILE = os.path.join(base_dir, "resources", "activate.wav")

    def _init_baidu_client(self):
        try:
            from aip import AipSpeech
            app_id = os.getenv("BAIDU_APP_ID")
            api_key = os.getenv("BAIDU_API_KEY")
            secret_key = os.getenv("BAIDU_SECRET_KEY")
            if app_id and api_key and secret_key:
                self.client = AipSpeech(app_id, api_key, secret_key)
                logger.info("Baidu AipSpeech client initialized.")
            else:
                logger.warning("Baidu API keys missing in .env")
        except ImportError:
            logger.error("baidu-aip not installed")

    def speak(self, text: str):
        """Perform text-to-speech using Baidu AIP."""
        if not self.client:
            self._offline_fallback_speak(text)
            return

        try:
            result = self.client.synthesis(text, 'zh', 1, {
                'vol': 5,
                'per': 4, # 4 is a common female voice
            })

            if not isinstance(result, dict):
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                    f.write(result)
                    temp_file = f.name

                self._play_audio(temp_file)
                os.remove(temp_file)
            else:
                logger.error(f"Baidu TTS error: {result}")
                self._offline_fallback_speak(text)
        except Exception as e:
            logger.error(f"Baidu TTS Exception: {e}")
            self._offline_fallback_speak(text)

    def _offline_fallback_speak(self, text: str):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logger.warning(f"Offline fallback TTS failed: {e}")

    def _play_audio(self, file_path: str):
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            logger.warning(f"Could not play audio {file_path}: {e}")

    def play_activation_sound(self):
        """Plays a sound to indicate listening started."""
        if os.path.exists(self.ACTIVATION_SOUND_FILE):
            self._play_audio(self.ACTIVATION_SOUND_FILE)

    def start_listening(self):
        """Start listening for a command. Triggered manually now since wake word is removed."""
        if self.is_listening:
            return
        self.is_listening = True
        if self.on_status_change:
            self.on_status_change(True)
        self.listen_thread = threading.Thread(target=self._baidu_listen_loop)
        self.listen_thread.daemon = True
        self.listen_thread.start()

    def stop_listening(self):
        self.is_listening = False
        if self.on_status_change:
            self.on_status_change(False)

    def set_voice_mode(self, mode: str):
        # Only 'online' (Baidu) is supported now for Chinese
        self.voice_mode = 'online'
        return True

    def _baidu_listen_loop(self):
        if not self.client:
            self.ui_print("Baidu 语音服务未配置，请检查 .env 文件。", tag='error')
            self.is_listening = False
            return

        try:
            from pvrecorder import PvRecorder
            # Using PvRecorder as a simple audio capturer (no model involved)
            access_key = os.getenv("PICOVOICE_ACCESS_KEY")
            if access_key:
                recorder = PvRecorder(access_key=access_key, device_index=-1, frame_length=512)
            else:
                recorder = PvRecorder(device_index=-1, frame_length=512)

            self.ui_print("正在录音...", tag='system_message')
            self.play_activation_sound()

            recorder.start()
            audio_data = []

            silence_threshold = 500 # Adjust based on environment
            max_silence_frames = 40
            silence_frames = 0
            max_record_frames = 300 # ~10 seconds

            for _ in range(max_record_frames):
                if not self.is_listening: break
                frame = recorder.read()
                audio_data.extend(frame)

                # Simple VAD (Voice Activity Detection)
                rms = (sum(f**2 for f in frame) / len(frame))**0.5
                if rms < silence_threshold:
                    silence_frames += 1
                else:
                    silence_frames = 0

                if silence_frames > max_silence_frames and len(audio_data) > 16000: # at least 1s
                    break

            recorder.stop()
            recorder.delete()

            if audio_data:
                # Convert to 16bit PCM WAV
                import struct
                import wave
                import io

                buffer = io.BytesIO()
                with wave.open(buffer, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(struct.pack('<' + ('h' * len(audio_data)), *audio_data))

                wav_data = buffer.getvalue()

                self.ui_print("正在识别...", tag='system_message')
                res = self.client.asr(wav_data, 'wav', 16000, {'dev_pid': 1537})

                if res.get('err_no') == 0:
                    result_text = res.get('result', [""])[0]
                    if result_text:
                        self.ui_print(f"识别到指令: {result_text}", tag='user_input')
                        self.on_command_received(result_text)
                else:
                    logger.error(f"Baidu ASR error: {res}")
                    self.ui_print(f"识别失败: {res.get('err_msg')}", tag='error')

        except Exception as e:
            self.ui_print(f"语音识别错误: {e}", tag='error')
            logger.exception("Baidu listen loop error")
        finally:
            self.is_listening = False
            if self.on_status_change:
                self.on_status_change(False)
