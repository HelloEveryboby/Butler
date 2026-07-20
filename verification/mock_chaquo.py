#!/usr/bin/env python3
"""
Butler Verification Scaffold - Mocking Chaquopy Java Bridge
用于在本地 PC 环境快速验证 skill_sdk.py 的路由与异常捕获逻辑
"""

import sys
import os
import types

# 1. 动态注入一个 Mock 的 java 模块，防止 skill_sdk 导入报错
mock_java = types.ModuleType("java")
sys.modules["java"] = mock_java

# 模拟 Android 原生 NativeOCR 桥接代理
class MockNativeOCR:
    @staticmethod
    def recognize_text(image_base64: str) -> str:
        print(f"[Mock Logcat] Java NativeOCR received: {image_base64[:20]}...")
        return "Simulated OCR Text from Android ML Kit"

# 将 Mock 类挂载到 java 模块上
mock_java.jnius = types.ModuleType("jnius")
mock_java.jnius.autoclass = lambda name: MockNativeOCR if "NativeOCR" in name else None

# 2. 模拟沙箱路径与初始化测试
def run_sandbox_test():
    print("====== [Local Sandbox Verification Launcher] ======")

    # 假设当前路径为沙箱内
    sys.path.append(os.path.abspath("./butler_android/app/src/main/python"))

    try:
        # 这里模拟加载 skill_sdk 并运行
        print("Testing skill_sdk native bridge mapping...")
        import butler_android

        # Test Initialize
        butler_android.initialize(".")
        print("✓ Bridge initialization: PASSED")

        # Test call_plugin error capturing
        print("Testing plugin execution and traceback capture...")
        res = butler_android.call_plugin("invalid_skill_id", "invalid_action", "{}")
        print(f"Captured response: {res}")
        if "InitializationError" in res or "invalid_skill_id" in res or "Error" in res:
            print("✓ Error traceback serialization: PASSED")
        else:
            raise RuntimeError("Failed to capture invalid plugin error")

        print("✓ Bridge verification: PASSED")
    except Exception as e:
        import traceback
        print(f"✗ Bridge verification failed:\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    run_sandbox_test()
