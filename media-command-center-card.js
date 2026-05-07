class MediaCommandCenterCard extends HTMLElement {
  setConfig(config) {
    this.config = Object.assign({
      player: 'media_player.android_tv_192_168_1_242',
      kodi: 'media_player.android_4',
      receiver: 'media_player.dolby_daddy',
      remote: 'remote.shield',
      active_source: 'sensor.active_media_source',
      active_title: 'sensor.active_media_title',
      active_series: 'sensor.active_media_series_title',
      stremio_current: 'sensor.stremio_canadian_made87_gmail_com_current_watching',
      stremio_last: 'sensor.stremio_canadian_made87_gmail_com_last_watched',
      stremio_title: 'sensor.stremio_android_tv_title',
      stremio_episode: 'sensor.stremio_android_tv_episode',
      tv_power: 'sensor.smart_tv_power',
      movie_mode: 'input_boolean.kodi_movie_mode',
      schedule_url: 'http://192.168.1.4:8765/api/schedule',
      compact_schedule_url: 'http://192.168.1.4:8765/schedule?compact=1',
      stremio_package: 'com.stremio.one',
      launch_kodi_script: 'script.launch_kodi',
      search_script: 'script.stremio_search_on_android_tv',
      open_script: 'script.stremio_search_and_open_first_result',
      search_title: 'input_text.stremio_search_title',
      search_type: 'input_select.stremio_search_type',
      search_season: 'input_number.stremio_search_season',
      search_episode: 'input_number.stremio_search_episode'
    }, config || {});
    this.schedule = [];
    this.error = '';
    this._scheduleLoaded = false;
    this.attachShadow({ mode: 'open' });
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._scheduleLoaded) this.loadSchedule();
    if (this.isEditing()) return;
    this.render();
  }

  st(entity, fallback='--') {
    const s = this._hass?.states?.[entity];
    if (!s || ['unknown', 'unavailable', ''].includes(String(s.state).toLowerCase())) return fallback;
    return s.state;
  }
  attr(entity, key, fallback='') { return this._hass?.states?.[entity]?.attributes?.[key] ?? fallback; }
  esc(v) { return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  isEditing() {
    const active = this.shadowRoot?.activeElement;
    return !!active && ['INPUT', 'SELECT', 'TEXTAREA'].includes(active.tagName);
  }
  image(entity) {
    return this.attr(entity, 'entity_picture') ||
      this.attr(entity, 'poster') ||
      this.attr(entity, 'media_image_url') ||
      this.attr(entity, 'media_image') ||
      this.attr(entity, 'thumbnail') ||
      this.attr(entity, 'fanart') ||
      this.attr(entity, 'poster_url') ||
      '';
  }
  nowArt(source) {
    if (String(source).toLowerCase() === 'stremio') {
      return this.image(this.config.stremio_current) || this.image(this.config.player) || this.image(this.config.stremio_last);
    }
    if (String(source).toLowerCase() === 'kodi') {
      return this.image(this.config.kodi) || this.image(this.config.player);
    }
    return this.image(this.config.player) || this.image(this.config.kodi) || this.image(this.config.stremio_current) || this.image(this.config.stremio_last);
  }

  async loadSchedule() {
    this._scheduleLoaded = true;
    try {
      const r = await fetch(this.config.schedule_url, { cache: 'no-store' });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      this.schedule = await r.json();
      this.error = '';
    } catch (e) {
      this.error = e.message;
    }
    if (this.isEditing()) return;
    this.render();
    clearTimeout(this._timer);
    this._timer = setTimeout(() => { this._scheduleLoaded = false; this.loadSchedule(); }, 10 * 60 * 1000);
  }

  call(domain, service, data={}, target={}) {
    if (!this._hass) return;
    this._hass.callService(domain, service, data, target);
  }
  script(entity) { this.call('script', 'turn_on', {}, { entity_id: entity }); }
  remote(command) { this.call('remote', 'send_command', { command }, { entity_id: this.config.remote }); }
  launchStremio() { this.call('media_player', 'select_source', { source: this.config.stremio_package }, { entity_id: this.config.player }); }
  setText(entity, value) { this.call('input_text', 'set_value', { value }, { entity_id: entity }); }
  setNumber(entity, value) { this.call('input_number', 'set_value', { value: Number(value || 0) }, { entity_id: entity }); }
  setSelect(entity, option) { this.call('input_select', 'select_option', { option }, { entity_id: entity }); }

  renderSchedule() {
    if (this.error) return `<div class="empty">Schedule unavailable<br><small>${this.esc(this.error)}</small></div>`;
    if (!this.schedule.length) return `<div class="empty">No shows today or tomorrow</div>`;
    return this.schedule.slice(0, 6).map(item => {
      const tag = item.tag || 'Episode';
      const cls = /finale/i.test(tag) ? 'finale' : (/premiere|new show/i.test(tag) ? 'premiere' : 'episode');
      const code = item.season && item.number ? `S${String(item.season).padStart(2,'0')}E${String(item.number).padStart(2,'0')}` : '';
      return `<article class="show ${cls}">
        ${item.poster ? `<img src="${this.esc(item.poster)}" alt="">` : `<div class="poster-fallback">TV</div>`}
        <div class="show-copy">
          <span>${this.esc(tag)}</span>
          <b>${this.esc(item.show)}</b>
          <p>${this.esc(code)}${item.episode ? ' - ' + this.esc(item.episode) : ''}</p>
          <em>${this.esc(item.available_label || '')}</em>
        </div>
      </article>`;
    }).join('');
  }

  render() {
    if (!this.shadowRoot) return;
    const c = this.config;
    const source = this.st(c.active_source, 'none');
    const title = this.st(c.active_title, this.st(c.stremio_title, this.st(c.stremio_current, 'Nothing playing')));
    const series = this.st(c.active_series, this.st(c.stremio_episode, 'Ready'));
    const appId = this.attr(c.player, 'app_id', 'unknown');
    const tvState = this.st(c.player, 'unknown');
    const kodiState = this.st(c.kodi, 'unknown');
    const receiverState = this.st(c.receiver, 'unknown');
    const power = this.st(c.tv_power, '--');
    const art = this.nowArt(source);
    const bg = art ? `url(${art})` : 'linear-gradient(135deg,#151f2f,#07111f)';

    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;font-family:'Hanken Grotesk',Inter,system-ui,sans-serif;color:#f8fbff;}
        ha-card{overflow:hidden;border:1px solid rgba(136,220,255,.22);border-radius:24px;background:#050914;box-shadow:0 24px 90px rgba(0,0,0,.45);}
        .shell{position:relative;height:calc(100dvh - 28px);min-height:0;box-sizing:border-box;padding:clamp(12px,1.8vw,22px);isolation:isolate;background:radial-gradient(circle at 72% 18%,rgba(255,76,45,.23),transparent 30%),radial-gradient(circle at 18% 85%,rgba(28,163,255,.20),transparent 32%),linear-gradient(135deg,#07111d 0%,#101829 48%,#05070d 100%);}
        .wash{position:absolute;inset:0;background-image:${bg};background-size:cover;background-position:center;opacity:.16;filter:blur(16px) saturate(1.3);transform:scale(1.05);z-index:-2}.shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(3,7,14,.92),rgba(3,7,14,.56),rgba(3,7,14,.86));z-index:-1}
        .grid{height:100%;display:grid;grid-template-columns:1.35fr .82fr;grid-template-rows:auto 1fr auto;gap:14px;}
        header{grid-column:1/3;display:flex;align-items:center;justify-content:space-between;gap:16px}.brand span{display:block;color:#7dd3fc;font-size:.72rem;font-weight:900;letter-spacing:.18em;text-transform:uppercase}.brand h1{margin:3px 0 0;font-size:clamp(1.8rem,4vw,3.6rem);line-height:.9;letter-spacing:0}.status{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end}.pill{border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.08);border-radius:999px;padding:8px 12px;font-size:.78rem;font-weight:850;color:#dbeafe}.pill.hot{background:rgba(249,115,22,.18);color:#fed7aa}
        .hero{position:relative;overflow:hidden;border:1px solid rgba(255,255,255,.14);border-radius:22px;background:linear-gradient(135deg,rgba(255,255,255,.13),rgba(255,255,255,.04));display:grid;grid-template-columns:minmax(190px,.34fr) 1fr;gap:16px;padding:16px;min-height:0}.poster{height:100%;min-height:0;border-radius:18px;background-image:${bg};background-size:cover;background-position:center;box-shadow:0 20px 44px rgba(0,0,0,.45);position:relative}.poster:after{content:'NOW PLAYING';position:absolute;left:12px;bottom:12px;padding:6px 9px;border-radius:999px;background:rgba(0,0,0,.62);font-size:.62rem;font-weight:950;letter-spacing:.12em}.now{display:flex;flex-direction:column;justify-content:space-between;min-width:0}.now h2{font-size:clamp(1.8rem,4.6vw,5rem);line-height:.9;margin:0;letter-spacing:0}.now p{font-size:clamp(.95rem,1.45vw,1.25rem);line-height:1.25;color:#cbd5e1;margin:10px 0}.app{color:#93c5fd;text-transform:uppercase;font-weight:900;letter-spacing:.14em;font-size:.72rem}.transport{display:grid;grid-template-columns:repeat(6,50px);gap:9px;margin-top:12px}.btn{height:44px;border:1px solid rgba(255,255,255,.14);border-radius:15px;background:rgba(255,255,255,.09);color:#fff;font-size:1rem;cursor:pointer}.btn.primary{background:#f97316}.launch{display:flex;gap:9px;flex-wrap:wrap;margin-top:14px}.launch button{height:42px;border:0;border-radius:14px;padding:0 14px;background:#1d4ed8;color:#fff;font-weight:900;cursor:pointer}.launch button:nth-child(2){background:#0ea5e9}.launch button:nth-child(3){background:#7c3aed}.launch button:nth-child(4){background:#334155}
        .side{display:grid;grid-template-rows:auto 1fr;gap:14px;min-height:0}.panel{border:1px solid rgba(255,255,255,.14);border-radius:22px;background:rgba(7,13,25,.72);backdrop-filter:blur(14px);padding:14px;min-height:0}.panel h3{margin:0 0 10px;color:#f8fafc;font-size:1rem;letter-spacing:.02em}.schedule{display:grid;grid-template-columns:1fr 1fr;gap:9px;overflow:hidden}.show{min-width:0;display:grid;grid-template-columns:52px 1fr;gap:8px;padding:7px;border-radius:16px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.10)}.show img,.poster-fallback{width:52px;aspect-ratio:2/3;object-fit:cover;border-radius:10px;background:#182033;display:grid;place-items:center;color:#64748b;font-weight:900}.show-copy{min-width:0}.show span{display:inline-block;padding:2px 6px;border-radius:999px;background:#1d4ed8;font-size:.54rem;font-weight:950;text-transform:uppercase;color:white}.show.finale span{background:#be123c}.show.premiere span{background:#7c3aed}.show b{display:block;margin-top:4px;font-size:.76rem;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.show p{margin:3px 0;color:#cbd5e1;font-size:.62rem;line-height:1.15;height:1.4em;overflow:hidden}.show em{font-style:normal;color:#fbbf24;font-size:.61rem;font-weight:850}.empty{padding:24px;text-align:center;color:#94a3b8;grid-column:1/3}.mini iframe{width:100%;height:100%;border:0;border-radius:16px;background:transparent}.mini{display:none}
        .remote{display:grid;grid-template-columns:repeat(3,52px);grid-auto-rows:48px;gap:9px;justify-content:center}.remote .blank{visibility:hidden}.search{display:grid;grid-template-columns:minmax(120px,1fr) .36fr .28fr .28fr auto;gap:9px}.search input,.search select{min-width:0;border:1px solid rgba(255,255,255,.14);border-radius:14px;background:rgba(255,255,255,.08);color:#fff;padding:0 10px}.search button{border:0;border-radius:14px;background:#f97316;color:#fff;font-weight:900;padding:0 13px}.metrics{grid-column:1/3;display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.metric{border:1px solid rgba(255,255,255,.14);border-radius:18px;background:rgba(255,255,255,.07);padding:12px}.metric span{display:block;color:#93c5fd;text-transform:uppercase;font-size:.68rem;font-weight:950;letter-spacing:.12em}.metric b{display:block;margin-top:5px;font-size:1.35rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        @media(max-width:1100px){.grid{grid-template-columns:1fr;grid-template-rows:auto 1fr auto auto}.hero,.side,.metrics,header{grid-column:1}.side{display:none}.metrics{grid-template-columns:repeat(2,1fr)}.poster{display:none}.hero{grid-template-columns:1fr}.now h2{font-size:clamp(1.7rem,7vw,3.8rem)}}
      </style>
      <ha-card><div class="shell"><div class="wash"></div><div class="shade"></div><div class="grid">
        <header><div class="brand"><span>Media Central</span><h1>Theatre Command</h1></div><div class="status"><div class="pill hot">${this.esc(source).toUpperCase()}</div><div class="pill">TV ${this.esc(tvState)}</div><div class="pill">Kodi ${this.esc(kodiState)}</div></div></header>
        <section class="hero"><div class="poster"></div><div class="now"><div><div class="app">${this.esc(appId)}</div><h2>${this.esc(title)}</h2><p>${this.esc(series)}</p></div><div><div class="transport"><button class="btn" data-cmd="MEDIA_REWIND">RW</button><button class="btn primary" data-service="play">PLAY</button><button class="btn" data-service="pause">PAUSE</button><button class="btn" data-service="stop">STOP</button><button class="btn" data-cmd="MEDIA_FAST_FORWARD">FF</button><button class="btn" data-cmd="BACK">BACK</button></div><div class="launch"><button data-action="stremio">Stremio</button><button data-action="kodi">Kodi</button><button data-action="movie">Movie Mode</button><button data-cmd="HOME">Home</button></div></div></div></section>
        <aside class="side"><section class="panel"><h3>Today + Tomorrow</h3><div class="schedule">${this.renderSchedule()}</div></section><section class="panel"><h3>SHIELD Control</h3><div class="remote"><div class="blank"></div><button class="btn" data-cmd="DPAD_UP">UP</button><div class="blank"></div><button class="btn" data-cmd="DPAD_LEFT">LEFT</button><button class="btn primary" data-cmd="DPAD_CENTER">OK</button><button class="btn" data-cmd="DPAD_RIGHT">RIGHT</button><button class="btn" data-cmd="BACK">BACK</button><button class="btn" data-cmd="DPAD_DOWN">DOWN</button><button class="btn" data-cmd="HOME">HOME</button></div></section></aside>
        <section class="panel"><h3>Stremio Search</h3><div class="search"><input class="q" placeholder="Title" value="${this.esc(this.st(c.search_title,''))}"><select class="type">${this.renderTypeOptions()}</select><input class="season" type="number" min="0" value="${this.esc(this.st(c.search_season,'0'))}"><input class="episode" type="number" min="0" value="${this.esc(this.st(c.search_episode,'0'))}"><button data-action="search">Search</button></div></section>
        <section class="metrics"><div class="metric"><span>Receiver</span><b>${this.esc(receiverState)}</b></div><div class="metric"><span>TV Power</span><b>${this.esc(power)} W</b></div><div class="metric"><span>Mode</span><b>${this.esc(this.st(c.movie_mode,'off'))}</b></div><div class="metric"><span>Schedule</span><b>${this.schedule.length} shows</b></div></section>
      </div></div></ha-card>`;
    this.bind();
  }

  bind() {
    this.shadowRoot.querySelectorAll('[data-cmd]').forEach(b => b.onclick = () => this.remote(b.dataset.cmd));
    this.shadowRoot.querySelectorAll('[data-service]').forEach(b => {
      b.onclick = () => {
        const map = { play:['media_player','media_play'], pause:['media_player','media_pause'], stop:['media_player','media_stop'] };
        const [d,s] = map[b.dataset.service]; this.call(d, s, {}, { entity_id: this.config.player });
      };
    });
    this.shadowRoot.querySelectorAll('[data-action]').forEach(b => b.onclick = () => {
      if (b.dataset.action === 'stremio') this.launchStremio();
      if (b.dataset.action === 'kodi') this.script(this.config.launch_kodi_script);
      if (b.dataset.action === 'movie') this.call('input_boolean','toggle',{}, { entity_id: this.config.movie_mode });
      if (b.dataset.action === 'search') this.submitSearch();
    });
    const q = this.shadowRoot.querySelector('.q'); if (q) q.oninput = e => { clearTimeout(this._inputTimer); this._inputTimer = setTimeout(() => this.setText(this.config.search_title, e.target.value), 350); };
    const t = this.shadowRoot.querySelector('.type'); if (t) t.onchange = e => this.setSelect(this.config.search_type, e.target.value);
    const s = this.shadowRoot.querySelector('.season'); if (s) s.onchange = e => this.setNumber(this.config.search_season, e.target.value);
    const ep = this.shadowRoot.querySelector('.episode'); if (ep) ep.onchange = e => this.setNumber(this.config.search_episode, e.target.value);
  }
  renderTypeOptions() {
    const selected = this.st(this.config.search_type, 'Any');
    const options = this.attr(this.config.search_type, 'options', ['Any', 'Movie', 'Show', 'Episode']);
    return options.map(o => `<option ${o === selected ? 'selected' : ''}>${this.esc(o)}</option>`).join('');
  }
  submitSearch() {
    const q = this.shadowRoot.querySelector('.q');
    const t = this.shadowRoot.querySelector('.type');
    const s = this.shadowRoot.querySelector('.season');
    const ep = this.shadowRoot.querySelector('.episode');
    if (q) this.setText(this.config.search_title, q.value);
    if (t) this.setSelect(this.config.search_type, t.value);
    if (s) this.setNumber(this.config.search_season, s.value);
    if (ep) this.setNumber(this.config.search_episode, ep.value);
    setTimeout(() => this.script(this.config.search_script), 250);
  }
  disconnectedCallback(){ clearTimeout(this._timer); }
  getCardSize(){ return 8; }
}
if (!customElements.get('media-command-center-card')) customElements.define('media-command-center-card', MediaCommandCenterCard);
window.customCards = window.customCards || [];
window.customCards.push({ type:'media-command-center-card', name:'Media Command Center', description:'Single-page cinematic media dashboard' });

