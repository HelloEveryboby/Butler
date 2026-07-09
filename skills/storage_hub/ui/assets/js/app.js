class StorageHubUI {
    constructor() {
        this.drives = [];
        this.currentDrive = null;
        this.currentPath = "/";

        this.init();
    }

    async init() {
        await this.loadDrives();
        this.renderDrives();
    }

    async loadDrives() {
        // Mocking for now
        this.drives = [
            { id: "onedrive_personal", name: "OneDrive", type: "onedrive", used: 1200, total: 5120, icon: "☁️" },
            { id: "baidu_pan", name: "Baidu Pan", type: "baidu", used: 450, total: 2048, icon: "🐾" },
            { id: "quark_pan", name: "Quark", type: "quark", used: 120, total: 1024, icon: "🚀" }
        ];
    }

    renderDrives() {
        const grid = document.getElementById('drive-list');
        grid.innerHTML = this.drives.map(drive => {
            const percent = (drive.used / drive.total) * 100;
            return `
            <div class="drive-card" onclick="ui.openDrive('${drive.id}')">
                <div class="drive-icon">${drive.icon}</div>
                <h3>${drive.name}</h3>
                <div class="stats">${(drive.used / 1024).toFixed(1)} TB / ${(drive.total / 1024).toFixed(1)} TB</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${percent}%"></div>
                </div>
            </div>
            `;
        }).join('');
    }

    async openDrive(driveId) {
        this.currentDrive = driveId;
        const drive = this.drives.find(d => d.id === driveId);
        document.getElementById('current-drive').innerText = drive.name;
        document.getElementById('drive-list').classList.add('hidden');
        document.getElementById('file-explorer').classList.remove('hidden');
        await this.loadFiles("/");
    }

    closeDrive() {
        this.currentDrive = null;
        document.getElementById('drive-list').classList.remove('hidden');
        document.getElementById('file-explorer').classList.add('hidden');
    }

    async loadFiles(path) {
        this.currentPath = path;
        document.getElementById('current-path').innerText = path === "/" ? "root" : path;
        // Mock files
        const files = [
            { name: "Documents", is_dir: true, size: 0 },
            { name: "Project_Blue.psd", is_dir: false, size: 1024 * 1024 * 850 },
            { name: "Family_Photos.zip", is_dir: false, size: 1024 * 1024 * 2400 },
            { name: "System_Backup.iso", is_dir: false, size: 1024 * 1024 * 1024 * 4.2 }
        ];
        this.renderFiles(files);
    }

    renderFiles(files) {
        const list = document.getElementById('file-list');
        list.innerHTML = files.map(file => `
            <div class="file-item">
                <span class="icon">${file.is_dir ? '📁' : '📄'}</span>
                <span class="name">${file.name}</span>
                <span class="size">${file.is_dir ? '--' : this.formatSize(file.size)}</span>
                <div class="actions">
                    <button class="btn-icon">⋮</button>
                </div>
            </div>
        `).join('');
    }

    formatSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
}

const ui = new StorageHubUI();
window.ui = ui;
