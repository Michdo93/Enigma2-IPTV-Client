#!/usr/bin/env python3
"""
IPTV Player - Enigma2 HLS Client
Konfiguration: iptv_config.json (im gleichen Verzeichnis)
Starten: python3 iptv_server.py
Voraussetzung: ffmpeg im PATH
"""

import http.server
from http.server import ThreadingHTTPServer
import urllib.request
import urllib.parse
import urllib.error
import base64
import threading
import webbrowser
import subprocess
import shutil
import json
import os
import time
import tempfile

PORT = 8765
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptv_config.json')

QUALITY_PRESETS = {
    "ultra":  {"bitrate": "8000k",  "maxrate": "8500k",  "bufsize": "16000k", "audio": "192k", "label": "Ultra (8 Mbit/s)"},
    "high":   {"bitrate": "4000k",  "maxrate": "4500k",  "bufsize": "8000k",  "audio": "128k", "label": "High (4 Mbit/s)"},
    "medium": {"bitrate": "2000k",  "maxrate": "2500k",  "bufsize": "4000k",  "audio": "128k", "label": "Medium (2 Mbit/s)"},
    "low":    {"bitrate": "800k",   "maxrate": "1000k",  "bufsize": "1600k",  "audio": "96k",  "label": "Low (1 Mbit/s)"},
}

# HLS-Segmente im temporären Verzeichnis
HLS_DIR = os.path.join(tempfile.gettempdir(), 'iptv_hls')
os.makedirs(HLS_DIR, exist_ok=True)

