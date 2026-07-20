// Global State Control
const petAvatar = document.getElementById('pet-avatar');
const petDialog = document.getElementById('pet-dialog');

let idleTimeout = null;

// Initialize custom namespace to prevent conflicts
window.ButlerPet = {
    onEvent: function(payload) {
        const { event, message } = payload;

        switch (event) {
            case 'ai_thinking':
                this.setPetState('state-thinking', message || 'Butler 正在思考...');
                break;
            case 'ai_streaming':
                this.setPetState('state-generating', message || 'Butler 正在生成...');
                break;
            case 'task_success':
                this.setPetState('state-success', message || '执行完毕');
                this.scheduleReset(3000);
                break;
            case 'task_failed':
                this.setPetState('state-error', `错误: ${message || '执行异常'}`);
                this.scheduleReset(5000);
                break;
            case 'user_idle':
                this.setPetState('state-idle', message || '休眠中');
                break;
            default:
                this.resetToIdle();
        }
    },

    setPetState: function(stateClass, text) {
        // Clear previous state classes
        petAvatar.className = 'butler-pet-avatar ' + stateClass;

        if (idleTimeout) {
            clearTimeout(idleTimeout);
            idleTimeout = null;
        }

        // Show dialogue text
        if (text) {
            petDialog.innerText = text;
            petDialog.classList.add('show');
        } else {
            petDialog.classList.remove('show');
        }
    },

    scheduleReset: function(delay) {
        if (idleTimeout) clearTimeout(idleTimeout);
        idleTimeout = setTimeout(() => {
            this.resetToIdle();
        }, delay);
    },

    resetToIdle: function() {
        this.setPetState('state-idle', 'Butler 正在守护你');
        // Let dialog hide automatically after 3 seconds of idle state
        setTimeout(() => {
            if (petAvatar.classList.contains('state-idle')) {
                petDialog.classList.remove('show');
            }
        }, 3000);
    }
};

// Initial state
window.ButlerPet.resetToIdle();
