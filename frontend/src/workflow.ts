/**
 * Butler Workflow Center Script in TypeScript
 */

async function refreshWorkflows(): Promise<void> {
  try {
    if (window.modernBridge) {
      const workflows = await window.modernBridge.callSkill('workflow_engine', 'list');
      renderWorkflows(workflows);
    }
  } catch (e) {
    console.error('Failed to load workflows', e);
  }
}

function renderWorkflows(workflows: Record<string, any>): void {
  const list = document.getElementById('workflow-list');
  if (!list) return;
  list.innerHTML = '';

  if (!workflows || Object.keys(workflows).length === 0) {
    list.innerHTML = '<div class="workflow-card">当前无活跃工作流。</div>';
    return;
  }

  for (const [id, wf] of Object.entries(workflows)) {
    const card = document.createElement('div');
    card.className = 'workflow-card';
    card.innerHTML = `
      <span class="status-badge status-${wf.status}">${wf.status}</span>
      <h3>${wf.name}</h3>
      <p><small>ID: ${id}</small></p>
      <div class="step-list">
        ${(wf.steps || [])
          .map(
            (step: any, i: number) => `
            <div class="step-item" style="opacity: ${i < wf.current_step ? 0.6 : 1}">
              ${i < wf.current_step ? '✅' : '⏳'} Step ${i + 1}: ${step.intent}
            </div>
          `
          )
          .join('')}
      </div>
    `;
    list.appendChild(card);
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    setInterval(refreshWorkflows, 3000);
    refreshWorkflows();
  });
}
