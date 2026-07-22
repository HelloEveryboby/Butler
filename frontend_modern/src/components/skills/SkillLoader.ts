/**
 * SkillLoader: 技能仓管理 (象限 1,1)
 *
 * 扫描并展示可用技能，支持热加载。
 */

import { bridge } from '@/api';
import { toast } from '@/utils/toast';
import { escapeHTML } from '@/utils/escape';

interface SkillInfo {
  name: string;
  description: string;
  icon: string;
  path: string;
}

export class SkillLoader {
  private container: HTMLElement | null = null;
  private skills: SkillInfo[] = [];

  constructor() {
    this.container = document.getElementById('skills-content');
    if (this.container) {
      this.loadSkills();
    }
  }

  private async loadSkills(): Promise<void> {
    try {
      const data = await bridge.callSkill('skill_manager', 'list');
      if (Array.isArray(data)) {
        this.skills = data;
        this.render();
      }
    } catch {
      toast.warning('技能仓', '无法加载技能列表');
    }
  }

  private render(): void {
    if (!this.container) return;

    if (this.skills.length === 0) {
      this.container.innerHTML = '<div class="glass-card text-muted text-center">暂无可用技能</div>';
      return;
    }

    // 使用 DOM API 安全构建
    this.container.innerHTML = '';
    for (const skill of this.skills) {
      const card = document.createElement('div');
      card.className = 'glass-card skill-card';

      const icon = document.createElement('span');
      icon.className = 'skill-icon';
      icon.textContent = skill.icon || '📦';

      const name = document.createElement('div');
      name.className = 'skill-name font-bold';
      name.textContent = skill.name;

      const desc = document.createElement('div');
      desc.className = 'skill-desc text-muted text-sm';
      desc.textContent = skill.description || '';

      card.appendChild(icon);
      card.appendChild(name);
      card.appendChild(desc);

      card.addEventListener('click', () => {
        toast.info('技能', `启动: ${skill.name}`);
        bridge.handleCommand(`/skill ${skill.name}`);
      });

      this.container.appendChild(card);
    }
  }
}
