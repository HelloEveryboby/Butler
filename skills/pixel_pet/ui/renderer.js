// ================================================================
// 色板 (Palette)
// ================================================================
const PAL = [
  null,            // 0 透明
  '#3D3D4A',       // 1 深色（身体主色）
  '#F5C6A5',       // 2 浅色（花纹/肚子/嘴部）
  '#1A1A1A',       // 3 黑色（眼/鼻）
  '#8A8A95',       // 4 灰色（思考泡泡）
  '#FF9999',       // 5 粉色（舌头）
  '#FFFFFF',       // 6 白色（眼睛高光）
];
const D=1, L=2, B=3, G=4, P=5, W=6;

// ================================================================
// PixelGrid — 像素画布工具
// ================================================================
class PixelGrid {
  constructor(w, h) {
    this.w = w; this.h = h;
    this.data = Array.from({length: h}, () => new Uint8Array(w));
  }
  clone() {
    const g = new PixelGrid(this.w, this.h);
    for (let y = 0; y < this.h; y++)
      g.data[y].set(this.data[y]);
    return g;
  }
  set(x, y, c) {
    if (x >= 0 && x < this.w && y >= 0 && y < this.h) this.data[y][x] = c;
  }
  rect(x, y, w, h, c) {
    for (let dy = 0; dy < h; dy++)
      for (let dx = 0; dx < w; dx++)
        this.set(x+dx, y+dy, c);
  }
}

// ================================================================
// 构建小狗帧 — 18×30 正面坐姿
// ================================================================
const GW = 18, GH = 30;
const MAP = { 'D':D, 'L':L, 'B':B, 'G':G, 'P':P, 'W':W };

// idle 帧 — 对称布局
const IDLE_MAP = [
  '........GG........',  // 0  思考泡泡 2×2圆
  '........GG........',  // 1
  '.........G........',  // 2  点状连接线
  '........G.........',  // 3
  '.......G..........',  // 4  连接头部
  '...D..........D...',  // 5  左耳尖col3   右耳尖col14
  '...D..........D...',  // 6  耳朵第2行
  '..DL..........LD..',  // 7  耳朵第3行 (内侧L色)
  '..DL..........LD..',  // 8  耳朵第4行
  '..DL..........LD..',  // 9  耳朵第5行
  '.DDL..........LDD.',  // 10 耳朵第6行 (基底变宽)
  '.DDL..........LDD.',  // 11 耳朵第7行
  'DDDDDDDDDDDDDDDDDD',  // 12 头顶 (耳朵汇入)
  'DDDDDDDDDDDDDDDDDD',  // 13 额头
  'DDDDDDLLDDDDDDDDDD',  // 14 眉间小L斑(col7-8)
  'DDDDDWBDDDDWBDDDDD',  // 15 眼睛: 左WB(col5-6) 右WB(col11-12)
  'DDDDDBBDDDDBBDDDDD',  // 16 眼睛下排
  'DDDDDDLLLLDDDDDDDD',  // 17 鼻口
  'DDDDDDLLLBLLDDDDDD',  // 18 鼻子 B(col8) + 嘴部L
  '.DDDDDDDDDDDDDDDD.',  // 19 下巴
  '.DDDDDDDDDDDDDDDD.',  // 20 下颌
  'DDDDDDDDDDDDDDDDDD',  // 21 身体顶
  'DDDDDDDDDDDDDDDDLD',  // 22 身体+尾巴L
  'DDDDDDDDDDDDDDDDLD',  // 23
  'DDLLLLLLLLLLLLDLD.',  // 24 肚子+尾巴L
  'DDLLLLLLLLLLLLDDLD',  // 25
  'DDLLLLLLLLLLLLDLD.',  // 26 肚子底+尾巴L
  '...DDDDD..DDDDD...',  // 27 腿 (5px宽,2px间隙)
  '...DDDDD..DDDDD...',  // 28
  '...DDLDD..DDLDD...',  // 29 脚掌
];

