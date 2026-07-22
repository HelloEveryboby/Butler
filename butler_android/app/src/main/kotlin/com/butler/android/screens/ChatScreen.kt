package com.butler.android.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.butler.android.ButlerBridge
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

data class ChatMessage(
    val role: String,   // "user" or "assistant"
    val content: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(onNavigate: (String) -> Unit) {
    var inputText by remember { mutableStateOf("") }
    val messages = remember { mutableStateListOf<ChatMessage>() }
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    var isLoading by remember { mutableStateOf(false) }

    // 初始化提示
    LaunchedEffect(Unit) {
        if (messages.isEmpty()) {
            messages.add(ChatMessage("assistant", "🤵 欢迎使用 Butler！\n输入消息开始对话。"))
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Butler") },
                navigationIcon = {
                    IconButton(onClick = { onNavigate("skills") }) {
                        Icon(Icons.Default.Menu, "菜单")
                    }
                },
                actions = {
                    TextButton(onClick = { onNavigate("skills") }) {
                        Text("技能")
                    }
                    TextButton(onClick = { onNavigate("settings") }) {
                        Text("设置")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // 消息列表
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                state = listState,
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(vertical = 12.dp)
            ) {
                items(messages) { msg ->
                    MessageBubble(msg)
                }
                if (isLoading) {
                    item {
                        CircularProgressIndicator(
                            modifier = Modifier.size(24.dp),
                            strokeWidth = 2.dp
                        )
                    }
                }
            }

            // 输入区
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedTextField(
                    value = inputText,
                    onValueChange = { inputText = it },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("输入消息...") },
                    singleLine = false,
                    maxLines = 4,
                    shape = RoundedCornerShape(24.dp)
                )
                FilledIconButton(
                    onClick = {
                        val text = inputText.trim()
                        if (text.isEmpty() || isLoading) return@FilledIconButton

                        messages.add(ChatMessage("user", text))
                        inputText = ""
                        isLoading = true

                        scope.launch {
                            // 在 IO 线程调用 Python
                            val response = withContext(Dispatchers.IO) {
                                try {
                                    val result = ButlerBridge.chat(text)
                                    val json = JSONObject(result)
                                    if (json.optString("status") == "success") {
                                        json.optJSONObject("data")?.optString("response", "无响应") ?: "无响应"
                                    } else {
                                        "❌ ${json.optString("message", "未知错误")}"
                                    }
                                } catch (e: Exception) {
                                    "❌ ${e.message}"
                                }
                            }
                            messages.add(ChatMessage("assistant", response))
                            isLoading = false
                            // 滚动到底部
                            listState.animateScrollToItem(messages.size - 1)
                        }
                    },
                    enabled = !isLoading
                ) {
                    Icon(Icons.AutoMirrored.Filled.Send, "发送")
                }
            }
        }
    }
}

@Composable
fun MessageBubble(msg: ChatMessage) {
    val isUser = msg.role == "user"
    val bubbleColor = if (isUser)
        MaterialTheme.colorScheme.primary
    else
        MaterialTheme.colorScheme.surfaceVariant

    val textColor = if (isUser)
        MaterialTheme.colorScheme.onPrimary
    else
        MaterialTheme.colorScheme.onSurfaceVariant

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Box(
            modifier = Modifier
                .widthIn(max = 300.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(bubbleColor)
                .padding(horizontal = 14.dp, vertical = 10.dp)
        ) {
            Text(
                text = msg.content,
                color = textColor,
                style = MaterialTheme.typography.bodyLarge
            )
        }
    }
}
