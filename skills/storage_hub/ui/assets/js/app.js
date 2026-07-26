class StorageHubUI {
    constructor() {
        this.drives = [];
        this.currentDrive = null;
        this.currentPath = "/";
        this.isMockMode = false;
        this.activePollingInterval = null;

        // Selection & Search state
        this.allFiles = [];
        this.selectedFiles = []; // array of selected indices in this.allFiles
        this.singleSelectedIndex = null; // index for single action in popup menu
        this.selectedChooserPath = "/";
        this.chooserAction = null; // 'copy', 'move', 'batch_copy', 'batch_move'
        this.lightboxImages = [];
        this.lightboxIndex = -1;

        // Mock state persistence for browser standalone fallback
        this.mockConfigSaved = false;

        // Initialize persistent mock files in localStorage
        const defaultMockFiles = {
            "microsoft_onedrive": [
                { name: "学习资料", is_dir: true, size: 0, path: "/学习资料" },
                { name: "工作汇报.docx", is_dir: false, size: 1024 * 412, path: "/工作汇报.docx" },
                { name: "Butler_Architecture_v2.pdf", is_dir: false, size: 1024 * 1024 * 12.4, path: "/Butler_Architecture_v2.pdf" },
                { name: "演示幻灯片.pptx", is_dir: false, size: 1024 * 1024 * 3.5, path: "/演示幻灯片.pptx" },
                { name: "Butler_Logo.png", is_dir: false, size: 1024 * 512, path: "/Butler_Logo.png" }
            ],
            "baidu_netdisk": [
                { name: "电影视频", is_dir: true, size: 0, path: "/电影视频" },
                { name: "备份照片.zip", is_dir: false, size: 1024 * 1024 * 145.2, path: "/备份照片.zip" },
                { name: "我的简历.pdf", is_dir: false, size: 1024 * 380, path: "/我的简历.pdf" },
                { name: "风景照片.jpg", is_dir: false, size: 1024 * 840, path: "/风景照片.jpg" }
            ],
            "alist_webdav": [
                { name: "Media_Streaming", is_dir: true, size: 0, path: "/Media_Streaming" },
                { name: "Ubuntu_24.04_LTS.iso", is_dir: false, size: 1024 * 1024 * 1024 * 3.8, path: "/Ubuntu_24.04_LTS.iso" },
                { name: "Readme_Guide.txt", is_dir: false, size: 4096, path: "/Readme_Guide.txt" },
                { name: "系统壁纸.png", is_dir: false, size: 1024 * 1200, path: "/系统壁纸.png" }
            ]
        };

        for (const driveId in defaultMockFiles) {
            const key = `butler_mock_files_${driveId}`;
            if (!localStorage.getItem(key)) {
                localStorage.setItem(key, JSON.stringify(defaultMockFiles[driveId]));
            }
        }

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

        document.getElementById('quota-used-text').innerText = `${totalUsed.toFixed(1)} GB`;
        document.getElementById('quota-total-text').innerText = `${totalCloud.toFixed(1)} GB`;

        const percent = totalCloud > 0 ? (totalUsed / totalCloud) * 100 : 0;
        document.getElementById('quota-percent-num').innerText = `${Math.round(percent)}%`;

        const ring = document.getElementById('quota-svg-ring');
        if (ring) {
            const circumference = 163.36;
            const offset = circumference - (percent / 100) * circumference;
            ring.style.strokeDashoffset = offset;

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
        this.selectedFiles = [];
        this.updateBatchPanel();
    }

    async loadFiles(path) {
        this.currentPath = path;
        document.getElementById('current-path').innerText = path === "/" ? "根目录" : path;

        // Reset search field
        document.getElementById('search-input').value = "";

        const res = await this.callBackend("list_files", { drive: this.currentDrive, path: path });
        if (res && res.status === "ok") {
            this.renderFiles(res.files || []);
        } else {
            this.renderFiles([]);
            this.showToast("读取失败", res.message || "无法加载该路径下的文件", "error");
        }
    }

    renderFiles(files) {
        this.allFiles = files;
        this.selectedFiles = [];
        this.updateBatchPanel();

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
            const escapedName = file.name.replace(/'/g, "\\'");
            const escapedId = (file.id || "").replace(/'/g, "\\'");

            const isImg = this.isImageFile(file.name);
            const onclickAttr = isImg ? `onclick="ui.openLightbox(${idx})"` : `onclick="ui.onFileClick(${idx})"`;

            return `
            <div class="file-item" draggable="true" ondragstart="ui.onFileDragStart(event, ${idx}, '${escapedName}', '${escapedId}', ${file.size || 0})">
                <span class="checkbox-col" onclick="event.stopPropagation()">
                    <input type="checkbox" class="apple-checkbox file-item-checkbox" data-idx="${idx}" onchange="ui.onFileSelectChange(${idx}, this.checked)">
                </span>
                <span class="icon" ${onclickAttr}>${file.is_dir ? '📁' : '📄'}</span>
                <span class="name" ${onclickAttr}>${file.name}</span>
                <span class="size" ${onclickAttr}>${sizeStr}</span>
                <div class="actions">
                    <button class="btn-icon-more" onclick="ui.showContextMenu(event, ${idx}, '${escapedName}')">⋮</button>
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

    joinPath(base, segment) {
        const b = base.replace(/\/+$/, "");
        const s = segment.replace(/^\/+/, "");
        return b === "" ? "/" + s : b + "/" + s;
    }

    onFileClick(idx) {
        const file = this.allFiles[idx];
        if (file && file.is_dir) {
            const newPath = this.joinPath(this.currentPath, file.name);
            this.loadFiles(newPath);
        }
    }

    // --- Image File Helper ---
    isImageFile(name) {
        const ext = name.split('.').pop().toLowerCase();
        return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext);
    }

    // --- Search Logic ---
    onSearchInput(value) {
        const query = value.trim().toLowerCase();
        const searchAll = document.getElementById('search-all-checkbox').checked;

        if (searchAll) {
            if (query.length >= 2) {
                this.executeSearchAll(query);
            }
            return;
        }

        if (!query) {
            this.renderFilteredFiles(this.allFiles);
            return;
        }

        // Support path: prefix syntax
        if (query.startsWith('path:')) {
            const targetPath = query.substring(5).trim();
            const filtered = this.allFiles.filter(f => f.path && f.path.toLowerCase().includes(targetPath));
            this.renderFilteredFiles(filtered);
            return;
        }

        const filtered = this.allFiles.filter(f => f.name.toLowerCase().includes(query));
        this.renderFilteredFiles(filtered);
    }

    async executeSearchAll(query) {
        const res = await this.callBackend("search_all", { query: query });
        if (res && res.status === "ok") {
            const results = (res.results || []).filter(r => r.drive === this.currentDrive);
            this.renderFilteredFiles(results);
        }
    }

    onSearchAllToggle(checked) {
        const searchInput = document.getElementById('search-input');
        if (!checked) {
            this.renderFilteredFiles(this.allFiles);
        } else if (searchInput.value.trim().length >= 2) {
            this.executeSearchAll(searchInput.value.trim());
        }
    }

    renderFilteredFiles(files) {
        const list = document.getElementById('file-list');
        if (files.length === 0) {
            list.innerHTML = `
                <div style="padding: 40px; text-align: center; color: var(--text-tertiary); font-size: 13px;">
                    🔍 未找到匹配的文件
                </div>
            `;
            return;
        }

        list.innerHTML = files.map((file) => {
            const sizeStr = file.is_dir ? '--' : this.formatSize(file.size);
            const escapedName = file.name.replace(/'/g, "\\'");
            const escapedId = (file.id || "").replace(/'/g, "\\'");

            const idx = this.allFiles.findIndex(f => f.name === file.name);
            const isImg = this.isImageFile(file.name);
            const onclickAttr = isImg ? `onclick="ui.openLightbox(${idx})"` : `onclick="ui.onFileClick(${idx})"`;

            return `
            <div class="file-item" draggable="true" ondragstart="ui.onFileDragStart(event, ${idx}, '${escapedName}', '${escapedId}', ${file.size || 0})">
                <span class="checkbox-col" onclick="event.stopPropagation()">
                    <input type="checkbox" class="apple-checkbox file-item-checkbox" data-idx="${idx}" onchange="ui.onFileSelectChange(${idx}, this.checked)">
                </span>
                <span class="icon" ${onclickAttr}>${file.is_dir ? '📁' : '📄'}</span>
                <span class="name" ${onclickAttr}>${file.name}</span>
                <span class="size" ${onclickAttr}>${sizeStr}</span>
                <div class="actions">
                    <button class="btn-icon-more" onclick="ui.showContextMenu(event, ${idx}, '${escapedName}')">⋮</button>
                </div>
            </div>
            `;
        }).join('');
    }

    // --- Checkbox selection handlers ---
    onFileSelectChange(idx, checked) {
        if (checked) {
            if (!this.selectedFiles.includes(idx)) {
                this.selectedFiles.push(idx);
            }
        } else {
            this.selectedFiles = this.selectedFiles.filter(i => i !== idx);
        }
        this.updateBatchPanel();
    }

    toggleSelectAll(checked) {
        document.querySelectorAll('.file-item-checkbox').forEach(cb => {
            cb.checked = checked;
            const idx = parseInt(cb.getAttribute('data-idx'));
            if (checked) {
                if (!this.selectedFiles.includes(idx)) this.selectedFiles.push(idx);
            } else {
                this.selectedFiles = this.selectedFiles.filter(i => i !== idx);
            }
        });
        this.updateBatchPanel();
    }

    updateBatchPanel() {
        const panel = document.getElementById('batch-panel');
        const count = document.getElementById('batch-count');
        const selectAllCb = document.getElementById('select-all-checkbox');

        if (this.selectedFiles.length > 0) {
            panel.classList.add('active');
            count.innerText = this.selectedFiles.length;
            if (selectAllCb) {
                selectAllCb.checked = this.selectedFiles.length === this.allFiles.length;
            }
        } else {
            panel.classList.remove('active');
            if (selectAllCb) selectAllCb.checked = false;
        }
    }

    // --- Directory Chooser tree Modal ---
    openDirectoryChooser(actionType) {
        this.chooserAction = actionType;
        const modal = document.getElementById('directory-chooser-modal');
        const container = document.getElementById('directory-tree');

        const dirs = [{ name: "根目录 (/)", path: "/" }];
        if (this.allFiles) {
            this.allFiles.forEach(f => {
                if (f.is_dir) {
                    dirs.push({
                        name: f.name,
                        path: this.joinPath(this.currentPath, f.name)
                    });
                }
            });
        }

        this.selectedChooserPath = "/";

        container.innerHTML = dirs.map(d => `
            <div class="directory-node ${d.path === '/' ? 'selected' : ''}" data-path="${d.path}" onclick="ui.onSelectChooserPath(this, '${d.path}')">
                📁 ${d.name}
            </div>
        `).join('');

        modal.classList.remove('hidden');
    }

    onSelectChooserPath(element, path) {
        document.querySelectorAll('.directory-node').forEach(n => n.classList.remove('selected'));
        element.classList.add('selected');
        this.selectedChooserPath = path;
    }

    closeDirectoryChooser() {
        document.getElementById('directory-chooser-modal').classList.add('hidden');
    }

    async confirmDirectoryChooser() {
        const targetPath = this.selectedChooserPath;
        this.closeDirectoryChooser();

        if (this.chooserAction === 'copy') {
            const file = this.allFiles[this.singleSelectedIndex];
            const srcPath = this.joinPath(this.currentPath, file.name);
            const dstPath = this.joinPath(targetPath, file.name);

            this.showToast("正在复制", `正在复制 "${file.name}"...`, "success");
            const res = await this.callBackend("copy_file", { drive: this.currentDrive, src_path: srcPath, dst_path: dstPath });
            if (res && res.status === "ok") {
                this.showToast("复制成功", `已成功复制到 ${targetPath}`, "success");
                this.loadFiles(this.currentPath);
            } else {
                this.showToast("复制失败", res.message || "操作无法完成", "error");
            }
        } else if (this.chooserAction === 'move') {
            const file = this.allFiles[this.singleSelectedIndex];
            const srcPath = this.joinPath(this.currentPath, file.name);
            const dstPath = this.joinPath(targetPath, file.name);

            this.showToast("正在移动", `正在移动 "${file.name}"...`, "success");
            const res = await this.callBackend("move_file", { drive: this.currentDrive, src_path: srcPath, dst_path: dstPath });
            if (res && res.status === "ok") {
                this.showToast("移动成功", `已成功移动到 ${targetPath}`, "success");
                this.loadFiles(this.currentPath);
            } else {
                this.showToast("移动失败", res.message || "操作无法完成", "error");
            }
        } else if (this.chooserAction === 'batch_copy') {
            this.showToast("正在批量复制", `正在复制 ${this.selectedFiles.length} 个项目...`, "success");
            let successCount = 0;
            let failCount = 0;
            for (const idx of this.selectedFiles) {
                const file = this.allFiles[idx];
                const srcPath = this.joinPath(this.currentPath, file.name);
                const dstPath = this.joinPath(targetPath, file.name);

                const res = await this.callBackend("copy_file", { drive: this.currentDrive, src_path: srcPath, dst_path: dstPath });
                if (res && res.status === "ok") successCount++;
                else failCount++;
            }
            this.showToast("批量复制结果", `成功: ${successCount} 项, 失败: ${failCount} 项`, successCount > 0 ? "success" : "error");
            this.loadFiles(this.currentPath);
        } else if (this.chooserAction === 'batch_move') {
            this.showToast("正在批量移动", `正在移动 ${this.selectedFiles.length} 个项目...`, "success");
            let successCount = 0;
            let failCount = 0;
            for (const idx of this.selectedFiles) {
                const file = this.allFiles[idx];
                const srcPath = this.joinPath(this.currentPath, file.name);
                const dstPath = this.joinPath(targetPath, file.name);

                const res = await this.callBackend("move_file", { drive: this.currentDrive, src_path: srcPath, dst_path: dstPath });
                if (res && res.status === "ok") successCount++;
                else failCount++;
            }
            this.showToast("批量移动结果", `成功: ${successCount} 项, 失败: ${failCount} 项`, successCount > 0 ? "success" : "error");
            this.loadFiles(this.currentPath);
        }
    }

    // --- Batch actions triggers ---
    startBatchCopy() {
        this.openDirectoryChooser('batch_copy');
    }

    startBatchMove() {
        this.openDirectoryChooser('batch_move');
    }

    async startBatchDelete() {
        const confirmMsg = `确定要批量删除选择的 ${this.selectedFiles.length} 个文件/文件夹吗？此操作无法撤销。`;
        if (!confirm(confirmMsg)) return;

        let successCount = 0;
        let failCount = 0;

        this.showToast("正在批量删除", `正在删除 ${this.selectedFiles.length} 项...`, "success");

        for (const idx of this.selectedFiles) {
            const file = this.allFiles[idx];
            if (!file) continue;

            const filePath = this.joinPath(this.currentPath, file.name);
            const res = await this.callBackend("delete_file", { drive: this.currentDrive, path: filePath });
            if (res && res.status === "ok") {
                successCount++;
            } else {
                failCount++;
            }
        }

        this.showToast("批量删除结果", `成功: ${successCount} 项, 失败: ${failCount} 项`, successCount > 0 ? "success" : "error");
        await this.loadFiles(this.currentPath);
    }

    // --- Single Operations actions ---
    startRename(idx, name) {
        const newName = prompt("请输入新的名称：", name);
        if (!newName || newName === name) return;

        const file = this.allFiles[idx];
        const oldPath = this.joinPath(this.currentPath, file.name);

        this.callBackend("rename_file", { drive: this.currentDrive, path: oldPath, new_name: newName }).then(res => {
            if (res && res.status === "ok") {
                this.showToast("重命名成功", `已重命名为 "${newName}"`, "success");
                this.loadFiles(this.currentPath);
            } else {
                this.showToast("重命名失败", res.message || "操作无法完成", "error");
            }
        });
    }

    startSingleCopy(idx, name) {
        this.singleSelectedIndex = idx;
        this.openDirectoryChooser('copy');
    }

    startSingleMove(idx, name) {
        this.singleSelectedIndex = idx;
        this.openDirectoryChooser('move');
    }

    startSingleDelete(idx, name) {
        if (!confirm(`确定要删除 "${name}" 吗？此操作不可撤销。`)) return;
        const file = this.allFiles[idx];
        const filePath = this.joinPath(this.currentPath, file.name);

        this.callBackend("delete_file", { drive: this.currentDrive, path: filePath }).then(res => {
            if (res && res.status === "ok") {
                this.showToast("删除成功", `已删除 "${name}"`, "success");
                this.loadFiles(this.currentPath);
            } else {
                this.showToast("删除失败", res.message || "无法删除文件", "error");
            }
        });
    }

    // --- Lightbox Image Preview Modal ---
    openLightbox(idx) {
        this.lightboxImages = this.allFiles.filter(f => !f.is_dir && this.isImageFile(f.name));
        this.lightboxIndex = this.lightboxImages.findIndex(f => f.name === this.allFiles[idx].name);

        if (this.lightboxIndex === -1) return;

        document.getElementById('lightbox-modal').classList.remove('hidden');
        this.renderLightboxImage();
        this.renderLightboxThumbnails();

        this.lightboxKeyHandler = (e) => {
            if (e.key === 'ArrowRight') this.nextImage();
            else if (e.key === 'ArrowLeft') this.prevImage();
            else if (e.key === 'Escape') this.closeLightbox();
        };
        document.addEventListener('keydown', this.lightboxKeyHandler);
    }

    closeLightbox() {
        document.getElementById('lightbox-modal').classList.add('hidden');
        document.removeEventListener('keydown', this.lightboxKeyHandler);
    }

    renderLightboxImage() {
        const file = this.lightboxImages[this.lightboxIndex];
        if (!file) return;

        document.getElementById('lightbox-title').innerText = file.name;
        const img = document.getElementById('lightbox-img');

        if (this.isMockMode) {
            img.src = `https://images.unsplash.com/photo-1542831371-29b0f74f9713?auto=format&fit=crop&w=800&q=80`;
        } else {
            this.callBackend("get_download_link", { drive: this.currentDrive, file_id: file.id }).then(res => {
                if (res && res.status === "ok") {
                    img.src = res.url || res;
                } else if (typeof res === 'string') {
                    img.src = res;
                } else {
                    img.src = `https://images.unsplash.com/photo-1542831371-29b0f74f9713?auto=format&fit=crop&w=800&q=80`;
                }
            });
        }

        document.getElementById('lightbox-img-container').classList.remove('zoomed');
    }

    renderLightboxThumbnails() {
        const container = document.getElementById('lightbox-thumbnails');
        container.innerHTML = this.lightboxImages.map((file, idx) => `
            <img class="lightbox-thumb ${idx === this.lightboxIndex ? 'active' : ''}" src="https://images.unsplash.com/photo-1542831371-29b0f74f9713?auto=format&fit=crop&w=150&q=80" onclick="ui.setLightboxIndex(${idx})">
        `).join('');
    }

    setLightboxIndex(idx) {
        this.lightboxIndex = idx;
        this.renderLightboxImage();
        this.renderLightboxThumbnails();
    }

    prevImage() {
        if (this.lightboxImages.length <= 1) return;
        this.lightboxIndex = (this.lightboxIndex - 1 + this.lightboxImages.length) % this.lightboxImages.length;
        this.renderLightboxImage();
        this.renderLightboxThumbnails();
    }

    nextImage() {
        if (this.lightboxImages.length <= 1) return;
        this.lightboxIndex = (this.lightboxIndex + 1) % this.lightboxImages.length;
        this.renderLightboxImage();
        this.renderLightboxThumbnails();
    }

    toggleZoomImage() {
        document.getElementById('lightbox-img-container').classList.toggle('zoomed');
    }

    // --- Drag & Drop Operations ---
    onFileDragStart(e, idx, name, id = "", size = 0) {
        e.dataTransfer.setData("text/plain", JSON.stringify({
            index: idx,
            name: name,
            id: id,
            size: size,
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
                this.showTargetChooser(payload);
            }
        } catch (err) {
            console.error("Drop handling failed", err);
        }
    }

    showTargetChooser(payload) {
        const modal = document.getElementById('target-chooser-modal');
        const list = document.getElementById('target-drive-list');

        const targets = this.drives.filter(d => d.id !== payload.sourceDrive);

        if (targets.length === 0) {
            this.showToast("无法中转", "请先配置至少两个网盘驱动以启用跨盘高速传输！", "error");
            return;
        }

        const escapedName = payload.name.replace(/'/g, "\\'");
        const escapedId = (payload.id || "").replace(/'/g, "\\'");
        const escapedSourcePath = (payload.sourcePath || "/").replace(/'/g, "\\'");

        list.innerHTML = targets.map(d => `
            <button class="target-drv-btn" onclick="ui.executeCrossTransfer('${payload.sourceDrive}', '${d.id}', '${escapedName}', '${escapedId}', ${payload.size || 0}, '${escapedSourcePath}')">
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
    async executeCrossTransfer(srcDrive, dstDrive, fileName, fileId = "", fileSize = 0, sourcePath = "/") {
        this.closeTargetChooser();

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
            file_id: fileId,
            file_size: fileSize,
            source_path: sourcePath,
            dst_path: "/"
        });

        if (res && res.status === "ok") {
            const taskId = res.task_id;
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
        const baidu = document.getElementById('subgroup-baidu');

        webdav.classList.add('hidden');
        onedrive.classList.add('hidden');
        baidu.classList.add('hidden');

        if (type === "webdav") {
            webdav.classList.remove('hidden');
        } else if (type === "onedrive") {
            onedrive.classList.remove('hidden');
        } else if (type === "baidu") {
            baidu.classList.remove('hidden');
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
        } else if (type === "onedrive") {
            driveConfig = {
                type: "onedrive",
                id: document.getElementById('onedrive-id').value,
                name: document.getElementById('onedrive-name').value,
                client_id: document.getElementById('onedrive-client-id').value,
                client_secret: document.getElementById('onedrive-client-secret').value,
                redirect_uri: document.getElementById('onedrive-redirect').value
            };
        } else if (type === "baidu") {
            driveConfig = {
                type: "baidu",
                id: document.getElementById('baidu-id').value,
                name: document.getElementById('baidu-name').value
            };
        }

        const currentConfRes = await this.callBackend("load_config");
        let currentDrives = [];
        if (currentConfRes && currentConfRes.status === "ok") {
            currentDrives = currentConfRes.config.drives || [];
        }

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

            this.mockConfigSaved = true;
            await this.loadDrives();
            this.renderDrives();
            this.updateQuotaOverview();
        } else {
            this.showToast("保存失败", saveRes.message || "无法持久化配置文件", "error");
        }
    }

    // --- High Fidelity Option Pop Menu Trigger ---
    showContextMenu(e, idx, name) {
        e.stopPropagation();
        const existing = document.getElementById('custom-context-menu');
        if (existing) existing.remove();

        const menu = document.createElement('div');
        menu.id = 'custom-context-menu';
        menu.className = 'custom-context-menu';
        menu.style.left = `${e.clientX}px`;
        menu.style.top = `${e.clientY}px`;

        menu.innerHTML = `
            <div class="context-menu-item" onclick="ui.startRename(${idx}, '${name.replace(/'/g, "\\'")}')">📝 重命名</div>
            <div class="context-menu-item" onclick="ui.startSingleCopy(${idx}, '${name.replace(/'/g, "\\'")}')">📋 复制到</div>
            <div class="context-menu-item" onclick="ui.startSingleMove(${idx}, '${name.replace(/'/g, "\\'")}')">📦 移动到</div>
            <div class="context-menu-item danger" onclick="ui.startSingleDelete(${idx}, '${name.replace(/'/g, "\\'")}')">🗑️ 删除</div>
        `;

        document.body.appendChild(menu);

        const closeMenu = () => {
            menu.remove();
            document.removeEventListener('click', closeMenu);
        };
        setTimeout(() => document.addEventListener('click', closeMenu), 50);
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

    // --- Mock Fallbacks with LocalStorage Local-First Persistence ---
    _mockResponse(action, params) {
        if (action === "list_drives") {
            if (!this.mockConfigSaved) {
                return { status: "ok", drives: [] };
            }
            return {
                status: "ok",
                drives: [
                    { id: "microsoft_onedrive", name: "Microsoft OneDrive", type: "onedrive", used: 1240, total: 5120, icon: "☁️" },
                    { id: "alist_webdav", name: "AList WebDAV", type: "webdav", used: 1820, total: 2048, icon: "🌐" },
                    { id: "baidu_netdisk", name: "Baidu Netdisk", type: "baidu", used: 3450, total: 5120, icon: "🐼" }
                ]
            };
        }

        if (action === "load_config") {
            return { status: "ok", config: { drives: [] } };
        }

        if (action === "save_config") {
            return { status: "ok" };
        }

        const key = `butler_mock_files_${params.drive}`;

        if (action === "list_files") {
            const files = JSON.parse(localStorage.getItem(key) || "[]");
            const targetPath = params.path;
            const filtered = files.filter(f => {
                const parts = f.path.split('/');
                const parent = parts.slice(0, -1).join('/') || "/";
                return parent === targetPath;
            });
            return { status: "ok", files: filtered };
        }

        if (action === "delete_file") {
            let files = JSON.parse(localStorage.getItem(key) || "[]");
            files = files.filter(f => f.path !== params.path && !f.path.startsWith(params.path + "/"));
            localStorage.setItem(key, JSON.stringify(files));
            return { status: "ok" };
        }

        if (action === "rename_file") {
            let files = JSON.parse(localStorage.getItem(key) || "[]");
            const file = files.find(f => f.path === params.path);
            if (file) {
                const oldPath = file.path;
                const parent = oldPath.split('/').slice(0, -1).join('/') || "/";
                const newPath = this.joinPath(parent, params.new_name);

                file.name = params.new_name;
                file.path = newPath;

                files.forEach(f => {
                    if (f.path.startsWith(oldPath + "/")) {
                        f.path = newPath + f.path.substring(oldPath.length);
                    }
                });

                localStorage.setItem(key, JSON.stringify(files));
                return { status: "ok" };
            }
            return { status: "error", message: "File not found" };
        }

        if (action === "copy_file") {
            let files = JSON.parse(localStorage.getItem(key) || "[]");
            const file = files.find(f => f.path === params.src_path);
            if (file) {
                const newFile = JSON.parse(JSON.stringify(file));
                newFile.path = params.dst_path;
                newFile.name = params.dst_path.split('/').pop();
                files.push(newFile);
                localStorage.setItem(key, JSON.stringify(files));
                return { status: "ok" };
            }
            return { status: "error", message: "Source file not found" };
        }

        if (action === "move_file") {
            let files = JSON.parse(localStorage.getItem(key) || "[]");
            const file = files.find(f => f.path === params.src_path);
            if (file) {
                const oldPath = file.path;
                file.path = params.dst_path;
                file.name = params.dst_path.split('/').pop();

                files.forEach(f => {
                    if (f.path.startsWith(oldPath + "/")) {
                        f.path = params.dst_path + f.path.substring(oldPath.length);
                    }
                });

                localStorage.setItem(key, JSON.stringify(files));
                return { status: "ok" };
            }
            return { status: "error", message: "Source file not found" };
        }

        if (action === "create_directory") {
            let files = JSON.parse(localStorage.getItem(key) || "[]");
            const folderName = params.path.split('/').pop();
            const newFolder = {
                name: folderName,
                is_dir: true,
                size: 0,
                path: params.path
            };
            files.push(newFolder);
            localStorage.setItem(key, JSON.stringify(files));
            return { status: "ok" };
        }

        if (action === "search_all") {
            const results = [];
            ["microsoft_onedrive", "baidu_netdisk", "alist_webdav"].forEach(driveId => {
                const mockKey = `butler_mock_files_${driveId}`;
                const files = JSON.parse(localStorage.getItem(mockKey) || "[]");
                files.forEach(f => {
                    if (f.name.toLowerCase().includes(params.query.toLowerCase())) {
                        results.push({
                            drive: driveId,
                            name: f.name,
                            size: f.size,
                            is_dir: f.is_dir,
                            path: f.path,
                            id: f.path
                        });
                    }
                });
            });
            return { status: "ok", results: results };
        }

        if (action === "transfer") {
            return { status: "ok", task_id: "mock_task_999" };
        }

        if (action === "check_transfer_status") {
            if (!this._mockProgress) this._mockProgress = 0;
            this._mockProgress += 15;

            if (this._mockProgress >= 100) {
                this._mockProgress = 0;
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