// blink 帧：眼睛闭合为两条横线
const BLINK_MAP = [
  '........GG........',  // 0
  '........GG........',  // 1
  '.........G........',  // 2
  '........G.........',  // 3
  '.......G..........',  // 4
  '...D..........D...',  // 5
  '...D..........D...',  // 6
  '..DL..........LD..',  // 7
  '..DL..........LD..',  // 8
  '..DL..........LD..',  // 9
  '.DDL..........LDD.',  // 10
  '.DDL..........LDD.',  // 11
  'DDDDDDDDDDDDDDDDDD',  // 12
  'DDDDDDDDDDDDDDDDDD',  // 13
  'DDDDDDLLDDDDDDDDDD',  // 14
  'DDDDDBBDDDDBBDDDDD',  // 15 闭眼
  'DDDDDDDDDDDDDDDDDD',  // 16
  'DDDDDDLLLLDDDDDDDD',  // 17
  'DDDDDDLLLBLLDDDDDD',  // 18
  '.DDDDDDDDDDDDDDDD.',  // 19
  '.DDDDDDDDDDDDDDDD.',  // 20
  'DDDDDDDDDDDDDDDDDD',  // 21
  'DDDDDDDDDDDDDDDDLD',  // 22
  'DDDDDDDDDDDDDDDDLD',  // 23
  'DDLLLLLLLLLLLLDLD.',  // 24
  'DDLLLLLLLLLLLLDDLD',  // 25
  'DDLLLLLLLLLLLLDLD.',  // 26
  '...DDDDD..DDDDD...',  // 27
  '...DDDDD..DDDDD...',  // 28
  '...DDLDD..DDLDD...',  // 29
];

// happy 帧：眯眼 + 伸舌头
const HAPPY_MAP = [
  '........GG........',  // 0
  '........GG........',  // 1
  '.........G........',  // 2
  '........G.........',  // 3
  '.......G..........',  // 4
  '...D..........D...',  // 5
  '...D..........D...',  // 6
  '..DL..........LD..',  // 7
  '..DL..........LD..',  // 8
  '..DL..........LD..',  // 9
  '.DDL..........LDD.',  // 10
  '.DDL..........LDD.',  // 11
  'DDDDDDDDDDDDDDDDDD',  // 12
  'DDDDDDDDDDDDDDDDDD',  // 13
  'DDDDDDLLDDDDDDDDDD',  // 14
  'DDDDDBBDDDDBBDDDDD',  // 15 开心眯眼
  'DDDDDDDDDDDDDDDDDD',  // 16
  'DDDDDDLLLLDDDDDDDD',  // 17
  'DDDDDDLLPPLLDDDDDD',  // 18 舌头PP(col8-9)替代鼻子
  '.DDDDDDDDDDDDDDDD.',  // 19
  '.DDDDDDDDDDDDDDDD.',  // 20
  'DDDDDDDDDDDDDDDDDD',  // 21
  'DDDDDDDDDDDDDDDDLD',  // 22
  'DDDDDDDDDDDDDDDDLD',  // 23
  'DDLLLLLLLLLLLLDLD.',  // 24
  'DDLLLLLLLLLLLLDDLD',  // 25
  'DDLLLLLLLLLLLLDLD.',  // 26
  '...DDDDD..DDDDD...',  // 27
  '...DDDDD..DDDDD...',  // 28
  '...DDLDD..DDLDD...',  // 29
];

// sad 帧：八字眉 + 悲伤流泪
const SAD_MAP = [
  '........GG........',  // 0
  '........GG........',  // 1
  '.........G........',  // 2
  '........G.........',  // 3
  '.......G..........',  // 4
  '...D..........D...',  // 5
  '...D..........D...',  // 6
  '..DL..........LD..',  // 7
  '..DL..........LD..',  // 8
  '..DL..........LD..',  // 9
  '.DDL..........LDD.',  // 10
  '.DDL..........LDD.',  // 11
  'DDDDDDDDDDDDDDDDDD',  // 12
  'DDDDDDDDDDDDDDDDDD',  // 13
  'DDDDDDLLDDDDDDDDDD',  // 14
  'DDDDLBBDDDDBBLDDDD',  // 15 八字眉+悲伤眼
  'DDDDDDDDDDDDDDDDDD',  // 16
  'DDDDDDLLLLDDDDDDDD',  // 17
  'DDDDDDLLLBLLDDDDDD',  // 18
  '.DDDDDDDDDDDDDDDD.',  // 19
  '.DDDDDDDDDDDDDDDD.',  // 20
  'DDDDDDDDDDDDDDDDDD',  // 21
  'DDDDDDDDDDDDDDDDLD',  // 22
  'DDDDDDDDDDDDDDDDLD',  // 23
  'DDLLLLLLLLLLLLDLD.',  // 24
  'DDLLLLLLLLLLLLDDLD',  // 25
  'DDLLLLLLLLLLLLDLD.',  // 26
  '...DDDDD..DDDDD...',  // 27
  '...DDDDD..DDDDD...',  // 28
  '...DDLDD..DDLDD...',  // 29
];

