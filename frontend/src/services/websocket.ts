/**
 * services/websocket.ts
 * Quản lý kết nối WebSocket truyền âm thanh (Audio Stream) và nhận Transcript.
 * Developer 3 sẽ hoàn thiện class này.
 */

export class VoiceWebSocketService {
  private ws: WebSocket | null = null;

  connect(callId: string, onMessage: (data: any) => void) {
    const wsUrl = `ws://localhost:8000/ws/call/${callId}`;
    console.log(`Connecting WebSocket to ${wsUrl}...`);
    
    // TODO: Developer 3 sẽ viết logic WebSocket thật ở đây
    /*
    this.ws = new WebSocket(wsUrl);
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage(data);
    };
    */
  }

  sendAudioChunk(chunk: ArrayBuffer) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(chunk);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
