/* ─────────────────────────────────────────────────────────────────
   ShopBot — app.js
   Auth: username + password → JWT stored in localStorage
   Sessions: fully server-side, per user
   ───────────────────────────────────────────────────────────────── */

const API_BASE = ''; // same origin; change to 'http://localhost:8000' if needed

/* ── State ────────────────────────────────────────────────────── */
let token        = null;   // JWT
let currentUser  = null;   // username string
let sessions     = [];     // [{ session_id, title, created_at, last_active }]
let activeId     = null;   // currently open session_id
let isLoading    = false;
let authMode     = 'login';

/* ── DOM refs (app shell) ──────────────────────────────────────── */
const messagesEl  = document.getElementById('messages');
const userInput   = document.getElementById('userInput');
const sendBtn     = document.getElementById('sendBtn');
const typingEl    = document.getElementById('typingIndicator');
const sessionList = document.getElementById('sessionList');
const welcome     = document.getElementById('welcome');

/* ── Init ─────────────────────────────────────────────────────── */
(function init() {
  const saved = localStorage.getItem('shopbot_token');
  const user  = localStorage.getItem('shopbot_user');
  if (saved && user) {
    token       = saved;
    currentUser = user;
    bootApp();
  }
})();

/* ── Auth tab switch ───────────────────────────────────────────── */
function switchTab(mode) {
  authMode = mode;
  document.getElementById('tabLogin').classList.toggle('active', mode === 'login');
  document.getElementById('tabRegister').classList.toggle('active', mode === 'register');
  document.getElementById('authSubmitLabel').textContent = mode === 'login' ? 'Sign in' : 'Create account';
  document.getElementById('authHint').innerHTML = mode === 'login'
    ? 'New here? Switch to <a href="#" onclick="switchTab(\'register\'); return false">Create account</a> — no email needed.'
    : 'Already have an account? <a href="#" onclick="switchTab(\'login\'); return false">Sign in</a>';
  document.getElementById('authError').textContent = '';
}

function appendAssistantMessage(text, scroll = true) {
  const el = document.createElement('div');
  el.className = 'msg bot';
  el.innerHTML = `
    <div class="msg-avatar">◈</div>
    <div class="msg-body">
      <div class="msg-bubble">${escHtml(text)}</div>
    </div>`;
  messagesEl.appendChild(el);
  if (scroll) scrollToBottom();
}

/* ── Auth submit ───────────────────────────────────────────────── */
async function submitAuth() {
  const username = document.getElementById('authUsername').value.trim();
  const password = document.getElementById('authPassword').value;
  const errEl    = document.getElementById('authError');
  const btnEl    = document.getElementById('authSubmit');
  const spinner  = document.getElementById('authSpinner');
  const label    = document.getElementById('authSubmitLabel');

  errEl.textContent = '';

  if (!username || !password) {
    errEl.textContent = 'Please fill in all fields.';
    return;
  }

  btnEl.disabled    = true;
  label.style.display = 'none';
  spinner.style.display = 'inline-block';

  try {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    const data = await res.json();

    if (!res.ok) {
      errEl.textContent = data.detail || 'Authentication failed.';
      return;
    }

    token       = data.token;
    currentUser = data.username;
    localStorage.setItem('shopbot_token', token);
    localStorage.setItem('shopbot_user', currentUser);

    bootApp();
  } catch (err) {
    errEl.textContent = 'Could not connect to server.';
    console.error(err);
  } finally {
    btnEl.disabled  = false;
    label.style.display = '';
    spinner.style.display = 'none';
  }
}

// Allow Enter key in auth form
document.getElementById('authPassword').addEventListener('keydown', e => {
  if (e.key === 'Enter') submitAuth();
});
document.getElementById('authUsername').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('authPassword').focus();
});

