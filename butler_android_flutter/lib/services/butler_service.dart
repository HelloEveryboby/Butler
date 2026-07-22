import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Butler 服务层
///
/// 通过 Platform Channel 调用原生 Python 引擎，
/// 或通过 WebSocket 连接远程 Butler 后端。
class ButlerService extends ChangeNotifier {
  // Platform Channel (Android Chaquopy)
  static const _channel = MethodChannel('com.butler.android/bridge');

  bool _initialized = false;
  bool _connecting = false;
  String? _error;

  bool get initialized => _initialized;
  bool get connecting => _connecting;
  String? get error => _error;

  /// 初始化 Python 引擎
  Future<bool> initialize(String filesDir) async {
    _connecting = true;
    _error = null;
    notifyListeners();

    try {
      final result = await _channel.invokeMethod('initialize', {
        'filesDir': filesDir,
      });
      _initialized = result == true;
      if (!_initialized) {
        _error = '初始化返回 false';
      }
    } on PlatformException catch (e) {
      _error = '${e.code}: ${e.message}';
      _initialized = false;
    } catch (e) {
      _error = e.toString();
      _initialized = false;
    }

    _connecting = false;
    notifyListeners();
    return _initialized;
  }

  /// 调用技能插件
  Future<Map<String, dynamic>> callPlugin(
    String skillId,
    String action, {
    Map<String, dynamic> params = const {},
  }) async {
    try {
      final result = await _channel.invokeMethod('callPlugin', {
        'skillId': skillId,
        'action': action,
        'paramsJson': jsonEncode(params),
      });

      if (result is String) {
        return jsonDecode(result) as Map<String, dynamic>;
      }
      return {'status': 'error', 'message': 'Invalid response type'};
    } on PlatformException catch (e) {
      return {'status': 'error', 'error_type': e.code, 'message': e.message};
    } catch (e) {
      return {'status': 'error', 'message': e.toString()};
    }
  }

  /// 发送聊天消息
  Future<String> chat(String message) async {
    final result = await callPlugin('chat', 'process', params: {
      'message': message,
    });

    if (result['status'] == 'success') {
      final data = result['data'];
      if (data is Map) {
        return data['response']?.toString() ?? '无响应';
      }
      return data?.toString() ?? '无响应';
    }
    return '❌ ${result['message'] ?? '未知错误'}';
  }

  /// 获取技能列表
  Future<List<Map<String, dynamic>>> getSkills() async {
    final result = await callPlugin('skill_manager', 'list');
    if (result['status'] == 'success') {
      final data = result['data'];
      if (data is Map && data['skills'] is List) {
        return (data['skills'] as List).cast<Map<String, dynamic>>();
      }
    }
    return [];
  }
}
