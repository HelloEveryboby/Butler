/* ============================================================
   Butler Translate — chrome.storage 封装
   ============================================================ */

import { TranslateConfig } from './types';
import { DEFAULT_CONFIG } from './config';

const STORAGE_KEY = 'butler_translate_config';

export async function loadConfig(): Promise<TranslateConfig> {
  try {
    const result = await chrome.storage.local.get(STORAGE_KEY);
    if (result[STORAGE_KEY]) {
      return { ...DEFAULT_CONFIG, ...result[STORAGE_KEY] };
    }
  } catch (e) {
    console.warn('[ButlerTranslate] Failed to load config:', e);
  }
  return { ...DEFAULT_CONFIG };
}

export async function saveConfig(config: Partial<TranslateConfig>): Promise<void> {
  const current = await loadConfig();
  const merged = { ...current, ...config };
  await chrome.storage.local.set({ [STORAGE_KEY]: merged });
}

export function loadConfigSync(): Promise<TranslateConfig> {
  return loadConfig();
}
