"""
Butler 语音服务 — 三引擎架构

三套语音引擎，用户可选，自动降级：
  system  → Windows/macOS/Linux 系统自带语音识别 (零安装)
  local   → Faster-Whisper AI 模型 (离线高精度)
  online  → 百度/讯飞/Google 第三方 API (最佳体验)

录音层统一使用 sounddevice，不再依赖 Picovoice。
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
from typing import Optional, Callable, Dict, Any
from dotenv import load_dotenv
from package.core_utils.log_manager import LogManager
from package.core_utils.config_loader import config_loader
from butler.core.asset_loader import asset_loader

logger = LogManager.get_logger(__name__)

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


def _is_windows() -> bool:
    return platform.system() == "Windows"


# ══════════════════════════════════════════════════════════════
# 统一录音层 — 替代 pvrecorder，零外部依赖
# ══════════════════════════════════════════════════════════════


class AudioRecorder:
    """
    统一录音模块。
    优先 sounddevice，备选 pyaudio，兜底 Windows MCI。
    不再依赖 Picovoice / pvrecorder。
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1
    SILENCE_THRESHOLD = 500
    MAX_SILENCE_FRAMES = 40
    MAX_RECORD_FRAMES = 300

    @staticmethod
    def list_devices() -> list:
        """列出可用录音设备"""
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
        """检测是否有可用麦克风"""
        return len(AudioRecorder.list_devices()) > 0

    @staticmethod
    def record(is_listening_fn: Callable[[], bool] = lambda: True,
               on_start: Callable = None) -> bytes | None:
        """
        录音直到检测到静音。
        :param is_listening_fn: 返回是否继续录音的函数
        :param on_start: 录音开始回调
        :return: WAV 音频数据 bytes，或 None
        """
        audio_data = AudioRecorder._record_sounddevice(is_listening_fn, on_start)
        if audio_data is None:
            audio_data = AudioRecorder._record_pyaudio(is_listening_fn, on_start)
        if audio_data is None:
            logger.error("所有录音方式均失败")
            return None
        return AudioRecorder._to_wav(audio_data)

    @staticmethod
    def _record_sounddevice(is_listening_fn, on_start) -> list | None:
        """使用 sounddevice 录音"""
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
                # 等待录音完成
                start_time = time.time()
                while is_listening_fn():
                    time.sleep(0.05)
                    if started and silence_frames > AudioRecorder.MAX_SILENCE_FRAMES:
                        break
                    if time.time() - start_time > 30:  # 最长 30 秒
                        break

            return frames if frames else None

        except Exception as e:
            logger.debug(f"sounddevice 录音失败: {e}")
            return None

    @staticmethod
    def _record_pyaudio(is_listening_fn, on_start) -> list | None:
        """使用 pyaudio 录音（备选）"""
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
        """将 PCM 数据转为 WAV bytes"""
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
    """语音引擎基类"""

    name: str = "base"
    display_name: str = "Base Engine"
    requires_install: bool = False
    requires_api_key: bool = False

    def is_available(self) -> bool:
        """检测此引擎是否可用"""
        return True

    def speak(self, text: str):
        """语音合成，返回 audio bytes 或 None（内部播放）"""
        pass

    def transcribe(self, wav_data: bytes) -> str:
        """语音识别，返回文本"""
        return ""


# ══════════════════════════════════════════════════════════════
# 引擎 1: Windows 系统自带 (system)
# STT: Windows Speech Recognition API
# TTS: Windows SAPI (pyttsx3)
# 零额外安装，零模型下载
# ══════════════════════════════════════════════════════════════


