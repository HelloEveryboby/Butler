package com.butler.android.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.butler.android.ButlerBridge

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(onNavigate: (String) -> Unit) {
    val context = LocalContext.current
    var serverUrl by remember { mutableStateOf("") }
    var apiKey by remember { mutableStateOf("") }
    var initStatus by remember { mutableStateOf("") }

    // 读取保存的设置
    val prefs = context.getSharedPreferences("butler_settings", 0)
    LaunchedEffect(Unit) {
        serverUrl = prefs.getString("server_url", "") ?: ""
        apiKey = prefs.getString("api_key", "") ?: ""
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("设置") },
                navigationIcon = {
                    IconButton(onClick = { onNavigate("chat") }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // 服务器地址 (远程后端模式)
            OutlinedTextField(
                value = serverUrl,
                onValueChange = { serverUrl = it },
                label = { Text("远程服务器地址 (可选)") },
                placeholder = { Text("ws://192.168.1.100:5001") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            // API Key
            OutlinedTextField(
                value = apiKey,
                onValueChange = { apiKey = it },
                label = { Text("API Key") },
                placeholder = { Text("DEEPSEEK_API_KEY") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            // 保存按钮
            Button(
                onClick = {
                    prefs.edit()
                        .putString("server_url", serverUrl)
                        .putString("api_key", apiKey)
                        .apply()
                    initStatus = "✅ 设置已保存"
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("保存设置")
            }

            // 初始化 Python 引擎
            OutlinedButton(
                onClick = {
                    initStatus = "⏳ 正在初始化..."
                    val success = ButlerBridge.initialize(context.filesDir.absolutePath)
                    initStatus = if (success) "✅ Python 引擎就绪" else "❌ 初始化失败"
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("初始化 Python 引擎")
            }

            if (initStatus.isNotEmpty()) {
                Text(
                    text = initStatus,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            HorizontalDivider()

            // 关于
            Text(
                text = "Butler Android v1.0.0",
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = "基于 Chaquopy 的本地优先智能管家\nPython 3.10 + Jetpack Compose",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
