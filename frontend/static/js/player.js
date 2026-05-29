class IVSPlayerManager {
  constructor(videoEl) {
    this.videoEl = videoEl;
    this.player = null;
    this.retryTimer = null;
  }

  async init(playbackUrl) {
    const { isPlayerSupported } = window.IVSPlayer;
    if (!isPlayerSupported) {
      throw new Error('IVS Player is not supported in this browser');
    }

    this.player = window.IVSPlayer.create();
    this.player.attachHTMLVideoElement(this.videoEl);

    this.player.addEventListener(window.IVSPlayer.PlayerState.PLAYING, () => {
      this._onStateChange('playing');
    });
    this.player.addEventListener(window.IVSPlayer.PlayerState.BUFFERING, () => {
      this._onStateChange('buffering');
    });
    this.player.addEventListener(window.IVSPlayer.PlayerState.ENDED, () => {
      this._onStateChange('ended');
      this._scheduleRetry(playbackUrl);
    });
    this.player.addEventListener(window.IVSPlayer.PlayerEventType.ERROR, (err) => {
      console.error('Player error:', err);
      this._onStateChange('error');
      this._scheduleRetry(playbackUrl);
    });

    this.player.load(playbackUrl);
    this.player.play();
  }

  _onStateChange(state) {
    if (this.onStateChange) this.onStateChange(state);
  }

  _scheduleRetry(playbackUrl, delay = 10000) {
    clearTimeout(this.retryTimer);
    this.retryTimer = setTimeout(() => {
      if (this.player) {
        this.player.load(playbackUrl);
        this.player.play();
      }
    }, delay);
  }

  destroy() {
    clearTimeout(this.retryTimer);
    if (this.player) {
      this.player.pause();
      this.player.delete();
      this.player = null;
    }
  }
}
