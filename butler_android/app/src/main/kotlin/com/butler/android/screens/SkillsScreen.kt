package com.butler.android.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Extension
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.butler.android.ButlerBridge
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

data class SkillInfo(
    val id: String,
    val name: String,
    val description: String,
    val enabled: Boolean
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SkillsScreen(onNavigate: (String) -> Unit) {
    val skills = remember { mutableStateListOf<SkillInfo>() }
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(Unit) {
        scope.launch {
            val result = withContext(Dispatchers.IO) {
                ButlerBridge.callPlugin("skill_manager", "list")
            }
            try {
                val json = JSONObject(result)
                if (json.optString("status") == "success") {
                    val arr = json.optJSONObject("data")?.optJSONArray("skills") ?: JSONArray()
                    for (i in 0 until arr.length()) {
                        val obj = arr.getJSONObject(i)
                        skills.add(
                            SkillInfo(
                                id = obj.optString("id"),
                                name = obj.optString("name", obj.optString("id")),
                                description = obj.optString("description", ""),
                                enabled = obj.optBoolean("enabled", true)
                            )
                        )
                    }
                }
            } catch (_: Exception) {}
            loading = false
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("技能列表") },
                navigationIcon = {
                    IconButton(onClick = { onNavigate("chat") }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回")
                    }
                }
            )
        }
    ) { padding ->
        if (loading) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else if (skills.isEmpty()) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                Text("暂无可用技能", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(skills) { skill ->
                    SkillCard(skill) {
                        onNavigate("chat")
                    }
                }
            }
        }
    }
}

@Composable
fun SkillCard(skill: SkillInfo, onClick: () -> Unit) {
    ElevatedCard(
        modifier = Modifier.fillMaxWidth().clickable { onClick() }
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Icon(
                Icons.Default.Extension,
                contentDescription = null,
                tint = if (skill.enabled) MaterialTheme.colorScheme.primary
                       else MaterialTheme.colorScheme.onSurfaceVariant
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(skill.name, style = MaterialTheme.typography.titleMedium)
                if (skill.description.isNotEmpty()) {
                    Text(
                        skill.description,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            if (!skill.enabled) {
                Text("禁用", style = MaterialTheme.typography.labelSmall,
                     color = MaterialTheme.colorScheme.error)
            }
        }
    }
}