def load_config():
    defaults = {
        "receiver_ip": "192.168.3.3",
        "username": "",
        "password": "",
        "port": 8765,
        "autoconnect": True,
        "quality": "ultra"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                cfg = json.load(f)
            defaults.update(cfg)
        except Exception as e:
            print(f'Fehler beim Lesen der Konfiguration: {e}')
    else:
        print(f'Erstelle Konfigurationsdatei: {CONFIG_FILE}')
        with open(CONFIG_FILE, 'w') as f:
            json.dump(defaults, f, indent=2)
    return defaults


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>IPTV</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest/dist/hls.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0d0d0d; color: #f0f0f0; font-family: sans-serif; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

#top-bar { display: flex; gap: 0.5rem; padding: 0.5rem 1rem; background: #1a1a1a; border-bottom: 1px solid #2a2a2a; flex-shrink: 0; align-items: center; flex-wrap: wrap; }
#quality-select { background: #0d0d0d; border: 1px solid #333; border-radius: 4px; padding: 0.4rem 0.7rem; color: #f0f0f0; font-size: 0.85rem; outline: none; cursor: pointer; }
#quality-select:focus { border-color: #00cc88; }
#top-msg { font-size: 0.85rem; color: #555; margin-left: auto; }

#bouquet-bar { display: none; gap: 0.4rem; padding: 0.5rem 1rem; background: #111; border-bottom: 1px solid #2a2a2a; flex-shrink: 0; flex-wrap: wrap; align-items: center; }
#bouquet-bar span { font-size: 0.8rem; color: #555; margin-right: 0.3rem; }
.bq-btn { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 3px; color: #aaa; padding: 0.3rem 0.8rem; font-size: 0.85rem; cursor: pointer; }
.bq-btn:hover { border-color: #00cc88; color: #00cc88; }
.bq-btn.active { background: #003322; border-color: #00cc88; color: #00cc88; }

#main { flex: 1; display: flex; overflow: hidden; position: relative; }

#list { width: 300px; flex-shrink: 0; display: flex; flex-direction: column; border-right: 1px solid #2a2a2a; background: #111; overflow: hidden; transition: width 0.25s ease, opacity 0.25s ease; }
#list.hidden { width: 0; opacity: 0; border-right: none; pointer-events: none; }
#search { background: #1a1a1a; border: none; border-bottom: 1px solid #2a2a2a; padding: 0.7rem 1rem; color: #f0f0f0; font-size: 0.9rem; outline: none; flex-shrink: 0; width: 100%; }
#channels { flex: 1; overflow-y: auto; }
.ch { padding: 0.65rem 1rem; cursor: pointer; border-bottom: 1px solid #1a1a1a; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ch:hover { background: #1e1e1e; }
.ch.active { background: #003322; color: #00cc88; border-left: 3px solid #00cc88; padding-left: calc(1rem - 3px); }

#video-area { flex: 1; background: #000; display: flex; align-items: center; justify-content: center; position: relative; min-width: 0; }
video { width: 100%; height: 100%; display: block; }
#placeholder { color: #444; font-size: 1rem; text-align: center; line-height: 2.2; }

#toggle-list { position: absolute; top: 50%; left: 0; transform: translateY(-50%); z-index: 10; background: rgba(0,0,0,0.7); border: 1px solid #333; border-left: none; border-radius: 0 6px 6px 0; color: #aaa; font-size: 1.1rem; width: 22px; height: 56px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 0.2s, color 0.2s; user-select: none; }
#toggle-list:hover { background: rgba(0,204,136,0.2); color: #00cc88; border-color: #00cc88; }

#now { position: absolute; top: 0.8rem; left: 0.8rem; background: rgba(0,0,0,0.75); border: 1px solid #00cc88; border-radius: 3px; padding: 0.3rem 0.7rem; font-size: 0.85rem; color: #00cc88; display: none; }
#quality-badge { position: absolute; top: 0.8rem; right: 0.8rem; background: rgba(0,0,0,0.75); border: 1px solid #444; border-radius: 3px; padding: 0.2rem 0.6rem; font-size: 0.75rem; color: #666; display: none; }
#msg { position: absolute; bottom: 0.8rem; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.75); border-radius: 3px; padding: 0.3rem 0.8rem; font-size: 0.85rem; color: #aaa; display: none; white-space: nowrap; }
#msg.show { display: block; }
#loading { position: absolute; inset: 0; background: rgba(0,0,0,0.6); display: none; align-items: center; justify-content: center; flex-direction: column; gap: 1rem; }
#loading.show { display: flex; }
.spinner { width: 40px; height: 40px; border: 3px solid rgba(0,204,136,0.2); border-top-color: #00cc88; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

#stream-url-bar {
  flex-shrink: 0;
  display: none;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 1rem;
  background: #0d0d0d;
  border-top: 1px solid #1e1e1e;
  font-size: 0.8rem;
}
#stream-url-bar span { color: #444; white-space: nowrap; }
#stream-url-text {
  flex: 1;
  background: #111;
  border: 1px solid #222;
  border-radius: 3px;
  padding: 0.3rem 0.6rem;
  color: #555;
  font-family: monospace;
  font-size: 0.78rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: text;
  user-select: all;
}
#stream-url-text:hover { color: #888; border-color: #333; }
#copy-btn {
  background: #1a1a1a;
  border: 1px solid #2a2a2a;
  border-radius: 3px;
  color: #555;
  font-size: 0.78rem;
  padding: 0.3rem 0.7rem;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.2s, border-color 0.2s;
}
#copy-btn:hover { color: #00cc88; border-color: #00cc88; }
</style>
</head>
<body>

<div id="top-bar">
  <span style="font-size:0.85rem;color:#555;">Qualität:</span>
  <select id="quality-select" onchange="onQualityChange()">
    <option value="ultra">Ultra (8 Mbit/s)</option>
    <option value="high">High (4 Mbit/s)</option>
    <option value="medium">Medium (2 Mbit/s)</option>
    <option value="low">Low (1 Mbit/s)</option>
  </select>
  <span id="top-msg"></span>
</div>

<div id="bouquet-bar"><span>Bouquet:</span></div>

<div id="main">
  <div id="list">
    <input id="search" type="text" placeholder="Sender suchen…" oninput="filterChannels(this.value)" />
    <div id="channels"></div>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0;">
    <div id="video-area">
      <button id="toggle-list" onclick="toggleList()" title="Senderliste ein/ausblenden">&#9664;</button>
      <div id="placeholder">Verbinde mit Receiver…</div>
      <video id="v" controls autoplay style="display:none"></video>
      <div id="now"></div>
      <div id="quality-badge"></div>
      <div id="loading"><div class="spinner"></div><span style="color:#aaa;font-size:0.9rem">Starte Stream…</span></div>
      <div id="msg"></div>
    </div>
    <div id="stream-url-bar">
      <span>HLS-URL:</span>
      <div id="stream-url-text" title="Klicken zum Auswählen"></div>
      <button id="copy-btn" onclick="copyUrl()">Kopieren</button>
    </div>
  </div>
</div>

<script>
let all = [], filtered = [], cur = -1;
let listVisible = true;
let hlsInstance = null;
let currentStreamId = null;

const CFG = __CONFIG__;

// Qualität aus Config vorauswählen
document.getElementById('quality-select').value = CFG.quality || 'ultra';

function toggleList() {
  listVisible = !listVisible;
  document.getElementById('list').classList.toggle('hidden', !listVisible);
  document.getElementById('toggle-list').innerHTML = listVisible ? '&#9664;' : '&#9654;';
}

function onQualityChange() {
  if (cur >= 0) play(cur); // Sender neu starten mit neuer Qualität
}

async function proxyFetch(url) {
  const res = await fetch('/proxy?url=' + encodeURIComponent(url));
  if (!res.ok) throw new Error('HTTP ' + res.status + ' — ' + await res.text());
  return res;
}

async function loadBouquets() {
  try {
    const res = await proxyFetch('http://' + CFG.receiver_ip + '/api/getservices');
    const json = await res.json();
    const bouquets = json.services || [];
    if (!bouquets.length) { showMsg('Keine Bouquets gefunden'); return; }
    renderBouquets(bouquets);
    loadChannels(bouquets[0].servicereference);
  } catch(e) { showMsg('Verbindungsfehler: ' + e.message); }
}

function renderBouquets(bouquets) {
  const bar = document.getElementById('bouquet-bar');
  while (bar.children.length > 1) bar.removeChild(bar.lastChild);
  bouquets.forEach((bq, i) => {
    const btn = document.createElement('button');
    btn.className = 'bq-btn' + (i === 0 ? ' active' : '');
    btn.textContent = bq.servicename;
    btn.onclick = () => {
      document.querySelectorAll('.bq-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      loadChannels(bq.servicereference);
    };
    bar.appendChild(btn);
  });
  bar.style.display = 'flex';
}

async function loadChannels(serviceRef) {
  const m3uUrl = 'http://' + CFG.receiver_ip + '/web/servicesm3u?bRef=' + encodeURIComponent(serviceRef);
  try {
    const res = await proxyFetch(m3uUrl);
    const text = await res.text();
    parseM3U(text);
  } catch(e) { showMsg('Fehler: ' + e.message); }
}

function parseM3U(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  const ch = [];
  let name = '';
  for (const line of lines) {
    if (line.startsWith('#EXTINF')) {
      const m = line.match(/,(.+)$/);
      name = m ? m[1].trim() : 'Unbekannt';
    } else if (/^https?:\/\//.test(line)) {
      if (name) { ch.push({name, url: line}); name = ''; }
    }
  }
  if (!ch.length) { showMsg('Keine Sender gefunden'); return; }
  all = ch; filtered = [...ch]; cur = -1;
  renderList();
  document.getElementById('search').value = '';
  document.getElementById('placeholder').textContent = filtered.length + ' Sender — Sender antippen zum Starten';
}

function renderList() {
  const div = document.getElementById('channels');
  div.innerHTML = '';
  filtered.forEach((ch, i) => {
    const el = document.createElement('div');
    el.className = 'ch' + (i === cur ? ' active' : '');
    el.textContent = (i+1) + '. ' + ch.name;
    el.onclick = () => play(i);
    div.appendChild(el);
  });
}

function filterChannels(q) {
  q = q.toLowerCase();
  filtered = q ? all.filter(c => c.name.toLowerCase().includes(q)) : [...all];
  cur = -1; renderList();
}

async function play(i) {
  cur = i;
  const ch = filtered[i];
  const v = document.getElementById('v');
  const quality = document.getElementById('quality-select').value;

  document.getElementById('placeholder').style.display = 'none';
  document.getElementById('loading').classList.add('show');
  v.style.display = 'block';

  // Alten HLS-Stream stoppen
  if (hlsInstance) { hlsInstance.destroy(); hlsInstance = null; }
  if (currentStreamId) {
    fetch('/stop?id=' + currentStreamId).catch(()=>{});
    currentStreamId = null;
  }
  v.pause();
  v.removeAttribute('src');
  v.load();

  // Neuen HLS-Stream starten
  try {
    const res = await fetch('/start?url=' + encodeURIComponent(ch.url) + '&quality=' + quality);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    currentStreamId = data.id;

    const hlsUrl = '/hls/' + data.playlist;

    document.getElementById('quality-badge').style.display = 'block';
    document.getElementById('quality-badge').textContent = quality.toUpperCase();
    updateStreamUrl(data.id, quality);

    if (Hls.isSupported()) {
      hlsInstance = new Hls({
        liveSyncDurationCount: 2,          // Nur 2 Segmente Puffer = ~2s Latenz
        liveMaxLatencyDurationCount: 4,    // Max 4s bevor Resync
        liveSyncOnStallEnabled: true,      // Bei Stall automatisch resync
        maxLiveSyncPlaybackRate: 1.5,      // Aufholen mit max 1.5x Speed
        manifestLoadingMaxRetry: 8,
        manifestLoadingRetryDelay: 500,
        levelLoadingMaxRetry: 8,
        fragLoadingMaxRetry: 8,
        lowLatencyMode: false,             // Kein CMAF nötig
      });
      hlsInstance.loadSource(hlsUrl);
      hlsInstance.attachMedia(v);
      hlsInstance.on(Hls.Events.MANIFEST_PARSED, () => {
        document.getElementById('loading').classList.remove('show');
        v.play().catch(()=>{});
      });
      hlsInstance.on(Hls.Events.ERROR, (e, data) => {
        if (data.fatal) {
          document.getElementById('loading').classList.remove('show');
          showMsg('Stream-Fehler: ' + data.type);
        }
      });
    } else if (v.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari native HLS
      v.src = hlsUrl;
      v.oncanplay = () => { document.getElementById('loading').classList.remove('show'); v.play().catch(()=>{}); };
    }

  } catch(e) {
    document.getElementById('loading').classList.remove('show');
    showMsg('Fehler: ' + e.message);
  }

  document.getElementById('now').style.display = 'block';
  document.getElementById('now').textContent = ch.name;
  document.title = ch.name + ' — IPTV';
  renderList();
  document.querySelectorAll('.ch')[i]?.scrollIntoView({block:'nearest'});
}

function updateStreamUrl(sid, quality) {
  const host = window.location.host;
  const url = `http://${host}/hls/live_${sid}.m3u8`;
  const bar = document.getElementById('stream-url-bar');
  const txt = document.getElementById('stream-url-text');
  bar.style.display = 'flex';
  txt.textContent = url;
  txt.title = url;
}

function copyUrl() {
  const txt = document.getElementById('stream-url-text').textContent;
  navigator.clipboard.writeText(txt).then(() => {
    const btn = document.getElementById('copy-btn');
    btn.textContent = '✓ Kopiert';
    setTimeout(() => btn.textContent = 'Kopieren', 2000);
  });
}

function showMsg(t, ms=3000) {
  const el = document.getElementById('msg');
  el.textContent = t; el.classList.add('show');
  if (ms) setTimeout(() => el.classList.remove('show'), ms);
}

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  if (e.key === 'ArrowDown') play(Math.min(cur+1, filtered.length-1));
  if (e.key === 'ArrowUp')   play(Math.max(cur-1, 0));
  if (e.key === 'Escape' || e.key === 'Tab') toggleList();
});

window.addEventListener('load', () => { if (CFG.autoconnect) loadBouquets(); });
</script>
</body>
</html>
"""

# ── Stream-Manager ──────────────────────────────────────────────────────────

_streams_lock = threading.Lock()
_streams = {}  # id -> {proc, playlist, last_access, dir}


def stream_id(url, quality):
    import hashlib
    return hashlib.md5(f'{url}:{quality}'.encode()).hexdigest()[:8]


def start_hls_stream(stream_url, quality, cfg):
    sid = stream_id(stream_url, quality)

    with _streams_lock:
        if sid in _streams:
            _streams[sid]['last_access'] = time.time()
            return sid, _streams[sid]['playlist']

    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('ffmpeg nicht gefunden')

    preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS['high'])

    # Auth aus URL extrahieren
    p = urllib.parse.urlparse(stream_url)
    if p.username:
        input_url = f'{p.scheme}://{p.hostname}:{p.port}{p.path}'
        auth_header = 'Authorization: Basic ' + base64.b64encode(
            f'{p.username}:{p.password}'.encode()).decode()
    else:
        input_url = stream_url
        auth_header = None

    if not auth_header and cfg.get('username'):
        auth_header = 'Authorization: Basic ' + base64.b64encode(
            f"{cfg['username']}:{cfg['password']}".encode()).decode()

    playlist_name = f'live_{sid}.m3u8'
    playlist_path = os.path.join(HLS_DIR, playlist_name)
    segment_pattern = os.path.join(HLS_DIR, f'{sid}_seg%03d.ts')

    cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error']
    if auth_header:
        cmd += ['-headers', auth_header + '\r\n']
    cmd += [
        '-user_agent', 'VLC/3.0.0',
        '-fflags', '+genpts+discardcorrupt+igndts',
        '-err_detect', 'ignore_err',
        '-analyzeduration', '500000',
        '-probesize', '500000',
        '-i', input_url,
        '-map', '0:v:0',       # Nur erster Video-Track
        '-map', '0:a:0',       # Nur erster Audio-Track
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-tune', 'zerolatency',
        '-profile:v', 'baseline',
        '-level', '3.1',
        '-b:v', preset['bitrate'],
        '-maxrate', preset['maxrate'],
        '-bufsize', preset['bufsize'],
        '-c:a', 'aac',
        '-b:a', preset['audio'],
        '-ar', '48000',
        '-ac', '2',
        '-f', 'hls',
        '-hls_time', '1',              # 1s Segmente statt 2s = weniger Latenz
        '-hls_list_size', '5',
        '-hls_flags', 'delete_segments+independent_segments+split_by_time',
        '-hls_allow_cache', '0',       # Browser soll nicht cachen
        '-hls_segment_filename', segment_pattern,
        playlist_path,
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    with _streams_lock:
        _streams[sid] = {
            'proc': proc,
            'playlist': playlist_name,
            'last_access': time.time(),
            'quality': quality,
        }

    # Warten bis Playlist existiert (max 40s)
    print(f'ffmpeg gestartet (PID {proc.pid}), warte auf Playlist: {playlist_path}')
    for i in range(400):
        if os.path.exists(playlist_path):
            print(f'Playlist bereit nach {i*0.1:.1f}s')
            break
        if proc.poll() is not None:
            raise RuntimeError(f'ffmpeg beendet mit Code {proc.returncode}')
        time.sleep(0.1)
    else:
        proc.terminate()
        raise RuntimeError('Timeout: Playlist wurde nicht erstellt (>40s)')

    return sid, playlist_name


def stop_stream(sid):
    with _streams_lock:
        s = _streams.pop(sid, None)
    if s:
        proc = s['proc']
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: proc.kill()
        # Segmente aufräumen
        for f in os.listdir(HLS_DIR):
            if f.startswith(sid) or f == s['playlist']:
                try: os.remove(os.path.join(HLS_DIR, f))
                except: pass


def cleanup_thread():
    """Beendet inaktive Streams nach 5 Minuten."""
    while True:
        time.sleep(30)
        now = time.time()
        with _streams_lock:
            stale = [sid for sid, s in _streams.items() if now - s['last_access'] > 300]
        for sid in stale:
            print(f'Cleanup: Stream {sid} beendet (inaktiv)')
            stop_stream(sid)


# ── HTTP Handler ─────────────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):

    def __init__(self, *args, config=None, **kwargs):
        self.config = config
        super().__init__(*args, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        cfg = self.config

        if parsed.path == '/favicon.ico':
            self.send_response(204); self.end_headers()

        # Hauptseite
        elif parsed.path in ('/', '/index.html'):
            cfg_json = json.dumps({
                "receiver_ip": cfg['receiver_ip'],
                "autoconnect": cfg.get('autoconnect', True),
                "quality": cfg.get('quality', 'ultra'),
            })
            html = HTML_TEMPLATE.replace('__CONFIG__', cfg_json)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        # M3U / API Proxy
        elif parsed.path == '/proxy':
            target = params.get('url', [''])[0]
            try:
                req = urllib.request.Request(target, headers={'User-Agent': 'Enigma2 IPTV Client'})
                if cfg.get('username'):
                    creds = base64.b64encode(f"{cfg['username']}:{cfg['password']}".encode()).decode()
                    req.add_header('Authorization', f'Basic {creds}')
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = r.read()
                    ct = r.headers.get('Content-Type', 'application/octet-stream')
                self.send_response(200)
                self.send_header('Content-Type', ct)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
            except urllib.error.HTTPError as e:
                self.respond(e.code, f'HTTP {e.code} {e.reason}'.encode())
            except Exception as e:
                self.respond(502, str(e).encode())

        # HLS Stream starten
        elif parsed.path == '/start':
            url = params.get('url', [''])[0]
            quality = params.get('quality', ['ultra'])[0]
            if quality not in QUALITY_PRESETS:
                quality = 'ultra'
            try:
                sid, playlist = start_hls_stream(url, quality, cfg)
                self.json_response({'id': sid, 'playlist': playlist})
            except Exception as e:
                self.respond(500, str(e).encode())

        # HLS Stream stoppen
        elif parsed.path == '/stop':
            sid = params.get('id', [''])[0]
            if sid:
                stop_stream(sid)
            self.json_response({'ok': True})

        # HLS Dateien ausliefern (.m3u8 und .ts Segmente)
        elif parsed.path.startswith('/hls/'):
            filename = os.path.basename(parsed.path)
            filepath = os.path.join(HLS_DIR, filename)

            # last_access aktualisieren bei Playlist-Abruf
            if filename.endswith('.m3u8'):
                sid = filename.replace('live_', '').replace('.m3u8', '')
                with _streams_lock:
                    if sid in _streams:
                        _streams[sid]['last_access'] = time.time()

            if os.path.exists(filepath):
                ct = 'application/vnd.apple.mpegurl' if filename.endswith('.m3u8') else 'video/mp2t'
                with open(filepath, 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', ct)
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
            else:
                self.respond(404, b'Segment not found')

        else:
            self.respond(404, b'Not found')

    def json_response(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def respond(self, code, body):
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args): pass


def main():
    cfg = load_config()
    port = cfg.get('port', PORT)

    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        print('WARNUNG: ffmpeg nicht im PATH gefunden!')
        print('Download: https://ffmpeg.org/download.html')
    else:
        print(f'ffmpeg: {ffmpeg}')

    print(f'Receiver:  {cfg["receiver_ip"]}')
    print(f'Qualität:  {cfg.get("quality", "ultra")}')
    print(f'HLS-Dir:   {HLS_DIR}')
    if cfg.get('username'): print(f'Benutzer:  {cfg["username"]}')

    # Cleanup-Thread starten
    t = threading.Thread(target=cleanup_thread, daemon=True)
    t.start()

    def handler_factory(*args, **kwargs):
        return Handler(*args, config=cfg, **kwargs)

    server = ThreadingHTTPServer(('0.0.0.0', port), handler_factory)
    server.socket.setsockopt(__import__('socket').SOL_SOCKET,
                              __import__('socket').SO_SNDBUF, 524288)
    print(f'IPTV Server läuft auf http://localhost:{port}')
    print('Strg+C zum Beenden')
    threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{port}')).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nBeende alle Streams…')
        with _streams_lock:
            sids = list(_streams.keys())
        for sid in sids:
            stop_stream(sid)
        print('Beendet.')

if __name__ == '__main__':
    main()
