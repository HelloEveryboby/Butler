package com.butler.automation

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONObject

/**
 * Butler Android Automation Core (Accessibility Service)
 * Implements "Brain-Executor" pattern.
 */
class ButlerAccessibilityService : AccessibilityService() {

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Monitor UI changes if needed
    }

    override fun onInterrupt() {}

    /**
     * Executes a command from the Butler Backend (DeepSeek Brain)
     */
    fun executeButlerCommand(jsonCommand: String) {
        val json = JSONObject(jsonCommand)
        when (json.getString("action")) {
            "click" -> {
                val x = json.getInt("x").toFloat()
                val y = json.getInt("y").toFloat()
                clickAt(x, y)
            }
            "swipe" -> {
                val fx = json.getInt("fromX").toFloat()
                val fy = json.getInt("fromY").toFloat()
                val tx = json.getInt("toX").toFloat()
                val ty = json.getInt("toY").toFloat()
                swipe(fx, fy, tx, ty)
            }
            "inputText" -> {
                val text = json.getString("text")
                // Logic to find node and input text
            }
        }
    }

    private fun clickAt(x: Float, y: Float) {
        val path = Path()
        path.moveTo(x, y)
        val builder = GestureDescription.Builder()
        builder.addStroke(GestureDescription.StrokeDescription(path, 0, 100))
        dispatchGesture(builder.build(), null, null)
    }

    private fun swipe(fx: Float, fy: Float, tx: Float, ty: Float) {
        val path = Path()
        path.moveTo(fx, fy)
        path.lineTo(tx, ty)
        val builder = GestureDescription.Builder()
        builder.addStroke(GestureDescription.StrokeDescription(path, 0, 500))
        dispatchGesture(builder.build(), null, null)
    }
}
