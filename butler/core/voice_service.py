"""
Butler 语音服务 — 多引擎架构（原生设备 + 厂商 API + 本地模型）

三层引擎，按优先级自动降级：
  native  → 操作系统原生语音（Windows SAPI / macOS Speech / Linux espeak）零安装
  online  → 厂商云 API（百度 / Google Cloud / Azure 等）最佳体验
  local   → 本地 AI 模型（Faster-Whisper）离线高精度

录音层统一使用 sounddevice / pyaudio，不再依赖 Picovoice。
"""

import os
import sys
import time
import json
import threading
import tempfile
import wave
import struct
import io
import platform
import subprocess
import shutil
from typing import Optional, Callable, Dict, Any, List
from dotenv import load_dotenv
from package.core_utils.log_manager import LogManager
from package.core_utils.config_loader import config_loader
from butler.core.asset_loader import asset_loader

logger = LogManager.get_logger(__name__)

PLATFORM = platform.system()  # "Windows" | "Darwin" | "Linux"


# ══════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════


def detect_and_configure_gpu_device() -> str:
    """检测 CUDA 可用性，显存不足自动降级到 CPU。"""
    try:
        import torch
        if torch.cuda.is_available():
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            logger.info(f"[GPU] CUDA available. VRAM: {vram_gb:.2f} GB")
            if vram_gb >= 6.0:
                return "cuda"
            logger.warning(f"[GPU] VRAM insufficient ({vram_gb:.2f} GB). Fallback to CPU.")
            return "cpu"
        return "cpu"
    except ImportError:
        return "cpu"
    except Exception as e:
        logger.warning(f"[GPU] Detection error: {e}. Using CPU.")
        return "cpu"


# ══════════════════════════════════════════════════════════════
# 统一录音层
# ══════════════════════════════════════════════════════════════


