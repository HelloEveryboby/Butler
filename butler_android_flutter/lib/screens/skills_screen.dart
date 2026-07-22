import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/butler_service.dart';

class SkillsScreen extends StatefulWidget {
  const SkillsScreen({super.key});

  @override
  State<SkillsScreen> createState() => _SkillsScreenState();
}

class _SkillsScreenState extends State<SkillsScreen> {
  List<Map<String, dynamic>> _skills = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadSkills();
  }

  Future<void> _loadSkills() async {
    final service = context.read<ButlerService>();
    final skills = await service.getSkills();
    setState(() {
      _skills = skills;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('技能列表')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _skills.isEmpty
              ? const Center(child: Text('暂无可用技能'))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _skills.length,
                  itemBuilder: (context, index) {
                    final skill = _skills[index];
                    return Card(
                      child: ListTile(
                        leading: const Icon(Icons.extension),
                        title: Text(skill['name'] ?? skill['id'] ?? ''),
                        subtitle: Text(skill['description'] ?? ''),
                        trailing: skill['enabled'] == false
                            ? const Text('禁用', style: TextStyle(color: Colors.red))
                            : null,
                      ),
                    );
                  },
                ),
    );
  }
}
