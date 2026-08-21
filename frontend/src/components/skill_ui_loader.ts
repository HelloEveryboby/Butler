/**
 * Butler Skill UI Loader Component in TypeScript
 */

interface UISkill {
  id?: string;
  name: string;
  icon?: string;
  color?: string;
  frontend_path: string;
}

class SkillUILoader {
  public drawer: HTMLElement | null;

  constructor() {
    this.drawer = document.getElementById('skills-drawer');
    if (this.drawer) {
      setTimeout(() => this.initSkillsList(), 100);
    }
  }

  public async initSkillsList(): Promise<void> {
    if (!this.drawer) return;

    const baseMockSkills = [
      { name: '截图排障', icon: 'fa-bug', color: '#FF3B30' },
      { name: '局域网同步', icon: 'fa-sync', color: '#34C759' },
      { name: '系统清理', icon: 'fa-broom', color: '#FF9500' },
    ];

    let uiSkills: UISkill[] = [];
    const isMockMode =
      typeof window.pywebview === 'undefined' || typeof window.pywebview.api === 'undefined';

    if (!isMockMode) {
      try {
        uiSkills = await window.pywebview!.api.get_ui_skills();
      } catch (err) {
        console.error('Failed to query real UI skills from backend', err);
      }
    } else {
      uiSkills = [
        {
          id: 'storage_hub',
          name: '存储中心',
          icon: 'fa-box-open',
          frontend_path: 'skills/storage_hub/ui/index.html',
        },
      ];
    }

    this.drawer.innerHTML = '';

    baseMockSkills.forEach((skill) => {
      const card = document.createElement('div');
      card.className = 'dag-node glass-surface';
      card.draggable = true;
      card.style.position = 'relative';
      card.style.marginBottom = '10px';
      card.innerHTML = `<i class="fas ${skill.icon}" style="color: ${skill.color}"></i> <span>${skill.name}</span>`;

      card.ondragstart = (e: DragEvent) => {
        e.dataTransfer?.setData(
          'application/json',
          JSON.stringify({
            type: 'skill',
            name: skill.name,
            icon: skill.icon,
          })
        );
      };
      this.drawer?.appendChild(card);
    });

    uiSkills.forEach((skill) => {
      const card = document.createElement('div');
      card.className = 'dag-node glass-surface live-ui-skill-card';
      card.draggable = true;
      card.style.position = 'relative';
      card.style.marginBottom = '10px';
      card.style.border = '1px solid rgba(45, 164, 78, 0.3)';
      card.style.boxShadow = '0 0 8px rgba(45, 164, 78, 0.1)';

      card.innerHTML = `
        <i class="fas ${skill.icon || 'fa-folder-open'}" style="color: #2da44e"></i>
        <span>${skill.name === 'Storage Hub' ? '存储中心' : skill.name}</span>
        <span style="position: absolute; right: 10px; font-size: 8px; background: rgba(45,164,78,0.2); color: #2da44e; padding: 2px 5px; border-radius: 4px; font-weight: 700; text-transform: uppercase;">UI</span>
      `;

      card.onclick = async () => {
        if (isMockMode) {
          window.location.href = skill.frontend_path;
        } else {
          try {
            window.showToast?.(
              '载入组件',
              `正在跳转至 ${skill.name === 'Storage Hub' ? '存储中心' : skill.name}...`,
              'success'
            );
            await window.pywebview!.api.load_skill_frontend(skill.frontend_path);
          } catch (err) {
            console.error('Navigation call failed', err);
            window.showToast?.('路由错误', '无法在 webview 容器内加载该页面', 'error');
          }
        }
      };

      card.ondragstart = (e: DragEvent) => {
        e.dataTransfer?.setData(
          'application/json',
          JSON.stringify({
            type: 'skill',
            name: skill.name,
            id: skill.id,
            is_ui: true,
            frontend_path: skill.frontend_path,
          })
        );
      };

      this.drawer?.appendChild(card);
    });
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    window.skillUiLoader = new SkillUILoader();
  });
}