class AudioRecorder:
    """统一录音模块。优先 sounddevice，备选 pyaudio，兜底 Windows MCI。"""

    SAMPLE_RATE = 16000
    CHANNELS = 1
    SILENCE_THRESHOLD = 500
    MAX_SILENCE_FRAMES = 40
    MAX_RECORD_FRAMES = 300

    @staticmethod
    def list_devices() -> list:
        devices = []
        try:
            import sounddevice as sd
            for i, d in enumerate(sd.query_devices()):
                if d["max_input_channels"] > 0:
                    devices.append({"index": i, "name": d["name"], "channels": d["max_input_channels"]})
        except ImportError:
            pass
        if not devices:
            try:
                import pyaudio
                p = pyaudio.PyAudio()
                for i in range(p.get_device_count()):
                    info = p.get_device_info_by_index(i)
                    if info["maxInputChannels"] > 0:
                        devices.append({"index": i, "name": info["name"], "channels": info["maxInputChannels"]})
                p.terminate()
            except ImportError:
                pass
        return devices

    @staticmethod
    def has_microphone() -> bool:
        return len(AudioRecorder.list_devices()) > 0

    @staticmethod
    def record(is_listening_fn: Callable[[], bool] = lambda: True,
               on_start: Callable = None) -> bytes | None:
        audio_data = AudioRecorder._record_sounddevice(is_listening_fn, on_start)
        if audio_data is None:
            audio_data = AudioRecorder._record_pyaudio(is_listening_fn, on_start)
        if audio_data is None:
            logger.error("所有录音方式均失败")
            return None
        return AudioRecorder._to_wav(audio_data)

    @staticmethod
    def _record_sounddevice(is_listening_fn, on_start) -> list | None:
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            return None
        try:
            frames = []
            silence_frames = 0
            started = False

            def callback(indata, frame_count, time_info, status):
                nonlocal silence_frames, started
                if not is_listening_fn():
                    raise sd.CallbackStop()
                frames_chunk = indata[:, 0].tolist()
                frames.extend(frames_chunk)
                rms = (sum(f ** 2 for f in frames_chunk) / len(frames_chunk)) ** 0.5
                if not started and rms > AudioRecorder.SILENCE_THRESHOLD:
                    started = True
                    if on_start:
                        on_start()
                if started:
                    if rms < AudioRecorder.SILENCE_THRESHOLD:
                        silence_frames += 1
                    else:
                        silence_frames = 0

            with sd.InputStream(
                samplerate=AudioRecorder.SAMPLE_RATE,
                channels=AudioRecorder.CHANNELS,
                dtype='int16',
                blocksize=512,
                callback=callback,
            ):
                start_time = time.time()
                while is_listening_fn():
                    time.sleep(0.05)
                    if started and silence_frames > AudioRecorder.MAX_SILENCE_FRAMES:
                        break
                    if time.time() - start_time > 30:
                        break
            return frames if frames else None
        except Exception as e:
            logger.debug(f"sounddevice 录音失败: {e}")
            return None

    @staticmethod
    def _record_pyaudio(is_listening_fn, on_start) -> list | None:
        try:
            import pyaudio
        except ImportError:
            return None
        try:
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=AudioRecorder.CHANNELS,
                rate=AudioRecorder.SAMPLE_RATE,
                input=True,
                frames_per_buffer=512,
            )
            audio_data = []
            silence_frames = 0
            started = False
            for _ in range(AudioRecorder.MAX_RECORD_FRAMES):
                if not is_listening_fn():
                    break
                data = stream.read(512, exception_on_overflow=False)
                frame = struct.unpack('<' + 'h' * (len(data) // 2), data)
                audio_data.extend(frame)
                rms = (sum(f ** 2 for f in frame) / len(frame)) ** 0.5
                if not started and rms > AudioRecorder.SILENCE_THRESHOLD:
                    started = True
                    if on_start:
                        on_start()
                if started:
                    if rms < AudioRecorder.SILENCE_THRESHOLD:
                        silence_frames += 1
                    else:
                        silence_frames = 0
                    if silence_frames > AudioRecorder.MAX_SILENCE_FRAMES:
                        break
            stream.stop_stream()
            stream.close()
            p.terminate()
            return audio_data if audio_data else None
        except Exception as e:
            logger.debug(f"pyaudio 录音失败: {e}")
            return None

    @staticmethod
    def _to_wav(audio_data: list) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(AudioRecorder.CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(AudioRecorder.SAMPLE_RATE)
            wf.writeframes(struct.pack('<' + 'h' * len(audio_data), *audio_data))
        return buf.getvalue()


# ══════════════════════════════════════════════════════════════
# 引擎基类
# ══════════════════════════════════════════════════════════════


class VoiceEngine:
    """语音引擎基类。子类实现 STT(transcribe) 与 TTS(speak)。"""

    name: str = "base"
    display_name: str = "Base Engine"
    requires_install: bool = False
    requires_api_key: bool = False
    # 引擎类别：native（操作系统原生）/ online（厂商云API）/ local（本地模型）
    category: str = "native"

    def is_available(self) -> bool:
        return True

    def speak(self, text: str) -> bytes | None:
        """语音合成。返回音频 bytes（由上层播放），或 None（引擎内部已播放）。"""
        return None

    def transcribe(self, wav_data: bytes) -> str:
        """语音识别，返回文本。"""
        return ""


# ══════════════════════════════════════════════════════════════
# 原生 TTS 统一封装（pyttsx3 跨平台：Windows SAPI / macOS NSSpeech / Linux espeak）
# ══════════════════════════════════════════════════════════════


def _get_native_tts_engine():
    """获取原生 TTS 引擎（pyttsx3），失败返回 None。"""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        for v in voices:
            if 'chinese' in v.name.lower() or 'zh' in v.id.lower():
                engine.setProperty('voice', v.id)
                break
        engine.setProperty('rate', 180)
        engine.setProperty('volume', 0.9)
        return engine
    except Exception as e:
        logger.debug(f"原生 TTS (pyttsx3) 不可用: {e}")
        return None


def _native_tts_speak(engine, text: str) -> None:
    """用原生 TTS 引擎直接播放语音。"""
    if engine:
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logger.error(f"原生 TTS 播放错误: {e}")


# ══════════════════════════════════════════════════════════════
# 引擎 1: 操作系统原生语音（native）
#   Windows → SAPI（win32com STT + pyttsx3 TTS）
#   macOS   → Speech framework（STT via speech_recognition + say/NSSpeech TTS）
#   Linux   → speech_recognition STT + espeak-ng TTS
# ══════════════════════════════════════════════════════════════


class NativeVoiceEngine(VoiceEngine):
    """操作系统原生语音引擎 — 零安装、零配置，直接调用设备自带语音能力。"""

    name = "native"
    display_name = f"系统原生 ({PLATFORM})"
    category = "native"

    def __init__(self):
        self._sr = None          # speech_recognition 库
        self._tts_engine = None  # pyttsx3
        self._sapi_available = False
        self._available = False
        self._init()

    def _init(self):
        # STT: speech_recognition 库（跨平台音频采集 + 多后端识别）
        try:
            import speech_recognition as sr
            self._sr = sr
            self._available = True
            logger.info(f"[Voice:native] speech_recognition 就绪 ({PLATFORM})")
        except ImportError:
            logger.warning("[Voice:native] speech_recognition 未安装: pip install SpeechRecognition")

        # Windows SAPI 原生 STT 检测（通过 win32com）
        if PLATFORM == "Windows":
            self._sapi_available = self._detect_sapi()

        # TTS: pyttsx3（跨平台原生）
        self._tts_engine = _get_native_tts_engine()
        if self._tts_engine:
            logger.info(f"[Voice:native] 原生 TTS 就绪 ({PLATFORM})")

    @staticmethod
    def _detect_sapi() -> bool:
        """检测 Windows SAPI 是否可用。"""
        try:
            import win32com.client
            win32com.client.Dispatch("SAPI.SpVoice")
            return True
        except Exception:
            return False

    def is_available(self) -> bool:
        return self._available and self._sr is not None

    def speak(self, text: str) -> bytes | None:
        # 原生 TTS 直接播放，不返回 bytes
        _native_tts_speak(self._tts_engine, text)
        return None

    def transcribe(self, wav_data: bytes) -> str:
        if not self._sr:
            return ""
        try:
            recognizer = self._sr.Recognizer()
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
                f.write(wav_data)
                temp_path = f.name

            with self._sr.AudioFile(temp_path) as source:
                audio = recognizer.record(source)
            os.remove(temp_path)

            # 按优先级尝试多种识别后端
            backends = self._get_stt_backends()
            for backend_name, backend_fn in backends:
                try:
                    text = backend_fn(recognizer, audio)
                    if text:
                        logger.debug(f"[Voice:native] STT 成功 via {backend_name}: {text[:50]}")
                        return text.strip()
                except Exception as e:
                    logger.debug(f"[Voice:native] STT 后端 {backend_name} 失败: {e}")
                    continue

            return ""
        except Exception as e:
            logger.error(f"[Voice:native] STT 错误: {e}")
            return ""

    def _get_stt_backends(self) -> List[tuple]:
        """返回 STT 后端列表（按优先级），各平台不同。"""
        backends = []
        sr = self._sr

        if PLATFORM == "Windows":
            # Windows：优先尝试 SAPI（通过 speech_recognition 的 recognize_sphinx 离线），
            # 再降级 Google 免费在线
            backends.append(("sphinx", lambda r, a: r.recognize_sphinx(a)))
            backends.append(("google", lambda r, a: r.recognize_google(a, language="zh-CN")))
        elif PLATFORM == "Darwin":
            # macOS：离线 Sphinx → Google 在线
            backends.append(("sphinx", lambda r, a: r.recognize_sphinx(a)))
            backends.append(("google", lambda r, a: r.recognize_google(a, language="zh-CN")))
        else:
            # Linux：离线 Sphinx → Google 在线
            backends.append(("sphinx", lambda r, a: r.recognize_sphinx(a)))
            backends.append(("google", lambda r, a: r.recognize_google(a, language="zh-CN")))

        return backends


# ══════════════════════════════════════════════════════════════
# 引擎 2: 本地 AI 模型（local）— Faster-Whisper STT + 原生 TTS
# ══════════════════════════════════════════════════════════════


class WhisperVoiceEngine(VoiceEngine):
    """本地 AI 模型语音引擎 — Faster-Whisper STT + 原生 TTS。"""

    name = "local"
    display_name = "本地模型 (Faster-Whisper)"
    category = "local"
    requires_install = True

    def __init__(self):
        self.stt_model = None
        self._tts_engine = None
        self._available = False
        self._init_models()

    def _init_models(self):
        # STT: Faster-Whisper
        try:
            from faster_whisper import WhisperModel
            model_size = config_loader.get("voice.local_stt_model", "base")
            dev_mode = detect_and_configure_gpu_device()
            compute_type = "float16" if dev_mode == "cuda" else "int8"
            self.stt_model = WhisperModel(model_size, device=dev_mode, compute_type=compute_type)
            self._available = True
            logger.info(f"[Voice:local] Whisper {model_size} 就绪 ({dev_mode})")
        except ImportError:
            logger.warning("[Voice:local] faster_whisper 未安装: pip install faster-whisper")
        except Exception as e:
            logger.error(f"[Voice:local] Whisper 初始化失败: {e}")

        # TTS: 原生
        self._tts_engine = _get_native_tts_engine()

    def is_available(self) -> bool:
        return self._available and self.stt_model is not None

    def speak(self, text: str) -> bytes | None:
        _native_tts_speak(self._tts_engine, text)
        return None

    def transcribe(self, wav_data: bytes) -> str:
        if not self.stt_model:
            return ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
                f.write(wav_data)
                temp_path = f.name
            segments, info = self.stt_model.transcribe(temp_path, beam_size=5)
            text = "".join([s.text for s in segments])
            os.remove(temp_path)
            return text.strip()
        except Exception as e:
            logger.error(f"[Voice:local] STT 错误: {e}")
            return ""


# ══════════════════════════════════════════════════════════════
# 引擎 3: 百度语音 API（online）
# ══════════════════════════════════════════════════════════════


class BaiduVoiceEngine(VoiceEngine):
    """百度语音 API 引擎 — 在线识别与合成。"""

    name = "baidu"
    display_name = "百度语音 (Baidu)"
    category = "online"
    requires_api_key = True

    def __init__(self):
        self.client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        try:
            from aip import AipSpeech
            app_id = config_loader.get("api.baidu.app_id") or os.getenv("BAIDU_APP_ID")
            api_key = config_loader.get("api.baidu.api_key") or os.getenv("BAIDU_API_KEY")
            secret_key = config_loader.get("api.baidu.secret_key") or os.getenv("BAIDU_SECRET_KEY")
            if app_id and api_key and secret_key and "YOUR_" not in str(app_id):
                self.client = AipSpeech(app_id, api_key, secret_key)
                self._available = True
                logger.info("[Voice:baidu] 百度语音 API 就绪")
            else:
                logger.warning("[Voice:baidu] 百度 API Key 未配置")
        except ImportError:
            logger.warning("[Voice:baidu] baidu-aip 未安装: pip install baidu-aip")

    def is_available(self) -> bool:
        return self._available and self.client is not None

    def speak(self, text: str) -> bytes | None:
        if not self.client:
            return None
        try:
            result = self.client.synthesis(text, 'zh', 1, {'vol': 5, 'per': 4})
            if not isinstance(result, dict):
                return result
            logger.error(f"[Voice:baidu] TTS 错误: {result}")
        except Exception as e:
            logger.error(f"[Voice:baidu] TTS 异常: {e}")
        return None

    def transcribe(self, wav_data: bytes) -> str:
        if not self.client:
            return ""
        try:
            res = self.client.asr(wav_data, 'wav', 16000, {'dev_pid': 1537})
            if res.get('err_no') == 0:
                return res.get('result', [""])[0]
            logger.error(f"[Voice:baidu] ASR 错误: {res}")
        except Exception as e:
            logger.error(f"[Voice:baidu] ASR 异常: {e}")
        return ""


# ══════════════════════════════════════════════════════════════
# 引擎 4: Google Cloud Speech API（online）
# ══════════════════════════════════════════════════════════════


class GoogleCloudVoiceEngine(VoiceEngine):
    """Google Cloud Speech-to-Text + Text-to-Speech API。"""

    name = "google"
    display_name = "Google Cloud"
    category = "online"
    requires_api_key = True

    def __init__(self):
        self._stt_client = None
        self._tts_client = None
        self._available = False
        self._init_clients()

    def _init_clients(self):
        # STT
        try:
            from google.cloud import speech
            self._stt_client = speech.SpeechClient()
            logger.info("[Voice:google] Google Cloud STT 就绪")
        except ImportError:
            logger.debug("[Voice:google] google-cloud-speech 未安装")
        except Exception as e:
            logger.debug(f"[Voice:google] STT 初始化失败: {e}")

        # TTS
        try:
            from google.cloud import texttospeech
            self._tts_client = texttospeech.TextToSpeechClient()
            logger.info("[Voice:google] Google Cloud TTS 就绪")
        except ImportError:
            logger.debug("[Voice:google] google-cloud-texttospeech 未安装")
        except Exception as e:
            logger.debug(f"[Voice:google] TTS 初始化失败: {e}")

        self._available = self._stt_client is not None

    def is_available(self) -> bool:
        return self._available

    def speak(self, text: str) -> bytes | None:
        if not self._tts_client or not text:
            return None
        try:
            from google.cloud import texttospeech
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="zh-CN",
                ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            response = self._tts_client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            return response.audio_content
        except Exception as e:
            logger.error(f"[Voice:google] TTS 错误: {e}")
            return None

    def transcribe(self, wav_data: bytes) -> str:
        if not self._stt_client:
            return ""
        try:
            from google.cloud import speech
            audio = speech.RecognitionAudio(content=wav_data)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="zh-CN",
            )
            response = self._stt_client.recognize(config=config, audio=audio)
            for result in response.results:
                return result.alternatives[0].transcript
            return ""
        except Exception as e:
            logger.error(f"[Voice:google] STT 错误: {e}")
            return ""


# ══════════════════════════════════════════════════════════════
# 引擎 5: Azure Speech API（online）
# ══════════════════════════════════════════════════════════════


class AzureVoiceEngine(VoiceEngine):
    """Microsoft Azure Speech SDK — STT + TTS。"""

    name = "azure"
    display_name = "Microsoft Azure"
    category = "online"
    requires_api_key = True

    def __init__(self):
        self._speech_config = None
        self._available = False
        self._init()

    def _init(self):
        try:
            import azure.cognitiveservices.speech as speechsdk
            key = os.getenv("AZURE_SPEECH_KEY")
            region = os.getenv("AZURE_SPEECH_REGION", "eastus")
            if key and "YOUR_" not in key:
                self._speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
                self._speech_config.speech_recognition_language = "zh-CN"
                self._available = True
                logger.info("[Voice:azure] Azure Speech 就绪")
            else:
                logger.warning("[Voice:azure] AZURE_SPEECH_KEY 未配置")
        except ImportError:
            logger.warning("[Voice:azure] azure-cognitiveservices-speech 未安装")
        except Exception as e:
            logger.debug(f"[Voice:azure] 初始化失败: {e}")

    def is_available(self) -> bool:
        return self._available and self._speech_config is not None

    def speak(self, text: str) -> bytes | None:
        if not self._speech_config or not text:
            return None
        try:
            import azure.cognitiveservices.speech as speechsdk
            self._speech_config.speech_synthesis_voice_name = "zh-CN-XiaoxiaoNeural"
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=self._speech_config)
            result = synthesizer.speak_text_async(text).get()
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return result.audio_data
            logger.error(f"[Voice:azure] TTS 失败: {result.reason}")
        except Exception as e:
            logger.error(f"[Voice:azure] TTS 异常: {e}")
        return None

    def transcribe(self, wav_data: bytes) -> str:
        if not self._speech_config:
            return ""
        try:
            import azure.cognitiveservices.speech as speechsdk
            # Azure 需要音频流输入
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
                f.write(wav_data)
                temp_path = f.name
            audio_config = speechsdk.audio.AudioConfig(filename=temp_path)
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=self._speech_config, audio_config=audio_config
            )
            result = recognizer.recognize_once_async().get()
            os.remove(temp_path)
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                return result.text
            logger.error(f"[Voice:azure] STT 失败: {result.reason}")
            return ""
        except Exception as e:
            logger.error(f"[Voice:azure] STT 异常: {e}")
            return ""


