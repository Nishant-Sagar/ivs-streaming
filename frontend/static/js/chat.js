/**
 * IVS Chat WebSocket client.
 * Connects directly to the IVS Chat edge endpoint using a token from the backend.
 * Protocol reference: https://docs.aws.amazon.com/ivs/latest/ChatAPIReference
 */
class IVSChat {
  constructor() {
    this.ws = null;
    this.region = 'us-east-1';
    this.onMessage = null;
    this.onConnect = null;
    this.onDisconnect = null;
    this._reconnectTimer = null;
    this._token = null;
    this._connected = false;
  }

  connect(token, region = 'us-east-1') {
    this._token = token;
    this.region = region;
    this._openSocket();
  }

  _openSocket() {
    const endpoint = `wss://edge.ivschat.${this.region}.amazonaws.com`;
    this.ws = new WebSocket(endpoint, 'com.amazonaws.ivs.chat');

    this.ws.onopen = () => {
      this.ws.send(JSON.stringify({
        action: 'CONNECT',
        requestId: this._uid(),
        token: this._token,
      }));
    };

    this.ws.onmessage = (event) => {
      let data;
      try { data = JSON.parse(event.data); } catch { return; }

      if (data.Type === 'SUCCESS' && data.RequestId) {
        this._connected = true;
        if (this.onConnect) this.onConnect();
        return;
      }

      if (data.Type === 'MESSAGE') {
        const msg = {
          id: data.Id,
          content: data.Content,
          userId: data.Sender?.UserId,
          username: data.Sender?.Attributes?.username || data.Sender?.UserId || 'Anonymous',
          sentAt: data.SendTime ? new Date(data.SendTime) : new Date(),
        };
        if (this.onMessage) this.onMessage(msg);
        return;
      }

      if (data.Type === 'EVENT') {
        // Stream events (STREAM_START, STREAM_END, custom events)
        if (this.onEvent) this.onEvent(data);
      }
    };

    this.ws.onclose = () => {
      this._connected = false;
      if (this.onDisconnect) this.onDisconnect();
      // Auto-reconnect after 5s
      this._reconnectTimer = setTimeout(() => {
        if (this._token) this._openSocket();
      }, 5000);
    };

    this.ws.onerror = (err) => {
      console.error('IVS Chat WebSocket error:', err);
    };
  }

  sendMessage(content) {
    if (!this._connected || this.ws?.readyState !== WebSocket.OPEN) {
      console.warn('Chat not connected');
      return;
    }
    content = content.trim();
    if (!content || content.length > 500) return;

    this.ws.send(JSON.stringify({
      action: 'SEND_MESSAGE',
      requestId: this._uid(),
      content,
    }));
  }

  disconnect() {
    clearTimeout(this._reconnectTimer);
    this._token = null;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._connected = false;
  }

  _uid() {
    return Math.random().toString(36).slice(2, 11);
  }
}

const chat = new IVSChat();
