/* ── API & Auth ─────────────────────────────────────────────────────────────── */
const API = '';

function getToken()      { return localStorage.getItem('studio_token'); }
function setToken(t)     { localStorage.setItem('studio_token', t); }
function clearToken()    { localStorage.removeItem('studio_token'); }

async function api(path, opts = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(API + path, { ...opts, headers });
  if (res.status === 401) { clearToken(); window.location.href = '/medico/login.html'; return; }
  if (res.status === 204) return null;
  const json = await res.json().catch(() => ({ detail: 'Errore sconosciuto' }));
  if (!res.ok) throw new Error(json.detail || `Errore ${res.status}`);
  return json;
}

function requireAuth() {
  if (!getToken()) { window.location.href = '/medico/login.html'; return false; }
  return true;
}

/* ── Formatters ─────────────────────────────────────────────────────────────── */
function fmtData(s) {
  if (!s) return '—';
  const d = new Date(s + (s.includes('T') ? '' : 'T00:00:00'));
  return d.toLocaleDateString('it-IT');
}
function fmtDataOra(s) {
  if (!s) return '—';
  return new Date(s).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' });
}
function fmtOra(s) {
  if (!s) return '—';
  return new Date(s).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
}
function nomeMese(n) {
  return ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
          'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre'][n];
}
function nomeGiorno(n) {
  return ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato','Domenica'][n];
}
function formatDataItaliano(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' });
}

/* ── Notifiche ──────────────────────────────────────────────────────────────── */
function showAlert(msg, type = 'success', container = null) {
  const el = document.createElement('div');
  el.className = `alert alert-${type}`;
  el.textContent = msg;
  const target = container || document.querySelector('.alert-container') || document.body;
  target.prepend(el);
  setTimeout(() => el.remove(), 4000);
}

/* ── Codice Fiscale (JS) ────────────────────────────────────────────────────── */
const _MESI_CF  = 'ABCDEHLMPRST';
const _DISPARI  = {0:1,1:0,2:5,3:7,4:9,5:13,6:15,7:17,8:19,9:21,
  A:1,B:0,C:5,D:7,E:9,F:13,G:15,H:17,I:19,J:21,K:2,L:4,M:18,N:20,
  O:11,P:3,Q:6,R:8,S:12,T:14,U:16,V:10,W:22,X:25,Y:24,Z:23};
const _PARI     = {0:0,1:1,2:2,3:3,4:4,5:5,6:6,7:7,8:8,9:9,
  A:0,B:1,C:2,D:3,E:4,F:5,G:6,H:7,I:8,J:9,K:10,L:11,M:12,N:13,
  O:14,P:15,Q:16,R:17,S:18,T:19,U:20,V:21,W:22,X:23,Y:24,Z:25};

function _pulisciCF(s) { return s.toUpperCase().replace(/[^A-Z]/g,''); }
function _codificaCognome(c) {
  c = _pulisciCF(c);
  const cons = [...c].filter(x=>'AEIOU'.includes(x)===false);
  const voc  = [...c].filter(x=>'AEIOU'.includes(x));
  return ([...cons,...voc,'X','X','X']).slice(0,3).join('');
}
function _codificaNome(n) {
  n = _pulisciCF(n);
  const cons = [...n].filter(x=>'AEIOU'.includes(x)===false);
  const voc  = [...n].filter(x=>'AEIOU'.includes(x));
  if (cons.length >= 4) return [cons[0],cons[2],cons[3]].join('');
  return ([...cons,...voc,'X','X','X']).slice(0,3).join('');
}
function _controlCF(cf15) {
  let sum = 0;
  for (let i = 0; i < cf15.length; i++) {
    const c = cf15[i];
    sum += i % 2 === 0 ? (_DISPARI[c] ?? 0) : (_PARI[c] ?? 0);
  }
  return String.fromCharCode(65 + (sum % 26));
}

function calcolaCodiceFiscale(cognome, nome, dataNascita, sesso, codiceBelfiore) {
  if (!cognome || !nome || !dataNascita || !sesso || !codiceBelfiore) return '';
  const d = new Date(dataNascita + 'T00:00:00');
  if (isNaN(d)) return '';
  const anno  = String(d.getFullYear()).slice(-2);
  const mese  = _MESI_CF[d.getMonth()];
  const giorno = String(d.getDate() + (sesso === 'F' ? 40 : 0)).padStart(2, '0');
  const cf15 = _codificaCognome(cognome) + _codificaNome(nome)
             + anno + mese + giorno + codiceBelfiore.toUpperCase();
  return cf15 + _controlCF(cf15);
}

/* ── Comuni helper ──────────────────────────────────────────────────────────── */
let _provinceCache = null;
async function caricaProvince(selectEl) {
  try {
    if (!_provinceCache) {
      _provinceCache = await api('/api/comuni/province');
    }
    selectEl.innerHTML = '<option value="">— Seleziona provincia —</option>';
    _provinceCache.forEach(p => {
      const o = document.createElement('option');
      o.value = p.sigla; o.textContent = `${p.sigla} — ${p.nome}`;
      selectEl.appendChild(o);
    });
  } catch(e) { console.error('Errore caricamento province', e); }
}

async function caricaComuni(sigla, selectEl) {
  selectEl.innerHTML = '<option value="">Caricamento...</option>';
  try {
    const comuni = await api(`/api/comuni/${sigla}`);
    selectEl.innerHTML = '<option value="">— Seleziona comune —</option>';
    comuni.forEach(c => {
      const o = document.createElement('option');
      o.value = c.codice_istat;
      o.textContent = c.nome;
      o.dataset.nome = c.nome;
      o.dataset.cap = c.cap || '';
      selectEl.appendChild(o);
    });
  } catch(e) { selectEl.innerHTML = '<option value="">Errore caricamento</option>'; }
}

async function cercaComune(nome, resultCb) {
  if (nome.length < 2) return;
  try {
    const res = await api(`/api/comuni/cerca/${encodeURIComponent(nome)}`);
    resultCb(res);
  } catch(e) { resultCb([]); }
}

/* ── Tab helper ─────────────────────────────────────────────────────────────── */
function initTabs(tabsEl) {
  const btns   = tabsEl.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.tab-panel');
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab)?.classList.add('active');
    });
  });
}

/* ── Modal helper ────────────────────────────────────────────────────────────── */
function openModal(id)  { document.getElementById(id)?.classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id)?.classList.add('hidden'); }
function initModalClose() {
  document.querySelectorAll('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', () => closeModal(btn.dataset.closeModal));
  });
  document.querySelectorAll('.modal-overlay').forEach(ov => {
    ov.addEventListener('click', e => {
      if (e.target === ov) ov.classList.add('hidden');
    });
  });
}
