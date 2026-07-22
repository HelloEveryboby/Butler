package com.butler.android

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.butler.android.screens.ChatScreen
import com.butler.android.screens.SkillsScreen
import com.butler.android.screens.SettingsScreen

@Composable
fun ButlerNavHost() {
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = "chat") {
        composable("chat") {
            ChatScreen(onNavigate = { route -> navController.navigate(route) })
        }
        composable("skills") {
            SkillsScreen(onNavigate = { route -> navController.navigate(route) })
        }
        composable("settings") {
            SettingsScreen(onNavigate = { route -> navController.navigate(route) })
        }
    }
}