/* ── Boot the app after auth ───────────────────────────────────── */
async function bootApp() {
  document.getElementById('authScreen').style.display = 'none';
  document.getElementById('appShell').style.display   = 'flex';

  // Set user pill
  document.getElementById('userPillName').textContent = currentUser;
  document.getElementById('userAvatar').textContent   = currentUser[0].toUpperCase();

  // Wire up events now that the shell is visible
  userInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  userInput.addEventListener('input', autoResize);
  sendBtn.addEventListener('click', send);
  document.getElementById('newChatBtn').addEventListener('click', () => { newChat(); closeSidebar(); });

  // Load sessions from server
  await loadSessions();

  if (sessions.length === 0) {
    await newChat();
  } else {
    await switchSession(sessions[0].session_id);
  }

  userInput.focus();
}

/* ── Logout ────────────────────────────────────────────────────── */
function logout() {
  token       = null;
  currentUser = null;
  sessions    = [];
  activeId    = null;
  localStorage.removeItem('shopbot_token');
  localStorage.removeItem('shopbot_user');
  document.getElementById('authScreen').style.display = '';
  document.getElementById('appShell').style.display   = 'none';
  document.getElementById('authPassword').value = '';
  document.getElementById('authError').textContent = '';
}

/* ── API helpers ───────────────────────────────────────────────── */
async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });

  if (res.status === 401) {
    logout();
    throw new Error('Session expired. Please sign in again.');
  }

  return res;
}

/* ── Session management ────────────────────────────────────────── */
async function loadSessions() {
  document.getElementById('sessionLoading').style.display = '';
  try {
    const res  = await apiFetch('/api/sessions');
    const data = await res.json();
    sessions   = data.sessions || [];
  } catch (err) {
    console.error('Failed to load sessions:', err);
    sessions = [];
  }
  renderSessionList();
}

async function newChat() {
  // Don't create duplicate empty sessions
  const existingEmpty = sessions.find(s => s.title === 'New chat');
  if (existingEmpty) {
    await switchSession(existingEmpty.session_id);
    return;
  }

  try {
    const res  = await apiFetch('/api/session', { method: 'POST' });
    const data = await res.json();
    sessions.unshift(data);
    renderSessionList();
    await switchSession(data.session_id);
  } catch (err) {
    console.error('Failed to create session:', err);
  }
}

async function switchSession(sessionId) {
  activeId = sessionId;
  renderSessionList();
  clearMessages();

  // Update topbar title
  const sess = sessions.find(s => s.session_id === sessionId);
  if (sess) {
    document.getElementById('topbarTitle').textContent =
      sess.title === 'New chat' ? 'ShopBot' : sess.title;
  }

  // Load full conversation with payloads
  setLoading(true);
  try {
    const res = await apiFetch(`/api/session/${sessionId}/full`);
    const data = await res.json();
    
    if (data.conversation && data.conversation.length > 0) {
      if (welcome) welcome.style.display = 'none';
      
      data.conversation.forEach(msg => {
        if (msg.role === 'user') {
          appendUserMessage(msg.content, false);
        } else if (msg.role === 'assistant') {
          if (msg.payload) {
            renderStoredResponse(msg.payload, false);
          } else {
            appendAssistantMessage(msg.content, false);
          }
        }
      });
      
      scrollToBottom();
    } else {
      if (welcome) welcome.style.display = '';
    }
  } catch (err) {
    console.error('Failed to load session:', err);
    if (welcome) welcome.style.display = '';
  } finally {
    setLoading(false);
  }
  
  userInput.focus();
}

async function deleteSession(sessionId, e) {
  e.stopPropagation();
  if (!confirm('Delete this conversation?')) return;

  try {
    await apiFetch(`/api/session/${sessionId}`, { method: 'DELETE' });
    sessions = sessions.filter(s => s.session_id !== sessionId);
    renderSessionList();

    if (activeId === sessionId) {
      if (sessions.length > 0) {
        await switchSession(sessions[0].session_id);
      } else {
        await newChat();
      }
    }
  } catch (err) {
    console.error('Failed to delete session:', err);
  }
}

