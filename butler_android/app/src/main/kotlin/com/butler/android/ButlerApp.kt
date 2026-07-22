package com.butler.android

import android.app.Application
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class ButlerApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // 初始化 Chaquopy Python 运行时
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
    }
}
