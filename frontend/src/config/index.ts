/**
 * Centralized Application Configuration with localStorage Persistence
 */

export interface AppConfig {
  wakeWords: string[];
  autoListenOnWake: boolean;
  ttsEnabled: boolean;
  ttsVoice: string;
  ttsRate: number;
  ttsPitch: number;
  audioVisualizerTheme: 'neon_cyan' | 'apple_glass' | 'liquid_purple' | 'matrix_green';
  ringRadius: number;
  wsUrl: string;
  theme: 'apple' | 'dark' | 'google';
  interfaceMode: 'desktop' | 'mobile';
  blurAmount: number;
  fontFamily: string;
  fontSize: string;
  commandPatterns: Array<{ pattern: string; command: string }>;
}

const DEFAULT_CONFIG: AppConfig = {
  wakeWords: ['butler', '贾维斯', '管家', '小管家', 'hey butler'],
  autoListenOnWake: true,
  ttsEnabled: true,
  ttsVoice: 'default',
  ttsRate: 1.0,
  ttsPitch: 1.0,
  audioVisualizerTheme: 'apple_glass',
  ringRadius: 80,
  wsUrl: 'ws://127.0.0.1:8765',
  theme: 'apple',
  interfaceMode: 'desktop',
  blurAmount: 20,
  fontFamily: 'Inter, system-ui, -apple-system',
  fontSize: '14px',
  commandPatterns: [
    { pattern: '^(打开|启动)(编辑器|笔记)', command: '/editor ' },
    { pattern: '^(清理|优化)(系统|垃圾)', command: '/clean' },
    { pattern: '^(暂停|停止)', command: '/pause' },
    { pattern: '^(搜索|查找)(.+)', command: '/search $2' },
  ]
};

const STORAGE_KEY = 'butler_app_config_v1';

class ConfigManager {
  private config: AppConfig;

  constructor() {
    this.config = this.loadConfig();
  }

  private loadConfig(): AppConfig {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        return { ...DEFAULT_CONFIG, ...JSON.parse(stored) };
      }
    } catch (e) {
      console.warn('[Config] Failed to read localStorage config:', e);
    }
    return { ...DEFAULT_CONFIG };
  }

  public get<K extends keyof AppConfig>(key: K): AppConfig[K] {
    return this.config[key];
  }

  public set<K extends keyof AppConfig>(key: K, value: AppConfig[K]): void {
    this.config[key] = value;
    this.save();
  }

  public update(partial: Partial<AppConfig>): void {
    this.config = { ...this.config, ...partial };
    this.save();
  }

  public getAll(): AppConfig {
    return { ...this.config };
  }

  public reset(): void {
    this.config = { ...DEFAULT_CONFIG };
    this.save();
  }

  private save(): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.config));
    } catch (e) {
      console.error('[Config] Failed to save config to localStorage:', e);
    }
  }
}

export const appConfig = new ConfigManager();