class WindowsSystemVoiceEngine(VoiceEngine):
    """Windows 系统自带语音引擎 — 零安装、零配置"""

    name = "system"
    display_name = "系统自带 (Windows SAPI)"

    def __init__(self):
        self._sr = None
        self._tts_engine = None
        self._available = False
        self._init()

    def _init(self):
        # STT: speech_recognition 库调用 Windows SAPI
        try:
            import speech_recognition as sr
            self._sr = sr
            # 测试 SAPI 是否可用
            recognizer = sr.Recognizer()
            self._available = True
            logger.info("[Voice:system] Windows SAPI STT 就绪")
        except ImportError:
            logger.warning("[Voice:system] speech_recognition 未安装: pip install SpeechRecognition")
        except Exception as e:
            logger.warning(f"[Voice:system] SAPI STT 初始化失败: {e}")

        # TTS: pyttsx3 调用 Windows SAPI
        try:
            import pyttsx3
            self._tts_engine = pyttsx3.init()
            # 设置中文语音（如果可用）
            voices = self._tts_engine.getProperty('voices')
            for v in voices:
                if 'chinese' in v.name.lower() or 'zh' in v.id.lower():
                    self._tts_engine.setProperty('voice', v.id)
                    break
            self._tts_engine.setProperty('rate', 180)
            self._tts_engine.setProperty('volume', 0.9)
            logger.info("[Voice:system] Windows SAPI TTS 就绪")
        except Exception as e:
            logger.warning(f"[Voice:system] SAPI TTS 初始化失败: {e}")

    def is_available(self) -> bool:
        return self._available and self._sr is not None

    def speak(self, text: str):
        if self._tts_engine:
            try:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
            except Exception as e:
                logger.error(f"[Voice:system] TTS 错误: {e}")

    def transcribe(self, wav_data: bytes) -> str:
        if not self._sr:
            return ""
        try:
            recognizer = self._sr.Recognizer()
            # 将 WAV bytes 写入临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
                f.write(wav_data)
                temp_path = f.name

            with self._sr.AudioFile(temp_path) as source:
                audio = recognizer.record(source)

            os.remove(temp_path)

            # 使用 Windows SAPI 识别（中文）
            try:
                text = recognizer.recognize_sphinx(audio)  # CMU Sphinx（离线）
                return text
            except Exception:
                pass

            # 降级：尝试 Google 免费 API（需要网络，但不需要 Key）
            try:
                text = recognizer.recognize_google(audio, language="zh-CN")
                return text
            except Exception:
                pass

            return ""
        except Exception as e:
            logger.error(f"[Voice:system] STT 错误: {e}")
            return ""


# ══════════════════════════════════════════════════════════════
# 引擎 2: AI 本地模型 (local)
# STT: Faster-Whisper
# TTS: pyttsx3
# ══════════════════════════════════════════════════════════════


class LocalVoiceEngine(VoiceEngine):
    """本地 AI 模型语音引擎 — Faster-Whisper + pyttsx3"""

    name = "local"
    display_name = "AI 模型 (Faster-Whisper)"
    requires_install = True

    def __init__(self):
        self.stt_model = None
        self.tts_engine = None
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

        # TTS: pyttsx3
        try:
            import pyttsx3
            self.tts_engine = pyttsx3.init()
            voices = self.tts_engine.getProperty('voices')
            for v in voices:
                if 'chinese' in v.name.lower() or 'zh' in v.id.lower():
                    self.tts_engine.setProperty('voice', v.id)
                    break
            self.tts_engine.setProperty('rate', 180)
            logger.info("[Voice:local] pyttsx3 TTS 就绪")
        except Exception as e:
            logger.warning(f"[Voice:local] TTS 初始化失败: {e}")

    def is_available(self) -> bool:
        return self._available and self.stt_model is not None

    def speak(self, text: str):
        if self.tts_engine:
            try:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except Exception as e:
                logger.error(f"[Voice:local] TTS 错误: {e}")

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
# 引擎 3: 第三方 API (online)
# STT: 百度 ASR
# TTS: 百度 TTS
# ══════════════════════════════════════════════════════════════


class BaiduVoiceEngine(VoiceEngine):
    """百度语音 API 引擎"""

    name = "online"
    display_name = "第三方 API (百度语音)"
    requires_api_key = True

    def __init__(self):
        self.client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        try:
            from aip import AipSpeech
            app_id = config_loader.get("api.baidu.app_id")
            api_key = config_loader.get("api.baidu.api_key")
            secret_key = config_loader.get("api.baidu.secret_key")

            if app_id and api_key and secret_key and "YOUR_" not in str(app_id):
                self.client = AipSpeech(app_id, api_key, secret_key)
                self._available = True
                logger.info("[Voice:online] 百度语音 API 就绪")
            else:
                logger.warning("[Voice:online] 百度 API Key 未配置")
        except ImportError:
            logger.warning("[Voice:online] baidu-aip 未安装: pip install baidu-aip")

    def is_available(self) -> bool:
        return self._available and self.client is not None

    def speak(self, text: str) -> bytes | None:
        if not self.client:
            return None
        try:
            result = self.client.synthesis(text, 'zh', 1, {'vol': 5, 'per': 4})
            if not isinstance(result, dict):
                return result
            logger.error(f"[Voice:online] TTS 错误: {result}")
        except Exception as e:
            logger.error(f"[Voice:online] TTS 异常: {e}")
        return None

    def transcribe(self, wav_data: bytes) -> str:
        if not self.client:
            return ""
        try:
            res = self.client.asr(wav_data, 'wav', 16000, {'dev_pid': 1537})
            if res.get('err_no') == 0:
                return res.get('result', [""])[0]
            logger.error(f"[Voice:online] ASR 错误: {res}")
        except Exception as e:
            logger.error(f"[Voice:online] ASR 异常: {e}")
        return ""


# ══════════════════════════════════════════════════════════════
# VoiceService — 统一调度层
# ══════════════════════════════════════════════════════════════


