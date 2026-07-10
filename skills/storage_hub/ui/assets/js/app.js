class StorageHubUI {
    constructor() {
        this.drives = [];
        this.currentDrive = null;
        this.currentPath = "/";
        this.isMockMode = false;
        this.activePollingInterval = null;

        // Mock state persistence for browser standalone fallback
        this.mockConfigSaved = false;

        this.init();
    }

    async init() {
        // Detect if running inside pywebview or a standard browser
        this.isMockMode = typeof window.pywebview === 'undefined' || typeof window.pywebview.api === 'undefined';

        this.setupEventListeners();
        await this.loadDrives();

        // Render initial view
        this.renderDrives();
        this.updateQuotaOverview();

        // Trigger onboarding spotlight if empty and first time
        this.checkOnboarding();
    }

    setupEventListeners() {
        // SVG Ring hover tooltip toggle
        const ring = document.getElementById('quota-ring-container');
        const tooltip = document.getElementById('quota-details-tooltip');
        if (ring && tooltip) {
            ring.addEventListener('mouseenter', () => tooltip.classList.remove('hidden'));
            ring.addEventListener('mouseleave', () => tooltip.classList.add('hidden'));
        }
    }

    checkOnboarding() {
        const hasDismissed = localStorage.getItem('butler_storage_onboard_dismissed');
        const empty = this.drives.length === 0;

        if (!hasDismissed && empty) {
            document.getElementById('onboarding-overlay').classList.remove('hidden');
        }
    }

    dismissOnboarding() {
        localStorage.setItem('butler_storage_onboard_dismissed', 'true');
        document.getElementById('onboarding-overlay').classList.add('hidden');
        this.showToast("欢迎使用", "开始配置您的存储中心吧！", "success");
    }

    // --- API Bridge Calls ---
    async callBackend(action, params = {}) {
        if (this.isMockMode) {
            return this._mockResponse(action, params);
        }
        try {
            const res = await window.pywebview.api.call_skill('storage_hub', action, params);
            return res;
        } catch (e) {
            console.error("Backend communication failed", e);
            this.showToast("通信失败", "无法连接到 Butler 后端模块：" + e, "error");
            return { status: "error", message: e.toString() };
        }
    }

    async loadDrives() {
        const res = await this.callBackend("list_drives");
        if (res && res.status === "ok") {
            this.drives = res.drives || [];
        } else if (res && Array.isArray(res)) {
            // Backward compatibility
            this.drives = res;
        } else {
            this.drives = [];
        }
    }

    renderDrives() {
        const grid = document.getElementById('drive-list');
        const emptyState = document.getElementById('empty-state-canvas');
        const drivePanel = document.getElementById('drive-grid-container');

        if (this.drives.length === 0) {
            emptyState.classList.remove('hidden');
            drivePanel.classList.add('hidden');
            return;
        }

        emptyState.classList.add('hidden');
        drivePanel.classList.remove('hidden');

        grid.innerHTML = this.drives.map(drive => {
            const percent = drive.total > 0 ? (drive.used / drive.total) * 100 : 0;
            // Adaptive gradient colors based on storage pressure
            let progressColor = "var(--accent-color)";
            if (percent >= 90) progressColor = "#ff453a"; // Red
            else if (percent >= 70) progressColor = "#ff9f0a"; // Amber

            return `
            <div class="drive-card" onclick="ui.openDrive('${drive.id}')">
                <div class="drive-card-header">
                    <span class="card-icon">${drive.icon || '🌐'}</span>
                    <span class="drive-type-badge">${drive.type}</span>
                </div>
                <h3>${drive.name}</h3>
                <div class="stats">${(drive.used).toFixed(1)} GB / ${(drive.total).toFixed(1)} GB</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${percent}%; background: ${progressColor}"></div>
                </div>
            </div>
            `;
        }).join('');
    }

    updateQuotaOverview() {
        let totalUsed = 0;
        let totalCloud = 0;

        this.drives.forEach(d => {
            totalUsed += d.used;
            totalCloud += d.total;
        });

        // Set values
        document.getElementById('quota-used-text').innerText = `${totalUsed.toFixed(1)} GB`;
        document.getElementById('quota-total-text').innerText = `${totalCloud.toFixed(1)} GB`;

        // Update Circular SVG Quota Progress Ring
        const percent = totalCloud > 0 ? (totalUsed / totalCloud) * 100 : 0;
        document.getElementById('quota-percent-num').innerText = `${Math.round(percent)}%`;

        const ring = document.getElementById('quota-svg-ring');
        if (ring) {
            // Stroke dasharray diameter logic: r = 26 => C = 2 * PI * 26 = ~163.36
            const circumference = 163.36;
            const offset = circumference - (percent / 100) * circumference;
            ring.style.strokeDashoffset = offset;

            // Update circle stroke color based on pressure
            if (percent >= 90) ring.style.stroke = "#ff453a";
            else if (percent >= 70) ring.style.stroke = "#ff9f0a";
            else ring.style.stroke = "var(--accent-color)";
        }
    }

    async openDrive(driveId) {
        this.currentDrive = driveId;
        const drive = this.drives.find(d => d.id === driveId);
        document.getElementById('current-drive').innerText = drive.name;

        document.getElementById('drive-grid-container').classList.add('hidden');
        document.getElementById('file-explorer').classList.remove('hidden');

        await this.loadFiles("/");
    }

    closeDrive() {
        this.currentDrive = null;
        document.getElementById('drive-grid-container').classList.remove('hidden');
        document.getElementById('file-explorer').classList.add('hidden');
    }

    async loadFiles(path) {
        this.currentPath = path;
        document.getElementById('current-path').innerText = path === "/" ? "根目录" : path;

        const res = await this.callBackend("list_files", { drive: this.currentDrive, path: path });
        if (res && res.status === "ok") {
            this.renderFiles(res.files || []);
        } else {
            this.renderFiles([]);
            this.showToast("读取失败", res.message || "无法加载该路径下的文件", "error");
        }
    }

    renderFiles(files) {
        const list = document.getElementById('file-list');
        if (files.length === 0) {
            list.innerHTML = `
                <div style="padding: 40px; text-align: center; color: var(--text-tertiary); font-size: 13px;">
                    📂 暂无任何文件或文件夹
                </div>
            `;
            return;
        }

        list.innerHTML = files.map((file, idx) => {
            const sizeStr = file.is_dir ? '--' : this.formatSize(file.size);
            return `
            <div class="file-item" draggable="true" ondragstart="ui.onFileDragStart(event, ${idx}, '${file.name}')">
                <span class="icon">${file.is_dir ? '📁' : '📄'}</span>
                <span class="name">${file.name}</span>
                <span class="size">${sizeStr}</span>
                <div class="actions">
                    <button class="btn-icon-more" onclick="ui.showContextMenu(event, ${idx}, '${file.name}')">⋮</button>
                </div>
            </div>
            `;
        }).join('');

        // Attach global drag-drop over the workspace main
        const mainPanel = document.getElementById('storage-app');
        mainPanel.ondragover = (e) => {
            e.preventDefault();
            mainPanel.classList.add('drag-hover');
        };
        mainPanel.ondragleave = (e) => {
            e.preventDefault();
            mainPanel.classList.remove('drag-hover');
        };
        mainPanel.ondrop = (e) => {
            e.preventDefault();
            mainPanel.classList.remove('drag-hover');
            this.onFileDrop(e);
        };
    }

    // --- Drag & Drop Operations ---
    onFileDragStart(e, idx, name) {
        e.dataTransfer.setData("text/plain", JSON.stringify({
            index: idx,
            name: name,
            sourceDrive: this.currentDrive,
            sourcePath: this.currentPath
        }));
    }

    onFileDrop(e) {
        try {
            const dataStr = e.dataTransfer.getData("text/plain");
            if (!dataStr) return;
            const payload = JSON.parse(dataStr);

            if (payload.sourceDrive) {
                // Dragged from one of our drives! Offer target list excluding current source drive
                this.showTargetChooser(payload);
            }
        } catch (err) {
            console.error("Drop handling failed", err);
        }
    }

    showTargetChooser(payload) {
        const modal = document.getElementById('target-chooser-modal');
        const list = document.getElementById('target-drive-list');

        // Exclude current drive
        const targets = this.drives.filter(d => d.id !== payload.sourceDrive);

        if (targets.length === 0) {
            this.showToast("无法中转", "请先配置至少两个网盘驱动以启用跨盘高速传输！", "error");
            return;
        }

        list.innerHTML = targets.map(d => `
            <button class="target-drv-btn" onclick="ui.executeCrossTransfer('${payload.sourceDrive}', '${d.id}', '${payload.name}')">
                <span>${d.icon || '🌐'}</span>
                <span>传输到 ${d.name} (${d.type})</span>
            </button>
        `).join('');

        modal.classList.remove('hidden');
    }

    closeTargetChooser() {
        document.getElementById('target-chooser-modal').classList.add('hidden');
    }

    // --- High-Performance Streaming Transfer ---
    async executeCrossTransfer(srcDrive, dstDrive, fileName) {
        this.closeTargetChooser();

        // Display loading transfer bar
        document.getElementById('transfer-overlay').classList.remove('hidden');
        document.getElementById('transfer-title').innerText = "正在初始化流传输线路...";
        document.getElementById('transfer-file').innerText = fileName;
        document.getElementById('transfer-route').innerText = `${srcDrive} ➜ ${dstDrive}`;
        document.getElementById('transfer-progress-fill').style.width = `0%`;
        document.getElementById('transfer-progress-text').innerText = `0%`;
        document.getElementById('transfer-speed-text').innerText = `0.0 MB/s`;

        const res = await this.callBackend("transfer", {
            src_drive: srcDrive,
            dst_drive: dstDrive,
            file_name: fileName,
            dst_path: "/"
        });

        if (res && res.status === "ok") {
            const taskId = res.task_id;
            // Begin status polling loop
            this.startStatusPolling(taskId);
        } else {
            document.getElementById('transfer-overlay').classList.add('hidden');
            this.showToast("启动失败", res.message || "无法建立高速中转通道", "error");
        }
    }

    startStatusPolling(taskId) {
        if (this.activePollingInterval) clearInterval(this.activePollingInterval);

        this.activePollingInterval = setInterval(async () => {
            const res = await this.callBackend("check_transfer_status", { task_id: taskId });
            if (res && res.status === "ok") {
                const task = res.task;
                document.getElementById('transfer-title').innerText = "跨盘极速流传输中...";
                document.getElementById('transfer-progress-fill').style.width = `${task.progress}%`;
                document.getElementById('transfer-progress-text').innerText = `${task.progress}%`;
                document.getElementById('transfer-speed-text').innerText = task.speed;
                document.getElementById('transfer-mode').innerText = task.pipe_mode || "RAM-Pipe 极速内存流管道";

                if (task.status === "completed") {
                    clearInterval(this.activePollingInterval);
                    document.getElementById('transfer-overlay').classList.add('hidden');
                    this.showToast("传输成功", "文件流中转已完成！", "success");
                    this.loadFiles(this.currentPath);
                }
            } else {
                clearInterval(this.activePollingInterval);
                document.getElementById('transfer-overlay').classList.add('hidden');
                this.showToast("传输异常", res.message || "流传输被意外中断", "error");
            }
        }, 500);
    }

    // --- Configuration Modals ---
    toggleConfigModal(show) {
        const modal = document.getElementById('config-modal');
        if (show) {
            modal.classList.remove('hidden');
            this.onDriveTypeChange();
        } else {
            modal.classList.add('hidden');
        }
    }

    onDriveTypeChange() {
        const type = document.getElementById('drive-type-select').value;
        const webdav = document.getElementById('subgroup-webdav');
        const onedrive = document.getElementById('subgroup-onedrive');

        if (type === "webdav") {
            webdav.classList.remove('hidden');
            onedrive.classList.add('hidden');
        } else {
            webdav.classList.add('hidden');
            onedrive.classList.remove('hidden');
        }
    }

    async saveConfig(e) {
        e.preventDefault();

        const type = document.getElementById('drive-type-select').value;
        let driveConfig = {};

        if (type === "webdav") {
            driveConfig = {
                type: "webdav",
                id: document.getElementById('webdav-id').value,
                name: document.getElementById('webdav-name').value,
                base_url: document.getElementById('webdav-url').value,
                username: document.getElementById('webdav-username').value,
                password: document.getElementById('webdav-password').value
            };
        } else {
            driveConfig = {
                type: "onedrive",
                id: document.getElementById('onedrive-id').value,
                name: document.getElementById('onedrive-name').value,
                client_id: document.getElementById('onedrive-client-id').value,
                client_secret: document.getElementById('onedrive-client-secret').value,
                redirect_uri: document.getElementById('onedrive-redirect').value
            };
        }

        // Send to backend save_config API
        // For standard setup we read current config first and append or replace
        const currentConfRes = await this.callBackend("load_config");
        let currentDrives = [];
        if (currentConfRes && currentConfRes.status === "ok") {
            currentDrives = currentConfRes.config.drives || [];
        }

        // Replace if exists, else append
        const existingIdx = currentDrives.findIndex(d => d.id === driveConfig.id);
        if (existingIdx > -1) {
            currentDrives[existingIdx] = driveConfig;
        } else {
            currentDrives.push(driveConfig);
        }

        const saveRes = await this.callBackend("save_config", { config: { drives: currentDrives } });
        if (saveRes && saveRes.status === "ok") {
            this.toggleConfigModal(false);
            this.showToast("配置已保存", "云盘存储驱动已成功初始化并连接！", "success");

            // Reload views
            this.mockConfigSaved = true;
            await this.loadDrives();
            this.renderDrives();
            this.updateQuotaOverview();
        } else {
            this.showToast("保存失败", saveRes.message || "无法持久化配置文件", "error");
        }
    }

    // --- Context Menu Trigger Mock ---
    showContextMenu(e, idx, name) {
        e.stopPropagation();
        this.showToast("极简选项", `已选择文件 "${name}"。您可以直接拖拽该行来触发跨盘零落地传输。`, "success");
    }

    // --- Global Toast Notification ---
    showToast(title, message, type = "success") {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icon = type === "success" ? "✓" : "✗";
        toast.innerHTML = `
            <span class="toast-icon">${icon}</span>
            <div>
                <strong style="display:block; margin-bottom:2px;">${title}</strong>
                <span style="font-size:12px; opacity:0.8;">${message}</span>
            </div>
        `;

        container.appendChild(toast);

        // Auto dismiss after 4 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            toast.style.transition = 'all 0.4s ease';
            setTimeout(() => toast.remove(), 400);
        }, 4000);
    }

    formatSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    // --- Mock Fallbacks for Browser Standalone Testing ---
    _mockResponse(action, params) {
        if (action === "list_drives") {
            if (!this.mockConfigSaved) {
                // Start as empty to let user see empty state & onboarding spotlight!
                return { status: "ok", drives: [] };
            }
            return {
                status: "ok",
                drives: [
                    { id: "microsoft_onedrive", name: "Microsoft OneDrive", type: "onedrive", used: 1240, total: 5120, icon: "☁️" },
                    { id: "alist_webdav", name: "AList WebDAV", type: "webdav", used: 1820, total: 2048, icon: "🌐" }
                ]
            };
        }

        if (action === "load_config") {
            return { status: "ok", config: { drives: [] } };
        }

        if (action === "save_config") {
            return { status: "ok" };
        }

        if (action === "list_files") {
            const files = params.drive === "microsoft_onedrive" ? [
                { name: "学习资料", is_dir: true, size: 0 },
                { name: "工作汇报.docx", is_dir: false, size: 1024 * 412 },
                { name: "Butler_Architecture_v2.pdf", is_dir: false, size: 1024 * 1024 * 12.4 }
            ] : [
                { name: "Media_Streaming", is_dir: true, size: 0 },
                { name: "Ubuntu_24.04_LTS.iso", is_dir: false, size: 1024 * 1024 * 1024 * 3.8 },
                { name: "Readme_Guide.txt", is_dir: false, size: 4096 }
            ];
            return { status: "ok", files: files };
        }

        if (action === "transfer") {
            return { status: "ok", task_id: "mock_task_999" };
        }

        if (action === "check_transfer_status") {
            // Increments progress mockup
            if (!this._mockProgress) this._mockProgress = 0;
            this._mockProgress += 15;

            if (this._mockProgress >= 100) {
                this._mockProgress = 0; // reset
                return {
                    status: "ok",
                    task: {
                        progress: 100,
                        speed: "0.0 MB/s",
                        status: "completed",
                        pipe_mode: "RAM-Pipe 极速内存流管道"
                    }
                };
            }

            return {
                status: "ok",
                task: {
                    progress: this._mockProgress,
                    speed: `${(45.5 + Math.random() * 10).toFixed(1)} MB/s`,
                    status: "transferring",
                    pipe_mode: "RAM-Pipe 极速内存流管道"
                }
            };
        }

        return { status: "error", message: `Unknown action ${action}` };
    }
}

const ui = new StorageHubUI();
window.ui = ui;