function renderSessionList() {
  const el = sessionList;
  el.innerHTML = '';

  if (sessions.length === 0) {
    el.innerHTML = '<div class="session-loading" style="color:var(--text3)">No conversations yet</div>';
    return;
  }

  // Group by date
  const today     = new Date();
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
  const lastWeek  = new Date(today); lastWeek.setDate(lastWeek.getDate() - 7);

  const groups = { Today: [], Yesterday: [], 'Last 7 days': [], Older: [] };

  sessions.forEach(s => {
    const d = new Date(s.last_active);
    if (isSameDay(d, today)) groups.Today.push(s);
    else if (isSameDay(d, yesterday)) groups.Yesterday.push(s);
    else if (d > lastWeek) groups['Last 7 days'].push(s);
    else groups.Older.push(s);
  });

  for (const [label, items] of Object.entries(groups)) {
    if (!items.length) continue;

    const groupLabel = document.createElement('div');
    groupLabel.className = 'session-group-label';
    groupLabel.textContent = label;
    el.appendChild(groupLabel);

    items.forEach(sess => {
      const item = document.createElement('div');
      item.className = 'session-item' + (sess.session_id === activeId ? ' active' : '');
      item.innerHTML = `
        <span class="session-item-icon">◇</span>
        <div class="session-item-text">
          <div class="session-item-title">${escHtml(sess.title)}</div>
          <div class="session-item-date">${formatRelativeTime(sess.last_active)}</div>
        </div>
        <button class="session-delete" title="Delete" onclick="deleteSession('${escHtml(sess.session_id)}', event)">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/></svg>
        </button>
      `;
      item.addEventListener('click', () => {
        switchSession(sess.session_id);
        closeSidebar();
      });
      el.appendChild(item);
    });
  }
}

/* ── Sidebar controls ──────────────────────────────────────────── */
function openSidebar() {
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('sidebarOverlay').classList.add('open');
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('open');
}

/* ── Send message ──────────────────────────────────────────────── */
async function send() {
  const text = userInput.value.trim();
  if (!text || isLoading || !activeId) return;

  if (welcome) welcome.style.display = 'none';
  appendUserMessage(text);
  userInput.value = '';
  userInput.style.height = 'auto';

  // Optimistically update session title in sidebar
  const sess = sessions.find(s => s.session_id === activeId);
  if (sess && sess.title === 'New chat') {
    sess.title = text.slice(0, 48) + (text.length > 48 ? '…' : '');
    renderSessionList();
    document.getElementById('topbarTitle').textContent = sess.title;
    
    // Also update title on backend
    try {
      await apiFetch(`/api/session/${activeId}/title`, {
        method: 'PATCH',
        body: JSON.stringify({ title: sess.title })
      });
    } catch (err) {
      console.error('Failed to update session title:', err);
    }
  }

  setLoading(true);
  try {
    const res = await apiFetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message: text, session_id: activeId }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    renderBotResponse(data);

    // Update last_active in local state
    if (sess) {
      sess.last_active = new Date().toISOString();
      // Move to top of list
      sessions = [sess, ...sessions.filter(s => s.session_id !== activeId)];
      renderSessionList();
    }
  } catch (err) {
    renderError('Could not reach the server. Is the backend running?');
    console.error(err);
  } finally {
    setLoading(false);
  }
}

function sendChip(el) {
  userInput.value = el.textContent;
  send();
}

/* ── Message rendering ─────────────────────────────────────────── */
function clearMessages() {
  messagesEl.innerHTML = '';
  if (welcome) {
    welcome.style.display = '';
    messagesEl.appendChild(welcome);
  }
}

function appendUserMessage(text, scroll = true) {
  const el = document.createElement('div');
  el.className = 'msg user';
  el.innerHTML = `
    <div class="msg-avatar">${escHtml((currentUser || 'U')[0].toUpperCase())}</div>
    <div class="msg-body">
      <div class="msg-bubble">${escHtml(text)}</div>
    </div>`;
  messagesEl.appendChild(el);
  if (scroll) scrollToBottom();
}

