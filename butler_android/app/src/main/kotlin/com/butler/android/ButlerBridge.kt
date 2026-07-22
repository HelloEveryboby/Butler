package com.butler.android

import com.chaquo.python.Python
import com.chaquo.python.PyObject
import org.json.JSONObject

/**
 * Butler Python 桥接层
 *
 * 通过 Chaquopy 调用 butler_android.py 中的函数。
 * 所有 Python 调用都在当前线程执行 (Chaquopy 自动处理 GIL)。
 */
object ButlerBridge {
    private var butlerModule: PyObject? = null
    private var initialized = false

    /**
     * 初始化 Python 端的 Butler
     */
    fun initialize(filesDir: String): Boolean {
        return try {
            val py = Python.getInstance()
            butlerModule = py.getModule("butler_android")
            butlerModule?.callAttr("initialize", filesDir)
            initialized = true
            true
        } catch (e: Exception) {
            android.util.Log.e("ButlerBridge", "Init failed: ${e.message}", e)
            false
        }
    }

    /**
     * 调用 Python 技能
     * @return JSON 字符串 {"status":"success","data":...} 或 {"status":"error","message":...}
     */
    fun callPlugin(skillId: String, action: String, params: Map<String, Any> = emptyMap()): String {
        if (!initialized) {
            return errorJson("NotInitialized", "Butler not initialized")
        }
        return try {
            val paramsJson = JSONObject(params).toString()
            val result = butlerModule?.callAttr("call_plugin", skillId, action, paramsJson)
            result?.toString() ?: errorJson("NullResult", "Python returned null")
        } catch (e: Exception) {
            android.util.Log.e("ButlerBridge", "callPlugin error: ${e.message}", e)
            errorJson(e.javaClass.simpleName, e.message ?: "Unknown error")
        }
    }

    /**
     * 发送聊天消息到 Python 端处理
     */
    fun chat(message: String): String {
        return callPlugin("chat", "process", mapOf("message" to message))
    }

    /**
     * 清理资源
     */
    fun cleanup() {
        try {
            butlerModule?.callAttr("cleanup")
        } catch (_: Exception) {}
        initialized = false
    }

    private fun errorJson(type: String, message: String): String {
        return JSONObject().apply {
            put("status", "error")
            put("error_type", type)
            put("message", message)
        }.toString()
    }
}