// angry 帧：怒眉 + 怒瞪
const ANGRY_MAP = [
  '........GG........',  // 0
  '........GG........',  // 1
  '.........G........',  // 2
  '........G.........',  // 3
  '.......G..........',  // 4
  '...D..........D...',  // 5
  '...D..........D...',  // 6
  '..DL..........LD..',  // 7
  '..DL..........LD..',  // 8
  '..DL..........LD..',  // 9
  '.DDL..........LDD.',  // 10
  '.DDL..........LDD.',  // 11
  'DDDDDDDDDDDDDDDDDD',  // 12
  'DDDDDDDDDDDDDDDDDD',  // 13
  'DDDDLLLLDDLLLLDDDD',  // 14 怒眉
  'DDDDDBBDDDDDBBDDDD',  // 15 怒瞪上排
  'DDDDDBBDDDDDBBDDDD',  // 16 怒瞪下排
  'DDDDDDLLLLDDDDDDDD',  // 17
  'DDDDDDLLLBLLDDDDDD',  // 18
  '.DDDDDDDDDDDDDDDD.',  // 19
  '.DDDDDDDDDDDDDDDD.',  // 20
  'DDDDDDDDDDDDDDDDDD',  // 21
  'DDDDDDDDDDDDDDDDLD',  // 22
  'DDDDDDDDDDDDDDDDLD',  // 23
  'DDLLLLLLLLLLLLDLD.',  // 24
  'DDLLLLLLLLLLLLDDLD',  // 25
  'DDLLLLLLLLLLLLDLD.',  // 26
  '...DDDDD..DDDDD...',  // 27
  '...DDDDD..DDDDD...',  // 28
  '...DDLDD..DDLDD...',  // 29
];

// sleepy 帧：安详闭眼 + Zzz思考泡泡
const SLEEPY_MAP = [
  '.......GGG........',  // 0  Z顶横
  '..........G.......',  // 1  Z斜线
  '.......GGG........',  // 2  Z底横
  '........G.........',  // 3
  '.......G..........',  // 4
  '...D..........D...',  // 5
  '...D..........D...',  // 6
  '..DL..........LD..',  // 7
  '..DL..........LD..',  // 8
  '..DL..........LD..',  // 9
  '.DDL..........LDD.',  // 10
  '.DDL..........LDD.',  // 11
  'DDDDDDDDDDDDDDDDDD',  // 12
  'DDDDDDDDDDDDDDDDDD',  // 13
  'DDDDDDLLDDDDDDDDDD',  // 14
  'DDDDDLLDDDDLLDDDDD',  // 15 安详闭眼
  'DDDDDDDDDDDDDDDDDD',  // 16
  'DDDDDDLLLLDDDDDDDD',  // 17
  'DDDDDDLLLBLLDDDDDD',  // 18
  '.DDDDDDDDDDDDDDDD.',  // 19
  '.DDDDDDDDDDDDDDDD.',  // 20
  'DDDDDDDDDDDDDDDDDD',  // 21
  'DDDDDDDDDDDDDDDDLD',  // 22
  'DDDDDDDDDDDDDDDDLD',  // 23
  'DDLLLLLLLLLLLLDLD.',  // 24
  'DDLLLLLLLLLLLLDDLD',  // 25
  'DDLLLLLLLLLLLLDLD.',  // 26
  '...DDDDD..DDDDD...',  // 27
  '...DDDDD..DDDDD...',  // 28
  '...DDLDD..DDLDD...',  // 29
];

// love 帧：心形眼 + 舌头
const LOVE_MAP = [
  '........GG........',  // 0
  '........GG........',  // 1
  '.........G........',  // 2
  '........G.........',  // 3
  '.......G..........',  // 4
  '...D..........D...',  // 5
  '...D..........D...',  // 6
  '..DL..........LD..',  // 7
  '..DL..........LD..',  // 8
  '..DL..........LD..',  // 9
  '.DDL..........LDD.',  // 10
  '.DDL..........LDD.',  // 11
  'DDDDDDDDDDDDDDDDDD',  // 12
  'DDDDDDDDDDDDDDDDDD',  // 13
  'DDDDDDLLDDDDDDDDDD',  // 14
  'DDDDDPPDDDDPPDDDDD',  // 15 心形眼
  'DDDDDPPDDDDPPDDDDD',  // 16
  'DDDDDDLLLLDDDDDDDD',  // 17
  'DDDDDDLLPPLLDDDDDD',  // 18 舌头
  '.DDDDDDDDDDDDDDDD.',  // 19
  '.DDDDDDDDDDDDDDDD.',  // 20
  'DDDDDDDDDDDDDDDDDD',  // 21
  'DDDDDDDDDDDDDDDDLD',  // 22
  'DDDDDDDDDDDDDDDDLD',  // 23
  'DDLLLLLLLLLLLLDLD.',  // 24
  'DDLLLLLLLLLLLLDDLD',  // 25
  'DDLLLLLLLLLLLLDLD.',  // 26
  '...DDDDD..DDDDD...',  // 27
  '...DDDDD..DDDDD...',  // 28
  '...DDLDD..DDLDD...',  // 29
];

