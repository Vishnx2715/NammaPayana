/**
 * Namma Payana — Authentication & User Controller
 * Registration-First Policy:
 * Users MUST be registered in the system before they are allowed to sign in,
 * even with Google OAuth. Unregistered users are redirected to Register.
 */

// escapeHtml is defined in i18n.js (first loaded script). This stub guards against
// loading order issues in testing or standalone contexts.
if (typeof escapeHtml === 'undefined') {
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#x27;');
  }
}

const SUPABASE_CONFIG = {
  url: (window.NP_CONFIG && window.NP_CONFIG.supabaseUrl) || "",
  anonKey: (window.NP_CONFIG && window.NP_CONFIG.supabaseAnonKey) || ""
};

let supabaseClient = null;
try {
  if (typeof window !== 'undefined' && window.supabase && window.supabase.createClient && SUPABASE_CONFIG.url && SUPABASE_CONFIG.anonKey) {
    supabaseClient = window.supabase.createClient(SUPABASE_CONFIG.url, SUPABASE_CONFIG.anonKey);
  }
} catch (err) {
  console.warn('[Supabase] Init failed:', err);
}

const Auth = {
  currentUser: null,
  supabase: supabaseClient,
  _csrfToken: null,

  async getCsrfToken() {
    try {
      const res = await fetch('/api/csrf-token');
      const json = await res.json();
      if (json.ok && json.data && json.data.csrf_token) {
        this._csrfToken = json.data.csrf_token;
        window._csrfToken = this._csrfToken;
      }
    } catch (e) {
      console.warn('[CSRF] Failed to fetch token:', e);
    }
    return this._csrfToken || '';
  },

  async init() {
    if (!supabaseClient && typeof window !== 'undefined' && window.supabase && window.supabase.createClient && SUPABASE_CONFIG.url && SUPABASE_CONFIG.anonKey) {
      supabaseClient = window.supabase.createClient(SUPABASE_CONFIG.url, SUPABASE_CONFIG.anonKey);
      this.supabase = supabaseClient;
    }

    await this.getCsrfToken();
    this.bindEvents();
    this.listenToAuthChanges();
    this.restoreSession();
  },

  listenToAuthChanges() {
    if (!supabaseClient) return;
    try {
      supabaseClient.auth.onAuthStateChange(async (event, session) => {
        if (event === 'SIGNED_IN' && session && session.user) {
          await this.handleGoogleSession(session);
        } else if (event === 'SIGNED_OUT') {
          this.currentUser = null;
          try { localStorage.removeItem('nammapayana_user'); } catch(e) {}
          this.updateNavbarUI();
        }
      });
    } catch (err) {
      console.warn('[Supabase] Auth listener error:', err);
    }
  },

  /**
   * Enforces Registration-First policy for Google OAuth.
   * Sends the Supabase access token to the server for verification.
   * If the Google email is not found in registered users, blocks sign in
   * and redirects them to the Register tab with pre-filled details.
   */
  async handleGoogleSession(session) {
    if (!session || !session.user) return;
    const userMeta = session.user.user_metadata || {};

    try {
      // Send the Supabase access token for server-side verification
      const res = await fetch('/api/auth/google-check', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`
        },
        body: JSON.stringify({})
      });
      const json = await res.json();

      if (res.ok && json.ok && json.registered && json.data) {
        // User IS registered! Welcome them in
        const user = json.data;
        if (userMeta.avatar_url || userMeta.picture) {
          user.avatar_url = userMeta.avatar_url || userMeta.picture;
        }
        this.setUser(user);
        if (typeof App !== 'undefined' && App.showToast) {
          App.showToast(`Signed in as ${user.full_name}! Welcome back! 🙏`, 'success');
        }
        if (typeof App !== 'undefined' && App.switchView) {
          App.switchView('landing');
        }
      } else {
        // User is NOT registered! Enforce registration before entry.
        if (supabaseClient) {
          try { await supabaseClient.auth.signOut(); } catch(e) {}
        }
        this.currentUser = null;
        try { localStorage.removeItem('nammapayana_user'); } catch(e) {}
        this.updateNavbarUI();

        // Switch to Register tab
        this.switchTab('register');

        // Pre-fill registration fields using Google profile info
        const nameInput = document.getElementById('reg-fullname');
        const emailInput = document.getElementById('reg-email');
        const userInput = document.getElementById('reg-username');

        const googleEmail = (session.user.email || '').toLowerCase();
        const googleName = userMeta.full_name || userMeta.name || '';
        const suggestedUser = (googleEmail.split('@')[0] || 'traveler').replace(/[^a-zA-Z0-9_]/g, '_');

        if (nameInput) nameInput.value = googleName;
        if (emailInput) emailInput.value = googleEmail;
        if (userInput && !userInput.value) userInput.value = suggestedUser;

        const notRegMsg = `No account registered with this Google account. Please choose a password and complete registration below.`;
        this.showAlert('register', notRegMsg, 'error');

        if (typeof App !== 'undefined' && App.showToast) {
          App.showToast('Not registered! Please create your account first to continue.', 'warn');
        }

        // Focus password input for quick completion
        const pwdInput = document.getElementById('reg-password');
        if (pwdInput) setTimeout(() => pwdInput.focus(), 150);
      }
    } catch (err) {
      console.error('[Auth] Google check error:', err);
      this.showAlert('login', 'Error verifying registration status. Please try again.');
    }
  },

  bindEvents() {
    // Auth Tabs Switcher
    const tabLogin = document.getElementById('auth-tab-btn-login');
    if (tabLogin) {
      tabLogin.addEventListener('click', (e) => {
        e.preventDefault();
        this.switchTab('login');
      });
    }

    const tabRegister = document.getElementById('auth-tab-btn-register');
    if (tabRegister) {
      tabRegister.addEventListener('click', (e) => {
        e.preventDefault();
        this.switchTab('register');
      });
    }

    // 1-Click Demo Login buttons
    document.querySelectorAll('.btn-demo-quick').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        this.quickDemoLogin();
      });
    });

    // Continue / Sign up with Google OAuth buttons
    document.querySelectorAll('.btn-google-oauth').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        this.signInWithGoogle();
      });
    });

    // Explore as Guest Traveler buttons
    document.querySelectorAll('.btn-guest-continue').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        this.continueAsGuest();
      });
    });

    // Switch tab text links in card footers
    document.querySelectorAll('.auth-card-footer a').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const text = (link.textContent || '').toLowerCase();
        if (text.includes('create') || text.includes('register')) {
          this.switchTab('register');
        } else {
          this.switchTab('login');
        }
      });
    });

    // Password toggle buttons
    document.querySelectorAll('.auth-pwd-toggle').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const inputWrap = btn.closest('.auth-input-wrap');
        const input = inputWrap ? inputWrap.querySelector('input') : null;
        if (input) {
          const isPwd = input.type === 'password';
          input.type = isPwd ? 'text' : 'password';
          btn.textContent = isPwd ? '🙈' : '👁️';
        }
      });
    });

    // Login form submit
    const loginForm = document.getElementById('auth-form-login');
    if (loginForm) {
      loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.submitLogin();
      });
    }

    // Register form submit
    const regForm = document.getElementById('auth-form-register');
    if (regForm) {
      regForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.submitRegister();
      });
    }

    // Real-time password strength
    const regPwd = document.getElementById('reg-password');
    if (regPwd) {
      regPwd.addEventListener('input', (e) => {
        this.updatePasswordStrength(e.target.value);
      });
    }

    // Nav logout button
    const logoutBtn = document.getElementById('nav-logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.logout();
      });
    }
  },

  async signInWithGoogle() {
    this.clearAlerts();
    if (!supabaseClient) {
      if (typeof window !== 'undefined' && window.supabase && window.supabase.createClient && SUPABASE_CONFIG.url && SUPABASE_CONFIG.anonKey) {
        supabaseClient = window.supabase.createClient(SUPABASE_CONFIG.url, SUPABASE_CONFIG.anonKey);
        this.supabase = supabaseClient;
      }
    }

    if (!supabaseClient) {
      this.showAlert('login', 'Supabase client library not ready. Please refresh the page.');
      this.showAlert('register', 'Supabase client library not ready. Please refresh the page.');
      return;
    }

    try {
      if (typeof App !== 'undefined' && App.showToast) {
        App.showToast('Connecting to Google Sign-In...', 'info');
      }

      const { data, error } = await supabaseClient.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: window.location.origin
        }
      });

      if (error) {
        console.error('[Supabase Google Auth Error]:', error);
        this.showAlert('login', `Google Sign-in: ${error.message}`);
        this.showAlert('register', `Google Sign-in: ${error.message}`);
        if (typeof App !== 'undefined' && App.showToast) {
          App.showToast(error.message, 'error');
        }
      }
    } catch (err) {
      console.error('[Supabase Google Auth Exception]:', err);
      this.showAlert('login', 'Unable to initiate Google OAuth. Please check network.');
    }
  },

  switchTab(tab) {
    const loginPanel = document.getElementById('auth-panel-login');
    const registerPanel = document.getElementById('auth-panel-register');
    const btnLogin = document.getElementById('auth-tab-btn-login');
    const btnRegister = document.getElementById('auth-tab-btn-register');
    const indicator = document.getElementById('auth-tab-indicator');

    this.clearAlerts();

    if (tab === 'register') {
      if (loginPanel) loginPanel.style.display = 'none';
      if (registerPanel) registerPanel.style.display = 'block';
      if (btnLogin) btnLogin.classList.remove('active');
      if (btnRegister) btnRegister.classList.add('active');
      if (indicator) indicator.style.transform = 'translateX(100%)';
    } else {
      if (loginPanel) loginPanel.style.display = 'block';
      if (registerPanel) registerPanel.style.display = 'none';
      if (btnLogin) btnLogin.classList.add('active');
      if (btnRegister) btnRegister.classList.remove('active');
      if (indicator) indicator.style.transform = 'translateX(0%)';
    }
  },

  togglePassword(inputId, btnEl) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    if (btnEl) {
      btnEl.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
      btnEl.innerHTML = isPassword ? '👁️‍🗨️' : '👁️';
    }
  },

  updatePasswordStrength(pwd) {
    const meter = document.getElementById('pwd-strength-bar');
    const label = document.getElementById('pwd-strength-label');
    if (!meter || !label) return;

    if (!pwd) {
      meter.style.width = '0%';
      meter.style.backgroundColor = 'var(--border-color)';
      label.textContent = '';
      return;
    }

    let score = 0;
    if (pwd.length >= 10) score++;
    if (pwd.length >= 14) score++;
    if (/[A-Z]/.test(pwd)) score++;
    if (/[0-9]/.test(pwd)) score++;
    if (/[^A-Za-z0-9]/.test(pwd)) score++;

    if (score <= 2) {
      meter.style.width = '33%';
      meter.style.backgroundColor = 'var(--danger)';
      label.textContent = 'Weak';
      label.style.color = 'var(--danger)';
    } else if (score <= 3) {
      meter.style.width = '66%';
      meter.style.backgroundColor = 'var(--warn)';
      label.textContent = 'Good';
      label.style.color = 'var(--warn)';
    } else {
      meter.style.width = '100%';
      meter.style.backgroundColor = 'var(--ok)';
      label.textContent = 'Strong';
      label.style.color = 'var(--ok)';
    }
  },

  showAlert(panel, message, type = 'error') {
    const alertEl = document.getElementById(`auth-alert-${panel}`);
    if (!alertEl) return;
    alertEl.textContent = message;
    alertEl.className = `auth-alert ${type}`;
    alertEl.style.display = 'block';
  },

  clearAlerts() {
    ['login', 'register'].forEach(p => {
      const alertEl = document.getElementById(`auth-alert-${p}`);
      if (alertEl) {
        alertEl.style.display = 'none';
        alertEl.textContent = '';
      }
    });
  },

  async submitLogin() {
    const identInput = document.getElementById('login-identifier');
    const pwdInput = document.getElementById('login-password');
    const submitBtn = document.getElementById('login-submit-btn');

    const identifier = (identInput ? identInput.value : '').trim();
    const password = pwdInput ? pwdInput.value : '';

    if (!identifier || !password) {
      this.showAlert('login', 'Please enter your username/email and password.');
      return;
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Verifying credentials...';
    }

    try {
      const csrfToken = await this.getCsrfToken();
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ identifier, password })
      });
      const json = await res.json();

      if (!res.ok || !json.ok) {
        const msg = (json.error && json.error.message) ? json.error.message : 'Invalid credentials.';
        this.showAlert('login', msg, 'error');
        if (typeof App !== 'undefined' && App.showToast) {
          App.showToast(msg, 'error');
        }
        return;
      }

      const user = json.data;
      this.setUser(user);
      if (typeof App !== 'undefined' && App.showToast) {
        App.showToast(`Welcome back, ${user.full_name}! 🙏`, 'success');
      }

      // Transition to Main Landing Page
      setTimeout(() => {
        if (typeof App !== 'undefined' && App.switchView) {
          App.switchView('landing');
        }
      }, 350);

    } catch (err) {
      console.error('[Auth] Login error:', err);
      this.showAlert('login', 'Connection error. Please try again.');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Sign In to Namma Payana →';
      }
    }
  },

  async submitRegister() {
    const nameInput = document.getElementById('reg-fullname');
    const emailInput = document.getElementById('reg-email');
    const userInput = document.getElementById('reg-username');
    const pwdInput = document.getElementById('reg-password');
    const confirmInput = document.getElementById('reg-confirm-password');
    const submitBtn = document.getElementById('register-submit-btn');

    const full_name = (nameInput ? nameInput.value : '').trim();
    const email = (emailInput ? emailInput.value : '').trim();
    const username = (userInput ? userInput.value : '').trim();
    const password = pwdInput ? pwdInput.value : '';
    const confirm = confirmInput ? confirmInput.value : '';

    if (!full_name || !email || !username || !password) {
      this.showAlert('register', 'Please fill in all required fields.');
      return;
    }

    if (password !== confirm) {
      this.showAlert('register', 'Passwords do not match. Please re-enter.');
      return;
    }

    if (password.length < 10) {
      this.showAlert('register', 'Password must be at least 10 characters long.');
      return;
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Creating account...';
    }

    try {
      const csrfToken = await this.getCsrfToken();
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          full_name,
          email,
          username,
          password,
          persona: 'Heritage Explorer',
          home_city: 'Bengaluru'
        })
      });
      const json = await res.json();

      if (!res.ok || !json.ok) {
        const msg = (json.error && json.error.message) ? json.error.message : 'Registration failed.';
        this.showAlert('register', msg);
        if (typeof App !== 'undefined' && App.showToast) {
          App.showToast(msg, 'error');
        }
        return;
      }

      // On success (or silently-swallowed duplicate), show confirmation
      if (typeof App !== 'undefined' && App.showToast) {
        App.showToast('Account created! Please check your email to verify. 🌟', 'success');
      }
      this.showAlert('register', 'Account created. Please verify your email before signing in.', 'success');

      // Transition to Login tab
      setTimeout(() => {
        this.switchTab('login');
      }, 1200);

    } catch (err) {
      console.error('[Auth] Registration error:', err);
      this.showAlert('register', 'Connection error. Please try again.');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create My Account & Enter →';
      }
    }
  },

  quickDemoLogin() {
    const identInput = document.getElementById('login-identifier');
    const pwdInput = document.getElementById('login-password');
    if (identInput) {
      identInput.value = 'demo@nammapayana.in';
      identInput.classList.add('flash-fill');
      setTimeout(() => identInput.classList.remove('flash-fill'), 600);
    }
    if (pwdInput) {
      pwdInput.value = 'demo123';
      pwdInput.classList.add('flash-fill');
      setTimeout(() => pwdInput.classList.remove('flash-fill'), 600);
    }
    this.submitLogin();
  },

  continueAsGuest() {
    this.currentUser = { id: 'guest', full_name: 'Guest Traveler', username: 'guest', persona: 'Explorer' };
    this.updateNavbarUI();
    if (typeof App !== 'undefined' && App.showToast) {
      App.showToast('Continuing as Guest Traveler. Feel free to plan journeys!', 'info');
    }
    if (typeof App !== 'undefined' && App.switchView) {
      App.switchView('landing');
    }
  },

  setUser(user) {
    this.currentUser = user;
    // Store only non-sensitive display data in localStorage
    try {
      const safeData = {
        display_name: user.full_name || user.username || 'Traveler',
        avatar_initial: (user.full_name || user.username || 'T').charAt(0).toUpperCase()
      };
      localStorage.setItem('nammapayana_user', JSON.stringify(safeData));
    } catch(e) { console.warn('Storage unavailable:', e); }
    this.updateNavbarUI();
  },

  async restoreSession() {
    // 1. Check if Supabase has an active OAuth session (e.g. from Google redirect)
    if (supabaseClient) {
      try {
        const { data: { session }, error } = await supabaseClient.auth.getSession();
        if (session && session.user) {
          await this.handleGoogleSession(session);
          return;
        }
      } catch (err) {
        console.warn('[Supabase session check]:', err);
      }
    }

    // 2. Check localStorage for display data and verify server session
    let savedDisplay = null;
    try {
      const raw = localStorage.getItem('nammapayana_user');
      if (raw) savedDisplay = JSON.parse(raw);
    } catch (e) {
      savedDisplay = null;
    }

    if (savedDisplay) {
      // Show a quick placeholder while we verify the session
      this.updateNavbarUI();
    }

    // Always verify with server session cookie (no Authorization header)
    try {
      const r = await fetch('/api/auth/me');
      const data = await r.json();
      if (data.ok && data.data) {
        this.setUser(data.data);
        // Authenticated! Direct to home page (or path if specified and not login)
        const path = (window.location.pathname || '').replace(/^\//, '').toLowerCase();
        if (!path || path === 'login' || path === 'signin') {
          if (typeof App !== 'undefined' && App.switchView) {
            App.switchView('landing');
          }
        } else if (typeof App !== 'undefined' && App.switchView) {
          App.switchView(path);
        }
      } else {
        // Not authenticated -> must be on login view!
        this.currentUser = null;
        try { localStorage.removeItem('nammapayana_user'); } catch(e) {}
        this.updateNavbarUI();
        if (typeof App !== 'undefined' && App.switchView) {
          App.switchView('login');
        }
      }
    } catch (e) {
      this.currentUser = null;
      this.updateNavbarUI();
      if (typeof App !== 'undefined' && App.switchView) {
        App.switchView('login');
      }
    }
  },

  updateNavbarUI() {
    const userContainer = document.getElementById('nav-user-container');
    const loginNavBtn = document.getElementById('nav-login-btn');
    const userNameEl = document.getElementById('nav-user-name');
    const userAvatarEl = document.getElementById('nav-user-avatar');
    const userPersonaEl = document.getElementById('nav-user-persona');

    if (this.currentUser) {
      if (loginNavBtn) loginNavBtn.style.display = 'none';
      if (userContainer) userContainer.style.display = 'flex';

      const initial = (this.currentUser.full_name || 'U').charAt(0).toUpperCase();
      if (userAvatarEl) {
        if (this.currentUser.avatar_url) {
          // Safely create img element without innerHTML
          const img = document.createElement('img');
          img.alt = 'Avatar';
          img.style.cssText = 'width:100%;height:100%;border-radius:50%;object-fit:cover;';
          // Validate https: URL before setting
          const avatarUrl = this.currentUser.avatar_url;
          if (typeof avatarUrl === 'string' && avatarUrl.startsWith('https://')) {
            img.src = avatarUrl;
            img.onerror = function() {
              this.onerror = null;
              userAvatarEl.textContent = initial;
            };
            userAvatarEl.textContent = '';
            userAvatarEl.appendChild(img);
          } else {
            userAvatarEl.textContent = initial;
          }
        } else {
          userAvatarEl.textContent = initial;
        }
      }
      if (userNameEl) userNameEl.textContent = this.currentUser.full_name || this.currentUser.username;
      if (userPersonaEl) userPersonaEl.textContent = this.currentUser.auth_provider === 'google' ? 'Google Account' : (this.currentUser.persona || 'Traveler');
    } else {
      if (userContainer) userContainer.style.display = 'none';
      if (loginNavBtn) loginNavBtn.style.display = 'inline-flex';
    }
  },

  async logout() {
    if (supabaseClient) {
      try {
        await supabaseClient.auth.signOut();
      } catch (e) {}
    }

    try {
      const csrfToken = await this.getCsrfToken();
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken }
      });
    } catch (e) {}

    this.currentUser = null;
    try {
      localStorage.removeItem('nammapayana_user');
    } catch (e) {}

    this.updateNavbarUI();
    if (typeof App !== 'undefined' && App.showToast) {
      App.showToast('You have been logged out. See you soon!', 'info');
    }
    // Return to login page
    if (typeof App !== 'undefined' && App.switchView) {
      App.switchView('login');
    }
  }
};
