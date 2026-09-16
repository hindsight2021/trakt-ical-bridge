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
      nuvio_title: 'input_text.nuvio_media_title',
      nuvio_type: 'input_select.nuvio_content_type',
      nuvio_art: '',
      nuvio_package: 'com.nuvio.tv.plus',
      stremio_current: 'sensor.stremio_canadian_made87_gmail_com_current_watching',
      stremio_last: 'sensor.stremio_canadian_made87_gmail_com_last_watched',
      stremio_title: 'sensor.stremio_android_tv_title',
      stremio_episode: 'sensor.stremio_android_tv_episode',
      tv_power: 'sensor.smart_tv_power',
      movie_mode: 'input_boolean.kodi_movie_mode',
      schedule_url: 'http://192.168.1.4:8765/api/schedule',
      nuvio_api_url: 'http://192.168.1.4:8765/api/nuvio',
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
    this._nuvioSearch = { query: '', results: [], selected: null, details: null, season: null, episode: null, loading: false, error: '' };
    this._themeMode = localStorage.getItem('media-command-theme') || 'auto';
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
  attrAny(entity, keys, fallback='') {
    for (const key of keys) {
      const value = this.attr(entity, key, '');
      if (value !== undefined && value !== null && String(value).trim() !== '') return value;
    }
    return fallback;
  }
  imdbLink(entity) {
    const id = this.attrAny(entity, ['imdb_id', 'imdb', 'media_imdb_id'], '');
    return /^tt\d+/i.test(String(id)) ? `https://www.imdb.com/title/${id}/` : '';
  }
  resolvedTheme() {
    if (this._themeMode === 'day' || this._themeMode === 'night') return this._themeMode;
    return this._hass?.states?.['sun.sun']?.state === 'below_horizon' ? 'night' : 'day';
  }
  cycleTheme() {
    const modes = ['auto', 'day', 'night'];
    this._themeMode = modes[(modes.indexOf(this._themeMode) + 1) % modes.length];
    localStorage.setItem('media-command-theme', this._themeMode);
    this.render();
  }
  nowData(source) {
    const sourceName = String(source).toLowerCase();
    const isNuvio = sourceName === 'nuvio';
    const stremioCurrent = this.st(this.config.stremio_current, '');
    const preferStremio = sourceName === 'stremio' || stremioCurrent;
    const entity = preferStremio ? this.config.stremio_current : (sourceName === 'kodi' ? this.config.kodi : this.config.player);
    const title = isNuvio
      ? this.st(this.config.nuvio_title, this.st(this.config.active_title, 'Nuvio+'))
      : this.st(this.config.active_title, this.st(this.config.stremio_title, this.st(entity, 'Nothing playing')));
    const season = this.attr(entity, 'season', '');
    const episode = this.attr(entity, 'episode', '');
    const epTitle = this.attrAny(entity, ['episode_title', 'media_episode_title'], '');
    const nuvioType = this.st(this.config.nuvio_type, 'playing').replaceAll('_', ' ');
    const series = isNuvio
      ? nuvioType.replace(/\b\w/g, c => c.toUpperCase())
      : this.st(this.config.active_series, this.st(this.config.stremio_episode, season && episode ? `S${String(season).padStart(2,'0')}E${String(episode).padStart(2,'0')}${epTitle ? ' - ' + epTitle : ''}` : 'Ready'));
    const rating = this.attrAny(entity, ['imdb_rating', 'rating', 'media_rating', 'score'], '');
    const description = this.attrAny(entity, ['description', 'summary', 'overview', 'plot', 'media_summary'], '');
    return { entity, title, series, rating, description, imdb: this.imdbLink(entity) };
  }
  nowArt(source) {
    if (String(source).toLowerCase() === 'nuvio') {
      const artState = this.config.nuvio_art ? this.st(this.config.nuvio_art, '') : '';
      return (/^https?:\/\//i.test(artState) ? artState : '') || this.image(this.config.nuvio_art) || this.image(this.config.player);
    }
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
      try {
        const start = new Date();
        const end = new Date(start.getTime() + 14 * 24 * 60 * 60 * 1000);
        let result;
        try {
          result = await this._hass.callWS({
            type: 'calendar/get_events',
            entity_ids: [this.config.calendar],
            start_time: start.toISOString(),
            end_time: end.toISOString()
          });
        } catch (_unsupportedCommand) {
          result = await this._hass.callService(
            'calendar',
            'get_events',
            { start_date_time: start.toISOString(), end_date_time: end.toISOString() },
            { entity_id: this.config.calendar },
            true,
            true
          );
        }
        const bucket = result?.[this.config.calendar] || result?.response?.[this.config.calendar] || result;
        const events = Array.isArray(bucket) ? bucket : (bucket?.events || []);
        this.schedule = events.map(event => ({
          tag: 'Calendar',
          show: event.summary || event.message || event.title || 'Scheduled show',
          episode: '',
          description: event.description || event.location || '',
          available_label: event.start?.dateTime
            ? new Date(event.start.dateTime).toLocaleString([], { weekday:'short', hour:'numeric', minute:'2-digit' })
            : (event.start?.date || '')
        }));
        this.error = '';
      } catch (calendarError) {
        this.schedule = [];
        this.error = `Schedule service ${e.message}; calendar fallback ${calendarError.message}`;
      }
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

  nuvioType(value) { return String(value || '').toLowerCase() === 'movie' ? 'movie' : 'series'; }
  async nuvioFetch(path, options={}) {
    const response = await fetch(`${this.config.nuvio_api_url}${path}`, { cache: 'no-store', ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Nuvio service returned ${response.status}`);
    return data;
  }
  async searchNuvio() {
    const q = this.shadowRoot.querySelector('.q')?.value?.trim() || '';
    const type = this.nuvioType(this.shadowRoot.querySelector('.type')?.value);
    if (!q) return;
    this._nuvioSearch = { query:q, results:[], selected:null, details:null, season:null, episode:null, loading:true, error:'' };
    this.render();
    try {
      const results = await this.nuvioFetch(`/search?q=${encodeURIComponent(q)}&type=${encodeURIComponent(type)}`);
      this._nuvioSearch.results = results;
      this._nuvioSearch.loading = false;
      if (results.length) await this.selectNuvioResult(results[0].id, results[0].type, false);
      else this._nuvioSearch.error = 'No Nuvio+ titles found.';
    } catch (error) {
      this._nuvioSearch.loading = false;
      this._nuvioSearch.error = error.message;
    }
    this.render();
  }
  async selectNuvioResult(id, type, rerender=true) {
    const selected = this._nuvioSearch.results.find(item => item.id === id) || { id, type };
    this._nuvioSearch.selected = selected;
    this._nuvioSearch.loading = true;
    if (rerender) this.render();
    try {
      const details = await this.nuvioFetch(`/details/${encodeURIComponent(type)}/${encodeURIComponent(id)}`);
      this._nuvioSearch.details = details;
      this._nuvioSearch.season = details.seasons?.[0] ?? null;
      this._nuvioSearch.episode = details.episodes?.find(item => item.season === this._nuvioSearch.season)?.episode ?? null;
      this._nuvioSearch.error = '';
    } catch (error) {
      this._nuvioSearch.error = error.message;
    }
    this._nuvioSearch.loading = false;
    if (rerender) this.render();
  }
  nuvioEpisodes() {
    return (this._nuvioSearch.details?.episodes || []).filter(item => item.season === Number(this._nuvioSearch.season));
  }
  renderNuvioSearch() {
    const n = this._nuvioSearch;
    const results = n.results.map(item => `<option value="${this.esc(item.id)}" data-type="${this.esc(item.type)}" ${item.id === n.selected?.id ? 'selected' : ''}>${this.esc(item.title)}${item.year ? ` (${this.esc(item.year)})` : ''}</option>`).join('');
    const seasons = (n.details?.seasons || []).map(season => `<option value="${season}" ${Number(season) === Number(n.season) ? 'selected' : ''}>Season ${season}</option>`).join('');
    const episodes = this.nuvioEpisodes().map(item => `<option value="${item.episode}" ${Number(item.episode) === Number(n.episode) ? 'selected' : ''}>E${String(item.episode).padStart(2,'0')}${item.title ? ` · ${this.esc(item.title)}` : ''}</option>`).join('');
    const movie = n.selected?.type === 'movie';
    return `<div class="search nuvio-search">
      <input class="q" placeholder="Search Nuvio+" value="${this.esc(n.query)}">
      <select class="type"><option value="series" ${this.nuvioType(n.selected?.type) === 'series' ? 'selected' : ''}>Show</option><option value="movie" ${n.selected?.type === 'movie' ? 'selected' : ''}>Movie</option></select>
      <button data-action="search">${n.loading ? 'Searching…' : 'Search'}</button>
      <select class="nuvio-result" ${results ? '' : 'disabled'}><option value="">${results ? 'Select title' : 'Search results'}</option>${results}</select>
      <select class="nuvio-season" ${movie || !seasons ? 'disabled' : ''}><option value="">Season</option>${seasons}</select>
      <select class="nuvio-episode" ${movie || !episodes ? 'disabled' : ''}><option value="">Episode</option>${episodes}</select>
      <button class="nuvio-play" data-action="nuvio-play" ${!n.selected || (!movie && (!n.season || !n.episode)) ? 'disabled' : ''}>▶ Play now</button>
    </div>${n.error ? `<div class="search-error">${this.esc(n.error)}</div>` : ''}`;
  }
  playNuvioSelection() {
    const n = this._nuvioSearch;
    const d = n.details;
    if (!n.selected || !d) return;
    const episode = this.nuvioEpisodes().find(item => item.episode === Number(n.episode));
    const videoId = n.selected.type === 'movie' ? d.id : `${d.id}:${n.season}:${n.episode}`;
    const quoted = value => `"${String(value || '').replaceAll('\\', '\\\\').replaceAll('"', '\\"')}"`;
    const parts = [
      'am start -W -a android.intent.action.MAIN',
      `-n ${quoted(`${this.config.nuvio_package}/com.nuvio.tv.MainActivity`)}`,
      `--es contentId ${quoted(d.id)}`, `--es contentType ${quoted(n.selected.type)}`,
      `--es launchMode ${quoted('stream')}`, `--es videoId ${quoted(videoId)}`,
      `--es name ${quoted(d.title)}`, '--ez android.intent.extra.START_PLAYBACK true'
    ];
    if (d.poster) parts.push(`--es poster ${quoted(d.poster)}`);
    if (d.background) parts.push(`--es backdrop ${quoted(d.background)}`);
    if (n.selected.type !== 'movie') {
      parts.push(`--ei season ${Number(n.season)}`, `--ei episode ${Number(n.episode)}`);
      if (episode?.title) parts.push(`--es episodeTitle ${quoted(episode.title)}`);
    }
    this.call('androidtv', 'adb_command', { entity_id:this.config.player, command:parts.join(' ') });
  }

  renderSchedule() {
    if (this.error) return `<div class="empty">Schedule unavailable<br><small>${this.esc(this.error)}</small></div>`;
    if (!this.schedule.length) return `<div class="empty">No upcoming shows in the next 14 days</div>`;
    return this.schedule.slice(0, 4).map(item => {
      const tag = item.tag || 'Episode';
      const cls = /finale/i.test(tag) ? 'finale' : (/premiere|new show/i.test(tag) ? 'premiere' : 'episode');
      const code = item.season && item.number ? `S${String(item.season).padStart(2,'0')}E${String(item.number).padStart(2,'0')}` : '';
      return `<article class="show ${cls}">
        ${item.poster ? `<img src="${this.esc(item.poster)}" alt="">` : `<div class="poster-fallback">TV</div>`}
        <div class="show-copy">
          <span>${this.esc(tag)}</span>
          <b>${this.esc(item.show)}</b>
          <p>${this.esc(code)}${item.episode ? ' - ' + this.esc(item.episode) : ''}</p>
          <p class="desc">${this.esc(item.description || '')}</p>
          <em>${this.esc(item.available_label || '')}</em>
          ${item.rating ? `<i>IMDb ${this.esc(item.rating)}</i>` : ''}
        </div>
      </article>`;
    }).join('');
  }

  render() {
    if (!this.shadowRoot) return;
    const c = this.config;
    const configuredSource = this.st(c.active_source, 'none');
    const appId = this.attr(c.player, 'app_id', 'unknown');
    const source = String(appId).toLowerCase() === String(c.nuvio_package).toLowerCase()
      ? 'nuvio'
      : configuredSource;
    const now = this.nowData(source);
    const title = now.title;
    const series = now.series;
    const tvState = this.st(c.player, 'unknown');
    const kodiState = this.st(c.kodi, 'unknown');
    const receiverState = this.st(c.receiver, 'unknown');
    const power = this.st(c.tv_power, '--');
    const art = this.nowArt(source);
    const bg = art ? `url(${art})` : 'linear-gradient(135deg,#151f2f,#07111f)';
    const resolvedTheme = this.resolvedTheme();
    const themeLabel = this._themeMode === 'auto' ? `AUTO ${resolvedTheme === 'night' ? '☾' : '☀'}` : this._themeMode.toUpperCase();

    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;font-family:Inter,'Hanken Grotesk',system-ui,sans-serif;color:#26332f;}
        ha-card{overflow:hidden;border:1px solid rgba(72,86,78,.18);border-radius:26px;background:#ecece6;box-shadow:0 22px 70px rgba(47,54,49,.18);}
        .shell{position:relative;min-height:calc(100dvh - 28px);box-sizing:border-box;padding:clamp(12px,1.8vw,22px);isolation:isolate;background:radial-gradient(circle at 72% 10%,rgba(192,151,79,.18),transparent 31%),radial-gradient(circle at 12% 88%,rgba(29,157,133,.13),transparent 34%),linear-gradient(135deg,#f1f1ec 0%,#e4e5de 52%,#eeece5 100%);}
        .wash{position:absolute;inset:0;background-image:${bg};background-size:cover;background-position:center;opacity:.08;filter:blur(22px) saturate(.75);transform:scale(1.05);z-index:-2}.shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(247,247,241,.78),rgba(244,244,238,.58),rgba(237,237,231,.72));z-index:-1}
        .grid{height:100%;display:grid;grid-template-columns:minmax(0,1.45fr) minmax(420px,.86fr);grid-template-rows:64px minmax(0,1fr) 148px 96px;grid-template-areas:"header header" "hero side" "search side" "metrics side";gap:14px;}
        header{grid-area:header;display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:0}.brand span{display:block;color:#168d79;font-size:.67rem;font-weight:800;letter-spacing:.20em;text-transform:uppercase}.brand h1{margin:3px 0 0;color:#26332f;font-family:Georgia,serif;font-size:clamp(1.75rem,2.8vw,2.8rem);font-weight:500;line-height:.92;letter-spacing:-.025em}.status{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.pill{border:1px solid rgba(61,74,67,.18);background:rgba(255,255,250,.62);border-radius:999px;padding:8px 12px;font-size:.72rem;font-weight:750;color:#4b5852;box-shadow:inset 0 1px rgba(255,255,255,.75)}.pill.hot{background:#bf8d37;border-color:#bf8d37;color:#fff}
        .theme-toggle{cursor:pointer;font:inherit}.theme-toggle:hover{transform:translateY(-1px)}
        .hero{grid-area:hero;position:relative;overflow:hidden;border:1px solid rgba(61,74,67,.14);border-radius:22px;background:rgba(255,255,250,.68);display:grid;grid-template-columns:minmax(190px,.32fr) minmax(0,1fr);gap:18px;padding:16px;min-height:0;box-shadow:0 12px 34px rgba(62,70,65,.10),inset 0 1px rgba(255,255,255,.88)}.poster{height:100%;min-height:0;border-radius:18px;background-image:${bg};background-size:cover;background-position:center;box-shadow:0 16px 34px rgba(48,55,51,.20);position:relative}.poster:after{content:'NOW PLAYING';position:absolute;left:12px;bottom:12px;padding:6px 9px;border-radius:999px;background:rgba(34,44,39,.76);color:#fff;font-size:.60rem;font-weight:850;letter-spacing:.13em}.now{display:flex;flex-direction:column;justify-content:space-between;min-width:0}.now h2{color:#26332f;font-family:Georgia,serif;font-size:clamp(2.1rem,4.2vw,4.8rem);font-weight:500;line-height:.94;margin:0;letter-spacing:-.025em}.now p{font-size:clamp(1rem,1.45vw,1.25rem);line-height:1.25;color:#69756f;margin:10px 0}.app{color:#168d79;text-transform:uppercase;font-weight:800;letter-spacing:.16em;font-size:.68rem}.transport{display:grid;grid-template-columns:repeat(6,56px);gap:9px;margin-top:12px}.btn{height:44px;border:1px solid rgba(61,74,67,.16);border-radius:15px;background:rgba(255,255,250,.76);color:#34433c;font-size:.72rem;font-weight:850;line-height:1;display:flex;align-items:center;justify-content:center;text-align:center;white-space:nowrap;overflow:hidden;cursor:pointer;box-shadow:0 4px 12px rgba(47,54,49,.08)}.btn.primary{background:#bf8d37;border-color:#bf8d37;color:#fff}.launch{display:flex;gap:9px;flex-wrap:wrap;margin-top:14px}.launch button{height:42px;border:0;border-radius:14px;padding:0 14px;background:#168d79;color:#fff;font-weight:850;cursor:pointer}.launch button:nth-child(2){background:#54706a}.launch button:nth-child(3){background:#8b6d9c}.launch button:nth-child(4){background:#737b76}
        .meta-row{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 4px}.meta-chip{border:1px solid rgba(61,74,67,.15);background:rgba(255,255,250,.72);border-radius:999px;padding:5px 8px;color:#52605a;font-size:.70rem;font-weight:800}.synopsis{max-width:720px;color:#66726c;font-size:.88rem;line-height:1.32;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
        .side{grid-area:side;display:grid;grid-template-rows:minmax(0,1fr) 202px;gap:14px;min-height:0}.panel{border:1px solid rgba(61,74,67,.14);border-radius:22px;background:rgba(255,255,250,.68);backdrop-filter:blur(14px);padding:14px;min-height:0;box-shadow:0 10px 28px rgba(62,70,65,.09),inset 0 1px rgba(255,255,255,.88)}.panel h3{margin:0 0 10px;color:#34433c;font-family:Georgia,serif;font-size:1.05rem;font-weight:500;letter-spacing:0}.schedule{height:calc(100% - 30px);display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:10px;overflow:hidden}.show{min-width:0;min-height:0;display:grid;grid-template-columns:58px minmax(0,1fr);gap:9px;padding:7px;border-radius:16px;background:rgba(244,244,238,.86);border:1px solid rgba(61,74,67,.12)}.show img,.poster-fallback{width:58px;height:100%;max-height:104px;object-fit:cover;border-radius:10px;background:#d8ddd6;display:grid;place-items:center;color:#537069;font-weight:850}.show-copy{min-width:0}.show span{display:inline-block;padding:2px 6px;border-radius:999px;background:#168d79;color:#fff;font-size:.52rem;font-weight:850;text-transform:uppercase}.show.finale span{background:#ad5b5b}.show.premiere span{background:#8b6d9c}.show b{display:block;margin-top:4px;color:#34433c;font-size:.76rem;line-height:1.08;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.show p{margin:2px 0;color:#6b7771;font-size:.60rem;line-height:1.12;height:1.28em;overflow:hidden}.show .desc{color:#78837d}.show em{font-style:normal;color:#a0742d;font-size:.60rem;font-weight:850}.show i{display:block;color:#4b5b54;font-style:normal;font-size:.58rem;font-weight:800}.empty{padding:24px;text-align:center;color:#748079;grid-column:1/3}.mini iframe{width:100%;height:100%;border:0;border-radius:16px;background:transparent}.mini{display:none}
        .remote{display:grid;grid-template-columns:repeat(3,64px);grid-auto-rows:42px;gap:8px;justify-content:center;align-content:center}.remote .blank{visibility:hidden}.remote .btn{width:64px;height:42px;padding:0 2px;border-radius:13px;font-size:.58rem;letter-spacing:0}.search-panel{grid-area:search}.search{display:grid;grid-template-columns:minmax(170px,1.4fr) 110px 100px;gap:9px;align-items:center}.nuvio-search{grid-template-columns:minmax(170px,1.4fr) 110px 100px minmax(180px,1.2fr) 118px minmax(160px,1fr) 116px}.search input,.search select{height:38px;min-width:0;border:1px solid rgba(61,74,67,.16);border-radius:14px;background:rgba(250,250,246,.82);color:#34433c;padding:0 12px;font-size:.86rem}.search button{height:38px;border:0;border-radius:14px;background:#bf8d37;color:#fff;font-weight:850;padding:0 14px}.search button:disabled,.search select:disabled{opacity:.46;cursor:not-allowed}.nuvio-result{grid-column:1/4}.nuvio-season{grid-column:4}.nuvio-episode{grid-column:5/7}.nuvio-play{grid-column:7;background:#168d79!important}.search-error{margin-top:6px;color:#ad5b5b;font-size:.76rem;font-weight:700}.metrics{grid-area:metrics;display:grid;grid-template-columns:repeat(4,1fr);gap:14px;min-height:0}.metric{border:1px solid rgba(61,74,67,.14);border-radius:18px;background:rgba(255,255,250,.64);padding:12px;min-width:0;box-shadow:0 7px 20px rgba(62,70,65,.07)}.metric span{display:block;color:#168d79;text-transform:uppercase;font-size:.64rem;font-weight:800;letter-spacing:.14em}.metric b{display:block;margin-top:8px;color:#34433c;font-size:1.22rem;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        ha-card.theme-night{background:#0b121c;border-color:rgba(148,216,255,.22);color:#f3f6f5}.theme-night .shell{background:radial-gradient(circle at 72% 10%,rgba(209,154,65,.20),transparent 30%),radial-gradient(circle at 12% 88%,rgba(29,157,133,.20),transparent 34%),linear-gradient(135deg,#111a27,#182331 52%,#0c151f)}.theme-night .shade{background:linear-gradient(90deg,rgba(9,18,28,.72),rgba(14,24,35,.55),rgba(7,15,24,.72))}.theme-night .brand h1,.theme-night .now h2,.theme-night .panel h3,.theme-night .metric b,.theme-night .show b{color:#f3f6f5}.theme-night .now p,.theme-night .synopsis,.theme-night .show p,.theme-night .show .desc{color:#c3cec9}.theme-night .hero,.theme-night .panel,.theme-night .metric{background:rgba(24,36,48,.82);border-color:rgba(190,210,202,.15);box-shadow:0 14px 38px rgba(0,0,0,.26)}.theme-night .show{background:rgba(39,53,65,.82);border-color:rgba(190,210,202,.13)}.theme-night .pill,.theme-night .btn,.theme-night .search input,.theme-night .search select,.theme-night .meta-chip{background:rgba(42,55,66,.82);border-color:rgba(200,219,211,.18);color:#eef3f1}.theme-night .wash{opacity:.18;filter:blur(18px) saturate(1.05)}
        @media(max-width:1100px){.shell{min-height:calc(100dvh - 28px)}.grid{height:auto;grid-template-columns:1fr;grid-template-rows:64px minmax(330px,52vh) auto auto auto;grid-template-areas:"header" "hero" "search" "metrics" "side"}.side{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(250px,.6fr);grid-template-rows:minmax(270px,auto);margin-bottom:8px}.schedule{min-height:230px}.metrics{grid-template-columns:repeat(4,1fr)}.hero{grid-template-columns:minmax(180px,.32fr) minmax(0,1fr)}.now h2{font-size:clamp(1.8rem,6vw,3.9rem)}}
        @media(max-width:720px){.grid{grid-template-rows:64px minmax(360px,auto) auto auto auto}.poster{display:none}.hero{grid-template-columns:1fr}.search,.nuvio-search{grid-template-columns:1fr 1fr}.search .q,.nuvio-result{grid-column:1/3}.nuvio-season,.nuvio-episode,.nuvio-play{grid-column:auto}.metrics{grid-template-columns:repeat(2,1fr)}.side{grid-template-columns:1fr;grid-template-rows:auto auto}.schedule{grid-template-columns:1fr;grid-template-rows:repeat(4,auto);height:auto}.empty{grid-column:1}.transport{grid-template-columns:repeat(3,56px)}}
      </style>
      <ha-card class="theme-${resolvedTheme}"><div class="shell"><div class="wash"></div><div class="shade"></div><div class="grid">
        <header><div class="brand"><span>Media Central</span><h1>Theatre Command</h1></div><div class="status"><button class="pill theme-toggle" data-action="theme" title="Theme: ${this.esc(this._themeMode)}">${this.esc(themeLabel)}</button><div class="pill hot">${this.esc(source).toUpperCase()}</div><div class="pill">TV ${this.esc(tvState)}</div><div class="pill">Kodi ${this.esc(kodiState)}</div></div></header>
        <section class="hero"><div class="poster"></div><div class="now"><div><div class="app">${this.esc(appId)}</div><h2>${this.esc(title)}</h2><p>${this.esc(series)}</p><div class="meta-row">${now.rating ? `<span class="meta-chip">IMDb ${this.esc(now.rating)}</span>` : ''}${now.imdb ? `<a class="meta-chip" href="${this.esc(now.imdb)}" target="_blank" rel="noreferrer">IMDb</a>` : ''}<span class="meta-chip">${this.esc(source).toUpperCase()}</span></div>${now.description ? `<div class="synopsis">${this.esc(now.description)}</div>` : ''}</div><div><div class="transport"><button class="btn" data-cmd="MEDIA_REWIND">RW</button><button class="btn primary" data-service="play">PLAY</button><button class="btn" data-service="pause">PAUSE</button><button class="btn" data-service="stop">STOP</button><button class="btn" data-cmd="MEDIA_FAST_FORWARD">FF</button><button class="btn" data-cmd="BACK">BACK</button></div><div class="launch"><button data-action="stremio">Stremio</button><button data-action="kodi">Kodi</button><button data-action="movie">Movie Mode</button><button data-cmd="HOME">Home</button></div></div></div></section>
        <aside class="side"><section class="panel"><h3>Up Next • 14 Days</h3><div class="schedule">${this.renderSchedule()}</div></section><section class="panel"><h3>SHIELD Control</h3><div class="remote"><div class="blank"></div><button class="btn" data-cmd="DPAD_UP">UP</button><div class="blank"></div><button class="btn" data-cmd="DPAD_LEFT">LEFT</button><button class="btn primary" data-cmd="DPAD_CENTER">OK</button><button class="btn" data-cmd="DPAD_RIGHT">RIGHT</button><button class="btn" data-cmd="BACK">BACK</button><button class="btn" data-cmd="DPAD_DOWN">DOWN</button><button class="btn" data-cmd="HOME">HOME</button></div></section></aside>
        <section class="panel search-panel"><h3>Nuvio+ Direct Play</h3>${this.renderNuvioSearch()}</section>
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
      if (b.dataset.action === 'theme') this.cycleTheme();
      if (b.dataset.action === 'search') this.searchNuvio();
      if (b.dataset.action === 'nuvio-play') this.playNuvioSelection();
    });
    const q = this.shadowRoot.querySelector('.q'); if (q) q.onkeydown = e => { if (e.key === 'Enter') this.searchNuvio(); };
    const result = this.shadowRoot.querySelector('.nuvio-result'); if (result) result.onchange = e => { const option=e.target.selectedOptions[0]; if (option?.value) this.selectNuvioResult(option.value, option.dataset.type || this.nuvioType(this.shadowRoot.querySelector('.type')?.value)); };
    const season = this.shadowRoot.querySelector('.nuvio-season'); if (season) season.onchange = e => { this._nuvioSearch.season=Number(e.target.value); this._nuvioSearch.episode=this.nuvioEpisodes()[0]?.episode ?? null; this.render(); };
    const episode = this.shadowRoot.querySelector('.nuvio-episode'); if (episode) episode.onchange = e => { this._nuvioSearch.episode=Number(e.target.value); this.render(); };
  }
  renderTypeOptions() {
    const selected = this.st(this.config.search_type, 'Any');
    const options = this.attr(this.config.search_type, 'options', ['Any', 'Movie', 'Show', 'Episode']);
    return options.map(o => `<option ${o === selected ? 'selected' : ''}>${this.esc(o)}</option>`).join('');
  }
  disconnectedCallback(){ clearTimeout(this._timer); }
  getCardSize(){ return 8; }
}
if (!customElements.get('media-command-center-card')) customElements.define('media-command-center-card', MediaCommandCenterCard);
window.customCards = window.customCards || [];
window.customCards.push({ type:'media-command-center-card', name:'Media Command Center', description:'Single-page cinematic media dashboard' });

