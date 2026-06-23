package com.butler.android

import android.content.Context
import android.util.Log
import java.io.File
import java.io.FileOutputStream

/**
 * Utility to extract skill assets from APK to internal storage for execution
 */
object AssetExtractor {
    fun extractSkills(context: Context) {
        val targetDir = File(context.filesDir, "skills")
        if (!targetDir.exists()) {
            targetDir.mkdirs()
        }

        try {
            val assets = context.assets.list("skills") ?: return
            for (skillName in assets) {
                val skillDir = File(targetDir, skillName)
                if (!skillDir.exists()) {
                    skillDir.mkdirs()
                    copyAssetDir(context, "skills/$skillName", skillDir)
                }
            }
        } catch (e: Exception) {
            Log.e("AssetExtractor", "Extraction failed: ${e.message}")
        }
    }

    private fun copyAssetDir(context: Context, assetPath: String, targetDir: File) {
        val assets = context.assets.list(assetPath) ?: return
        for (item in assets) {
            val itemAssetPath = "$assetPath/$item"
            val targetFile = File(targetDir, item)

            val isDir = context.assets.list(itemAssetPath)?.isNotEmpty() ?: false
            if (isDir) {
                targetFile.mkdirs()
                copyAssetDir(context, itemAssetPath, targetFile)
            } else {
                context.assets.open(itemAssetPath).use { input ->
                    FileOutputStream(targetFile).use { output ->
                        input.copyTo(output)
                    }
                }
            }
        }
    }
}
