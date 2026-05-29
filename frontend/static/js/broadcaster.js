/**
 * IVS Web Broadcast SDK wrapper.
 * Works in desktop and mobile browsers — mobile uses portrait config by default.
 * SDK: https://web-broadcast.live-video.net/1.6.0/amazon-ivs-web-broadcast.js
 */
class IVSBroadcaster {
  constructor() {
    this.client = null;
    this.isLive = false;
    this.facingMode = 'user'; // front camera by default on mobile
    this.mediaStream = null;
    this.onStatusChange = null;
  }

  get isMobile() {
    return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  }

  async requestPermissions() {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    stream.getTracks().forEach(t => t.stop()); // just checking permissions
  }

  async setup(previewEl, ingestEndpoint) {
    const { IVSBroadcastClient } = window;
    if (!IVSBroadcastClient) throw new Error('IVS Web Broadcast SDK not loaded');

    const streamConfig = this.isMobile
      ? IVSBroadcastClient.STANDARD_PORTRAIT
      : IVSBroadcastClient.STANDARD_LANDSCAPE;

    this.client = IVSBroadcastClient.create({
      streamConfig,
      ingestEndpoint,
    });

    await this._attachDevices(previewEl);

    this.client.on('connectionStateChange', (state) => {
      if (this.onStatusChange) this.onStatusChange(state);
    });
  }

  async _attachDevices(previewEl) {
    const constraints = {
      video: {
        facingMode: this.facingMode,
        width: this.isMobile ? { ideal: 720 } : { ideal: 1280 },
        height: this.isMobile ? { ideal: 1280 } : { ideal: 720 },
      },
      audio: { echoCancellation: true, noiseSuppression: true },
    };

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(t => t.stop());
    }
    this.mediaStream = await navigator.mediaDevices.getUserMedia(constraints);

    // Mirror front camera in preview
    if (previewEl) {
      previewEl.srcObject = this.mediaStream;
      previewEl.classList.toggle('environment', this.facingMode === 'environment');
    }

    try { this.client.removeVideoInputDevice('camera'); } catch (_) {}
    try { this.client.removeAudioInputDevice('mic'); } catch (_) {}

    await this.client.addVideoInputDevice(this.mediaStream, 'camera', { index: 0 });
    await this.client.addAudioInputDevice(this.mediaStream, 'mic', { index: 0 });
  }

  async flipCamera(previewEl) {
    if (!this.isMobile) return;
    this.facingMode = this.facingMode === 'user' ? 'environment' : 'user';
    await this._attachDevices(previewEl);
  }

  async startBroadcast(streamKey) {
    if (!this.client) throw new Error('Broadcaster not initialized');
    await this.client.startBroadcast(streamKey);
    this.isLive = true;
  }

  async stopBroadcast() {
    if (!this.client || !this.isLive) return;
    await this.client.stopBroadcast();
    this.isLive = false;
  }

  getAudioMeter() {
    return this.client?.getAudioContext()
      ? this.client.getAudioContext()
      : null;
  }

  destroy() {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(t => t.stop());
      this.mediaStream = null;
    }
    if (this.client && this.isLive) {
      try { this.client.stopBroadcast(); } catch (_) {}
    }
    this.client = null;
    this.isLive = false;
  }
}

const broadcaster = new IVSBroadcaster();
