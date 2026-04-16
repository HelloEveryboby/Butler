import os
import time
import json
import threading
import tempfile
import wave
import struct
import io
from typing import Optional, Callable, Dict, Any
from dotenv import load_dotenv
from package.core_utils.log_manager import LogManager
from package.core_utils.config_loader import config_loader
from butler.core.asset_loader import asset_loader

logger = LogManager.get_logger(__name__)

class VoiceEngine:
    def speak(self, text: str):
        pass

    def transcribe(self, wav_data: bytes) -> str:
        pass

class BaiduVoiceEngine(VoiceEngine):
    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            from aip import AipSpeech
            app_id = config_loader.get("api.baidu.app_id")
            api_key = config_loader.get("api.baidu.api_key")
            secret_key = config_loader.get("api.baidu.secret_key")

            if app_id and api_key and secret_key:
                self.client = AipSpeech(app_id, api_key, secret_key)
            else:
                logger.warning("Baidu API keys missing.")
        except ImportError:
            logger.error("baidu-aip not installed")

    def speak(self, text: str):
        if not self.client: return None
        try:
            result = self.client.synthesis(text, 'zh', 1, {'vol': 5, 'per': 4})
            if not isinstance(result, dict):
                return result # bytes
            logger.error(f"Baidu TTS error: {result}")
        except Exception as e:
            logger.error(f"Baidu TTS Exception: {e}")
        return None

    def transcribe(self, wav_data: bytes) -> str:
        if not self.client: return ""
        try:
            res = self.client.asr(wav_data, 'wav', 16000, {'dev_pid': 1537})
            if res.get('err_no') == 0:
                return res.get('result', [""])[0]
            logger.error(f"Baidu ASR error: {res}")
        except Exception as e:
            logger.error(f"Baidu ASR Exception: {e}")
        return ""

class LocalVoiceEngine(VoiceEngine):
    def __init__(self):
        self.stt_model = None
        self.tts_engine = None
        self._init_models()

    def _init_models(self):
        # STT: Faster-Whisper
        try:
            from faster_whisper import WhisperModel
            model_size = config_loader.get("voice.local_stt_model", "base")
            # In a real scenario, we'd want to specify where to download/load models
            # For this sandbox, we assume it can reach HF or is pre-cached
            self.stt_model = WhisperModel(model_size, device="cpu", compute_type="int8")
            logger.info(f"Local STT (Whisper {model_size}) initialized.")
        except Exception as e:
            logger.error(f"Failed to init Local STT: {e}")

        # TTS: pyttsx3 as a simple local fallback, piper would require external binaries/models
        try:
            import pyttsx3
            self.tts_engine = pyttsx3.init()
            logger.info("Local TTS (pyttsx3) initialized.")
        except Exception as e:
            logger.error(f"Failed to init Local TTS: {e}")

    def speak(self, text: str):
        # pyttsx3 is blocking or has its own loop. For consistency, we'll try to use it.
        # Note: pyttsx3 doesn't easily return bytes, it plays directly.
        if self.tts_engine:
            try:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except Exception as e:
                logger.error(f"pyttsx3 speak error: {e}")
        return None

    def transcribe(self, wav_data: bytes) -> str:
        if not self.stt_model: return ""
        try:
            # Whisper needs a file path or a file-like object
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
                f.write(wav_data)
                temp_path = f.name

            segments, info = self.stt_model.transcribe(temp_path, beam_size=5)
            text = "".join([s.text for s in segments])
            os.remove(temp_path)
            return text.strip()
        except Exception as e:
            logger.error(f"Local STT error: {e}")
        return ""

class VoiceService:
    def __init__(self, on_command_received: Callable[[str], None], ui_print_func: Callable, on_status_change: Optional[Callable[[bool], None]] = None):
        self.on_command_received = on_command_received
        self.ui_print = ui_print_func
        self.on_status_change = on_status_change
        self.is_listening = False

        # Load mode from config
        self.mode = config_loader.get("voice.mode", "online")
        self.engines: Dict[str, VoiceEngine] = {
            "online": BaiduVoiceEngine(),
            "local": LocalVoiceEngine()
        }

        self.ACTIVATION_SOUND_FILE = asset_loader.resolve_path("audio://activate.wav")

    def get_engine(self) -> VoiceEngine:
        return self.engines.get(self.mode, self.engines["online"])

    def speak(self, text: str):
        engine = self.get_engine()
        audio_bytes = engine.speak(text)

        if audio_bytes:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                f.write(audio_bytes)
                temp_file = f.name
            self._play_audio(temp_file)
            os.remove(temp_file)
        # If engine.speak returns None, it might have played it internally (like pyttsx3)

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
        if os.path.exists(self.ACTIVATION_SOUND_FILE):
            self._play_audio(self.ACTIVATION_SOUND_FILE)

    def start_listening(self):
        if self.is_listening: return
        self.is_listening = True
        if self.on_status_change: self.on_status_change(True)
        self.listen_thread = threading.Thread(target=self._listen_loop)
        self.listen_thread.daemon = True
        self.listen_thread.start()

    def stop_listening(self):
        self.is_listening = False
        if self.on_status_change: self.on_status_change(False)

    def set_voice_mode(self, mode: str):
        if mode in self.engines:
            self.mode = mode
            config_loader.save({"voice": {"mode": mode}})
            self.ui_print(f"语音模式已切换至: {mode}", tag='system_message')
            return True
        return False

    def _listen_loop(self):
        try:
            from pvrecorder import PvRecorder
            access_key = config_loader.get("api.picovoice.access_key")
            recorder = PvRecorder(access_key=access_key, device_index=-1, frame_length=512) if access_key else PvRecorder(device_index=-1, frame_length=512)

            self.ui_print(f"正在录音 ({self.mode} 模式)...", tag='system_message')
            self.play_activation_sound()

            recorder.start()
            audio_data = []

            silence_threshold = 500
            max_silence_frames = 40
            silence_frames = 0
            max_record_frames = 300

            for _ in range(max_record_frames):
                if not self.is_listening: break
                frame = recorder.read()
                audio_data.extend(frame)

                rms = (sum(f**2 for f in frame) / len(frame))**0.5
                if rms < silence_threshold: silence_frames += 1
                else: silence_frames = 0

                if silence_frames > max_silence_frames and len(audio_data) > 16000: break

            recorder.stop()
            recorder.delete()

            if audio_data:
                buffer = io.BytesIO()
                with wave.open(buffer, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(struct.pack('<' + ('h' * len(audio_data)), *audio_data))
                wav_data = buffer.getvalue()

                self.ui_print("正在识别...", tag='system_message')
                result_text = self.get_engine().transcribe(wav_data)

                if result_text:
                    self.ui_print(f"识别到指令: {result_text}", tag='user_input')
                    self.on_command_received(result_text)
                else:
                    self.ui_print("未能识别语音内容。", tag='error')

        except Exception as e:
            self.ui_print(f"语音识别错误: {e}", tag='error')
            logger.exception("Listen loop error")
        finally:
            self.is_listening = False
            if self.on_status_change: self.on_status_change(False)
