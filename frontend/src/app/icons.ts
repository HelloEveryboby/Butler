/**
 * 轻量内联图标集 —— 关键导航/标题栏不依赖外部图标 CDN。
 */

export type IconName = 'chat' | 'clock' | 'flow' | 'box' | 'gear' | 'moon' | 'sun' | 'search' | 'terminal' | 'note';

const PATHS: Record<IconName, string> = {
  chat: '<path d="M3.2 3.4h9.6v6.4H7.1L4 12.2v-2.4H3.2z"/>',
  clock: '<circle cx="8" cy="8" r="5.4"/><path d="M8 4.9V8l2.1 1.3"/>',
  flow: '<rect x="2.3" y="2.3" width="3.8" height="3.8" rx="0.9"/><rect x="9.9" y="9.9" width="3.8" height="3.8" rx="0.9"/><path d="M6.1 4.2h2.3a1.5 1.5 0 0 1 1.5 1.5v2.3M4.2 6.1v2.3a1.5 1.5 0 0 0 1.5 1.5h2.3"/>',
  box: '<path d="M2.6 5.2 8 2.6l5.4 2.6v5.6L8 13.4l-5.4-2.6z"/><path d="M2.8 5.3 8 7.9l5.2-2.6M8 7.9v5.5"/>',
  gear: '<path d="M2.4 4.4h11.2M2.4 8h11.2M2.4 11.6h11.2"/><circle cx="6.1" cy="4.4" r="1.35"/><circle cx="10.2" cy="8" r="1.35"/><circle cx="5.2" cy="11.6" r="1.35"/>',
  moon: '<path d="M12.9 9.8A5.4 5.4 0 0 1 6.2 3.1a5.4 5.4 0 1 0 6.7 6.7z"/>',
  sun: '<circle cx="8" cy="8" r="2.5"/><path d="M8 1.6v1.4M8 13v1.4M1.6 8h1.4M13 8h1.4M3.5 3.5l1 1M11.5 11.5l1 1M12.5 3.5l-1 1M4.5 11.5l-1 1"/>',
  search: '<circle cx="7.2" cy="7.2" r="4.1"/><path d="m10.3 10.3 3 3"/>',
  terminal: '<rect x="2.3" y="3.2" width="11.4" height="9.6" rx="1.1"/><path d="m4.7 6.6 1.8 1.6-1.8 1.6M8.4 10h2.7"/>',
  note: '<path d="M4 2.6h6.2l2.2 2.2v8.6H4z"/><path d="M10 2.7v2.3h2.3M5.8 7.2h4.4M5.8 9.4h4.4"/>',
};

export function icon(name: IconName, size: number = 16): string {
  return `<svg class="w11-icon" width="${size}" height="${size}" viewBox="0 0 16 16" fill="none"
    stroke="currentColor" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round"
    aria-hidden="true">${PATHS[name]}</svg>`;
}