function parseMap(mapData) {
  const g = new PixelGrid(GW, GH);
  for (let y = 0; y < mapData.length && y < GH; y++) {
    const row = mapData[y];
    for (let x = 0; x < row.length && x < GW; x++) {
      const ch = row[x];
      if (MAP[ch]) g.set(x, y, MAP[ch]);
    }
  }
  return g;
}

function buildDog(mood) {
  const maps = {
    'idle': IDLE_MAP, 'blink': BLINK_MAP, 'happy': HAPPY_MAP,
    'sad': SAD_MAP, 'angry': ANGRY_MAP, 'sleepy': SLEEPY_MAP, 'love': LOVE_MAP
  };
  return parseMap(maps[mood] || IDLE_MAP);
}

// 预生成帧
const frameIdle  = buildDog('idle');
const frameBlink = buildDog('blink');
const frameHappy = buildDog('happy');
const frameSad   = buildDog('sad');
const frameAngry = buildDog('angry');
const frameSleepy= buildDog('sleepy');
const frameLove  = buildDog('love');

// ================================================================
// Canvas 渲染
// ================================================================
const cv  = document.getElementById('cv');
const ctx = cv.getContext('2d');
let px = 16;

function resize() {
  cv.width  = GW * px;
  cv.height = GH * px;
}
resize();

// 离屏预渲染优化
function prerenderGrid(grid) {
  const off = document.createElement('canvas');
  off.width  = GW * px;
  off.height = GH * px;
  const octx = off.getContext('2d');
  for (let y = 0; y < GH; y++) {
    for (let x = 0; x < GW; x++) {
      const c = grid.data[y][x];
      if (c === 0) continue;
      octx.fillStyle = PAL[c];
      octx.fillRect(x * px, y * px, px, px);
    }
  }
  return off;
}

const cache = new Map();
function getCached(grid) {
  if (!cache.has(grid)) cache.set(grid, prerenderGrid(grid));
  return cache.get(grid);
}

let lastFrame = null;
function drawFrame(grid) {
  if (lastFrame === grid) return;
  lastFrame = grid;
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.drawImage(getCached(grid), 0, 0);
}

function invalidateCache() {
  cache.clear();
  lastFrame = null;
}

// ================================================================
// 动画循环
// ================================================================
let animOn     = true;
let tick       = 0;
let blinkCount = 0;
let happyCount = 0;
let nextBlink  = 120 + Math.random() * 180;
let currentMood= 'idle';
let moodTimer  = 0;

const MOOD_FRAMES = {
  idle: frameIdle, happy: frameHappy, sad: frameSad,
  angry: frameAngry, sleepy: frameSleepy, love: frameLove
};

const MOOD_TEXT = {
  idle: '点击小狗和它互动吧', happy: '汪汪！好开心~ 🐾',
  sad: '呜呜...主人不要走 😢', angry: '汪！不许碰我！😤',
  sleepy: '好困...zzZ 💤', love: '好喜欢主人~ ❤️'
};

const MOOD_PARTICLES = {
  idle: null,
  happy: ['💕','💗','🐶','✨'],
  sad: ['💧','😢','💦'],
  angry: ['💢','⚡','🔥'],
  sleepy: ['💤','☁️','⭐'],
  love: ['💕','💗','💖','❤️']
};