class VoiceService:
    """
    Butler 语音服务主控。
    管理三套引擎、录音、TTS 播放、自动降级。
    """

    # 引擎注册表（按优先级排序）
    ENGINE_PRIORITY = ["system", "local", "online"]

    def __init__(self, on_command_received: Callable[[str], None],
                 ui_print_func: Callable,
                 on_status_change: Optional[Callable[[bool], None]] = None):
        self.on_command_received = on_command_received
        self.ui_print = ui_print_func
        self.on_status_change = on_status_change
        self.is_listening = False
        self.voice_available = True

        # 加载用户配置的语音模式
        self.mode = config_loader.get("voice.mode", "auto")

        # 初始化所有引擎
        self.engines: Dict[str, VoiceEngine] = {
            "system": WindowsSystemVoiceEngine(),
            "local": LocalVoiceEngine(),
            "online": BaiduVoiceEngine(),
        }

        # 自动选择或验证用户选择
        self._resolve_mode()

        # 检测硬件
        self._test_hardware()

        self.ACTIVATION_SOUND_FILE = asset_loader.resolve_path("audio://activate.wav")

    def _resolve_mode(self):
        """解析语音模式：auto 自动选择 / 手动指定验证"""
        if self.mode == "auto":
            # 按优先级自动选择第一个可用引擎
            for name in self.ENGINE_PRIORITY:
                engine = self.engines.get(name)
                if engine and engine.is_available():
                    self.mode = name
                    logger.info(f"[Voice] 自动选择引擎: {name} ({engine.display_name})")
                    return
            # 全部不可用
            self.mode = "text"
            logger.warning("[Voice] 所有语音引擎不可用，降级为文本模式")
        else:
            # 用户手动指定，验证是否可用
            engine = self.engines.get(self.mode)
            if engine and engine.is_available():
                logger.info(f"[Voice] 使用用户指定引擎: {self.mode}")
            else:
                logger.warning(f"[Voice] 指定引擎 {self.mode} 不可用，尝试自动降级")
                self.mode = "auto"
                self._resolve_mode()

    def _test_hardware(self):
        """检测麦克风和扬声器"""
        mic_ok = AudioRecorder.has_microphone()
        speaker_ok = False

        # 检测扬声器
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
        """获取当前活跃引擎"""
        engine = self.engines.get(self.mode)
        if engine and engine.is_available():
            return engine
        # 降级
        for name in self.ENGINE_PRIORITY:
            e = self.engines.get(name)
            if e and e.is_available():
                logger.warning(f"[Voice] 引擎 {self.mode} 不可用，降级到 {name}")
                return e
        return VoiceEngine()  # 空引擎

    def get_available_engines(self) -> list[dict]:
        """列出所有引擎及状态"""
        result = []
        for name in self.ENGINE_PRIORITY:
            engine = self.engines.get(name)
            result.append({
                "name": name,
                "display_name": engine.display_name if engine else name,
                "available": engine.is_available() if engine else False,
                "active": name == self.mode,
                "requires_install": engine.requires_install if engine else False,
                "requires_api_key": engine.requires_api_key if engine else False,
            })
        return result

    # ── 语音合成 (TTS) ──

    def speak(self, text: str):
        """语音播报"""
        if not self.voice_available:
            self.ui_print(text, tag='ai_response')
            return

        engine = self.get_engine()
        audio_bytes = engine.speak(text)

        # 如果引擎返回 audio bytes（如百度 TTS），播放它
        if audio_bytes:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                f.write(audio_bytes)
                temp_file = f.name
            self._play_audio(temp_file)
            os.remove(temp_file)
        # 如果返回 None，说明引擎内部已直接播放（如 pyttsx3）

    def _play_audio(self, file_path: str):
        """播放音频文件"""
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
        """播放激活提示音"""
        if self.voice_available and os.path.exists(self.ACTIVATION_SOUND_FILE):
            self._play_audio(self.ACTIVATION_SOUND_FILE)

    # ── 语音识别 (STT) ──

    def start_listening(self):
        """开始语音监听"""
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
        """停止语音监听"""
        self.is_listening = False
        if self.on_status_change:
            self.on_status_change(False)

    def _listen_loop(self):
        """录音 → 识别 → 回调"""
        try:
            self.ui_print(f"正在录音 ({self.get_engine().display_name})...", tag='system_message')
            self.play_activation_sound()

            # 使用统一录音层
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
        """
        切换语音模式。
        :param mode: "system" / "local" / "online" / "auto" / "text"
        :return: 是否切换成功
        """
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
            available = [n for n in self.ENGINE_PRIORITY
                         if self.engines.get(n) and self.engines[n].is_available()]
            self.ui_print(f"引擎 {mode} 不可用。可用: {', '.join(available)}", tag='error')
            return False

    def get_status(self) -> dict:
        """获取语音服务状态"""
        engine = self.get_engine()
        return {
            "mode": self.mode,
            "available": self.voice_available,
            "current_engine": engine.display_name,
            "engines": self.get_available_engines(),
        }
