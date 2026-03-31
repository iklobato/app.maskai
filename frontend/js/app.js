const API = '/api';

async function api(endpoint, options = {}) {
    const response = await fetch(`${API}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
        credentials: 'include',
    });
    if (response.redirected) {
        window.location.href = response.url;
        return;
    }
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Request failed');
    return data;
}

async function getUser() {
    try {
        return await api('/auth/me');
    } catch {
        return null;
    }
}

function renderLogin() {
    return `
        <div class="card" style="max-width: 400px; margin: 4rem auto;">
            <h2>Sign in to maskai</h2>
            <div id="login-error" class="alert alert-error hidden"></div>
            <form id="login-form">
                <div class="form-group">
                    <input type="text" name="username" placeholder="Email or username" required>
                </div>
                <div class="form-group">
                    <input type="password" name="password" placeholder="Password" required>
                </div>
                <button type="submit" class="btn" style="width: 100%;">Sign in</button>
            </form>
            <p style="text-align: center; margin-top: 1rem; color: var(--text-muted);">
                Don't have an account? <a href="#register" style="color: var(--accent);">Register</a>
            </p>
        </div>
    `;
}

function renderRegister() {
    return `
        <div class="card" style="max-width: 400px; margin: 4rem auto;">
            <h2>Create account</h2>
            <div id="register-error" class="alert alert-error hidden"></div>
            <form id="register-form">
                <div class="form-group">
                    <input type="email" name="email" placeholder="Email" required>
                </div>
                <div class="form-group">
                    <input type="text" name="username" placeholder="Username" required>
                </div>
                <div class="form-group">
                    <input type="password" name="password" placeholder="Password" minlength="8" required>
                </div>
                <button type="submit" class="btn" style="width: 100%;">Create account</button>
            </form>
            <p style="text-align: center; margin-top: 1rem; color: var(--text-muted);">
                Already have an account? <a href="#login" style="color: var(--accent);">Sign in</a>
            </p>
        </div>
    `;
}

async function renderDashboard(user, params) {
    const [accounts, subscription, apiKeys] = await Promise.all([
        api('/accounts').catch(() => []),
        api('/subscription').catch(() => ({ tier: null, status: 'inactive' })),
        api('/keys').catch(() => []),
    ]);

    let alert = '';
    if (params.get('connected') === 'true') alert = '<div class="alert alert-success">Email account connected! Syncing emails in background.</div>';
    if (params.get('subscribed') === 'true') alert = '<div class="alert alert-success">Subscription activated!</div>';
    if (params.get('canceled') === 'true') alert = '<div class="alert alert-error">Subscription canceled.</div>';

    return `
        ${alert}
        <div class="card">
            <h2>Welcome, ${user.username}</h2>
            <p style="color: var(--text-muted);">${user.email}</p>
        </div>

        ${subscription.tier ? `
            <div class="card">
                <h2>Subscription</h2>
                <p><strong>Tier:</strong> ${subscription.tier}</p>
                <p><strong>Status:</strong> ${subscription.status}</p>
                ${subscription.current_period_end ? `<p><strong>Renews:</strong> ${new Date(subscription.current_period_end).toLocaleDateString()}</p>` : ''}
                <div style="margin-top: 1rem;">
                    <button class="btn btn-secondary" onclick="manageSubscription()">Manage Subscription</button>
                </div>
            </div>
        ` : `
            <div class="card">
                <h2>Choose a Plan</h2>
                <div class="pricing-grid">
                    <div class="pricing-card">
                        <h3>Basic</h3>
                        <div class="price">$9<span>/mo</span></div>
                        <p style="margin-top: 0.5rem; font-size: 0.875rem;">1 email account</p>
                        <button class="btn" style="margin-top: 1rem;" onclick="subscribe('basic')">Subscribe</button>
                    </div>
                    <div class="pricing-card featured">
                        <h3>Pro</h3>
                        <div class="price">$29<span>/mo</span></div>
                        <p style="margin-top: 0.5rem; font-size: 0.875rem;">5 email accounts</p>
                        <button class="btn" style="margin-top: 1rem;" onclick="subscribe('pro')">Subscribe</button>
                    </div>
                    <div class="pricing-card">
                        <h3>Enterprise</h3>
                        <div class="price">$99<span>/mo</span></div>
                        <p style="margin-top: 0.5rem; font-size: 0.875rem;">Unlimited accounts</p>
                        <button class="btn" style="margin-top: 1rem;" onclick="subscribe('enterprise')">Subscribe</button>
                    </div>
                </div>
            </div>
        `}

        <div class="card">
            <h2>Connected Accounts</h2>
            ${accounts.length === 0 ? '<p style="color: var(--text-muted);">No accounts connected yet.</p>' : ''}
            ${accounts.map(acc => `
                <div class="account-item">
                    <div class="account-info">
                        <div class="account-email">${acc.email}</div>
                        <div class="account-meta">
                            ${acc.provider} · ${acc.sync_status} · ${acc.emails_synced} emails synced
                            ${acc.last_sync_at ? ` · Last sync: ${new Date(acc.last_sync_at).toLocaleString()}` : ''}
                        </div>
                    </div>
                    <button class="btn btn-danger btn-sm" onclick="disconnectAccount('${acc.id}')">Disconnect</button>
                </div>
            `).join('')}
            <button class="btn" style="margin-top: 1rem;" onclick="connectGoogle()">Connect Google Account</button>
        </div>

        <div class="card">
            <h2>API Keys</h2>
            <p style="color: var(--text-muted); font-size: 0.875rem; margin-bottom: 1rem;">
                Use these keys to connect AI assistants like Claude to your email.
            </p>
            ${apiKeys.map(key => `
                <div class="key-item">
                    <div class="account-info">
                        <div class="account-email">${key.name}</div>
                        <div class="account-meta">
                            ${key.prefix}*** · Created ${new Date(key.created_at).toLocaleDateString()}
                            ${key.last_used_at ? ` · Last used ${new Date(key.last_used_at).toLocaleDateString()}` : ''}
                        </div>
                    </div>
                    <button class="btn btn-danger btn-sm" onclick="revokeKey('${key.id}')">Revoke</button>
                </div>
            `).join('')}
            <button class="btn" style="margin-top: 1rem;" onclick="createApiKey()">Generate New Key</button>
        </div>

        <div class="card">
            <h2>MCP Server</h2>
            <p style="color: var(--text-muted); margin-bottom: 1rem;">Connect Claude Desktop or other MCP clients to your email.</p>
            <pre><code>npm install -g @anthropic-ai/claude-mcp</code></pre>
            <p style="margin-top: 1rem; color: var(--text-muted);">Configure in Claude Desktop settings:</p>
            <pre><code>{
  "mcpServers": {
    "maskai": {
      "command": "uvicorn",
      "args": ["backend.main:app", "--host", "localhost", "--port", "8000"]
    }
  }
}</code></pre>
        </div>
    `;
}

async function connectGoogle() {
    const data = await api('/auth/google/start');
    window.location.href = data.url;
}

async function disconnectAccount(id) {
    if (confirm('Disconnect this account? All synced emails will be deleted.')) {
        await api(`/accounts/${id}`, { method: 'DELETE' });
        router();
    }
}

async function subscribe(tier) {
    const data = await api('/subscription/checkout', {
        method: 'POST',
        body: JSON.stringify({ tier }),
    });
    window.location.href = data.url;
}

async function manageSubscription() {
    const data = await api('/subscription/portal', { method: 'POST' });
    window.location.href = data.url;
}

async function createApiKey() {
    const name = prompt('Enter a name for this key:');
    if (!name) return;
    const data = await api('/keys', {
        method: 'POST',
        body: new URLSearchParams({ name }),
    });
    alert(`API Key created!\n\nName: ${data.name}\nKey: ${data.key}\n\nSave this key - you won't see it again!`);
    router();
}

async function revokeKey(id) {
    if (confirm('Revoke this API key?')) {
        await api(`/keys/${id}`, { method: 'DELETE' });
        router();
    }
}

async function logout() {
    await api('/auth/logout', { method: 'POST' });
    window.location.hash = '#login';
    router();
}

async function router() {
    const hash = window.location.hash || '#login';
    const [path, queryString] = hash.slice(1).split('?');
    const params = new URLSearchParams(queryString || '');
    const main = document.getElementById('main-content');
    const navLinks = document.getElementById('nav-links');

    const user = await getUser();

    if (!user && path !== 'login' && path !== 'register') {
        window.location.hash = '#login';
        return;
    }

    if (user) {
        navLinks.innerHTML = `
            <a href="#dashboard">Dashboard</a>
            <a href="#" onclick="logout(); return false;">Logout</a>
        `;
    } else {
        navLinks.innerHTML = '';
    }

    switch (path) {
        case 'login':
            main.innerHTML = renderLogin();
            document.getElementById('login-form').onsubmit = async (e) => {
                e.preventDefault();
                const fd = new FormData(e.target);
                try {
                    await api('/auth/login', {
                        method: 'POST',
                        body: new URLSearchParams(fd),
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    });
                    router();
                } catch (err) {
                    document.getElementById('login-error').textContent = err.message;
                    document.getElementById('login-error').classList.remove('hidden');
                }
            };
            break;
        case 'register':
            main.innerHTML = renderRegister();
            document.getElementById('register-form').onsubmit = async (e) => {
                e.preventDefault();
                const fd = new FormData(e.target);
                try {
                    await api('/auth/register', {
                        method: 'POST',
                        body: new URLSearchParams(fd),
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    });
                    router();
                } catch (err) {
                    document.getElementById('register-error').textContent = err.message;
                    document.getElementById('register-error').classList.remove('hidden');
                }
            };
            break;
        case 'dashboard':
            main.innerHTML = await renderDashboard(user, params);
            break;
        default:
            main.innerHTML = await renderDashboard(user, params);
    }
}

window.addEventListener('hashchange', router);
router();
