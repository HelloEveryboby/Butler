import os
import sys
import time
import importlib
import importlib.util
import datetime
import subprocess
import json
import tkinter as tk
from tkinter import messagebox
import requests
import shutil
import tempfile
import threading
import concurrent.futures
from functools import lru_cache
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv
import numpy as np
import heapq
import math
import cv2
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 假设这些模块存在
from package.thread import process_tasks
from .binary_extensions import binary_extensions
from package.virtual_keyboard import VirtualKeyboard
from package.markdown_converter import convert_to_markdown
from package.log_manager import LogManager
from butler.CommandPanel import CommandPanel
from plugin.PluginManager import PluginManager
from . import algorithms
from local_interpreter.interpreter import Interpreter
from plugin.long_memory.deepseek_long_memory import DeepSeekLongMemory
from plugin.long_memory.chroma_long_memory import SQLiteLongMemory
from .usb_screen import USBScreen
from .resource_manager import ResourceManager, PerformanceMode
from package.algorithm import read_file_list, hybrid_sort_with_progress

class Jarvis:
    def __init__(self, root, usb_screen=None):
        self.root = root
        self.usb_screen = usb_screen
        self.resource_manager = ResourceManager()
        self.display_mode = 'host'  # 'host', 'usb', or 'both'
        load_dotenv()
        # 替换为DeepSeek API密钥
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        self.engine = None # Will be initialized in speak()
        self.logging = LogManager.get_logger(__name__)
        self.plugin_manager = PluginManager("plugin")
        self._initialize_long_memory()

        base_dir = os.path.dirname(__file__)
        self.JARVIS_AUDIO_FILE = os.path.join(base_dir, "resources", "jarvis.wav")

        # Load prompts from the JSON file
        try:
            prompts_path = os.path.join(base_dir, "prompts.json")
            with open(prompts_path, 'r', encoding='utf-8') as f:
                self.prompts = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logging.error(f"Failed to load prompts: {e}")
            # Fallback to empty prompts if loading fails
            self.prompts = {}

        # Paths for temporary files are relative to the current working directory
        self.OUTPUT_FILE = "./temp.wav"

        try:
            mapping_path = os.path.join(base_dir, "program_mapping.json")
            with open(mapping_path, 'r', encoding='utf-8') as f:
                self.program_mapping = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logging.error(f"Failed to load program mapping: {e}")
            self.program_mapping = {}

        self.conversation_history = []
        self.running = True
        self.matched_program = None
        self.panel = None
        self.MAX_HISTORY_MESSAGES = 10
        self.interpreter = Interpreter()
        self.program_folder = []
        self.is_listening = False
        self.speech_recognizer = None
        self.voice_mode = 'offline'  # 'offline' or 'online'
        
    def set_panel(self, panel):
        self.panel = panel

    def ui_print(self, message, tag='ai_response', response_id=None):
        """Prints a message to the UI and/or USB screen, with support for response IDs."""
        print(message)  # Keep console output for logging/debugging

        if self.display_mode in ('host', 'both'):
            if self.panel:
                # If it's the start of a new response, use a different method
                if tag == 'ai_response_start':
                    # This will create the initial text block
                    self.panel.append_to_history(message, 'ai_response', response_id=response_id)
                else:
                    self.panel.append_to_history(message, tag) # Fallback for non-streaming messages

        if self.display_mode in ('usb', 'both'):
            if self.usb_screen:
                self.usb_screen.display(message, clear_screen=True)

    # 核心功能
    def preprocess(self, text):
        """
        使用DeepSeek API将用户输入文本转换为结构化的意图和实体。
        """
        # 从加载的配置中获取系统提示
        system_prompt = self.prompts.get("nlu_intent_extraction", {}).get("prompt")
        if not system_prompt:
            self.logging.error("NLU intent extraction prompt not found. Using fallback.")
            # Provide a minimal fallback prompt to avoid crashing
            system_prompt = "You are an NLU assistant. Return JSON with 'intent' and 'entities'."

        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }
        # 构造发送给API的消息列表
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)

        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result_text = response.json()['choices'][0]['message']['content']

            # 清理和解析JSON
            # LLM有时会返回被markdown代码块包围的JSON
            if result_text.strip().startswith("```json"):
                result_text = result_text.strip()[7:-4].strip()

            return json.loads(result_text)
        except requests.exceptions.RequestException as e:
            self.ui_print(f"DeepSeek API 请求失败: {e}")
            return {"intent": "unknown", "entities": {"error": str(e)}}
        except json.JSONDecodeError as e:
            self.ui_print(f"无法解析来自API的JSON响应: {e}")
            self.logging.error(f"原始响应文本: {result_text}")
            return {"intent": "unknown", "entities": {"error": "Invalid JSON response"}}
        except (KeyError, IndexError) as e:
            self.ui_print(f"API响应格式不符合预期: {e}")
            return {"intent": "unknown", "entities": {"error": "Unexpected API response format"}}

    def generate_response(self, text):
        # 使用DeepSeek API
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }
        # 从加载的配置中获取系统提示
        system_prompt = self.prompts.get("general_response", {}).get("prompt")
        if not system_prompt:
            self.logging.error("General response prompt not found. Using fallback.")
            system_prompt = "You are a helpful AI assistant."

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "max_tokens": 150,
            "temperature": 0.5
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            self.ui_print(f"DeepSeek API调用失败: {e}")
            return "抱歉，我暂时无法回答这个问题。"  # 出错时返回默认响应

    def speak(self, audio):
        self.ui_print(audio, tag='ai_response')

        # 将助手的响应添加到历史记录
        self.conversation_history.append({"role": "assistant", "content": audio})
        # 裁剪历史记录，防止其无限增长
        if len(self.conversation_history) > self.MAX_HISTORY_MESSAGES:
            self.conversation_history = self.conversation_history[-self.MAX_HISTORY_MESSAGES:]

        try:
            import pyttsx3
            if not self.engine:
                self.engine = pyttsx3.init()

            self.engine.say(audio)
            self.engine.runAndWait()
        except Exception as e:
            self.ui_print(f"音频处理(TTS)出错: {e}", tag='error')
            self.logging.warning(f"Could not initialize or use pyttsx3 for TTS: {e}")

    def start_listening(self):
        """
        Starts the offline voice recognition system.
        This will run in a background thread.
        """
        if self.is_listening:
            return

        self.is_listening = True

        if self.voice_mode == 'offline':
            self.ui_print("正在启动离线语音识别引擎...", tag='system_message')
            target_loop = self._offline_listen_loop
        else: # 'online'
            self.ui_print("正在启动在线语音识别引擎...", tag='system_message')
            target_loop = self._online_listen_loop

        # Start the listening process in a separate thread
        self.listen_thread = threading.Thread(target=target_loop)
        self.listen_thread.daemon = True
        self.listen_thread.start()

    def stop_listening(self):
        """
        Stops the offline voice recognition system.
        """
        if not self.is_listening:
            return

        self.is_listening = False
        # The thread will exit on its own when is_listening is False
        self.ui_print("正在停止离线语音识别...", tag='system_message')

    def _offline_listen_loop(self):
        """
        The main loop for offline wake word and command recognition.
        """
        porcupine_access_key = os.getenv("PICOVOICE_ACCESS_KEY")
        if not porcupine_access_key:
            self.ui_print("错误: 未设置PICOVOICE_ACCESS_KEY环境变量。", tag='error')
            self.ui_print("请在 https://console.picovoice.ai/ 注册免费账户并获取您的密钥。", tag='error')
            self.is_listening = False
            return

        vosk_model_path = "vosk-model-small-en-us-0.15"
        if not os.path.exists(vosk_model_path):
            self.ui_print(f"错误: Vosk模型未在 '{vosk_model_path}' 找到。", tag='error')
            self.ui_print("请从 https://alphacephei.com/vosk/models 下载模型并解压到此处。", tag='error')
            self.is_listening = False
            return

        try:
            from pvrecorder import PvRecorder
            import pvporcupine
            from vosk import Model, KaldiRecognizer

            keyword_paths = [pvporcupine.KEYWORD_PATHS["jarvis"]]
            porcupine = pvporcupine.create(
                access_key=porcupine_access_key,
                keyword_paths=keyword_paths
            )

            vosk_model = Model(vosk_model_path)

            self.ui_print("离线语音引擎已就绪，正在监听唤醒词 'Jarvis'...", tag='system_message')

            while self.is_listening:
                recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
                recorder.start()

                # Wake word detection loop
                while self.is_listening:
                    pcm = recorder.read()
                    result = porcupine.process(pcm)
                    if result >= 0:
                        self.ui_print("唤醒词 'Jarvis' 已检测!", tag='system_message')
                        # Play a sound to indicate wake word detected
                        # self.play_activation_sound() # You can implement this
                        recorder.stop()
                        break

                if not self.is_listening:
                    recorder.stop()
                    break

                # Command recognition
                self.ui_print("正在聆听指令...", tag='system_message')
                recognizer = KaldiRecognizer(vosk_model, 16000)

                # Use a new recorder for command recognition
                command_recorder = PvRecorder(device_index=-1, frame_length=512) # A more standard frame length
                command_recorder.start()

                # Simple silence detection logic
                silence_frames = 0
                max_silence_frames = 30 # about 3 seconds of silence

                while self.is_listening:
                    pcm_command = command_recorder.read()

                    if recognizer.AcceptWaveform(bytes(pcm_command)):
                        result_json = recognizer.Result()
                        result_text = json.loads(result_json).get("text", "")
                        if result_text:
                            self.ui_print(f"识别到的指令: {result_text}", tag='user_input')
                            # Safely update the GUI from the main thread
                            if self.panel:
                                self.root.after(0, self.panel.set_input_text, result_text)
                            self.handle_user_command(result_text, self.panel.programs if self.panel else {})
                        break # Go back to wake word listening
                    else:
                        partial_result = json.loads(recognizer.PartialResult())
                        if not partial_result.get("partial", ""):
                            silence_frames += 1
                        else:
                            silence_frames = 0

                    if silence_frames > max_silence_frames:
                        self.ui_print("未检测到指令 (超时)。", tag='system_message')
                        break

                command_recorder.stop()
                self.ui_print("返回等待唤醒词...", tag='system_message')

        except ImportError:
            self.ui_print("错误: 请安装 'pvporcupine', 'pvrecorder', 和 'vosk' 库。", tag='error')
        except Exception as e:
            self.ui_print(f"语音识别时发生错误: {e}", tag='error')
        finally:
            if 'porcupine' in locals() and porcupine is not None:
                porcupine.delete()
            if 'recorder' in locals() and recorder.is_recording:
                recorder.stop()
            if 'command_recorder' in locals() and command_recorder.is_recording:
                command_recorder.stop()
            self.is_listening = False
            self.ui_print("离线语音识别已停止。", tag='system_message')

    def _online_listen_loop(self):
        """
        The main loop for online (Azure) command recognition.
        """
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError:
            self.ui_print("错误: 请安装 'azure-cognitiveservices-speech' 库。", tag='error')
            self.is_listening = False
            return

        speech_key = os.getenv("AZURE_SPEECH_KEY")
        service_region = os.getenv("AZURE_SERVICE_REGION", "chinaeast2")

        if not speech_key or not service_region:
            self.ui_print("错误: 未设置AZURE_SPEECH_KEY或AZURE_SERVICE_REGION环境变量。", tag='error')
            self.is_listening = False
            return

        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
        speech_config.speech_recognition_language = "zh-CN"

        self.speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config)
        self.speech_recognizer.recognized.connect(self.on_speech_recognized)

        # Connect session events to handle stopping
        self.speech_recognizer.session_stopped.connect(lambda evt: self.stop_listening())
        self.speech_recognizer.canceled.connect(lambda evt: self.stop_listening())

        self.speech_recognizer.start_continuous_recognition()
        self.ui_print("在线语音引擎已就绪，正在聆听...", tag='system_message')

        # Keep the thread alive while listening
        while self.is_listening:
            time.sleep(0.5)

        self.speech_recognizer.stop_continuous_recognition()
        self.ui_print("在线语音识别已停止。", tag='system_message')

    def on_speech_recognized(self, event_args):
        query = event_args.result.text
        if query and self.panel:
            # Safely update the GUI from the main thread
            self.root.after(0, self.panel.set_input_text, query)
            # Now handle the command itself
            self.handle_user_command(query, self.panel.programs)

    def handle_user_command(self, command, programs):
        if command is None:
            return

        # Handle voice mode command
        if command.strip().startswith("/voice-mode"):
            parts = command.strip().split()
            if len(parts) == 2:
                mode = parts[1].lower()
                if mode in ['online', 'offline']:
                    if self.voice_mode != mode:
                        self.voice_mode = mode
                        self.ui_print(f"语音模式已切换到: {self.voice_mode}", tag='system_message')
                        # Restart listening to apply the new mode
                        self.stop_listening()
                        self.start_listening()
                    else:
                        self.ui_print(f"语音模式已经是: {self.voice_mode}", tag='system_message')
                else:
                    self.ui_print(f"无效的语音模式: {mode}。请使用 'online' 或 'offline'。", tag='error')
            else:
                self.ui_print("用法: /voice-mode [online|offline]", tag='error')
            return

        # Handle safety mode command
        if command.strip().startswith("/safety"):
            parts = command.strip().split()
            if len(parts) == 2:
                mode = parts[1].lower()
                if mode == 'on':
                    self.interpreter.safety_mode = True
                    self.ui_print("Safety mode enabled.", tag='system_message')
                elif mode == 'off':
                    self.interpreter.safety_mode = False
                    self.ui_print("Safety mode disabled.", tag='system_message')
                else:
                    self.ui_print(f"Invalid safety mode: {mode}. Use 'on' or 'off'.", tag='error')
            else:
                self.ui_print("Usage: /safety [on|off]", tag='error')
            return

        # Handle approve command
        if command.strip() == "/approve":
            if self.interpreter.last_code_for_approval:
                # The approval now also runs in a stream
                self.stream_interpreter_response(command, approved=True)
            else:
                self.ui_print("No code to approve.", tag='system_message')
            return

        # Handle OS mode command
        if command.strip().startswith("/os-mode"):
            parts = command.strip().split()
            if len(parts) == 2:
                mode = parts[1].lower()
                if mode == 'on':
                    self.interpreter.os_mode = True
                    self.ui_print("Operating System Mode enabled. Interpreter will now control the GUI.", tag='system_message')
                elif mode == 'off':
                    self.interpreter.os_mode = False
                    self.ui_print("Operating System Mode disabled.", tag='system_message')
                else:
                    self.ui_print(f"Invalid OS mode: {mode}. Use 'on' or 'off'.", tag='error')
            else:
                self.ui_print("Usage: /os-mode [on|off]", tag='error')
            return

        if command.strip().startswith("markdown "):
            parts = command.strip().split()
            if len(parts) > 1:
                file_path = parts[1]
                convert_to_markdown(file_path)
            else:
                self.ui_print("Usage: markdown <file_path>")
            return

        # Handle display mode command
        if command.strip().startswith("/display"):
            parts = command.strip().split()
            if len(parts) == 2:
                mode = parts[1].lower()
                if mode in ['host', 'usb', 'both']:
                    self.display_mode = mode
                    self.ui_print(f"Display mode set to: {self.display_mode}", tag='system_message')
                else:
                    self.ui_print(f"Invalid display mode: {mode}. Use 'host', 'usb', or 'both'.", tag='error')
            else:
                self.ui_print("Usage: /display [host|usb|both]", tag='error')
            return

        # Handle performance mode command
        if command.strip().startswith("/mode"):
            parts = command.strip().split()
            if len(parts) == 2:
                mode_str = parts[1].lower()
                if mode_str == 'eco':
                    self.resource_manager.set_mode(PerformanceMode.ECO)
                    self.ui_print("Performance mode set to ECO.", tag='system_message')
                elif mode_str == 'normal':
                    self.resource_manager.set_mode(PerformanceMode.NORMAL)
                    self.ui_print("Performance mode set to NORMAL.", tag='system_message')
                else:
                    self.ui_print(f"Invalid mode: {mode_str}. Use 'eco' or 'normal'.", tag='error')
            else:
                self.ui_print("Usage: /mode [eco|normal]", tag='error')
            return

        # New hybrid handler logic: Interpreter is the default.
        if command.strip().startswith("/legacy "):
            legacy_command = command.strip()[8:]
            self.ui_print(f"Jarvis (Legacy Mode): Processing '{legacy_command}'")
            self.conversation_history.append({"role": "user", "content": legacy_command})
            nlu_result = self.preprocess(legacy_command)
            intent = nlu_result.get("intent", "unknown")
            entities = nlu_result.get("entities", {})
            self._execute_legacy_intent(intent, entities, programs, legacy_command)
        else:
            # Default to the new streaming interpreter
            if self.interpreter.is_ready:
                self.stream_interpreter_response(command)
            else:
                # Use root.after to safely print from a non-main thread
                self.root.after(0, self.ui_print, "Jarvis: Interpreter is not ready. Please check API key.")

    def _execute_legacy_intent(self, intent, entities, programs, legacy_command):
        """Helper to execute legacy intent-based commands."""
        intent_handlers = {
            "sort_numbers": self._handle_sort_numbers,
            "find_number": self._handle_find_number,
            "calculate_fibonacci": self._handle_calculate_fibonacci,
            "edge_detect_image": self._handle_edge_detect_image,
            "text_similarity": self._handle_text_similarity,
            "open_program": self._handle_open_program,
            "exit": self._handle_exit,
        }
        handler = intent_handlers.get(intent)
        if handler:
            handler(entities=entities, programs=programs)
        else:
            plugin_found = False
            for plugin in self.plugin_manager.get_all_plugins():
                if plugin.get_name().lower() in legacy_command.lower():
                    plugin_result = self.plugin_manager.run_plugin(plugin.get_name(), legacy_command, entities)
                    if plugin_result.success:
                        self.speak(plugin_result.result)
                        plugin_found = True
                        break
            if not plugin_found:
                self.ui_print(f"未知指令或意图: {legacy_command}")
                self.logging.warning(f"未知指令或意图: {intent}")
                self.speak("抱歉，我不太理解您的意思，请换一种方式表达。")

    def stream_interpreter_response(self, command, approved=False):
        """
        Handles the streaming response from the interpreter and updates the UI.
        This method is run in a separate thread.
        """
        response_id = f"response_{time.time()}"

        # Schedule the initial message on the main thread
        self.root.after(0, self.ui_print, "Jarvis:", 'ai_response_start', response_id)

        stream = self.interpreter.run_approved_code() if approved else self.interpreter.run(command)

        for event_type, payload in stream:
            if not self.root:
                break # Stop if the window has been closed

            if event_type == "status":
                self.logging.info(f"Interpreter status: {payload}")
            elif event_type == "code_chunk":
                # Schedule the chunk to be appended on the main thread
                self.root.after(0, self.panel.append_to_response, payload, response_id)
            elif event_type == "result":
                # Schedule the final result to be appended
                final_text = f"\n\nOutput:\n{payload}\n\n"
                self.root.after(0, self.panel.append_to_response, final_text, response_id)

    def _handle_sort_numbers(self, entities, **kwargs):
        try:
            numbers = entities.get("numbers", [])
            if not numbers or not all(isinstance(n, (int, float)) for n in numbers):
                 self.speak("排序失败，请提供有效的数字列表。")
                 return
            sorted_nums = algorithms.quick_sort(numbers)
            self.speak(f"排序结果: {sorted_nums}")
        except Exception as e:
            self.speak(f"排序时发生错误: {e}")

    def _handle_find_number(self, entities, **kwargs):
        try:
            numbers = entities.get("numbers", [])
            target = entities.get("target")
            if not numbers or target is None:
                self.speak("查找失败，请提供数字列表和目标数字。")
                return

            numbers.sort()
            index = algorithms.binary_search(numbers, target)
            if index != -1:
                self.speak(f"数字 {target} 在排序后的位置是: {index}")
            else:
                self.speak(f"数字 {target} 不在数组中")
        except Exception as e:
            self.speak(f"查找时发生错误: {e}")

    def _handle_calculate_fibonacci(self, entities, **kwargs):
        try:
            n = entities.get("number")
            if n is None or not isinstance(n, int):
                self.speak("计算失败，请输入一个有效的整数。")
                return
            fib = algorithms.fibonacci(n)
            self.speak(f"斐波那契数列第{n}项是: {fib}")
        except Exception as e:
            self.speak(f"计算斐波那契数时出错: {e}")

    def _handle_edge_detect_image(self, entities, **kwargs):
        try:
            image_path = entities.get("path")
            if not image_path or not isinstance(image_path, str):
                self.speak("图像处理失败，请提供有效的路径。")
                return

            if os.path.exists(image_path):
                edges = algorithms.edge_detection(image_path)
                if edges is not None:
                    output_path = os.path.splitext(image_path)[0] + '_edges.jpg'
                    cv2.imwrite(output_path, edges)
                    self.speak(f"边缘检测完成，结果已保存到: {output_path}")
                else:
                    self.speak("图像处理失败，无法读取图片。")
            else:
                self.speak("找不到指定的图像文件。")
        except Exception as e:
            self.speak(f"图像处理时出错: {e}")

    def _handle_text_similarity(self, entities, **kwargs):
        try:
            text1 = entities.get("text1")
            text2 = entities.get("text2")
            if not text1 or not text2:
                self.speak("相似度计算失败，请提供两段文本。")
                return
            similarity = algorithms.text_cosine_similarity(text1, text2)
            self.speak(f"文本相似度是: {similarity:.2f}")
        except Exception as e:
            self.speak(f"计算相似度时出错: {e}")

    def _handle_open_program(self, entities, programs, **kwargs):
        program_name = entities.get("program_name")
        if not program_name:
            self.speak("无法打开程序，未指定程序名称。")
            return

        # 优先匹配程序映射表
        if program_name in self.program_mapping:
            self.execute_program(self.program_mapping[program_name])
            return

        # 其次匹配动态加载的程序
        if program_name in programs:
            self.execute_program(programs[program_name])
            return

        # 最后模糊匹配
        for key in self.program_mapping:
            if program_name in key:
                self.execute_program(self.program_mapping[key])
                return

        self.ui_print(f"未找到程序 '{program_name}'")
        self.speak(f"未找到程序 {program_name}")

    def _handle_exit(self, **kwargs):
        self.logging.info("程序已退出")
        self.speak("再见")
        self.running = False
        if self.is_listening:
            self.stop_listening()
        if self.root:
            self.root.quit()

    def open_programs(self, program_folder, external_folders=None):
        """
        加载、排序和缓存所有可用的程序模块。

        该函数首先尝试从 'file_list.txt' 加载模块列表和它们的优先级。
        如果该文件不存在，它会自动扫描指定的程序文件夹，为所有找到的模块
        生成一个默认的 'file_list.txt'，并赋予它们一个默认的优先级。

        然后，它使用 `hybrid_sort_with_progress` 算法根据优先级对模块进行排序，
        并按照排序后的顺序加载它们。

        Args:
            program_folder (str): 主程序包所在的文件夹 (例如, './package').
            external_folders (list, optional): 其他包含模块的文件夹列表. Defaults to None.

        Returns:
            dict: 一个字典，其中键是模块名称，值是已加载的模块对象。
        """
        programs_cache = {}
        programs = {}
        file_list_path = "file_list.txt"

        try:
            # 尝试读取现有的 file_list.txt
            module_list_with_priority = read_file_list(file_list_path)
            self.ui_print(f"成功从 {file_list_path} 加载模块列表。", tag='system_message')
        except FileNotFoundError:
            self.ui_print(f"未找到 {file_list_path}。正在扫描文件夹并生成默认列表...", tag='system_message')

            # 自动生成模块列表
            all_folders = [program_folder] + (external_folders or [])
            found_modules = []
            default_priority = 10  # 为自动发现的模块设置默认优先级

            for folder in all_folders:
                if not os.path.exists(folder):
                    continue
                for root, _, files in os.walk(folder):
                    for file in files:
                        # 排除 __init__.py 和 algorithm.py
                        if file.endswith('.py') and file not in ['__init__.py', 'algorithm.py']:
                            # 构建完整的模块路径，例如 'package.my_module'
                            # 这假设 program_folder 是 'package'
                            relative_path = os.path.relpath(os.path.join(root, file), start='.')
                            module_name = relative_path.replace(os.sep, '.')[:-3]
                            found_modules.append((module_name, default_priority, module_name.split('.')[-1]))

            # 将找到的模块写入 file_list.txt
            with open(file_list_path, 'w') as f:
                for module_name, priority, identifier in found_modules:
                    f.write(f"{module_name} {priority} {identifier}\n")

            self.ui_print(f"已生成默认的 {file_list_path}，包含 {len(found_modules)} 个模块。", tag='system_message')
            module_list_with_priority = found_modules

        # 根据优先级对模块列表进行排序
        hybrid_sort_with_progress(module_list_with_priority)

        # 按照排序后的顺序加载模块
        for module_name, _, _ in module_list_with_priority:
            try:
                # 假设模块路径是相对于当前工作目录的
                # 例如, 'package.my_module' 可以被直接导入
                program_module = importlib.import_module(module_name)

                # 检查模块是否具有 'run' 函数
                if hasattr(program_module, 'run'):
                    programs[module_name] = program_module
                else:
                    self.logging.warning(f"程序模块 '{module_name}' 没有 'run' 方法，已跳过。")

            except ImportError as e:
                self.ui_print(f"加载程序模块 '{module_name}' 时出错: {e}", tag='error')
                self.logging.error(f"加载程序模块 '{module_name}' 时出错: {e}")
            except Exception as e:
                self.ui_print(f"处理模块 '{module_name}' 时发生未知错误: {e}", tag='error')
                self.logging.error(f"处理模块 '{module_name}' 时发生未知错误: {e}")

        return programs
    
    def execute_program(self, program_name):
        try:
            # 尝试从缓存中获取模块
            if program_name in sys.modules:
                program_module = sys.modules[program_name]
            else:
                # 查找文件路径
                program_path = None
                for folder in self.program_folder:
                    for root, dirs, files in os.walk(folder):
                        if program_name in files:
                            program_path = os.path.join(root, program_name)
                            break
                    if program_path:
                        break
                
                if not program_path:
                    self.ui_print(f"未找到程序文件: {program_name}")
                    self.speak(f"未找到程序 {program_name}")
                    return
                
                # 动态加载模块
                spec = importlib.util.spec_from_file_location(program_name, program_path)
                program_module = importlib.util.module_from_spec(spec)
                sys.modules[program_name] = program_module
                spec.loader.exec_module(program_module)
            
            # 执行程序
            if hasattr(program_module, 'run'):
                self.ui_print(f"执行程序: {program_name}")
                self.speak(f"正在启动 {program_name}")
                program_module.run()
            else:
                self.ui_print(f"程序 {program_name} 没有run方法")
                self.speak(f"程序 {program_name} 无法启动")
                
        except Exception as e:
            self.ui_print(f"执行程序出错: {e}")
            self.logging.error(f"执行程序 {program_name} 出错: {e}")
            self.speak(f"启动程序时出错")

    def manage_temp_files(self):
        """管理临时文件"""
        temp_dir = tempfile.gettempdir()
        for filename in os.listdir(temp_dir):
            if filename.startswith("jarvis_temp_"):
                filepath = os.path.join(temp_dir, filename)
                try:
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                    elif os.path.isdir(filepath):
                        shutil.rmtree(filepath)
                except Exception as e:
                    self.ui_print(f"删除临时文件失败: {filepath} - {e}")

    def match_program(self, command, programs):
        """尝试匹配程序"""
        # 简化实现 - 实际应用中应使用更智能的匹配
        for name in programs:
            if name in command:
                self.execute_program(name)
                return
        self.speak("未找到匹配的程序")

    def panel_command_handler(self, command_type, command_payload):
        if command_type == "text":
            # The /approve command is handled directly here to avoid ambiguity
            if command_payload.strip() == "/approve":
                thread = threading.Thread(target=self.handle_user_command, args=(command_payload, self.panel.programs))
            else:
                thread = threading.Thread(target=self.handle_user_command, args=(command_payload, self.panel.programs))
            thread.daemon = True
            thread.start()
        elif command_type == "execute_program":
            self.execute_program(command_payload)
        elif command_type == "display_mode_change":
            mode = command_payload
            if mode in ['host', 'usb', 'both']:
                self.display_mode = mode
                self.ui_print(f"Display mode set to: {self.display_mode}", tag='system_message')
            else:
                self.ui_print(f"Invalid display mode from UI: {mode}", tag='error')


    def _background_monitor(self):
        """A mock background task that adjusts its frequency based on the performance mode."""
        while self.running:
            if self.resource_manager.get_mode() == PerformanceMode.ECO:
                # In ECO mode, the task runs less frequently.
                time.sleep(10)
                self.logging.info("Background monitor running in ECO mode (slow).")
            else:
                # In NORMAL mode, it runs more frequently.
                time.sleep(2)
                self.logging.info("Background monitor running in NORMAL mode (fast).")

    def main(self):
        # handler = self.ProgramHandler(self.program_folder)
        # observer = Observer()
        # for folder in self.program_folder:
        #     observer.schedule(handler, folder, recursive=True)
        # observer.start()

        # Start the background monitor in a separate thread
        monitor_thread = threading.Thread(target=self._background_monitor)
        monitor_thread.daemon = True
        monitor_thread.start()

        # process_tasks() # Temporarily disabled for UI testing
        # schedule_management() # This is a standalone command line tool, disabling for now
        self.manage_temp_files()

        self.speak("Jarvis 助手已启动")
        
        # observer.stop()
        # observer.join()

    def _initialize_long_memory(self):
        """Initializes the long-term memory, with a fallback to local storage."""
        try:
            if self.deepseek_api_key:
                self.logging.info("DeepSeek API key found. Initializing DeepSeekLongMemory.")
                self.long_memory = DeepSeekLongMemory(api_key=self.deepseek_api_key)
                self.long_memory.init(self.logging)
                self.logging.info("DeepSeekLongMemory initialized successfully.")
            else:
                raise ValueError("DeepSeek API key not found.")
        except (ValueError, ConnectionError) as e:
            self.logging.warning(f"Failed to initialize DeepSeekLongMemory ({e}). Falling back to SQLiteLongMemory.")
            self.long_memory = SQLiteLongMemory()
            self.long_memory.init() # Pass logger if the interface is updated to accept it
            self.logging.info("SQLiteLongMemory initialized as a fallback.")

    class ProgramHandler(FileSystemEventHandler):
        def __init__(self, program_folder, external_folders=None):
            self.program_folder = program_folder
            self.external_folders = external_folders or []
            self.programs_cache = {}
            self.programs = self.open_programs()

        def on_modified(self, event):
            if event.src_path.endswith('.py') or event.src_path.split('.')[-1] in binary_extensions:
                self.programs = self.open_programs.clear_cache()()

        def on_created(self, event):
            if event.src_path.endswith('.py') or event.src_path.split('.')[-1] in binary_extensions:
                self.programs = self.open_programs.clear_cache()()

        @lru_cache(maxsize=128)
        def open_programs(self):
            return Jarvis(None).open_programs(self.program_folder, self.external_folders)

