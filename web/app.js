// Estudio de voz · lógica de la web
const DEMO = !!window.ESTUDIO_DEMO;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const api = async (path, opts = {}) => {
  const r = await fetch('/api' + path, opts);
  if (!r.ok) {
    let msg = 'Algo ha fallado';
    try { msg = (await r.json()).detail || msg; } catch {}
    throw new Error(typeof msg === 'string' ? msg : 'Datos no válidos');
  }
  return r.json();
};
const toast = (t) => { const el = $('#toast'); el.textContent = t; el.classList.add('show'); clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove('show'), 2600); };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const store = { get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} } };

/* tema */
const applyTheme = (t) => { if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme; };
applyTheme(store.get('tema', null));
$('#theme').onclick = () => {
  const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  const t = dark ? 'light' : 'dark'; applyTheme(t); store.set('tema', t);
};

/* navegación */
$('#tabbar').innerHTML = $$('.nav button').map((b) => `<button data-view="${b.dataset.view}">${b.innerHTML}</button>`).join('');
const show = (v) => {
  $$('[data-view]').forEach((b) => b.classList.toggle('on', b.dataset.view === v));
  $$('.view').forEach((s) => s.classList.toggle('on', s.id === 'v-' + v));
  if (v === 'voces') loadVoices();
  if (v === 'historial') loadHistory();
  history.replaceState(null, '', '#' + v);
};
document.addEventListener('click', (e) => { const b = e.target.closest('[data-view]'); if (b) show(b.dataset.view); });

/* estado del motor */
api('/estado').then((s) => {
  const el = $('#engine');
  el.textContent = s.motor === 'demo' ? 'Motor demo (sin GPU)' : 'Motor: ' + s.motor;
  if (s.motor === 'demo') {
    const n = document.createElement('div');
    n.className = 'demo-note'; n.setAttribute('role', 'note');
    n.textContent = 'Modo demo: aquí suenan pitidos de prueba, no una voz. Para la voz de verdad abre el estudio desde Google Colab.';
    $('.main').prepend(n);
  }
  el.className = 'engine ' + (s.motor === 'demo' ? 'demo' : 'ok');
}).catch(() => { $('#engine').textContent = 'Servidor apagado'; });

/* voces */
let voices = [];
const hue = (id) => [...id].reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
async function loadVoices() {
  voices = await api('/voces');
  const sel = $('#voice'), cur = sel.value || store.get('voz', 'base');
  sel.innerHTML = voices.map((v) => `<option value="${v.id}">${esc(v.name)}</option>`).join('');
  sel.value = voices.some((v) => v.id === cur) ? cur : 'base';
  $('#voice-grid').innerHTML = voices.map((v) => `
    <article class="vcard glass">
      <div class="av" style="--a:hsl(${hue(v.id)} 80% 62%);--b:hsl(${(hue(v.id) + 60) % 360} 80% 66%)"></div>
      <b>${esc(v.name)}</b><p>${esc(v.description || '')}</p>
      <div class="tags">${(v.tags || []).map((t) => `<span>${esc(t)}</span>`).join('')}</div>
      <div class="row">
        <button class="btn" data-use="${v.id}">Usar</button>
        ${v.kind === 'base' ? '' : `<button class="btn danger" data-del="${v.id}">Borrar</button>`}
      </div>
    </article>`).join('');
}
$('#voice').onchange = (e) => store.set('voz', e.target.value);
api('/idiomas').then((l) => {
  const sel = $('#lang');
  sel.innerHTML = Object.entries(l).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('');
  sel.value = store.get('idioma', 'es') in l ? store.get('idioma', 'es') : 'es';
}).catch(() => {});
$('#lang').onchange = (e) => store.set('idioma', e.target.value);
$('#voice-grid').onclick = async (e) => {
  const use = e.target.closest('[data-use]'), del = e.target.closest('[data-del]');
  if (use) { $('#voice').value = use.dataset.use; store.set('voz', use.dataset.use); show('tts'); }
  if (del) {
    if (!del.dataset.sure) { del.dataset.sure = '1'; del.textContent = '¿Seguro?'; setTimeout(() => { delete del.dataset.sure; del.textContent = 'Borrar'; }, 3000); return; }
    await api('/voces/' + del.dataset.del, { method: 'DELETE' }); toast('Voz borrada'); loadVoices();
  }
};