function renderBotResponse(data, scroll = true) {
  const el = document.createElement('div');
  el.className = 'msg bot';

  el.innerHTML = `<div class="msg-avatar">◈</div><div class="msg-body msg-rich"></div>`;
  const body = el.querySelector('.msg-rich');

  switch (data.type) {
    case 'products':
    case 'similar':
      body.innerHTML = buildProductsHTML(data);
      break;
    case 'detail':
      body.innerHTML = buildDetailHTML(data);
      break;
    case 'comparison':
      body.innerHTML = buildComparisonHTML(data);
      break;
    case 'clarification':
      body.innerHTML = buildClarificationHTML(data);
      break;
    case 'error':
      body.innerHTML = `<div class="error-bubble">${escHtml(data.text)}</div>`;
      break;
    default:
      body.innerHTML = `<div class="msg-bubble">${escHtml(data.text)}</div>`;
  }

  messagesEl.appendChild(el);
  if (scroll) scrollToBottom();
}

function renderStoredResponse(payload, scroll = true) {
  const el = document.createElement('div');
  el.className = 'msg bot';
  
  el.innerHTML = `<div class="msg-avatar">◈</div><div class="msg-body msg-rich"></div>`;
  const body = el.querySelector('.msg-rich');
  
  switch (payload.type) {
    case 'products':
    case 'similar':
      body.innerHTML = buildProductsHTML(payload);
      break;
    case 'detail':
      body.innerHTML = buildDetailHTML(payload);
      break;
    case 'comparison':
      body.innerHTML = buildComparisonHTML(payload);
      break;
    case 'clarification':
      body.innerHTML = buildClarificationHTML(payload);
      break;
    case 'message':
      body.innerHTML = `<div class="msg-bubble">${escHtml(payload.text)}</div>`;
      break;
    case 'error':
      body.innerHTML = `<div class="error-bubble">${escHtml(payload.text)}</div>`;
      break;
    default:
      body.innerHTML = `<div class="msg-bubble">${escHtml(payload.text || '')}</div>`;
  }
  
  messagesEl.appendChild(el);
  if (scroll) scrollToBottom();
}

function renderError(msg) {
  const el = document.createElement('div');
  el.className = 'msg bot';
  el.innerHTML = `
    <div class="msg-avatar">◈</div>
    <div class="msg-body msg-rich">
      <div class="error-bubble">${escHtml(msg)}</div>
    </div>`;
  messagesEl.appendChild(el);
  scrollToBottom();
}

/* ── Product builder ───────────────────────────────────────────── */
function buildProductsHTML(data) {
  const products   = data.products || [];
  const text       = data.text || '';
  const filters    = data.filters_applied || {};
  const relaxations = data.relaxations || [];
  let html = '';

  if (data.meta?.result_count != null) {
    html += `<div class="meta-badge">◈ ${data.meta.result_count} result${data.meta.result_count !== 1 ? 's' : ''}</div>`;
  }

  const filterKeys = Object.keys(filters).filter(k => filters[k] != null);
  if (filterKeys.length) {
    html += `<div class="filters-row">` +
      filterKeys.map(k => `<span class="filter-tag">${escHtml(k)}: ${escHtml(String(filters[k]))}</span>`).join('') +
      `</div>`;
  }

  if (relaxations.length) {
    html += `<div class="relaxation-tags">` +
      relaxations.map(r => `<span class="relaxation-tag">↕ ${escHtml(r)}</span>`).join('') +
      `</div>`;
  }

  if (text) html += `<div class="products-intro">${escHtml(text)}</div>`;

  if (products.length === 0) {
    html += `<div class="products-intro" style="color:var(--text3)">No products found.</div>`;
  } else {
    html += `<div class="product-grid">`;
    products.forEach(p => { html += buildProductCard(p); });
    html += `</div>`;
  }

  return html;
}