def main():
    """Main entry point for the application."""
    import argparse
    import traceback
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="Run in headless mode without GUI")
    args = parser.parse_args()

    try:
        # Instantiate the USB screen regardless of mode
        usb_screen = USBScreen(width=40, height=8)

        if args.headless:
            print("Running in headless mode")
            # Pass usb_screen even in headless mode
            jarvis = Jarvis(None, usb_screen=usb_screen)
            jarvis.main()
            jarvis.start_listening() # Start listening automatically
            # Keep the application running
            while jarvis.running:
                time.sleep(1)
        else:
            root = tk.Tk()
            root.title("Jarvis Assistant")
            root.geometry("800x600")

            # Pass usb_screen to Jarvis
            jarvis = Jarvis(root, usb_screen=usb_screen)

            # Load programs once and pass them to the panel
            programs = jarvis.open_programs("./package", external_folders=["."])
            panel = CommandPanel(
                root,
                program_mapping=jarvis.program_mapping,
                programs=programs,
                command_callback=jarvis.panel_command_handler
            )
            panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            jarvis.set_panel(panel) # Link Jarvis to the panel

            jarvis.main()
            jarvis.start_listening() # Start listening automatically

            root.mainloop()

    except Exception as e:
        print(f"An unexpected error occurred during execution: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
