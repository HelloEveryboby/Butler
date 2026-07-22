import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/butler_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _serverController = TextEditingController();
  final _apiKeyController = TextEditingController();
  String _status = '';

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    _serverController.text = prefs.getString('server_url') ?? '';
    _apiKeyController.text = prefs.getString('api_key') ?? '';
  }

  @override
  void dispose() {
    _serverController.dispose();
    _apiKeyController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final service = context.watch<ButlerService>();

    return Scaffold(
      appBar: AppBar(title: const Text('设置')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 服务器地址
          TextField(
            controller: _serverController,
            decoration: const InputDecoration(
              labelText: '远程服务器地址 (可选)',
              hintText: 'ws://192.168.1.100:5001',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),

          // API Key
          TextField(
            controller: _apiKeyController,
            decoration: const InputDecoration(
              labelText: 'API Key',
              hintText: 'DEEPSEEK_API_KEY',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),

          // 保存
          FilledButton(
            onPressed: () async {
              final prefs = await SharedPreferences.getInstance();
              await prefs.setString('server_url', _serverController.text);
              await prefs.setString('api_key', _apiKeyController.text);
              setState(() => _status = '✅ 设置已保存');
            },
            child: const Text('保存设置'),
          ),
          const SizedBox(height: 8),

          // 初始化
          OutlinedButton(
            onPressed: service.connecting
                ? null
                : () async {
                    setState(() => _status = '⏳ 正在初始化...');
                    // Platform Channel 初始化需要原生端支持
                    setState(() => _status = 'ℹ️ 需要原生端 Chaquopy 支持');
                  },
            child: const Text('初始化 Python 引擎'),
          ),

          if (_status.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text(_status, style: Theme.of(context).textTheme.bodyMedium),
          ],

          const Divider(height: 32),

          // 状态
          Text(
            'Butler Android v1.0.0 (Flutter)',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: 4),
          Text(
            '引擎状态: ${service.initialized ? "✅ 就绪" : "❌ 未初始化"}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}
