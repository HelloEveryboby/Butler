package com.butler.android

import android.content.Context
import android.util.Log
import org.json.JSONObject
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

        val currentVersion = getAppVersionIdentifier(context)
        val versionFile = File(targetDir, ".extracted_version")
        var forceOverwrite = true

        if (versionFile.exists()) {
            val storedVersion = versionFile.readText().trim()
            if (storedVersion == currentVersion) {
                forceOverwrite = false
            }
        }

        try {
            val meta = loadAssetMeta(context)
            if (meta != null && meta.has("files")) {
                val filesObj = meta.getJSONObject("files")
                val keys = filesObj.keys()
                val activeRelativePaths = HashSet<String>()

                while (keys.hasNext()) {
                    val assetPath = keys.next()
                    if (assetPath.startsWith("skills/")) {
                        val relativePath = assetPath.substring("skills/".length)
                        activeRelativePaths.add(relativePath)

                        val targetFile = File(targetDir, relativePath)
                        val targetParent = targetFile.parentFile
                        if (targetParent != null && !targetParent.exists()) {
                            targetParent.mkdirs()
                        }

                        if (forceOverwrite || !targetFile.exists()) {
                            // Copy file from assets
                            copyAssetFile(context, assetPath, targetFile)
                        }
                    }
                }

                // Clean up any stale files/directories that are no longer present in the assets meta (run unconditionally)
                cleanupStaleFiles(targetDir, activeRelativePaths)
            } else {
                // Fallback to legacy full copy if no metadata available or failed
                val assets = context.assets.list("skills") ?: return
                for (skillName in assets) {
                    val skillDir = File(targetDir, skillName)
                    if (forceOverwrite || !skillDir.exists()) {
                        skillDir.mkdirs()
                        copyAssetDir(context, "skills/$skillName", skillDir)
                    }
                }
            }

            // Write the current version marker to avoid re-extraction next time
            versionFile.writeText(currentVersion)
            Log.i("AssetExtractor", "Skills extraction and sync complete. Version: $currentVersion")
        } catch (e: Exception) {
            Log.e("AssetExtractor", "Extraction failed: ${e.message}", e)
        }
    }

    private fun getAppVersionIdentifier(context: Context): String {
        return try {
            val pInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            val versionCode = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
                pInfo.longVersionCode
            } else {
                @Suppress("DEPRECATION")
                pInfo.versionCode.toLong()
            }
            "version_${versionCode}_time_${pInfo.lastUpdateTime}"
        } catch (e: Exception) {
            "version_unknown_${System.currentTimeMillis()}"
        }
    }

    private fun loadAssetMeta(context: Context): JSONObject? {
        return try {
            context.assets.open(".asset_meta").use { input ->
                val size = input.available()
                val buffer = ByteArray(size)
                input.read(buffer)
                val jsonStr = String(buffer, Charsets.UTF_8)
                JSONObject(jsonStr)
            }
        } catch (e: Exception) {
            Log.w("AssetExtractor", "No .asset_meta found: ${e.message}")
            null
        }
    }

    private fun copyAssetFile(context: Context, assetPath: String, targetFile: File) {
        try {
            context.assets.open(assetPath).use { input ->
                FileOutputStream(targetFile).use { output ->
                    input.copyTo(output)
                }
            }
        } catch (e: Exception) {
            Log.e("AssetExtractor", "Failed to copy asset $assetPath: ${e.message}")
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
                copyAssetFile(context, itemAssetPath, targetFile)
            }
        }
    }

    private fun cleanupStaleFiles(dir: File, activePaths: Set<String>) {
        val allFiles = dir.walkTopDown()
        for (file in allFiles) {
            if (file == dir || file.name == ".extracted_version") continue
            val relPath = file.relativeTo(dir).path.replace('\\', '/')
            if (file.isFile && !activePaths.contains(relPath)) {
                if (file.delete()) {
                    Log.i("AssetExtractor", "Deleted stale file: $relPath")
                }
            }
        }
        // Second pass to clean up empty directories
        for (file in dir.walkBottomUp()) {
            if (file != dir && file.isDirectory && file.listFiles()?.isEmpty() == true) {
                file.delete()
            }
        }
    }
}
