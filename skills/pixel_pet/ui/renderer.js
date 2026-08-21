/**
 * Pixel Pet Renderer Script in TypeScript
 */
export const PAL = [
    null,
    '#3D3D4A',
    '#F5C6A5',
    '#1A1A1A',
    '#8A8A95',
    '#FF9999',
    '#FFFFFF',
];
const D = 1, L = 2, B = 3, G = 4, P = 5, W = 6;
export class PixelGrid {
    w;
    h;
    data;
    constructor(w, h) {
        this.w = w;
        this.h = h;
        this.data = Array.from({ length: h }, () => new Uint8Array(w));
    }
    clone() {
        const g = new PixelGrid(this.w, this.h);
        for (let y = 0; y < this.h; y++) {
            g.data[y].set(this.data[y]);
        }
        return g;
    }
    set(x, y, c) {
        if (x >= 0 && x < this.w && y >= 0 && y < this.h)
            this.data[y][x] = c;
    }
    rect(x, y, w, h, c) {
        for (let dy = 0; dy < h; dy++)
            for (let dx = 0; dx < w; dx++)
                this.set(x + dx, y + dy, c);
    }
}
const GW = 18;
const GH = 30;
const MAP = { D: D, L: L, B: B, G: G, P: P, W: W };
const IDLE_MAP = [
    '........GG........',
    '........GG........',
    '.........G........',
    '........G.........',
    '.......G..........',
    '...D..........D...',
    '...D..........D...',
    '..DL..........LD..',
    '..DL..........LD..',
    '..DL..........LD..',
    '.DDL..........LDD.',
    '.DDL..........LDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDLLDDDDDDDDDD',
    'DDDDDWBDDDDWBDDDDD',
    'DDDDDBBDDDDBBDDDDD',
    'DDDDDDLLLLDDDDDDDD',
    'DDDDDDLLLBLLDDDDDD',
    '.DDDDDDDDDDDDDDDD.',
    '.DDDDDDDDDDDDDDDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDLD',
    'DDDDDDDDDDDDDDDDLD',
    'DDLLLLLLLLLLLLDLD.',
    'DDLLLLLLLLLLLLDDLD',
    'DDLLLLLLLLLLLLDLD.',
    '...DDDDD..DDDDD...',
    '...DDDDD..DDDDD...',
    '...DDLDD..DDLDD...',
];
const BLINK_MAP = [
    '........GG........',
    '........GG........',
    '.........G........',
    '........G.........',
    '.......G..........',
    '...D..........D...',
    '...D..........D...',
    '..DL..........LD..',
    '..DL..........LD..',
    '..DL..........LD..',
    '.DDL..........LDD.',
    '.DDL..........LDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDLLDDDDDDDDDD',
    'DDDDDBBDDDDBBDDDDD',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDLLLLDDDDDDDD',
    'DDDDDDLLLBLLDDDDDD',
    '.DDDDDDDDDDDDDDDD.',
    '.DDDDDDDDDDDDDDDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDLD',
    'DDDDDDDDDDDDDDDDLD',
    'DDLLLLLLLLLLLLDLD.',
    'DDLLLLLLLLLLLLDDLD',
    'DDLLLLLLLLLLLLDLD.',
    '...DDDDD..DDDDD...',
    '...DDDDD..DDDDD...',
    '...DDLDD..DDLDD...',
];
const HAPPY_MAP = [
    '........GG........',
    '........GG........',
    '.........G........',
    '........G.........',
    '.......G..........',
    '...D..........D...',
    '...D..........D...',
    '..DL..........LD..',
    '..DL..........LD..',
    '..DL..........LD..',
    '.DDL..........LDD.',
    '.DDL..........LDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDLLDDDDDDDDDD',
    'DDDDDBBDDDDBBDDDDD',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDLLLLDDDDDDDD',
    'DDDDDDLLPPLLDDDDDD',
    '.DDDDDDDDDDDDDDDD.',
    '.DDDDDDDDDDDDDDDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDLD',
    'DDDDDDDDDDDDDDDDLD',
    'DDLLLLLLLLLLLLDLD.',
    'DDLLLLLLLLLLLLDDLD',
    'DDLLLLLLLLLLLLDLD.',
    '...DDDDD..DDDDD...',
    '...DDDDD..DDDDD...',
    '...DDLDD..DDLDD...',
];
const SAD_MAP = [
    '........GG........',
    '........GG........',
    '.........G........',
    '........G.........',
    '.......G..........',
    '...D..........D...',
    '...D..........D...',
    '..DL..........LD..',
    '..DL..........LD..',
    '..DL..........LD..',
    '.DDL..........LDD.',
    '.DDL..........LDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDLLDDDDDDDDDD',
    'DDDDLBBDDDDBBLDDDD',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDLLLLDDDDDDDD',
    'DDDDDDLLLBLLDDDDDD',
    '.DDDDDDDDDDDDDDDD.',
    '.DDDDDDDDDDDDDDDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDLD',
    'DDDDDDDDDDDDDDDDLD',
    'DDLLLLLLLLLLLLDLD.',
    'DDLLLLLLLLLLLLDDLD',
    'DDLLLLLLLLLLLLDLD.',
    '...DDDDD..DDDDD...',
    '...DDDDD..DDDDD...',
    '...DDLDD..DDLDD...',
];
const ANGRY_MAP = [
    '........GG........',
    '........GG........',
    '.........G........',
    '........G.........',
    '.......G..........',
    '...D..........D...',
    '...D..........D...',
    '..DL..........LD..',
    '..DL..........LD..',
    '..DL..........LD..',
    '.DDL..........LDD.',
    '.DDL..........LDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDLLLLDDLLLLDDDD',
    'DDDDDBBDDDDDBBDDDD',
    'DDDDDBBDDDDDBBDDDD',
    'DDDDDDLLLLDDDDDDDD',
    'DDDDDDLLLBLLDDDDDD',
    '.DDDDDDDDDDDDDDDD.',
    '.DDDDDDDDDDDDDDDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDLD',
    'DDDDDDDDDDDDDDDDLD',
    'DDLLLLLLLLLLLLDLD.',
    'DDLLLLLLLLLLLLDDLD',
    'DDLLLLLLLLLLLLDLD.',
    '...DDDDD..DDDDD...',
    '...DDDDD..DDDDD...',
    '...DDLDD..DDLDD...',
];
const SLEEPY_MAP = [
    '.......GGG........',
    '..........G.......',
    '.......GGG........',
    '........G.........',
    '.......G..........',
    '...D..........D...',
    '...D..........D...',
    '..DL..........LD..',
    '..DL..........LD..',
    '..DL..........LD..',
    '.DDL..........LDD.',
    '.DDL..........LDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDLLDDDDDDDDDD',
    'DDDDDLLDDDDLLDDDDD',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDLLLLDDDDDDDD',
    'DDDDDDLLLBLLDDDDDD',
    '.DDDDDDDDDDDDDDDD.',
    '.DDDDDDDDDDDDDDDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDLD',
    'DDDDDDDDDDDDDDDDLD',
    'DDLLLLLLLLLLLLDLD.',
    'DDLLLLLLLLLLLLDDLD',
    'DDLLLLLLLLLLLLDLD.',
    '...DDDDD..DDDDD...',
    '...DDDDD..DDDDD...',
    '...DDLDD..DDLDD...',
];
const LOVE_MAP = [
    '........GG........',
    '........GG........',
    '.........G........',
    '........G.........',
    '.......G..........',
    '...D..........D...',
    '...D..........D...',
    '..DL..........LD..',
    '..DL..........LD..',
    '..DL..........LD..',
    '.DDL..........LDD.',
    '.DDL..........LDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDLLDDDDDDDDDD',
    'DDDDDPPDDDDPPDDDDD',
    'DDDDDPPDDDDPPDDDDD',
    'DDDDDDLLLLDDDDDDDD',
    'DDDDDDLLPPLLDDDDDD',
    '.DDDDDDDDDDDDDDDD.',
    '.DDDDDDDDDDDDDDDD.',
    'DDDDDDDDDDDDDDDDDD',
    'DDDDDDDDDDDDDDDDLD',
    'DDDDDDDDDDDDDDDDLD',
    'DDLLLLLLLLLLLLDLD.',
    'DDLLLLLLLLLLLLDDLD',
    'DDLLLLLLLLLLLLDLD.',
    '...DDDDD..DDDDD...',
    '...DDDDD..DDDDD...',
    '...DDLDD..DDLDD...',
];
function parseMap(mapData) {
    const g = new PixelGrid(GW, GH);
    for (let y = 0; y < mapData.length && y < GH; y++) {
        const row = mapData[y];
        for (let x = 0; x < row.length && x < GW; x++) {
            const ch = row[x];
            if (MAP[ch])
                g.set(x, y, MAP[ch]);
        }
    }
    return g;
}
function buildDog(mood) {
    const maps = {
        idle: IDLE_MAP,
        blink: BLINK_MAP,
        happy: HAPPY_MAP,
        sad: SAD_MAP,
        angry: ANGRY_MAP,
        sleepy: SLEEPY_MAP,
        love: LOVE_MAP,
    };
    return parseMap(maps[mood] || IDLE_MAP);
}
const frameIdle = buildDog('idle');
const frameBlink = buildDog('blink');
const frameHappy = buildDog('happy');
const frameSad = buildDog('sad');
const frameAngry = buildDog('angry');
const frameSleepy = buildDog('sleepy');
const frameLove = buildDog('love');
const cv = document.getElementById('cv');
const ctx = cv?.getContext('2d');
let px = 16;
function resize() {
    if (!cv)
        return;
    cv.width = GW * px;
    cv.height = GH * px;
}
if (cv)
    resize();
