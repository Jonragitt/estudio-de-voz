// Modo vista previa: la web funciona sola en el navegador, sin servidor.
// Sustituye la API por datos en memoria y lee el texto con la voz del navegador.
(() => {
  const mem = {
    voces: [
      { id: 'base', name: 'Narrador base', kind: 'base', tags: ['neutra', 'español'], description: 'La voz por defecto del modelo.' },
      { id: 'ejemplo1', name: 'Narradora Heian', kind: 'clon', tags: ['ejemplo', 'cálida'], description: 'Voz de ejemplo para narrar lecciones de historia.' },
    ],
    historial: [
      { id: 'h1', text: 'En el año 794 la capital se trasladó a Heian-kyō, la actual Kioto.', voice_id: 'base', voice_name: 'Narrador base', created: Math.floor(Date.now() / 1000) - 3600 },
    ],
  };
  const ok = (data) => new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } });
  const err = (code, detail) => new Response(JSON.stringify({ detail }), { status: code, headers: { 'Content-Type': 'application/json' } });
  const id = () => Math.random().toString(36).slice(2, 12);

  window.ESTUDIO_DEMO = {
    speak(item) {
      const s = window.speechSynthesis;
      $('#audio').hidden = true; $('#pl-dl').hidden = true;
      let again = $('#pl-again');
      if (!again) {
        again = document.createElement('button'); again.id = 'pl-again'; again.className = 'btn';
        again.innerHTML = '<svg viewBox="0 0 24 24"><path d="M7 5l12 7-12 7z"/></svg>Escuchar otra vez';
        $('#player').append(again);
      }
      again.onclick = () => window.ESTUDIO_DEMO.speak(item);
      if (!s) { toast('Tu navegador no puede leer en voz alta'); return; }
      s.cancel();
      const u = new SpeechSynthesisUtterance(item.text);
      const lang = item.language || 'es';
      u.lang = lang;
      const es = s.getVoices().filter((v) => v.lang.startsWith(lang));
      if (es.length) u.voice = es[[...item.voice_id].reduce((a, c) => a + c.charCodeAt(0), 0) % es.length];
      u.rate = item.speed || 1;
      u.pitch = 0.7 + (item.exaggeration ?? 0.5) * 0.6;
      s.speak(u);
    },
  };

  const real = window.fetch.bind(window);
  window.fetch = async (url, opts = {}) => {
    if (typeof url !== 'string' || !url.startsWith('/api')) return real(url, opts);
    const path = url.slice(4), method = (opts.method || 'GET').toUpperCase();
    if (path === '/estado') return ok({ motor: 'vista previa', listo: true });
    if (path === '/idiomas') return ok({ es: 'Español', en: 'Inglés', fr: 'Francés', it: 'Italiano', pt: 'Portugués', de: 'Alemán', ja: 'Japonés' });
    if (path === '/voces' && method === 'GET') return ok(mem.voces);
    if (path === '/historial' && method === 'GET') return ok(mem.historial);
    if (path === '/tts') {
      const b = JSON.parse(opts.body);
      const v = mem.voces.find((x) => x.id === b.voice_id) || mem.voces[0];
      const item = { id: id(), text: b.text, voice_id: v.id, voice_name: v.name, created: Math.floor(Date.now() / 1000), speed: b.speed, exaggeration: b.exaggeration, language: b.language };
      mem.historial.unshift(item);
      return ok(item);
    }
    if (path === '/voces/importar') {
      const b = JSON.parse(opts.body);
      if (!b.permiso) return err(400, 'Marca la casilla confirmando que tienes derecho a usar esta voz.');
      const v = { id: id(), name: b.nombre, kind: 'importada', tags: ['importada'], description: 'Desde enlace (en la vista previa no se descarga de verdad).' };
      mem.voces.push(v);
      return ok(v);
    }
    if (path === '/voces/clonar') {
      if (opts.body.get('permiso') !== 'true') return err(400, 'Marca la casilla confirmando que tienes derecho a usar esta voz.');
      const nombre = (opts.body.get('nombre') || '').trim() || 'Voz sin nombre';
      const v = { id: id(), name: nombre, kind: 'clon', tags: ['clonada'], description: 'Clon rápido (en la vista previa no se clona de verdad).' };
      mem.voces.push(v);
      return ok(v);
    }
    let m;
    if ((m = path.match(/^\/voces\/(\w+)$/)) && method === 'DELETE') { mem.voces = mem.voces.filter((v) => v.id !== m[1]); return ok({ ok: true }); }
    if ((m = path.match(/^\/historial\/(\w+)$/)) && method === 'DELETE') { mem.historial = mem.historial.filter((h) => h.id !== m[1]); return ok({ ok: true }); }
    return err(404, 'No disponible en la vista previa');
  };
})();
