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
$('#tabbar').innerHTML = $$('.nav button').map((b) => `<button data-view="${b.dataset.view}">${b.dataset.short ? b.querySelector('svg').outerHTML + b.dataset.short : b.innerHTML}</button>`).join('');
const show = (v) => {
  $$('[data-view]').forEach((b) => b.classList.toggle('on', b.dataset.view === v));
  $$('.view').forEach((s) => s.classList.toggle('on', s.id === 'v-' + v));
  if (v === 'voces') loadVoices();
  if (v === 'historial') loadHistory();
  if (v === 'pronunciaciones') loadPron();
  if (v === 'lote') loadLote();
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
  sel.value = voices.some((v) => v.id === cur) ? cur : voices[0]?.id;
  $('#voice-grid').innerHTML = voices.map((v) => `
    <article class="vcard glass">
      <div class="av" style="--a:hsl(${hue(v.id)} 80% 62%);--b:hsl(${(hue(v.id) + 60) % 360} 80% 66%)"></div>
      <b>${esc(v.name)}</b><p>${esc(v.description || '')}</p>
      <div class="tags">${(v.tags || []).map((t) => `<span>${esc(t)}</span>`).join('')}</div>
      <div class="row">
        <button class="btn" data-use="${v.id}">Usar</button>
        ${v.kind === 'base' ? '' : `${voices.length > 1 ? `<button class="btn" data-solo="${v.id}">Dejar solo esta</button>` : ''}<button class="btn danger" data-del="${v.id}">Borrar</button>`}
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
  const use = e.target.closest('[data-use]'), del = e.target.closest('[data-del]'), solo = e.target.closest('[data-solo]');
  if (solo) {
    if (!solo.dataset.sure) { solo.dataset.sure = '1'; solo.textContent = '¿Borrar las demás?'; setTimeout(() => { delete solo.dataset.sure; solo.textContent = 'Dejar solo esta'; }, 3000); return; }
    await api('/voces/' + solo.dataset.solo + '/solo', { method: 'POST' }); store.set('voz', solo.dataset.solo); toast('Ahora solo queda esta voz'); loadVoices();
  }
  if (use) { $('#voice').value = use.dataset.use; store.set('voz', use.dataset.use); show('tts'); }
  if (del) {
    if (!del.dataset.sure) { del.dataset.sure = '1'; del.textContent = '¿Seguro?'; setTimeout(() => { delete del.dataset.sure; del.textContent = 'Borrar'; }, 3000); return; }
    await api('/voces/' + del.dataset.del, { method: 'DELETE' }); toast('Voz borrada'); loadVoices();
  }
};

/* ajustes */
const sliders = { speed: ['#o-speed', (v) => (+v).toFixed(2) + '×'], exa: ['#o-exa', (v) => (+v).toFixed(2)], cfg: ['#o-cfg', (v) => (+v).toFixed(2)], pausa: ['#o-pausa', (v) => (+v).toFixed(1) + '×'] };
const defaults = { speed: 1, exa: 0.5, cfg: 0.5, pausa: 1 };
const calma = { speed: 0.95, exa: 0.35, cfg: 0.3, pausa: 1.4 };
const saved = store.get('ajustes', defaults);
for (const [id, [out, fmt]] of Object.entries(sliders)) {
  const el = $('#' + id); el.value = saved[id] ?? defaults[id];
  const upd = () => { $(out).textContent = fmt(el.value); store.set('ajustes', { speed: +$('#speed').value, exa: +$('#exa').value, cfg: +$('#cfg').value, pausa: +$('#pausa').value }); };
  el.oninput = upd; upd();
}
const applySet = (set) => { for (const id in set) { $('#' + id).value = set[id]; $('#' + id).oninput(); } };
$('#reset').onclick = () => applySet(defaults);
$('#preset-calma').onclick = () => { applySet(calma); toast('Ajustes de narrador pausado'); };

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
      body: JSON.stringify({ text: text.value, voice_id: $('#voice').value, speed: +$('#speed').value, exaggeration: +$('#exa').value, cfg: +$('#cfg').value, pausa: +$('#pausa').value, language: $('#lang').value }),
    });
    play(item);
  } catch (e) { toast(e.message); }
  finally { btn.classList.remove('busy'); btn.lastChild.textContent = 'Generar'; }
};

/* clonar */
const drop = $('#drop'), file = $('input[type=file]', drop);
let cloneMode = 'archivos';
file.onchange = () => {
  const n = file.files.length;
  $('#drop-name').textContent = n ? [...file.files].map((f) => f.name).join(', ') : 'o pulsa para elegir (hasta 10 archivos: MP3, WAV, M4A, MP4)';
};
['dragover', 'dragenter'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove('over')));
drop.addEventListener('drop', (e) => { e.preventDefault(); if (e.dataTransfer.files.length) { file.files = e.dataTransfer.files; file.onchange(); } });
$$('.seg [data-mode]').forEach((b) => b.onclick = () => {
  cloneMode = b.dataset.mode;
  $$('.seg [data-mode]').forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-selected', x === b); });
  $$('#clone-form [data-panel]').forEach((p) => { p.hidden = p.dataset.panel !== cloneMode; });
});
$('#clone-form').onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target, btn = $('#clone-btn'), status = $('#clone-status');
  const nombre = f.nombre.value.trim(), permiso = f.permiso.checked;
  let req;
  if (cloneMode === 'archivos') {
    if (!file.files.length) { toast('Elige al menos una grabación'); return; }
    const fd = new FormData();
    fd.append('nombre', nombre); fd.append('permiso', permiso);
    [...file.files].slice(0, 10).forEach((x) => fd.append('audio', x));
    req = api('/voces/clonar', { method: 'POST', body: fd });
  } else {
    const enlaces = f.enlaces.value.split(/\s+/).filter((x) => x.startsWith('http')).slice(0, 5);
    if (!enlaces.length) { toast('Pega al menos un enlace'); return; }
    req = api('/voces/importar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nombre, enlaces, permiso }) });
  }
  btn.classList.add('busy'); btn.textContent = 'Creando voz…';
  status.textContent = cloneMode === 'enlaces' ? 'Descargando y limpiando el audio. Puede tardar un par de minutos.' : 'Limpiando las grabaciones…';
  try {
    const v = await req;
    toast(`Voz «${v.name}» creada`); f.reset(); file.onchange(); status.textContent = '';
    await loadVoices(); $('#voice').value = v.id; store.set('voz', v.id); show('voces');
  } catch (err) { status.textContent = ''; toast(err.message); }
  finally { btn.classList.remove('busy'); btn.textContent = 'Crear voz'; }
};

/* ver cómo lo leerá */
$('#preview-read').onclick = async () => {
  if (!text.value.trim()) { toast('Escribe algún texto primero'); return; }
  try {
    const r = await api('/normalizar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: text.value, language: $('#lang').value }) });
    $('#leido-text').textContent = r.texto; $('#leido').hidden = false;
  } catch (e) { toast(e.message); }
};
$('#leido-close').onclick = () => { $('#leido').hidden = true; };

/* pronunciaciones */
const pronRow = (p = { palabra: '', lectura: '' }) => {
  const row = document.createElement('div'); row.className = 'pron-row';
  row.innerHTML = `<input aria-label="Se escribe" maxlength="60" placeholder="Hokkaido"><input aria-label="Se lee" maxlength="120" placeholder="Jokaido"><button type="button" class="icon-btn danger" aria-label="Quitar"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button>`;
  const [a, b] = $$('input', row); a.value = p.palabra; b.value = p.lectura;
  $('button', row).onclick = () => row.remove();
  return row;
};
async function loadPron() {
  const list = await api('/pronunciaciones');
  $('#pron-list').replaceChildren(...list.map(pronRow));
}
$('#pron-add').onclick = () => { const r = pronRow(); $('#pron-list').append(r); $('input', r).focus(); };
$('#pron-save').onclick = async () => {
  const lista = $$('#pron-list .pron-row').map((r) => { const [a, b] = $$('input', r); return { palabra: a.value.trim(), lectura: b.value.trim() }; }).filter((p) => p.palabra && p.lectura);
  try { await api('/pronunciaciones', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(lista) }); toast('Pronunciaciones guardadas'); loadPron(); }
  catch (e) { toast(e.message); }
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
/* narrar lecciones */
let fuente = null, plantillas = [];
const ajustesActuales = () => ({ speed: +$('#speed').value, exaggeration: +$('#exa').value, cfg: +$('#cfg').value, pausa: +$('#pausa').value, language: $('#lang').value });
const mins = (s) => s >= 3600 ? `${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} min` : `${Math.max(1, Math.round(s / 60))} min`;
function pintaFuentes() {
  $('#lote-fuentes').innerHTML = plantillas.map((p) => `
    <button type="button" class="fuente ${fuente?.id === p.id ? 'on' : ''}" data-fuente="${esc(p.id)}">
      <b>${esc(p.nombre)}</b><span>${p.lecciones} lecciones · ≈ ${mins(p.palabras / 140 * 60)} de audio</span>
    </button>`).join('') || '<p class="soon">Aún no hay textos: sube un JSON de lecciones.</p>';
}
async function loadLote() {
  const a = ajustesActuales();
  $('#lote-ajustes').textContent = `Se usan tus ajustes de Texto a voz: velocidad ${a.speed.toFixed(2)}×, expresividad ${a.exaggeration.toFixed(2)}, ritmo ${a.cfg.toFixed(2)}, pausas ${a.pausa.toFixed(1)}×.`;
  if (!$('#voice').options.length) await loadVoices().catch(() => {});
  const sel = $('#lote-voice');
  sel.innerHTML = $('#voice').innerHTML; sel.value = $('#voice').value;
  try { plantillas = await api('/lotes/plantillas'); } catch { plantillas = []; }
  if (!fuente && plantillas[0]) fuente = { id: plantillas[0].id, nombre: plantillas[0].nombre };
  pintaFuentes();
  refrescaLotes();
}
$('#lote-fuentes').onclick = (e) => {
  const b = e.target.closest('[data-fuente]'); if (!b) return;
  const p = plantillas.find((x) => x.id === b.dataset.fuente); fuente = { id: p.id, nombre: p.nombre }; pintaFuentes();
};
$('#lote-file').onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  try {
    const datos = JSON.parse(await f.text());
    if (!Array.isArray(datos.lecciones) || !datos.lecciones.length) throw new Error();
    if (!datos.nombre) datos.nombre = f.name.replace(/\.json$/, '');
    const p = await api('/lotes/plantillas', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos) });
    plantillas = await api('/lotes/plantillas'); fuente = { id: p.id, nombre: p.nombre }; pintaFuentes();
    toast('Textos guardados: ya puedes narrarlos');
  } catch (err) { toast(err.message && err.message !== 'Algo ha fallado' ? err.message : 'Ese archivo no tiene lecciones (hace falta {"lecciones": [{"id", "titulo", "texto"}]})'); }
};
$('#lote-form').onsubmit = async (e) => {
  e.preventDefault();
  if (!fuente) return toast('Elige qué textos narrar');
  const btn = $('#lote-start'); btn.classList.add('busy');
  try {
    const datos = await api('/lotes/plantillas/' + encodeURIComponent(fuente.id));
    const lecciones = datos.lecciones.map((l) => ({ id: String(l.id), titulo: l.titulo || '', texto: l.texto }));
    await api('/lotes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nombre: fuente.nombre, voice_id: $('#lote-voice').value, ...ajustesActuales(), lecciones }) });
    toast('Narrando… puedes dejarlo trabajando'); refrescaLotes();
  } catch (err) { toast(err.message); } finally { btn.classList.remove('busy'); }
};
const abiertos = new Set(store.get('lotes-abiertos', []));
async function refrescaLotes() {
  clearTimeout(refrescaLotes.t);
  let ls = [];
  try { ls = await api('/lotes'); } catch { return; }
  $('#lotes').innerHTML = ls.map((l) => {
    const pct = Math.round(100 * l.hechas / Math.max(1, l.total));
    const dur = l.lecciones.reduce((a, x) => a + (x.segundos || 0), 0);
    const est = { 'en curso': 'Narrando', pausado: 'En pausa', terminado: 'Terminado' }[l.estado];
    return `<li class="lote glass" data-lote="${l.id}">
      <div class="lote-h"><b>${esc(l.nombre)}</b><span class="pill ${l.estado.replace(' ', '-')}">${est}</span></div>
      <div class="m">${esc(l.voice_name || '')} · ${l.hechas} de ${l.total} lecciones${dur ? ' · ' + mins(dur) + ' de audio' : ''}</div>
      <div class="bar"><i style="width:${pct}%"></i></div>
      ${l.error ? `<p class="err">Se paró en ${esc(l.error)}</p>` : ''}
      <div class="row-btns">
        ${l.estado === 'en curso' ? `<button class="btn" data-acc="pausar">Pausar</button>` : l.estado === 'pausado' ? `<button class="btn primary" data-acc="continuar">Continuar</button>` : ''}
        ${l.hechas ? `<a class="btn" href="/api/lotes/${l.id}/zip" download>Descargar todo (ZIP)</a>` : ''}
        <button class="btn" data-acc="ver">${abiertos.has(l.id) ? 'Ocultar lecciones' : 'Ver lecciones'}</button>
        <button class="btn danger" data-acc="borrar">Borrar</button>
      </div>
      ${abiertos.has(l.id) ? `<ol class="lecs">${l.lecciones.map((x) => `<li class="${x.lista ? 'ok' : ''}"><span>${esc(x.titulo || x.id)}</span>${x.lista ? `<audio controls preload="none" src="/api/lotes/${l.id}/audio/${encodeURIComponent(x.id)}"></audio>` : '<small>pendiente</small>'}</li>`).join('')}</ol>` : ''}
    </li>`;
  }).join('');
  if (ls.some((l) => l.estado === 'en curso') && $('#v-lote').classList.contains('on')) refrescaLotes.t = setTimeout(refrescaLotes, 8000);
}
$('#lotes').onclick = async (e) => {
  const b = e.target.closest('[data-acc]'); if (!b) return;
  const id = b.closest('[data-lote]').dataset.lote, acc = b.dataset.acc;
  if (acc === 'ver') { abiertos.has(id) ? abiertos.delete(id) : abiertos.add(id); store.set('lotes-abiertos', [...abiertos]); return refrescaLotes(); }
  if (acc === 'borrar') {
    if (!b.dataset.sure) { b.dataset.sure = '1'; b.textContent = '¿Borrar los audios?'; setTimeout(() => { delete b.dataset.sure; b.textContent = 'Borrar'; }, 3000); return; }
    await api('/lotes/' + id, { method: 'DELETE' }); return refrescaLotes();
  }
  try { await api(`/lotes/${id}/${acc}`, { method: 'POST' }); } catch (err) { toast(err.message); }
  refrescaLotes();
};

show(location.hash.slice(1) || 'tts');
