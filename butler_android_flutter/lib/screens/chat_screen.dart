import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/butler_service.dart';
import '../models/chat_message.dart';
import '../widgets/message_bubble.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _messages = <ChatMessage>[];
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _messages.add(ChatMessage(
      role: 'assistant',
      content: '🤵 欢迎使用 Butler！\n输入消息开始对话。',
    ));
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _isLoading) return;

    setState(() {
      _messages.add(ChatMessage(role: 'user', content: text));
      _isLoading = true;
    });
    _controller.clear();
    _scrollToBottom();

    final service = context.read<ButlerService>();
    final response = await service.chat(text);

    setState(() {
      _messages.add(ChatMessage(role: 'assistant', content: response));
      _isLoading = false;
    });
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Butler')),
      body: Column(
        children: [
          // 消息列表
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              itemCount: _messages.length + (_isLoading ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == _messages.length) {
                  return const Padding(
                    padding: EdgeInsets.all(8),
                    child: Center(
                      child: SizedBox(
                        width: 24, height: 24,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
                  );
                }
                return MessageBubble(message: _messages[index]);
              },
            ),
          ),

          // 输入区
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    decoration: InputDecoration(
                      hintText: '输入消息...',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 12,
                      ),
                    ),
                    maxLines: 4,
                    minLines: 1,
                    onSubmitted: (_) => _send(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  onPressed: _isLoading ? null : _send,
                  icon: const Icon(Icons.send),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
