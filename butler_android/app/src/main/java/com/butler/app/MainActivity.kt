package com.butler.app

import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.JavascriptInterface
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.PyObject
import android.util.Log
import org.json.JSONObject

/**
 * Main Activity - WebView with Butler Frontend and JS-Python Bridge
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private var butlerModule: PyObject? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Initialize Python and Butler bridge module
        val py = Python.getInstance()
        butlerModule = py.getModule("butler_android")
        try {
            butlerModule?.callAttr("initialize")
        } catch (e: Exception) {
            Log.e("MainActivity", "Butler init error: ${e.message}")
        }

        // Setup WebView
        webView = WebView(this)
        setContentView(webView)

        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.allowFileAccess = true
        settings.databaseEnabled = true

        // Add JS Bridge to simulate pywebview
        webView.addJavascriptInterface(AndroidBridge(), "androidBridge")

        // Inject JS to create window.pywebview.api proxy
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                val injectJs = """
                    window.pywebview = {
                        api: new Proxy({}, {
                            get: function(target, prop) {
                                return function() {
                                    var args = JSON.stringify(Array.from(arguments));
                                    return new Promise((resolve, reject) => {
                                        var callId = "call_" + Math.random().toString(36).substr(2, 9);
                                        window[callId] = resolve;
                                        androidBridge.callPython(prop, args, callId);
                                    });
                                }
                            }
                        })
                    };
                    console.log("Butler Android JS Bridge Injected");
                """.trimIndent()
                webView.evaluateJavascript(injectJs, null)
            }
        }

        webView.loadUrl("file:///android_asset/www/index.html")
    }

    inner class AndroidBridge {
        @JavascriptInterface
        fun callPython(methodName: String, argsJson: String, callId: String) {
            Log.d("ButlerBridge", "Method: $methodName, Args: $argsJson")

            try {
                val args = org.json.JSONArray(argsJson)
                val params = mutableListOf<Any?>()
                for (i in 0 until args.length()) {
                    params.add(args.get(i))
                }

                // Route calls to Python
                val result = when (methodName) {
                    "handle_command" -> butlerModule?.callAttr("process_message", params[0] as String)
                    "call_skill" -> {
                        val skillId = params[0] as String
                        val action = params[1] as String
                        butlerModule?.callAttr("call_plugin", skillId, action, emptyMap<String, Any>())
                    }
                    else -> butlerModule?.callAttr(methodName, *params.toTypedArray())
                }

                val resultStr = result?.toString() ?: ""

                runOnUiThread {
                    // Escape result string for JS
                    val safeResult = JSONObject.quote(resultStr)
                    webView.evaluateJavascript("if(window['$callId']) { window['$callId']($safeResult); delete window['$callId']; }", null)
                }
            } catch (e: Exception) {
                Log.e("ButlerBridge", "Error: ${e.message}")
                runOnUiThread {
                    webView.evaluateJavascript("if(window['$callId']) { window['$callId'](JSON.stringify({error: '${e.message}'})); delete window['$callId']; }", null)
                }
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        try {
            butlerModule?.callAttr("cleanup")
        } catch (e: Exception) {}
    }
}