function setMood(mood, statusTextOverride = null) {
  currentMood = mood;
  moodTimer = 300; // Keep expression active for 300 frames (~5 seconds)

  const targetText = statusTextOverride || MOOD_TEXT[mood] || MOOD_TEXT.idle;

  // Update panel status row
  const sts = document.getElementById('sts');
  sts.textContent = targetText;
  sts.style.color = mood === 'idle' ? 'rgba(255,255,255,0.45)' : '#F5C6A5';

  // Update floating bubble
  const petDialog = document.getElementById('pet-dialog');
  petDialog.innerText = targetText;
  petDialog.classList.add('show');

  // Hide bubble automatically after 4 seconds in widget mode, except if state is not idle
  if (mood === 'idle') {
    setTimeout(() => {
      if (currentMood === 'idle') {
        petDialog.classList.remove('show');
      }
    }, 4000);
  }

  // Update expression buttons active state
  document.querySelectorAll('.mood-btn').forEach(b => {
    b.classList.toggle('on', b.dataset.mood === mood);
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
    if (happyCount > 0) happyCount--;
    if (moodTimer > 0) {
      moodTimer--;
      if (moodTimer <= 0) {
        currentMood = 'idle';
        const sts = document.getElementById('sts');
        sts.textContent = MOOD_TEXT.idle;
        sts.style.color = 'rgba(255,255,255,0.45)';
        document.querySelectorAll('.mood-btn').forEach(b => b.classList.remove('on'));
      }
    }
  }

  // Choose frame based on state
  let frame = MOOD_FRAMES[currentMood] || frameIdle;
  if (currentMood === 'idle') {
    if (happyCount > 0) frame = frameHappy;
    else if (blinkCount > 0 && blinkCount < 8) frame = frameBlink;
  }

  drawFrame(frame);
  requestAnimationFrame(loop);
}

// ================================================================
// 特殊属性资质抽卡系统
// ================================================================
const TRAITS = [
  { name: '贪吃鬼', desc: '看到食物就移不开眼' },
  { name: '胆小鬼', desc: '容易被突然的声音吓到' },
  { name: '小太阳', desc: '总是充满活力和热情' },
  { name: '瞌睡虫', desc: '随时随地都能睡着' },
  { name: '捣蛋王', desc: '喜欢把东西弄乱' },
  { name: '粘人精', desc: '一刻也不想离开主人' },
  { name: '独行侠', desc: '更喜欢自己待着' },
  { name: '好奇猫', desc: '对一切新事物充满好奇' },
];

const RARITY_TABLE = [
  { key: 'N',   label: 'N',   chance: 0.50, class: 'rarity-N' },
  { key: 'R',   label: 'R',   chance: 0.30, class: 'rarity-R' },
  { key: 'SR',  label: 'SR',  chance: 0.15, class: 'rarity-SR' },
  { key: 'SSR', label: 'SSR', chance: 0.05, class: 'rarity-SSR' },
];

function rollRarity() {
  const r = Math.random();
  let cum = 0;
  for (const item of RARITY_TABLE) {
    cum += item.chance;
    if (r < cum) return item;
  }
  return RARITY_TABLE[0];
}

function rollStats(rarity) {
  const base = { N: 20, R: 35, SR: 50, SSR: 65 };
  const b = base[rarity.key] || 20;
  const roll = () => Math.min(99, b + Math.floor(Math.random() * (100 - b)));
  return { str: roll(), agi: roll(), luk: roll() };
}

function generateTraits() {
  const rarity = rollRarity();
  const trait = TRAITS[Math.floor(Math.random() * TRAITS.length)];
  const stats = rollStats(rarity);

  const badge = document.getElementById('rarity');
  badge.textContent = rarity.label;
  badge.className = 'rarity-badge ' + rarity.class;

  document.getElementById('trait').textContent = trait.name;

  document.getElementById('bar-str').style.width = stats.str + '%';
  document.getElementById('val-str').textContent = stats.str;
  document.getElementById('bar-agi').style.width = stats.agi + '%';
  document.getElementById('val-agi').textContent = stats.agi;
  document.getElementById('bar-luk').style.width = stats.luk + '%';
  document.getElementById('val-luk').textContent = stats.luk;

  return { rarity, trait, stats };
}

const dogTraits = generateTraits();

// ================================================================
// 粒子系统
// ================================================================
function spawnHearts(cx, cy, mood) {
  const box = document.getElementById('ptcl');
  const chars = MOOD_PARTICLES[mood] || ['💕','💗','🐶'];
  for (let i = 0; i < 7; i++) {
    const el = document.createElement('span');
    el.className = 'heart';
    el.textContent = chars[Math.floor(Math.random() * chars.length)];
    el.style.left = (cx + (Math.random() - 0.5) * 80) + 'px';
    el.style.top  = (cy - 10) + 'px';
    el.style.animationDelay = (Math.random() * 0.2) + 's';
    box.appendChild(el);
    setTimeout(() => el.remove(), 1400);
  }
}

// ================================================================
// 适配双模 (Widget / Panel Mode) 转换
// ================================================================
let currentMode = 'widget'; // widget (default) or panel

function setUIMode(mode) {
  currentMode = mode;
  const body = document.body;
  if (mode === 'panel') {
    body.classList.remove('mode-widget');
    body.classList.add('mode-panel');
    // Invoke Native Bridge resize
    if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_mode) {
      window.pywebview.api.toggle_mode(true);
    }
  } else {
    body.classList.remove('mode-panel');
    body.classList.add('mode-widget');
    // Invoke Native Bridge resize
    if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_mode) {
      window.pywebview.api.toggle_mode(false);
    }
  }
}

