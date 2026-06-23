package com.butler.android

import android.app.Application
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class ButlerApp : Application() {
    override fun onCreate() {
        super.onCreate()

        // Extract skills to internal storage for Chaquopy/SkillManager
        AssetExtractor.extractSkills(this)

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
    }
}
