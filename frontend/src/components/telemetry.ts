/**
 * Butler Telemetry: Connects to the backend WebSocket and updates StateMatrix.
 */
class ButlerTelemetry {
  public url: string;
  public socket: WebSocket | null = null;
  public reconnectInterval: number = 5000;

  constructor(url: string = 'ws://localhost:8000') {
    this.url = url;
    this.connect();
  }

  public connect(): void {
    console.log(`📡 Connecting to Telemetry: ${this.url}`);
    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      console.log('✅ Telemetry Connected');
      this.socket?.send(
        JSON.stringify({
          type: 'register',
          runner_id: 'butler_ui',
          token: 'BUTLER_SECRET_2026',
        })
      );
    };

    this.socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'metrics' && window.stateMatrix) {
          if (msg.data.cpu !== undefined) window.stateMatrix.update('metrics.cpu', msg.data.cpu);
          if (msg.data.memory !== undefined) window.stateMatrix.update('metrics.memory', msg.data.memory);
          if (msg.data.disk !== undefined) window.stateMatrix.update('metrics.disk', msg.data.disk);
          if (msg.data.network !== undefined) window.stateMatrix.update('metrics.network', msg.data.network);
        }
      } catch (e) {
        console.error('Telemetry parse error', e);
      }
    };

    this.socket.onclose = () => {
      console.warn('⚠️ Telemetry Disconnected. Reconnecting...');
      setTimeout(() => this.connect(), this.reconnectInterval);
    };

    this.socket.onerror = (err) => {
      console.error('Telemetry error', err);
      this.socket?.close();
    };
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    (window as any).telemetry = new ButlerTelemetry();
    (window as any).ButlerTelemetry = ButlerTelemetry;
  });
}