# ══════════════════════════════════════════════════════════════
# VoiceService — 统一调度层
# ══════════════════════════════════════════════════════════════


# 引擎注册表（按优先级：原生 → 本地模型 → 厂商云API）
ENGINE_REGISTRY = [
    ("native", NativeVoiceEngine),
    ("local", WhisperVoiceEngine),
    ("baidu", BaiduVoiceEngine),
    ("google", GoogleCloudVoiceEngine),
    ("azure", AzureVoiceEngine),
]

# 兼容旧配置名：system → native, online → baidu
LEGACY_MODE_MAP = {
    "system": "native",
    "online": "baidu",
}


class VoiceService:
    """Butler 语音服务主控。管理多引擎、录音、TTS 播放、自动降级。"""

    def __init__(self, on_command_received: Callable[[str], None],
                 ui_print_func: Callable,
                 on_status_change: Optional[Callable[[bool], None]] = None):
        self.on_command_received = on_command_received
        self.ui_print = ui_print_func
        self.on_status_change = on_status_change
        self.is_listening = False
        self.voice_available = True

        # 加载用户配置的语音模式
        raw_mode = config_loader.get("voice.mode", "auto")
        self.mode = LEGACY_MODE_MAP.get(raw_mode, raw_mode)

        # 初始化所有引擎
        self.engines: Dict[str, VoiceEngine] = {}
        for name, engine_cls in ENGINE_REGISTRY:
            try:
                self.engines[name] = engine_cls()
            except Exception as e:
                logger.error(f"[Voice] 引擎 {name} 初始化异常: {e}")
                self.engines[name] = VoiceEngine()

        # 自动选择或验证用户选择
        self._resolve_mode()

        # 检测硬件
        self._test_hardware()

        self.ACTIVATION_SOUND_FILE = asset_loader.resolve_path("audio://activate.wav")

    def _resolve_mode(self):
        """解析语音模式：auto 自动选择 / 手动指定验证。"""
        if self.mode == "auto":
            for name, _ in ENGINE_REGISTRY:
                engine = self.engines.get(name)
                if engine and engine.is_available():
                    self.mode = name
                    logger.info(f"[Voice] 自动选择引擎: {name} ({engine.display_name})")
                    return
            self.mode = "text"
            logger.warning("[Voice] 所有语音引擎不可用，降级为文本模式")
        else:
            engine = self.engines.get(self.mode)
            if engine and engine.is_available():
                logger.info(f"[Voice] 使用用户指定引擎: {self.mode}")
            else:
                logger.warning(f"[Voice] 指定引擎 {self.mode} 不可用，尝试自动降级")
                self.mode = "auto"
                self._resolve_mode()

    def _test_hardware(self):
        """检测麦克风和扬声器。"""
        mic_ok = AudioRecorder.has_microphone()
        speaker_ok = False
        try:
            import pygame
            pygame.mixer.init()
            speaker_ok = True
        except Exception:
            try:
                import sounddevice as sd
                sd.query_devices()
                speaker_ok = True
            except Exception:
                pass

        if not mic_ok or not speaker_ok or self.mode == "text":
            self.voice_available = False
            reason = []
            if not mic_ok:
                reason.append("未检测到麦克风")
            if not speaker_ok:
                reason.append("扬声器不可用")
            if self.mode == "text":
                reason.append("无可用语音引擎")
            msg = f"语音模块不可用 ({', '.join(reason)})，已降级为文本模式。"
            logger.warning(f"[Voice] {msg}")
            threading.Timer(1.0, lambda: self.ui_print(f"⚠️ {msg}", tag="system_message")).start()
        else:
            engine = self.get_engine()
            logger.info(f"[Voice] 就绪: {engine.display_name} (模式: {self.mode})")

    def get_engine(self) -> VoiceEngine:
        """获取当前活跃引擎，不可用时自动降级。"""
        engine = self.engines.get(self.mode)
        if engine and engine.is_available():
            return engine
        for name, _ in ENGINE_REGISTRY:
            e = self.engines.get(name)
            if e and e.is_available():
                logger.warning(f"[Voice] 引擎 {self.mode} 不可用，降级到 {name}")
                return e
        return VoiceEngine()

    def get_available_engines(self) -> list:
        """列出所有引擎及状态。"""
        result = []
        for name, _ in ENGINE_REGISTRY:
            engine = self.engines.get(name)
            result.append({
                "name": name,
                "display_name": engine.display_name if engine else name,
                "available": engine.is_available() if engine else False,
                "active": name == self.mode,
                "category": engine.category if engine else "native",
                "requires_install": engine.requires_install if engine else False,
                "requires_api_key": engine.requires_api_key if engine else False,
            })
        return result

    # ── 语音合成 (TTS) ──

    def speak(self, text: str):
        """语音播报。"""
        if not self.voice_available:
            self.ui_print(text, tag='ai_response')
            return

        engine = self.get_engine()
        audio_bytes = engine.speak(text)

        # 引擎返回 audio bytes（如百度/Azure/Google TTS）则播放
        if audio_bytes:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                f.write(audio_bytes)
                temp_file = f.name
            self._play_audio(temp_file)
            os.remove(temp_file)
        # 返回 None 说明引擎内部已直接播放（如原生 pyttsx3）

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
            logger.warning(f"音频播放失败: {e}")

    def play_activation_sound(self):
        if self.voice_available and os.path.exists(self.ACTIVATION_SOUND_FILE):
            self._play_audio(self.ACTIVATION_SOUND_FILE)

    # ── 语音识别 (STT) ──

    def start_listening(self):
        """开始语音监听。"""
        if not self.voice_available:
            self.ui_print("⚠️ 语音模块不可用，请使用纯文本控制。", tag='error')
            return
        if self.is_listening:
            return
        self.is_listening = True
        if self.on_status_change:
            self.on_status_change(True)
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()

    def stop_listening(self):
        self.is_listening = False
        if self.on_status_change:
            self.on_status_change(False)

    def _listen_loop(self):
        """录音 → 识别 → 回调。"""
        try:
            self.ui_print(f"正在录音 ({self.get_engine().display_name})...", tag='system_message')
            self.play_activation_sound()

            wav_data = AudioRecorder.record(
                is_listening_fn=lambda: self.is_listening,
                on_start=lambda: logger.debug("检测到语音活动"),
            )

            if not wav_data:
                self.ui_print("未检测到语音输入。", tag='error')
                return

            self.ui_print("正在识别...", tag='system_message')
            engine = self.get_engine()
            result_text = engine.transcribe(wav_data)

            if result_text:
                self.ui_print(f"识别到指令: {result_text}", tag='user_input')
                self.on_command_received(result_text)
            else:
                self.ui_print("未能识别语音内容。", tag='error')

        except Exception as e:
            self.ui_print(f"语音识别错误: {e}", tag='error')
            logger.exception("[Voice] Listen loop error")
        finally:
            self.is_listening = False
            if self.on_status_change:
                self.on_status_change(False)

    # ── 引擎切换 ──

    def set_voice_mode(self, mode: str) -> bool:
        """切换语音模式。mode: native/local/baidu/google/azure/auto/text"""
        # 兼容旧配置名
        mode = LEGACY_MODE_MAP.get(mode, mode)

        if mode == "text":
            self.mode = "text"
            self.voice_available = False
            self.ui_print("已切换为纯文本模式。", tag='system_message')
            config_loader.save({"voice": {"mode": "text"}})
            return True

        if mode == "auto":
            self.mode = "auto"
            self._resolve_mode()
            self.voice_available = (self.mode != "text")
            engine = self.get_engine()
            self.ui_print(f"自动选择引擎: {engine.display_name}", tag='system_message')
            config_loader.save({"voice": {"mode": "auto"}})
            return True

        engine = self.engines.get(mode)
        if engine and engine.is_available():
            self.mode = mode
            self.voice_available = True
            config_loader.save({"voice": {"mode": mode}})
            self.ui_print(f"已切换语音引擎: {engine.display_name}", tag='system_message')
            logger.info(f"[Voice] 切换到: {mode}")
            return True
        else:
            available = [n for n, _ in ENGINE_REGISTRY
                         if self.engines.get(n) and self.engines[n].is_available()]
            self.ui_print(f"引擎 {mode} 不可用。可用: {', '.join(available)}", tag='error')
            return False

    def get_status(self) -> dict:
        """获取语音服务状态。"""
        engine = self.get_engine()
        return {
            "mode": self.mode,
            "available": self.voice_available,
            "current_engine": engine.display_name,
            "engines": self.get_available_engines(),
            "platform": PLATFORM,
        }