/* ajustes */
const sliders = { speed: ['#o-speed', (v) => (+v).toFixed(1) + '×'], exa: ['#o-exa', (v) => (+v).toFixed(2)], cfg: ['#o-cfg', (v) => (+v).toFixed(2)] };
const defaults = { speed: 1, exa: 0.5, cfg: 0.5 };
const saved = store.get('ajustes', defaults);
for (const [id, [out, fmt]] of Object.entries(sliders)) {
  const el = $('#' + id); el.value = saved[id] ?? defaults[id];
  const upd = () => { $(out).textContent = fmt(el.value); store.set('ajustes', { speed: +$('#speed').value, exa: +$('#exa').value, cfg: +$('#cfg').value }); };
  el.oninput = upd; upd();
}
$('#reset').onclick = () => { for (const id in defaults) { $('#' + id).value = defaults[id]; $('#' + id).oninput(); } };

/* texto a voz */
const text = $('#text');
text.value = store.get('borrador', '');
const count = () => { $('#count').textContent = `${text.value.length} / 5000`; store.set('borrador', text.value); };
text.oninput = count; count();

function play(item) {
  $('#player').hidden = false;
  $('#pl-voice').textContent = item.voice_name;
  $('#pl-text').textContent = item.text;
  if (DEMO) { window.ESTUDIO_DEMO.speak(item); return; }
  $('#audio').src = '/api/audio/' + item.id;
  $('#pl-dl').href = '/api/audio/' + item.id;
  $('#audio').play().catch(() => {});
}
$('#gen').onclick = async () => {
  if (!text.value.trim()) { toast('Escribe algún texto primero'); text.focus(); return; }
  const btn = $('#gen'); btn.classList.add('busy'); btn.lastChild.textContent = 'Generando…';
  try {
    const item = await api('/tts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text.value, voice_id: $('#voice').value, speed: +$('#speed').value, exaggeration: +$('#exa').value, cfg: +$('#cfg').value, language: $('#lang').value }),
    });
    play(item);
  } catch (e) { toast(e.message); }
  finally { btn.classList.remove('busy'); btn.lastChild.textContent = 'Generar'; }
};

/* clonar */
const drop = $('#drop'), file = $('input[type=file]', drop);
file.onchange = () => { $('#drop-name').textContent = file.files[0]?.name || 'o pulsa para elegir un archivo'; };
['dragover', 'dragenter'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove('over')));
drop.addEventListener('drop', (e) => { e.preventDefault(); if (e.dataTransfer.files.length) { file.files = e.dataTransfer.files; file.onchange(); } });
$('#clone-form').onsubmit = async (e) => {
  e.preventDefault();
  const btn = $('button', e.target); btn.classList.add('busy');
  try {
    const v = await api('/voces/clonar', { method: 'POST', body: new FormData(e.target) });
    toast(`Voz «${v.name}» creada`); e.target.reset(); file.onchange();
    await loadVoices(); $('#voice').value = v.id; store.set('voz', v.id); show('voces');
  } catch (err) { toast(err.message); }
  finally { btn.classList.remove('busy'); }
};

/* historial */
async function loadHistory() {
  const h = await api('/historial');
  $('#hist').innerHTML = h.length ? h.map((i) => `
    <li class="glass">
      <span class="t">${esc(i.text)}</span>
      <span class="m">${esc(i.voice_name)} · ${new Date(i.created * 1000).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' })}</span>
      <span class="acts">
        <button data-play="${i.id}" aria-label="Escuchar"><svg viewBox="0 0 24 24"><path d="M7 5l12 7-12 7z"/></svg></button>
        <a href="/api/audio/${i.id}" download aria-label="Descargar"><svg viewBox="0 0 24 24"><path d="M12 4v11m-5-5 5 5 5-5M5 20h14"/></svg></a>
        <button data-rm="${i.id}" aria-label="Borrar" class="danger"><svg viewBox="0 0 24 24"><path d="M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13"/></svg></button>
      </span>
    </li>`).join('') : '<li class="empty">Aún no has generado ningún audio.</li>';
  $('#hist').onclick = async (e) => {
    const p = e.target.closest('[data-play]'), r = e.target.closest('[data-rm]');
    if (p) { play(h.find((i) => i.id === p.dataset.play)); show('tts'); }
    if (r) { await api('/historial/' + r.dataset.rm, { method: 'DELETE' }); loadHistory(); }
  };
}

loadVoices().catch(() => {});
show(location.hash.slice(1) || 'tts');
