/* ============================================================
   Butler Translate — 消息通信（Content ↔ Background）
   ============================================================ */

import { MsgType, MsgResponse } from './types';

/** Content Script → Background */
export function sendMessage(msg: MsgType): Promise<MsgResponse> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (response: MsgResponse | undefined) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else if (response) {
        resolve(response);
      } else {
        reject(new Error('Empty response from background'));
      }
    });
  });
}

/** Background 监听 */
export function onMessage(
  handler: (msg: MsgType, sender: chrome.runtime.MessageSender) => Promise<MsgResponse | null>
): void {
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    handler(msg as MsgType, sender).then((resp) => {
      if (resp) sendResponse(resp);
    }).catch((err) => {
      console.error('[ButlerTranslate] Message handler error:', err);
      sendResponse({ type: 'TRANSLATE_ERROR', error: String(err) });
    });
    return true; // 异步响应
  });
}