function buildProductCard(p) {
  const price  = p.min_price != null ? `$${parseFloat(p.min_price).toFixed(2)}` : 'N/A';
  const rating = p.avg_rating
    ? renderStars(p.avg_rating) + ` <span>${parseFloat(p.avg_rating).toFixed(1)}</span>`
    : '';
  const img = p.image_url
    ? `<img class="product-card-img" src="${escHtml(p.image_url)}" alt="${escHtml(p.title || '')}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
    + `<div class="product-card-img-placeholder" style="display:none">📦</div>`
    : `<div class="product-card-img-placeholder">📦</div>`;

  const href    = shopifyUrl(p);
  const tag     = href ? 'a' : 'div';
  const hrefAttr = href ? `href="${href}" target="_blank" rel="noopener"` : '';

  return `<${tag} class="product-card" ${hrefAttr}>
    ${img}
    <div class="product-card-body">
      <div class="product-card-vendor">${escHtml(p.vendor || '')}</div>
      <div class="product-card-title">${escHtml(p.title || 'Unknown Product')}</div>
      <div class="product-card-footer">
        <div class="product-card-price">${price}</div>
        <div class="product-card-rating">${rating}</div>
      </div>
    </div>
  </${tag}>`;
}

/* ── Detail builder ────────────────────────────────────────────── */
function buildDetailHTML(data) {
  const d    = data.detail || {};
  const text = data.text || '';
  const price  = d.min_price != null ? `$${parseFloat(d.min_price).toFixed(2)}` : (d.price_range || 'N/A');
  const rating = d.avg_rating != null ? parseFloat(d.avg_rating).toFixed(1) : null;
  const href   = shopifyUrl(d);

  const imgHTML = d.image_url
    ? `<img class="detail-img" src="${escHtml(d.image_url)}" alt="${escHtml(d.title || '')}" onerror="this.style.display='none'">`
    : `<div class="detail-img-placeholder">📦</div>`;

  let variantsHTML = '';
  if (d.variants && d.variants.length) {
    const chips = d.variants.slice(0, 10).map(v => {
      const label = [v.title, v.price ? `$${parseFloat(v.price).toFixed(2)}` : ''].filter(Boolean).join(' — ');
      return `<span class="variant-chip">${escHtml(label)}</span>`;
    }).join('');
    variantsHTML = `
      <div class="detail-variants">
        <div class="detail-variants-title">Variants (${d.variants_count || d.variants.length})</div>
        <div class="variant-chips">${chips}</div>
      </div>`;
  }

  let reviewHTML = '';
  if (d.top_review && d.top_review.body) {
    const stars = d.top_review.rating ? renderStars(d.top_review.rating) : '';
    reviewHTML = `
      <div class="detail-bottom">
        <div class="top-review">
          <div class="top-review-label">Top review ${stars}</div>
          <div class="top-review-body">"${escHtml(d.top_review.body)}"</div>
          <div class="top-review-author">— ${escHtml(d.top_review.reviewer_name || 'Anonymous')}</div>
        </div>
      </div>`;
  }

  const shopifyBtn = href
    ? `<a class="btn-primary" href="${href}" target="_blank" rel="noopener">View on Store ↗</a>`
    : '';

  return `
    <div class="detail-card">
      <div class="detail-top">
        <div class="detail-img-wrap">${imgHTML}</div>
        <div class="detail-info">
          ${d.vendor ? `<div class="detail-vendor">${escHtml(d.vendor)}</div>` : ''}
          <div class="detail-title">${escHtml(d.title || 'Product Details')}</div>
          ${rating ? `
            <div class="detail-rating-row">
              <span class="detail-rating-score">${renderStars(d.avg_rating)} ${rating}</span>
              <span class="detail-review-count">${d.total_reviews ? `(${d.total_reviews} reviews)` : ''}</span>
            </div>` : ''}
          <div class="detail-price">${price}</div>
          ${d.description ? `<div class="detail-desc">${escHtml(d.description).slice(0, 400)}${d.description.length > 400 ? '…' : ''}</div>` : ''}
          ${variantsHTML}
          <div class="detail-actions">${shopifyBtn}</div>
        </div>
      </div>
      ${reviewHTML}
    </div>
    ${text ? `<div class="products-intro" style="margin-top:10px">${escHtml(text)}</div>` : ''}
  `;
}

/* ── Comparison builder ────────────────────────────────────────── */
function buildComparisonHTML(data) {
  const cmp      = data.comparison || {};
  const products = cmp.products || [];
  const highlight = cmp.highlight || {};
  const text     = data.text || '';

  if (!products.length) {
    return `<div class="msg-bubble">${escHtml(text || 'No comparison data.')}</div>`;
  }

  let thead = '<tr><th>Feature</th>';
  products.forEach((p, i) => {
    const isWinner = Object.values(highlight).some(wi => wi === i);
    thead += `<th>${escHtml(p.title || `Product ${i+1}`)}${isWinner ? '<span class="compare-badge">★ Best</span>' : ''}</th>`;
  });
  thead += '</tr>';

  const rowDefs = [
    { key: 'image_url',     label: 'Image',    render: (v) => v ? `<img class="compare-img" src="${escHtml(v)}" alt="">` : '—' },
    { key: 'vendor',        label: 'Brand',    render: v => escHtml(v || '—') },
    { key: 'min_price',     label: 'Price',    render: (v, p, i) => {
        const val = v != null ? `$${parseFloat(v).toFixed(2)}` : (p.price_range || '—');
        return i === highlight.price ? `<span class="compare-winner">${val} ✓</span>` : val;
    }},
    { key: 'avg_rating',    label: 'Rating',   render: (v, p, i) => {
        if (!v) return '—';
        const txt = `${renderStars(v)} ${parseFloat(v).toFixed(1)}`;
        return i === highlight.rating ? `<span class="compare-winner">${txt} ✓</span>` : txt;
    }},
    { key: 'total_reviews', label: 'Reviews',  render: v => v != null ? v.toLocaleString() : '—' },
    { key: 'variants_count',label: 'Variants', render: v => v != null ? v : '—' },
    { key: 'description',   label: 'About',    render: v => v ? escHtml(v.slice(0, 110)) + (v.length > 110 ? '…' : '') : '—' },
    { key: '_shopify',      label: 'Link',     render: (_, p) => {
        const url = shopifyUrl(p);
        return url ? `<a class="btn-primary" href="${url}" target="_blank" style="font-size:11px;padding:5px 10px">View ↗</a>` : '—';
    }},
  ];

  let tbody = '';
  rowDefs.forEach(({ key, label, render }) => {
    tbody += '<tr>';
    tbody += `<td>${label}</td>`;
    products.forEach((p, i) => {
      const val = key === '_shopify' ? null : p[key];
      tbody += `<td>${render(val, p, i)}</td>`;
    });
    tbody += '</tr>';
  });

  return `
    ${text ? `<div class="compare-intro">${escHtml(text)}</div>` : ''}
    <div class="compare-wrap">
      <table class="compare-table">
        <thead>${thead}</thead>
        <tbody>${tbody}</tbody>
      </table>
    </div>
  `;
}

/* ── Clarification builder ─────────────────────────────────────── */
function buildClarificationHTML(data) {
  const q = (data.clarification && data.clarification.question) || data.text || 'Could you tell me more?';
  return `
    <div class="clarification-card">
      <div class="clarification-icon">💬</div>
      <div class="clarification-text">${escHtml(q)}</div>
    </div>
  `;
}

/* ── Utilities ─────────────────────────────────────────────────── */
function shopifyUrl(p) {
  const STORE_DOMAIN = window.SHOPIFY_STORE_DOMAIN || '';
  if (p.product_handle && STORE_DOMAIN) {
    return `https://${STORE_DOMAIN}/products/${p.product_handle}`;
  }
  if (p.product_handle) return `/products/${p.product_handle}`;
  return null;
}

function renderStars(rating) {
  const r = Math.round(parseFloat(rating));
  let s = '';
  for (let i = 0; i < 5; i++) s += `<span class="star">${i < r ? '★' : '☆'}</span>`;
  return s;
}

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function setLoading(val) {
  isLoading = val;
  sendBtn.disabled  = val;
  typingEl.style.display = val ? 'flex' : 'none';
  if (val) scrollToBottom();
}

function scrollToBottom() {
  requestAnimationFrame(() => { messagesEl.scrollTop = messagesEl.scrollHeight; });
}

function autoResize() {
  userInput.style.height = 'auto';
  userInput.style.height = Math.min(userInput.scrollHeight, 160) + 'px';
}

function isSameDay(a, b) {
  return a.getFullYear() === b.getFullYear() &&
         a.getMonth()    === b.getMonth() &&
         a.getDate()     === b.getDate();
}

function formatRelativeTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1)   return 'just now';
  if (diffMin < 60)  return `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24)    return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7)     return `${diffD}d ago`;
  return d.toLocaleDateString();
}