function prerenderGrid(grid) {
    const off = document.createElement('canvas');
    off.width = GW * px;
    off.height = GH * px;
    const octx = off.getContext('2d');
    for (let y = 0; y < GH; y++) {
        for (let x = 0; x < GW; x++) {
            const c = grid.data[y][x];
            if (c === 0)
                continue;
            const color = PAL[c];
            if (color) {
                octx.fillStyle = color;
                octx.fillRect(x * px, y * px, px, px);
            }
        }
    }
    return off;
}
const cache = new Map();
function getCached(grid) {
    if (!cache.has(grid))
        cache.set(grid, prerenderGrid(grid));
    return cache.get(grid);
}
let lastFrame = null;
function drawFrame(grid) {
    if (!ctx || !cv)
        return;
    if (lastFrame === grid)
        return;
    lastFrame = grid;
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.drawImage(getCached(grid), 0, 0);
}
function invalidateCache() {
    cache.clear();
    lastFrame = null;
}
let animOn = true;
let tick = 0;
let blinkCount = 0;
let happyCount = 0;
let nextBlink = 120 + Math.random() * 180;
let currentMood = 'idle';
let moodTimer = 0;
const MOOD_FRAMES = {
    idle: frameIdle,
    happy: frameHappy,
    sad: frameSad,
    angry: frameAngry,
    sleepy: frameSleepy,
    love: frameLove,
};
const MOOD_TEXT = {
    idle: '点击小狗和它互动吧',
    happy: '汪汪！好开心~ 🐾',
    sad: '呜呜...主人不要走 😢',
    angry: '汪！不许碰我！😤',
    sleepy: '好困...zzZ 💤',
    love: '好喜欢主人~ ❤️',
};
const MOOD_PARTICLES = {
    idle: null,
    happy: ['💕', '💗', '🐶', '✨'],
    sad: ['💧', '😢', '💦'],
    angry: ['💢', '⚡', '🔥'],
    sleepy: ['💤', '☁️', '⭐'],
    love: ['💕', '💗', '💖', '❤️'],
};
function setMood(mood, statusTextOverride = null) {
    currentMood = mood;
    moodTimer = 300;
    const targetText = statusTextOverride || MOOD_TEXT[mood] || MOOD_TEXT.idle;
    const sts = document.getElementById('sts');
    if (sts) {
        sts.textContent = targetText;
        sts.style.color = mood === 'idle' ? 'rgba(255,255,255,0.45)' : '#F5C6A5';
    }
    const petDialog = document.getElementById('pet-dialog');
    if (petDialog) {
        petDialog.innerText = targetText;
        petDialog.classList.add('show');
        if (mood === 'idle') {
            setTimeout(() => {
                if (currentMood === 'idle') {
                    petDialog.classList.remove('show');
                }
            }, 4000);
        }
    }
    document.querySelectorAll('.mood-btn').forEach((b) => {
        const el = b;
        el.classList.toggle('on', el.dataset.mood === mood);
    });
}
function loop() {
    if (animOn) {
        tick++;
        blinkCount--;
        if (blinkCount <= 0) {
            blinkCount = nextBlink;
            nextBlink = 120 + Math.random() * 180;
        }
        if (happyCount > 0)
            happyCount--;
        if (moodTimer > 0) {
            moodTimer--;
            if (moodTimer <= 0) {
                currentMood = 'idle';
                const sts = document.getElementById('sts');
                if (sts) {
                    sts.textContent = MOOD_TEXT.idle;
                    sts.style.color = 'rgba(255,255,255,0.45)';
                }
                document.querySelectorAll('.mood-btn').forEach((b) => b.classList.remove('on'));
            }
        }
    }
    let frame = MOOD_FRAMES[currentMood] || frameIdle;
    if (currentMood === 'idle') {
        if (happyCount > 0)
            frame = frameHappy;
        else if (blinkCount > 0 && blinkCount < 8)
            frame = frameBlink;
    }
    drawFrame(frame);
    requestAnimationFrame(loop);
}
function spawnHearts(cx, cy, mood) {
    const box = document.getElementById('ptcl');
    if (!box)
        return;
    const chars = MOOD_PARTICLES[mood] || ['💕', '💗', '🐶'];
    for (let i = 0; i < 7; i++) {
        const el = document.createElement('span');
        el.className = 'heart';
        el.textContent = chars[Math.floor(Math.random() * chars.length)];
        el.style.left = cx + (Math.random() - 0.5) * 80 + 'px';
        el.style.top = cy - 10 + 'px';
        el.style.animationDelay = Math.random() * 0.2 + 's';
        box.appendChild(el);
        setTimeout(() => el.remove(), 1400);
    }
}
let currentMode = 'widget';
function setUIMode(mode) {
    currentMode = mode;
    const body = document.body;
    if (mode === 'panel') {
        body.classList.remove('mode-widget');
        body.classList.add('mode-panel');
        if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_mode) {
            window.pywebview.api.toggle_mode(true);
        }
    }
    else {
        body.classList.remove('mode-panel');
        body.classList.add('mode-widget');
        if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_mode) {
            window.pywebview.api.toggle_mode(false);
        }
    }
}
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        document.getElementById('wrap')?.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            setUIMode(currentMode === 'widget' ? 'panel' : 'widget');
        });
        document.getElementById('pet-dialog')?.addEventListener('click', (e) => {
            e.stopPropagation();
            setUIMode('panel');
        });
        document.getElementById('btn-collapse')?.addEventListener('click', () => {
            setUIMode('widget');
        });
        cv?.addEventListener('click', (e) => {
            e.stopPropagation();
            happyCount = 100;
            setMood('happy');
            const rect = cv.getBoundingClientRect();
            spawnHearts(rect.width / 2, rect.height / 2, 'happy');
        });
        const sz = document.getElementById('sz');
        sz?.addEventListener('input', (e) => {
            px = +e.target.value;
            resize();
            invalidateCache();
        });
        const btnA = document.getElementById('ba');
        btnA?.addEventListener('click', () => {
            animOn = !animOn;
            if (btnA) {
                btnA.textContent = '动画: ' + (animOn ? '开' : '关');
                btnA.classList.toggle('on', animOn);
            }
        });
        document.querySelectorAll('.mood-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const mood = btn.dataset.mood || 'idle';
                setMood(mood);
                const rect = cv.getBoundingClientRect();
                spawnHearts(rect.width / 2, rect.height / 2, mood);
            });
        });
        document.getElementById('be')?.addEventListener('click', () => {
            const s = 16;
            const ec = document.createElement('canvas');
            ec.width = GW * s;
            ec.height = GH * s;
            const ex = ec.getContext('2d');
            const frame = MOOD_FRAMES[currentMood] || frameIdle;
            for (let y = 0; y < GH; y++) {
                for (let x = 0; x < GW; x++) {
                    const c = frame.data[y][x];
                    if (!c)
                        continue;
                    const color = PAL[c];
                    if (color) {
                        ex.fillStyle = color;
                        ex.fillRect(x * s, y * s, s, s);
                    }
                }
            }
            const a = document.createElement('a');
            a.download = `pixel-puppy-${currentMood}.png`;
            a.href = ec.toDataURL('image/png');
            a.click();
        });
        if (!window.pywebview) {
            document.body.classList.add('standalone');
        }
        setUIMode('widget');
    });
}
window.ButlerPet = {
    onEvent: function (payload) {
        const { event, message } = payload;
        switch (event) {
            case 'ai_thinking':
                setMood('sleepy', message || 'Butler 正在思考...');
                break;
            case 'ai_streaming':
                setMood('love', message || 'Butler 正在生成...');
                break;
            case 'task_success':
                setMood('happy', message || '执行完毕！🐾');
                if (cv) {
                    const rect = cv.getBoundingClientRect();
                    spawnHearts(rect.width / 2, rect.height / 2, 'happy');
                }
                break;
            case 'task_failed':
                setMood('angry', `发生错误: ${message || '执行异常'}`);
                if (cv) {
                    const er = cv.getBoundingClientRect();
                    spawnHearts(er.width / 2, er.height / 2, 'angry');
                }
                break;
            case 'user_idle':
                setMood('idle', message || '休眠中');
                break;
            default:
                setMood('idle');
        }
    },
};
loop();
