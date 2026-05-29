const API_BASE = window.API_BASE || window.location.origin;

const api = (() => {
  function getToken() {
    return localStorage.getItem('ivs_token');
  }

  function setToken(token) {
    localStorage.setItem('ivs_token', token);
  }

  function clearToken() {
    localStorage.removeItem('ivs_token');
    localStorage.removeItem('ivs_user');
  }

  function setUser(user) {
    localStorage.setItem('ivs_user', JSON.stringify(user));
  }

  function getUser() {
    try { return JSON.parse(localStorage.getItem('ivs_user')); } catch { return null; }
  }

  async function request(method, path, body = null, auth = false) {
    const headers = { 'Content-Type': 'application/json' };
    if (auth) {
      const token = getToken();
      if (!token) throw new Error('Not authenticated');
      headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (res.status === 204) return null;

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    return data;
  }

  async function formRequest(path, formData) {
    const res = await fetch(`${API_BASE}${path}`, { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    return data;
  }

  return {
    getToken, setToken, clearToken, setUser, getUser,
    isLoggedIn: () => !!getToken(),

    async register(username, email, password) {
      return request('POST', '/api/auth/register', { username, email, password });
    },

    async login(username, password) {
      const form = new FormData();
      form.append('username', username);
      form.append('password', password);
      const data = await formRequest('/api/auth/login', form);
      setToken(data.access_token);
      const user = await this.getMe();
      setUser(user);
      return user;
    },

    async getMe() {
      return request('GET', '/api/auth/me', null, true);
    },

    logout() {
      clearToken();
      window.location.href = '/app/index.html';
    },

    async listChannels() {
      return request('GET', '/api/channels');
    },

    async listLiveChannels() {
      return request('GET', '/api/channels/live');
    },

    async getMyChannel() {
      return request('GET', '/api/channels/mine', null, true);
    },

    async getChannel(id) {
      return request('GET', `/api/channels/${id}`);
    },

    async createChannel(name, description = '') {
      return request('POST', '/api/channels', { name, description }, true);
    },

    async updateChannel(id, data) {
      return request('PATCH', `/api/channels/${id}`, data, true);
    },

    async deleteChannel(id) {
      return request('DELETE', `/api/channels/${id}`, null, true);
    },

    async getStreamKey(channelId) {
      return request('GET', `/api/channels/${channelId}/stream-key`, null, true);
    },

    async rotateStreamKey(channelId) {
      return request('POST', `/api/channels/${channelId}/rotate-key`, null, true);
    },

    async getChatToken(channelId) {
      return request('POST', `/api/channels/${channelId}/chat-token`, null, true);
    },

    async getStreamStatus(channelId) {
      return request('GET', `/api/streams/${channelId}/status`);
    },

    async stopStream(channelId) {
      return request('POST', `/api/streams/${channelId}/stop`, null, true);
    },
  };
})();
