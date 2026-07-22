/**
 * 工作流入口 (workflow.html)
 *
 * 工作流中心的独立入口脚本。
 */

import { bridge } from '@/api';
import { workflowStore } from '@/stores/workflow-store';
import { initErrorBoundary } from '@/utils/error-boundary';
import { escapeHTML } from '@/utils/escape';

initErrorBoundary();

const listEl = document.getElementById('workflow-list');

function renderWorkflows(): void {
  if (!listEl) return;
  listEl.innerHTML = '';

  const workflows = workflowStore.getAll();

  if (workflows.size === 0) {
    listEl.innerHTML = '<div class="workflow-card">当前无活跃工作流。</div>';
    return;
  }

  for (const [id, wf] of workflows) {
    const card = document.createElement('div');
    card.className = 'workflow-card';

    const badge = document.createElement('span');
    badge.className = `status-badge status-${wf.status}`;
    badge.textContent = wf.status;

    const title = document.createElement('h3');
    title.textContent = wf.name;

    const idEl = document.createElement('p');
    idEl.innerHTML = `<small>ID: ${escapeHTML(id)}</small>`;

    const stepList = document.createElement('div');
    stepList.className = 'step-list';

    wf.steps.forEach((step, i) => {
      const stepEl = document.createElement('div');
      stepEl.className = 'step-item';
      if (i < wf.currentStep) stepEl.style.opacity = '0.6';
      stepEl.textContent = `${i < wf.currentStep ? '✅' : '⏳'} Step ${i + 1}: ${step.intent}`;
      stepList.appendChild(stepEl);
    });

    card.appendChild(badge);
    card.appendChild(title);
    card.appendChild(idEl);
    card.appendChild(stepList);
    listEl.appendChild(card);
  }
}

// 订阅状态变化
workflowStore.subscribe(renderWorkflows);

// 定时刷新
async function refresh(): Promise<void> {
  try {
    const data = await bridge.callSkill('workflow_engine', 'list');
    if (data && typeof data === 'object') {
      workflowStore.sync(data as Record<string, any>);
    }
  } catch {
    // 静默失败
  }
}

setInterval(refresh, 3000);
refresh();
