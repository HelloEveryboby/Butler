package com.butler.app.butler_android

import androidx.annotation.NonNull
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import com.butler.app.NativeLib

class MainActivity: FlutterActivity() {
    private val CHANNEL = "com.butler.app/native"
    private val nativeLib = NativeLib()

    override fun configureFlutterEngine(@NonNull flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler {
            call, result ->
            when (call.method) {
                "getHardwareStatus" -> {
                    val status = nativeLib.getHardwareStatus()
                    result.success(status)
                }
                "simulateNFC" -> {
                    val tag = nativeLib.simulateNFCScan()
                    result.success(tag)
                }
                "controlLED" -> {
                    val turnOn = call.argument<Boolean>("turnOn") ?: false
                    val success = nativeLib.controlLED(turnOn)
                    result.success(success)
                }
                "calculateVolume" -> {
                    val noise = call.argument<Double>("noise")?.toFloat() ?: 0.0f
                    val volume = nativeLib.calculateOptimalVolume(noise)
                    result.success(volume.toDouble())
                }
                else -> {
                    result.notImplemented()
                }
            }
        }
    }
}