// Double click to toggle modes
document.getElementById('wrap').addEventListener('dblclick', (e) => {
  e.stopPropagation();
  if (currentMode === 'widget') {
    setUIMode('panel');
  } else {
    setUIMode('widget');
  }
});

// Dialogue bubble click toggles to Panel Mode
document.getElementById('pet-dialog').addEventListener('click', (e) => {
  e.stopPropagation();
  setUIMode('panel');
});

// Collapse button listener
document.getElementById('btn-collapse').addEventListener('click', () => {
  setUIMode('widget');
});

// Standard clicking for playful actions
cv.addEventListener('click', (e) => {
  e.stopPropagation();
  // Playful interactions
  happyCount = 100;
  setMood('happy');
  const rect = cv.getBoundingClientRect();
  spawnHearts(rect.width / 2, rect.height / 2, 'happy');
});

// Controls & settings bindings
document.getElementById('sz').addEventListener('input', e => {
  px = +e.target.value;
  resize();
  invalidateCache();
});

const btnA = document.getElementById('ba');
btnA.addEventListener('click', () => {
  animOn = !animOn;
  btnA.textContent = '动画: ' + (animOn ? '开' : '关');
  btnA.classList.toggle('on', animOn);
});

// Expression manual triggers
document.querySelectorAll('.mood-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const mood = btn.dataset.mood;
    setMood(mood);
    const rect = cv.getBoundingClientRect();
    spawnHearts(rect.width / 2, rect.height / 2, mood);
  });
});

// Export PNG functionality
document.getElementById('be').addEventListener('click', () => {
  const s = 16;
  const ec = document.createElement('canvas');
  ec.width = GW * s; ec.height = GH * s;
  const ex = ec.getContext('2d');

  let frame = MOOD_FRAMES[currentMood] || frameIdle;
  for (let y = 0; y < GH; y++) {
    for (let x = 0; x < GW; x++) {
      const c = frame.data[y][x];
      if (!c) continue;
      ex.fillStyle = PAL[c];
      ex.fillRect(x * s, y * s, s, s);
    }
  }
  const a = document.createElement('a');
  a.download = `pixel-puppy-${currentMood}.png`;
  a.href = ec.toDataURL('image/png');
  a.click();
});

// ================================================================
// 背景星空 (Stars overlay in panel mode)
// ================================================================
(() => {
  for (let i = 0; i < 40; i++) {
    const s = document.createElement('div');
    s.className = 'bg-star';
    s.style.left = Math.random() * 100 + '%';
    s.style.top  = Math.random() * 100 + '%';
    s.style.setProperty('--dur', (1.5 + Math.random() * 3) + 's');
    s.style.animationDelay = (Math.random() * 3) + 's';
    if (Math.random() > 0.75) { s.style.width = '3px'; s.style.height = '3px'; }
    document.body.appendChild(s);
  }
})();

// ================================================================
// Standalone Mode & Native Event Routing
// ================================================================
window.addEventListener('DOMContentLoaded', () => {
  if (!window.pywebview) {
    document.body.classList.add('standalone');
  }

  // Start in micro-widget mode
  setUIMode('widget');
});

// Expose standard namespace for Butler process messages via UDP
window.ButlerPet = {
  onEvent: function(payload) {
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
        const rect = cv.getBoundingClientRect();
        spawnHearts(rect.width / 2, rect.height / 2, 'happy');
        break;
      case 'task_failed':
        setMood('angry', `发生错误: ${message || '执行异常'}`);
        const er = cv.getBoundingClientRect();
        spawnHearts(er.width / 2, er.height / 2, 'angry');
        break;
      case 'user_idle':
        setMood('idle', message || '休眠中');
        break;
      default:
        setMood('idle');
    }
  }
};

// Start animation loop
loop();
