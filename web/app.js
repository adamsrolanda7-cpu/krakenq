/* KrakenQ — interface en onglets. JavaScript natif, aucune dépendance. */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const STORE_KEY = 'krakenq.v1';
  const FIRST_QUESTION = "C'est quoi une API ?";
  const MAX_TABS = 16;
  const STARTERS = [
    'REST ou WebSocket ?',
    'Comment faire un backtest sans me tromper ?',
    'Explique le Sharpe et le drawdown',
    'Comment sécuriser mes clés API ?',
    'Comment calculer la taille de position ?',
    "Que contient un carnet d'ordres ?",
  ];
  const COARSE = window.matchMedia('(pointer: coarse)').matches;

  // ------------------------------------------------------------------ outils DOM
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v == null) continue;
      if (k === 'class') el.className = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid != null) el.append(kid);
    return el;
  }
  const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ------------------------------------------------------------------ markdown (sûr : tout est échappé)
  const KEYWORDS = new Set(('and as assert async await break class continue def del elif else except finally for from global if import in is ' +
    'lambda nonlocal not or pass raise return try while with yield True False None self const let var function new null undefined true false ' +
    'switch case default export typeof echo fi then do done').split(' '));
  const LANGS = new Set(['py', 'python', 'js', 'javascript', 'ts', 'typescript', 'bash', 'sh', 'shell', 'json']);
  const TOKEN_RE = /(#[^\n]*|\/\/[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`)|(\b\d[\d_]*\.?\d*(?:e[+-]?\d+)?\b)|(\b[A-Za-z_][A-Za-z0-9_]*\b)/g;

  function highlight(code, lang) {
    if (!LANGS.has((lang || '').toLowerCase())) return esc(code);
    const re = new RegExp(TOKEN_RE.source, 'g');
    let out = '', last = 0, m;
    while ((m = re.exec(code))) {
      out += esc(code.slice(last, m.index));
      const t = esc(m[0]);
      if (m[1]) out += `<span class="tk-c">${t}</span>`;
      else if (m[2]) out += `<span class="tk-s">${t}</span>`;
      else if (m[3]) out += `<span class="tk-n">${t}</span>`;
      else if (KEYWORDS.has(m[0])) out += `<span class="tk-k">${t}</span>`;
      else if (code[re.lastIndex] === '(') out += `<span class="tk-f">${t}</span>`;
      else out += t;
      last = re.lastIndex;
    }
    return out + esc(code.slice(last));
  }

  function inline(src) {
    const codes = [];
    let s = src.replace(/`([^`\n]+)`/g, (_, c) => { codes.push(c); return '\u0000' + (codes.length - 1) + '\u0000'; });
    s = esc(s);
    s = s.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*\w])\*([^*\s][^*\n]*?)\*(?![*\w])/g, '$1<em>$2</em>');
    s = s.replace(/(^|[^\w])_([^_\s][^_\n]*?)_(?![\w])/g, '$1<em>$2</em>');
    s = s.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => '<code>' + esc(codes[+i]) + '</code>');
  }

  function renderList(items) {
    let html = '';
    const stack = [];
    for (const it of items) {
      while (stack.length && it.indent < stack[stack.length - 1].indent) html += '</li></' + (stack.pop().ordered ? 'ol' : 'ul') + '>';
      const top = stack[stack.length - 1];
      if (!top || it.indent > top.indent) { html += '<' + (it.ordered ? 'ol' : 'ul') + '>'; stack.push({ indent: it.indent, ordered: it.ordered }); }
      else html += '</li>';
      html += '<li>' + inline(it.text);
    }
    while (stack.length) html += '</li></' + (stack.pop().ordered ? 'ol' : 'ul') + '>';
    return html;
  }

  const cells = (line) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
  const LIST_RE = /^(\s*)([-*•]|\d+[.)])\s+(.*)$/;
  const FENCE_OPEN = /^\s*```\s*([\w+-]*)\s*$/;
  const FENCE_CLOSE = /^\s*```\s*$/;
  const TABLE_SEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

  function startsBlock(line, next) {
    return FENCE_OPEN.test(line) || /^#{1,4}\s/.test(line) || LIST_RE.test(line) || /^\s*>/.test(line) ||
      /^\s*(-{3,}|\*{3,})\s*$/.test(line) || (/^\s*\|.*\|\s*$/.test(line) && next !== undefined && TABLE_SEP.test(next));
  }

  function md(src) {
    const lines = src.replace(/\r\n?/g, '\n').split('\n');
    const out = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      let m;
      if (!line.trim()) { i++; continue; }
      if ((m = line.match(FENCE_OPEN))) {
        const lang = m[1], buf = [];
        i++;
        while (i < lines.length && !FENCE_CLOSE.test(lines[i])) buf.push(lines[i++]);
        i++;
        const label = lang || 'texte';
        out.push(`<div class="code"><div class="code-bar"><span>${esc(label)}</span><button type="button" data-copy>Copier</button></div><pre><code>${highlight(buf.join('\n'), lang)}</code></pre></div>`);
        continue;
      }
      if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { const lv = m[1].length + 1; out.push(`<h${lv}>${inline(m[2])}</h${lv}>`); i++; continue; }
      if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) { out.push('<hr>'); i++; continue; }
      if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && TABLE_SEP.test(lines[i + 1])) {
        const head = cells(line);
        i += 2;
        const rows = [];
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
        out.push('<div class="tbl"><table><thead><tr>' + head.map((c) => `<th>${inline(c)}</th>`).join('') + '</tr></thead><tbody>' +
          rows.map((r) => '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('') + '</tbody></table></div>');
        continue;
      }
      if (/^\s*>/.test(line)) {
        const buf = [];
        while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ''));
        out.push('<blockquote>' + md(buf.join('\n')) + '</blockquote>');
        continue;
      }
      if (LIST_RE.test(line)) {
        const items = [];
        while (i < lines.length) {
          const lm = lines[i].match(LIST_RE);
          if (lm) { items.push({ indent: lm[1].replace(/\t/g, '    ').length, ordered: /\d/.test(lm[2]), text: lm[3] }); i++; }
          else if (lines[i].trim() && /^\s{2,}\S/.test(lines[i]) && items.length && !startsBlock(lines[i])) { items[items.length - 1].text += ' ' + lines[i].trim(); i++; }
          else if (!lines[i].trim() && i + 1 < lines.length && LIST_RE.test(lines[i + 1])) i++;
          else break;
        }
        out.push(renderList(items));
        continue;
      }
      const buf = [line];
      i++;
      while (i < lines.length && lines[i].trim() && !startsBlock(lines[i], lines[i + 1])) buf.push(lines[i++]);
      out.push('<p>' + inline(buf.join('\n')).replace(/\n/g, '<br>') + '</p>');
    }
    return out.join('\n');
  }

  // ------------------------------------------------------------------ état
  const refs = new WeakMap(); // message -> éléments DOM
  const runtime = new Map(); // id d'onglet -> { ctrl }
  let status = null;
  let saveTimer = 0;
  let state = load();

  function load() {
    try {
      const s = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
      if (s && Array.isArray(s.tabs) && s.tabs.length) {
        for (const t of s.tabs) {
          t.msgs = Array.isArray(t.msgs) ? t.msgs : [];
          t.busy = false;
          const last = t.msgs[t.msgs.length - 1];
          if (last && last.pending) {
            delete last.pending;
            if (last.content) last.content += '\n\n> ⚠️ Réponse interrompue (la page a été rechargée).';
            else t.msgs.pop();
          }
        }
        s.seq = s.seq || s.tabs.length;
        if (!s.tabs.some((t) => t.id === s.active)) s.active = s.tabs[0].id;
        return s;
      }
    } catch (e) { /* stockage indisponible ou corrompu : on repart à zéro */ }
    return { seq: 0, active: null, tabs: [], fresh: true };
  }

  function save() {
    clearTimeout(saveTimer);
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({
        seq: state.seq, active: state.active,
        tabs: state.tabs.map((t) => ({ id: t.id, title: t.title, custom: t.custom, unread: t.unread, draft: t.draft, msgs: t.msgs })),
      }));
    } catch (e) { /* quota ou navigation privée : l'app fonctionne quand même */ }
  }
  const saveSoon = () => { clearTimeout(saveTimer); saveTimer = setTimeout(save, 1200); };

  const active = () => state.tabs.find((t) => t.id === state.active);
  const shorten = (s, n = 28) => { s = s.replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n - 1) + '…' : s; };

  // ------------------------------------------------------------------ éléments
  const tabsEl = $('#tabs'), threadEl = $('#thread'), inputEl = $('#input'), sendEl = $('#send'), composerEl = $('#composer');
  const ICON_SEND = sendEl.innerHTML;
  const ICON_STOP = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2.5" fill="currentColor"/></svg>';

  // ------------------------------------------------------------------ onglets
  function createTab(title) {
    const t = { id: 't' + (++state.seq), title: title || 'Nouvel onglet', custom: false, msgs: [], busy: false, unread: false, draft: '' };
    state.tabs.push(t);
    return t;
  }

  function activate(id) {
    const prev = active();
    if (prev) prev.draft = inputEl.value;
    state.active = id;
    const t = active();
    t.unread = false;
    inputEl.value = t.draft || '';
    renderTabs();
    renderThread(true);
    updateComposer();
    autosize();
    save();
    if (!COARSE) inputEl.focus();
  }

  function openNewTab() {
    const cur = active();
    if (cur && !cur.msgs.length) { inputEl.focus(); return cur; }
    if (state.tabs.length >= MAX_TABS) return cur;
    const t = createTab();
    activate(t.id);
    return t;
  }

  function closeTab(id) {
    const t = state.tabs.find((x) => x.id === id);
    if (!t) return;
    if (t.msgs.length > 1 && !confirm('Fermer cet onglet ? La conversation sera supprimée.')) return;
    const rt = runtime.get(id);
    if (rt) rt.ctrl.abort();
    const idx = state.tabs.indexOf(t);
    state.tabs.splice(idx, 1);
    if (!state.tabs.length) { activate(createTab().id); return; }
    if (state.active === id) activate(state.tabs[Math.min(idx, state.tabs.length - 1)].id);
    else { renderTabs(); save(); }
  }

  function renameTab(t) {
    const name = prompt("Nom de l'onglet", t.title);
    if (name == null) return;
    t.title = shorten(name, 40) || t.title;
    t.custom = true;
    renderTabs();
    save();
  }

  function renderTabs() {
    tabsEl.replaceChildren();
    for (const t of state.tabs) {
      const isActive = t.id === state.active;
      const dotClass = 'dot' + (t.busy ? ' busy' : t.unread ? ' unread' : '');
      const label = t.title + (t.busy ? ' (Kraken répond)' : t.unread ? ' (nouvelle réponse)' : '');
      const main = h('button', {
        class: 'tab-main', type: 'button', role: 'tab', id: 'tab-' + t.id, 'aria-selected': String(isActive), 'aria-label': label,
        tabindex: isActive ? '0' : '-1', title: t.title,
        onclick: () => { if (!isActive) activate(t.id); },
        ondblclick: () => renameTab(t),
        onkeydown: (e) => {
          const i = state.tabs.indexOf(t);
          const to = e.key === 'ArrowRight' ? state.tabs[i + 1] : e.key === 'ArrowLeft' ? state.tabs[i - 1] : null;
          if (to) { e.preventDefault(); activate(to.id); $('#tab-' + to.id)?.focus(); }
        },
      }, h('span', { class: dotClass, 'aria-hidden': 'true' }), h('span', { class: 'tab-title' }, t.title));
      const close = h('button', { class: 'tab-close', type: 'button', 'aria-label': 'Fermer l\'onglet ' + t.title, onclick: () => closeTab(t.id) },
        h('span', { 'aria-hidden': 'true' }, '×'));
      tabsEl.append(h('div', { class: 'tab' + (isActive ? ' active' : '') }, main, close));
    }
    tabsEl.append(h('button', {
      class: 'tab-new', type: 'button', 'aria-label': 'Nouvel onglet', title: 'Nouvel onglet', disabled: state.tabs.length >= MAX_TABS,
      onclick: openNewTab,
    }, '+'));
    $('.tab.active', tabsEl)?.scrollIntoView({ inline: 'nearest', block: 'nearest' });
  }

  // ------------------------------------------------------------------ fil de discussion
  function providerLabel(meta) {
    if (!meta) return '';
    if (meta.provider === 'offline') return 'Hors-ligne, base intégrée';
    return (meta.provider === 'anthropic' ? 'Claude' : 'API compatible OpenAI') + ' (' + meta.model + ')';
  }

  function msgEl(tab, m, index) {
    if (m.role === 'user') return h('article', { class: 'msg user' }, h('div', { class: 'bubble' }, m.content));
    const body = h('div', { class: 'md' });
    const col = h('div', { class: 'col' });
    const notice = h('div', { class: 'callout', hidden: true });
    const foot = h('div', { class: 'foot' });
    col.append(notice, body, foot);
    refs.set(m, { body, notice, foot, col });
    paintBot(tab, m, index);
    return h('article', { class: 'msg bot' }, h('img', { class: 'avatar', src: 'assets/mark-128.png', alt: '', width: 32, height: 32 }), col);
  }

  // Pendant le flux, referme provisoirement un ** ou un ` resté ouvert pour éviter les symboles bruts qui clignotent.
  function closeDangling(src) {
    const fences = (src.match(/^\s*```/gm) || []).length;
    if (fences % 2) return src; // bloc de code en cours : rendu tel quel
    const last = src.slice(src.lastIndexOf('\n') + 1);
    let out = src;
    if (((last.match(/\*\*/g) || []).length) % 2) out += '**';
    if (((last.replace(/\*\*/g, '').match(/`/g) || []).length) % 2) out += '`';
    return out;
  }

  function paintBot(tab, m, index) {
    const r = refs.get(m);
    if (!r) return;
    if (m.err) {
      r.body.replaceChildren();
      r.notice.className = 'callout error';
      r.notice.hidden = false;
      r.notice.setAttribute('role', 'alert');
      r.notice.replaceChildren(m.err, h('button', { type: 'button', class: 'link', onclick: () => retry(tab, m) }, 'Réessayer'));
      r.foot.replaceChildren();
      return;
    }
    if (m.notice) {
      r.notice.className = 'callout';
      r.notice.hidden = false;
      r.notice.textContent = 'Le service IA ne répond pas (' + m.notice + '). Réponse du mode hors-ligne :';
    }
    r.body.innerHTML = m.content ? md(m.pending ? closeDangling(m.content) : m.content) : '<span class="typing" role="status" aria-label="Kraken réfléchit"><i></i><i></i><i></i></span>';
    r.foot.replaceChildren();
    if (!m.pending && m.content) {
      r.foot.append(h('button', { type: 'button', onclick: (e) => copyText(m.content, e.currentTarget, 'Copier la réponse') }, 'Copier la réponse'));
      if (m.meta) r.foot.append(h('span', {}, providerLabel(m.meta)));
    }
  }

  function renderThread(toBottom) {
    const t = active();
    if (!t) return;
    const inner = h('div', { class: 'thread-in' });
    if (!t.msgs.length) {
      inner.append(h('section', { class: 'empty' },
        h('img', { src: 'assets/logo-mark.svg', alt: '' }),
        h('h1', {}, 'Pose ta question Quant dev'),
        h('p', {}, 'Chaque onglet est une conversation indépendante : lance-en plusieurs et passe de l\'un à l\'autre pendant que Kraken répond.'),
        h('div', { class: 'chips' }, STARTERS.map((q) => h('button', { class: 'chip', type: 'button', onclick: () => send(t, q) }, q))),
        h('p', { class: 'fine-print' }, 'Projet fun, prototype éducatif : pas un conseil d\'investissement, pas pour de l\'argent réel.')));
    } else {
      t.msgs.forEach((m, i) => inner.append(msgEl(t, m, i)));
      const last = t.msgs[t.msgs.length - 1];
      if (last.role === 'user' && !t.busy) {
        inner.append(h('div', { class: 'callout' }, 'Ce message n\'a pas reçu de réponse.', h('button', { type: 'button', class: 'link', onclick: () => answer(t) }, 'Relancer')));
      }
    }
    threadEl.replaceChildren(inner);
    if (toBottom) threadEl.scrollTop = t.scroll != null && !t.busy ? t.scroll : threadEl.scrollHeight;
  }

  const nearBottom = () => threadEl.scrollHeight - threadEl.scrollTop - threadEl.clientHeight < 90;
  threadEl.addEventListener('scroll', () => { const t = active(); if (t) t.scroll = threadEl.scrollTop; }, { passive: true });

  const pendingPaint = new Set();
  function schedulePaint(tab, m) {
    if (pendingPaint.has(m)) return;
    pendingPaint.add(m);
    requestAnimationFrame(() => {
      pendingPaint.delete(m);
      if (tab.id !== state.active) return;
      const stick = nearBottom();
      paintBot(tab, m, tab.msgs.indexOf(m));
      if (stick) threadEl.scrollTop = threadEl.scrollHeight;
    });
  }

  threadEl.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-copy]');
    if (!btn) return;
    const code = btn.closest('.code')?.querySelector('code');
    if (code) copyText(code.textContent, btn, 'Copier');
  });

  async function copyText(text, btn, idle) {
    let ok = false;
    try { await navigator.clipboard.writeText(text); ok = true; }
    catch (e) {
      const ta = h('textarea', { style: 'position:fixed;opacity:0' }, text);
      document.body.append(ta); ta.select();
      try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
      ta.remove();
    }
    btn.textContent = ok ? 'Copié' : 'Copie impossible';
    setTimeout(() => { btn.textContent = idle; }, 1600);
  }

  // ------------------------------------------------------------------ envoi et flux
  function send(tab, text) {
    text = (text || '').trim();
    if (!text || tab.busy) return;
    if (tab.id !== state.active) activate(tab.id);
    tab.msgs.push({ role: 'user', content: text });
    if (!tab.custom && tab.msgs.filter((m) => m.role === 'user').length === 1) tab.title = shorten(text);
    tab.draft = '';
    if (tab.id === state.active) { inputEl.value = ''; autosize(); }
    answer(tab);
  }

  function retry(tab, errMsg) {
    const i = tab.msgs.indexOf(errMsg);
    if (i >= 0) tab.msgs.splice(i, 1);
    answer(tab);
  }

  function answer(tab) {
    const m = { role: 'assistant', content: '', pending: true };
    tab.msgs.push(m);
    tab.busy = true;
    delete tab.scroll;
    renderTabs(); renderThread(true); updateComposer(); save();
    streamReply(tab, m);
  }

  async function streamReply(tab, m) {
    const ctrl = new AbortController();
    runtime.set(tab.id, { ctrl });
    const history = tab.msgs.filter((x) => x !== m && !x.err && !x.pending).map((x) => ({ role: x.role, content: x.content }));
    let stopped = false;
    try {
      const res = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: history }), signal: ctrl.signal,
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.error || 'Erreur ' + res.status);
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      const handle = (ev) => {
        if (ev.t === 'meta') m.meta = { provider: ev.provider, model: ev.model, note: ev.note };
        else if (ev.t === 'delta') { m.content += ev.v; schedulePaint(tab, m); saveSoon(); }
        else if (ev.t === 'fallback') { m.notice = ev.v; schedulePaint(tab, m); }
        else if (ev.t === 'error') m.err = ev.v;
      };
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let nl;
        while ((nl = buf.indexOf('\n')) >= 0) {
          const line = buf.slice(0, nl).trim();
          buf = buf.slice(nl + 1);
          if (line) { try { handle(JSON.parse(line)); } catch (e) { /* ligne partielle ignorée */ } }
        }
      }
    } catch (e) {
      if (e.name === 'AbortError') stopped = true;
      else {
        const msg = e instanceof TypeError
          ? 'Le serveur KrakenQ ne répond pas. Vérifie que « python app.py » tourne toujours, puis réessaie.'
          : String(e.message || e);
        if (m.content) m.content += '\n\n> ⚠️ Réponse interrompue : ' + msg;
        else m.err = msg;
      }
    } finally {
      delete m.pending;
      tab.busy = false;
      runtime.delete(tab.id);
      if (!m.content && !m.err) {
        if (stopped) { const i = tab.msgs.indexOf(m); if (i >= 0) tab.msgs.splice(i, 1); }
        else m.err = 'Réponse vide. Réessaie ou change de cerveau dans les réglages.';
      }
      if (tab.id !== state.active && tab.msgs.includes(m)) tab.unread = true;
      renderTabs();
      if (tab.id === state.active) { const stick = nearBottom(); renderThread(false); if (stick) threadEl.scrollTop = threadEl.scrollHeight; updateComposer(); }
      save();
    }
  }

  function stopReply() {
    const t = active();
    const rt = t && runtime.get(t.id);
    if (rt) rt.ctrl.abort();
  }

  // ------------------------------------------------------------------ saisie
  function autosize() {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 176) + 'px';
  }

  function updateComposer() {
    const t = active();
    const busy = !!(t && t.busy);
    sendEl.classList.toggle('stop', busy);
    sendEl.type = busy ? 'button' : 'submit';
    sendEl.innerHTML = busy ? ICON_STOP : ICON_SEND;
    sendEl.setAttribute('aria-label', busy ? 'Arrêter la réponse' : 'Envoyer');
    sendEl.disabled = !busy && !inputEl.value.trim();
    inputEl.placeholder = busy ? 'Kraken répond…' : 'Pose ta question Quant dev…';
  }

  inputEl.addEventListener('input', () => { autosize(); updateComposer(); const t = active(); if (t) t.draft = inputEl.value; saveSoon(); });
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && !COARSE) { e.preventDefault(); composerEl.requestSubmit(); }
  });
  composerEl.addEventListener('submit', (e) => { e.preventDefault(); const t = active(); if (t) send(t, inputEl.value); });
  sendEl.addEventListener('click', () => { if (sendEl.classList.contains('stop')) stopReply(); });

  // ------------------------------------------------------------------ état du serveur et réglages
  async function refreshStatus() {
    try {
      const res = await fetch('/api/status', { cache: 'no-store' });
      status = res.ok ? await res.json() : null;
    } catch (e) { status = null; }
    renderStatus();
  }

  function renderStatus() {
    const pill = $('#mode'), main = $('#mode-main'), sub = $('#mode-sub');
    if (!status) { pill.dataset.mode = 'down'; main.textContent = 'Serveur injoignable'; sub.textContent = ''; return; }
    const offline = status.resolved === 'offline';
    pill.dataset.mode = offline ? 'offline' : 'online';
    main.textContent = offline ? 'Hors-ligne' : status.resolved === 'anthropic' ? 'Claude' : 'API compatible';
    sub.textContent = offline ? (status.note || 'base intégrée') : status.model;
  }

  const dlg = $('#settings'), form = $('#settings-form');
  const errEl = $('#settings-error');
  const fld = { ak: $('#f-anthropic-key'), am: $('#f-anthropic-model'), ou: $('#f-openai-url'), ok: $('#f-openai-key'), om: $('#f-openai-model'), mx: $('#f-max') };
  let clearAnthropic = false, clearOpenai = false;

  function openSettings() {
    if (!status) { refreshStatus(); }
    const s = status || {};
    clearAnthropic = clearOpenai = false;
    form.elements.provider.value = s.provider || 'auto';
    fld.ak.value = ''; fld.ok.value = '';
    fld.ak.placeholder = s.anthropic_key ? s.anthropic_key + ' (laisse vide pour la garder)' : 'sk-ant-…';
    fld.ok.placeholder = s.openai_key ? s.openai_key + ' (laisse vide pour la garder)' : 'Facultative pour un serveur local';
    $('#clear-anthropic').hidden = !s.anthropic_key;
    $('#clear-openai').hidden = !s.openai_key;
    fld.am.value = s.anthropic_model || '';
    fld.ou.value = s.openai_base_url || '';
    fld.om.value = s.openai_model || '';
    fld.mx.value = s.max_tokens || 1500;
    errEl.hidden = true;
    dlg.showModal();
  }

  $('#mode').addEventListener('click', openSettings);
  $('#settings-close').addEventListener('click', () => dlg.close());
  $('#settings-cancel').addEventListener('click', () => dlg.close());
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
  $('#clear-anthropic').addEventListener('click', (e) => { clearAnthropic = true; fld.ak.value = ''; fld.ak.placeholder = 'Clé effacée à l\'enregistrement'; e.currentTarget.hidden = true; });
  $('#clear-openai').addEventListener('click', (e) => { clearOpenai = true; fld.ok.value = ''; fld.ok.placeholder = 'Clé effacée à l\'enregistrement'; e.currentTarget.hidden = true; });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const patch = {
      provider: form.elements.provider.value,
      anthropic_model: fld.am.value, openai_base_url: fld.ou.value, openai_model: fld.om.value, max_tokens: fld.mx.value,
    };
    if (clearAnthropic) patch.anthropic_api_key = null; else if (fld.ak.value.trim()) patch.anthropic_api_key = fld.ak.value.trim();
    if (clearOpenai) patch.openai_api_key = null; else if (fld.ok.value.trim()) patch.openai_api_key = fld.ok.value.trim();
    try {
      const res = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Erreur ' + res.status);
      status = data;
      renderStatus();
      dlg.close();
    } catch (err) {
      errEl.textContent = err instanceof TypeError ? 'Le serveur KrakenQ ne répond pas.' : String(err.message || err);
      errEl.hidden = false;
    }
  });

  // ------------------------------------------------------------------ démarrage
  window.addEventListener('pagehide', save);
  document.addEventListener('visibilitychange', () => { if (document.hidden) save(); });

  const firstRun = state.fresh;
  if (firstRun) { delete state.fresh; state.active = createTab().id; }
  const first = active();
  inputEl.value = first.draft || '';
  renderTabs();
  renderThread(true);
  updateComposer();
  autosize();
  refreshStatus();
  if (firstRun) send(first, FIRST_QUESTION); // la toute première question : « C'est quoi une API ? »
  else if (!COARSE) inputEl.focus();

  // pour les tests et le débogage depuis la console
  window.krakenq = { get state() { return state; }, send: (text) => send(active(), text), openNewTab };
})();
