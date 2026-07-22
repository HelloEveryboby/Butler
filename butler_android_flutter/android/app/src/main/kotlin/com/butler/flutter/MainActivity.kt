package com.butler.flutter

import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.butler.android/bridge"
    private var initialized = false

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "initialize" -> {
                        val filesDir = call.argument<String>("filesDir") ?: filesDir.absolutePath
                        // TODO: Chaquopy Python 初始化
                        initialized = true
                        result.success(true)
                    }
                    "callPlugin" -> {
                        val skillId = call.argument<String>("skillId") ?: ""
                        val action = call.argument<String>("action") ?: ""
                        val paramsJson = call.argument<String>("paramsJson") ?: "{}"
                        // TODO: Chaquopy 调用 Python
                        result.success("""{"status":"success","data":{"response":"Flutter + Android 桥接就绪。配置 Chaquopy 后可调用 Python 技能。"}}""")
                    }
                    else -> result.notImplemented()
                }
            }
    }
}
