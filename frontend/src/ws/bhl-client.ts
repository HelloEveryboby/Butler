/**
 * BHL Communication Client with PyWebView & WebSocket Dual Transport
 */

import { PyWebViewBridge } from '../core/bridge';
import { BHLMessage, BHLCommandPayload, BridgeResponse } from '../types/global';
import { appConfig } from '../config';

export class BHLClient {
  private ws: WebSocket | null = null;
  private isConnected: boolean = false;
  private reconnectTimer: any = null;
  private eventListeners: Map<string, Array<(payload: any) => void>> = new Map();

  constructor() {
    this.initWebSocket();
  }

  private initWebSocket(): void {
    const wsUrl = appConfig.get('wsUrl');
    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.isConnected = true;
        console.log(`[BHL Client] Connected to WebSocket at ${wsUrl}`);
        this.emit('connection_change', { connected: true });
      };

      this.ws.onmessage = (event) => {
        try {
          const msg: BHLMessage = JSON.parse(event.data);
          this.emit(msg.action, msg.payload);
        } catch (err) {
          console.warn('[BHL Client] Failed to parse WebSocket message:', event.data);
        }
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this.emit('connection_change', { connected: false });
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.isConnected = false;
      };
    } catch (e) {
      // WebSocket is optional if PyWebView is present
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.isConnected) {
        this.initWebSocket();
      }
    }, 5000);
  }

  public async sendCommand(cmd: string, args: Record<string, any> = {}, source: 'voice' | 'flash_input' | 'gui' = 'gui'): Promise<BridgeResponse> {
    const payload: BHLCommandPayload = { cmd, args, source };

    // Primary transport: PyWebView Bridge if available
    if (PyWebViewBridge.isAvailable()) {
      try {
        if (cmd.startsWith('/')) {
          const res = await PyWebViewBridge.handleCommand(cmd);
          return { success: true, data: res };
        } else {
          const res = await PyWebViewBridge.submitFlashCommand(cmd);
          return { success: true, data: res };
        }
      } catch (e: any) {
        return { success: false, error: e.message || String(e) };
      }
    }

    // Secondary transport: WebSocket
    if (this.ws && this.isConnected) {
      const msg: BHLMessage<BHLCommandPayload> = {
        type: 'command',
        action: 'execute_command',
        payload,
        timestamp: Date.now(),
        requestId: `req_${Math.random().toString(36).substr(2, 9)}`
      };
      this.ws.send(JSON.stringify(msg));
      return { success: true, message: 'Command sent via WebSocket' };
    }

    console.warn('[BHL Client] Neither PyWebView Bridge nor WebSocket is connected. Mock fallback executed.');
    return { success: true, data: { mock: true, cmd } };
  }

  public on(event: string, callback: (payload: any) => void): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event)!.push(callback);
  }

  public off(event: string, callback: (payload: any) => void): void {
    if (!this.eventListeners.has(event)) return;
    const list = this.eventListeners.get(event)!;
    const idx = list.indexOf(callback);
    if (idx !== -1) {
      list.splice(idx, 1);
    }
  }

  private emit(event: string, payload: any): void {
    const list = this.eventListeners.get(event);
    if (list) {
      list.forEach((cb) => cb(payload));
    }
  }
}

export const bhlClient = new BHLClient();
