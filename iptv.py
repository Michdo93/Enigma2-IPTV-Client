#!/usr/bin/env python3
"""
IPTV Player - Enigma2 Client
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

PORT = 8765
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptv_config.json')

def load_config():
    defaults = {"receiver_ip": "192.168.3.3", "username": "", "password": "", "port": 8765, "autoconnect": True}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                cfg = json.load(f)
            defaults.update(cfg)
        except Exception as e:
            print(f'Fehler beim Lesen der Konfiguration: {e}')
    else:
        print(f'Keine Konfigurationsdatei gefunden, erstelle: {CONFIG_FILE}')
        with open(CONFIG_FILE, 'w') as f:
            json.dump(defaults, f, indent=2)
    return defaults

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>IPTV</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0d0d0d; color: #f0f0f0; font-family: sans-serif; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

#bouquet-bar { display: none; gap: 0.4rem; padding: 0.5rem 1rem; background: #111; border-bottom: 1px solid #2a2a2a; flex-shrink: 0; flex-wrap: wrap; align-items: center; }
#bouquet-bar span { font-size: 0.8rem; color: #555; margin-right: 0.3rem; }
.bq-btn { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 3px; color: #aaa; padding: 0.3rem 0.8rem; font-size: 0.85rem; cursor: pointer; }
.bq-btn:hover { border-color: #00cc88; color: #00cc88; }
.bq-btn.active { background: #003322; border-color: #00cc88; color: #00cc88; }

#main { flex: 1; display: flex; overflow: hidden; position: relative; }

/* Senderliste - einblendbar */
#list {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #2a2a2a;
  background: #111;
  overflow: hidden;
  transition: width 0.25s ease, opacity 0.25s ease;
}
#list.hidden {
  width: 0;
  opacity: 0;
  border-right: none;
  pointer-events: none;
}
#search { background: #1a1a1a; border: none; border-bottom: 1px solid #2a2a2a; padding: 0.7rem 1rem; color: #f0f0f0; font-size: 0.9rem; outline: none; flex-shrink: 0; width: 100%; }
#channels { flex: 1; overflow-y: auto; }
.ch { padding: 0.65rem 1rem; cursor: pointer; border-bottom: 1px solid #1a1a1a; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ch:hover { background: #1e1e1e; }
.ch.active { background: #003322; color: #00cc88; border-left: 3px solid #00cc88; padding-left: calc(1rem - 3px); }

#video-area { flex: 1; background: #000; display: flex; align-items: center; justify-content: center; position: relative; min-width: 0; }
video { width: 100%; height: 100%; display: block; }
#placeholder { color: #444; font-size: 1rem; text-align: center; line-height: 2.2; }

/* Toggle-Button */
#toggle-list {
  position: absolute;
  top: 50%;
  left: 0;
  transform: translateY(-50%);
  z-index: 10;
  background: rgba(0,0,0,0.7);
  border: 1px solid #333;
  border-left: none;
  border-radius: 0 6px 6px 0;
  color: #aaa;
  font-size: 1.1rem;
  width: 22px;
  height: 56px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, color 0.2s;
  user-select: none;
}
#toggle-list:hover { background: rgba(0,204,136,0.2); color: #00cc88; border-color: #00cc88; }

#now { position: absolute; top: 0.8rem; left: 0.8rem; background: rgba(0,0,0,0.75); border: 1px solid #00cc88; border-radius: 3px; padding: 0.3rem 0.7rem; font-size: 0.85rem; color: #00cc88; display: none; }
#msg { position: absolute; bottom: 0.8rem; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.75); border-radius: 3px; padding: 0.3rem 0.8rem; font-size: 0.85rem; color: #aaa; display: none; white-space: nowrap; }
#msg.show { display: block; }
#loading { position: absolute; inset: 0; background: rgba(0,0,0,0.6); display: none; align-items: center; justify-content: center; flex-direction: column; gap: 1rem; }
#loading.show { display: flex; }
.spinner { width: 40px; height: 40px; border: 3px solid rgba(0,204,136,0.2); border-top-color: #00cc88; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
#format-badge { position: absolute; bottom: 0.8rem; right: 0.8rem; background: rgba(0,0,0,0.6); border: 1px solid #333; border-radius: 3px; padding: 0.2rem 0.6rem; font-size: 0.75rem; color: #555; display: none; }
</style>
</head>
<body>

<div id="bouquet-bar"><span>Bouquet:</span></div>

<div id="main">
  <div id="list">
    <input id="search" type="text" placeholder="Sender suchen…" oninput="filterChannels(this.value)" />
    <div id="channels"></div>
  </div>

  <div id="video-area">
    <button id="toggle-list" onclick="toggleList()" title="Senderliste ein/ausblenden">&#9664;</button>
    <div id="placeholder">Verbinde mit Receiver…</div>
    <video id="v" controls autoplay style="display:none"></video>
    <div id="now"></div>
    <div id="loading"><div class="spinner"></div><span style="color:#aaa;font-size:0.9rem">Transcoding…</span></div>
    <div id="format-badge"></div>
    <div id="msg"></div>
  </div>
</div>

<script>
let all = [], filtered = [], cur = -1;
let listVisible = true;

const CFG = __CONFIG__;

function toggleList() {
  listVisible = !listVisible;
  document.getElementById('list').classList.toggle('hidden', !listVisible);
  document.getElementById('toggle-list').innerHTML = listVisible ? '&#9664;' : '&#9654;';
}

function detectFormat() {
  // Alle Browser bekommen MP4 (frag_keyframe) — funktioniert ab Firefox 42+
  return 'mp4';
}

function supportsMediaSource(fmt) {
  if (!window.MediaSource) return false;
  const types = { mp4: 'video/mp4; codecs="avc1.42E01E, mp4a.40.2"', webm: 'video/webm; codecs="vp8, vorbis"', 'webm-vp9': 'video/webm; codecs="vp9, opus"' };
  return MediaSource.isTypeSupported(types[fmt] || '');
}

function getMimeType(fmt) {
  return { mp4: 'video/mp4; codecs="avc1.42E01E, mp4a.40.2"', webm: 'video/webm; codecs="vp8, vorbis"', 'webm-vp9': 'video/webm; codecs="vp9, opus"' }[fmt] || 'video/mp4';
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



function play(i) {
  cur = i;
  const ch = filtered[i];
  const v = document.getElementById('v');
  document.getElementById('placeholder').style.display = 'none';
  document.getElementById('loading').classList.add('show');
  v.style.display = 'block';

  // Alten Stream stoppen
  v.pause();
  v.removeAttribute('src');
  v.load();

  const fmt = detectFormat();
  document.getElementById('format-badge').style.display = 'block';
  document.getElementById('format-badge').textContent = fmt.toUpperCase();

  const transcodeUrl = '/transcode?fmt=' + fmt + '&url=' + encodeURIComponent(ch.url);

  v.src = transcodeUrl;
  v.oncanplay = () => {
    document.getElementById('loading').classList.remove('show');
    v.play().catch(()=>{});
  };
  v.onerror = () => {
    document.getElementById('loading').classList.remove('show');
    showMsg('Fehler beim Laden: ' + ch.name);
  };

  document.getElementById('now').style.display = 'block';
  document.getElementById('now').textContent = ch.name;
  document.title = ch.name + ' — IPTV';
  renderList();
  document.querySelectorAll('.ch')[i]?.scrollIntoView({block:'nearest'});
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

// Autoconnect beim Start
window.addEventListener('load', () => { if (CFG.autoconnect) loadBouquets(); });
</script>
</body>
</html>
"""

_ffmpeg_lock = threading.Lock()
_current_proc = None

def kill_ffmpeg():
    global _current_proc
    with _ffmpeg_lock:
        if _current_proc and _current_proc.poll() is None:
            _current_proc.terminate()
            try: _current_proc.wait(timeout=2)
            except subprocess.TimeoutExpired: _current_proc.kill()
        _current_proc = None

def build_ffmpeg_cmd(input_url, auth_header, fmt):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg: return None, None
    cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error']
    if auth_header: cmd += ['-headers', auth_header + '\r\n']
    cmd += ['-user_agent', 'VLC/3.0.0', '-i', input_url]
    if fmt == 'mp4':
        cmd += ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-f', 'mp4',
                '-movflags', 'frag_keyframe+empty_moov+faststart+default_base_moof',
                '-frag_duration', '500000', '-reset_timestamps', '1']
    elif fmt in ('webm', 'webm-vp9'):
        vcodec = 'libvpx-vp9' if fmt == 'webm-vp9' else 'libvpx'
        acodec = 'libopus' if fmt == 'webm-vp9' else 'libvorbis'
        cmd += ['-c:v', vcodec, '-b:v', '1500k', '-crf', '33', '-deadline', 'realtime',
                '-cpu-used', '8', '-c:a', acodec, '-b:a', '128k',
                '-f', 'webm', '-cluster_size_limit', '512k', '-cluster_time_limit', '1000']
    cmd += ['pipe:1']
    return ffmpeg, cmd


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

        elif parsed.path == '/proxy':
            target = params.get('url', [''])[0]
            try:
                req = urllib.request.Request(target, headers={'User-Agent': 'Enigma2 IPTV Client'})
                if cfg['username']:
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

        elif parsed.path == '/transcode':
            global _current_proc
            target = params.get('url', [''])[0]
            fmt    = params.get('fmt', ['mp4'])[0]
            if fmt not in ('mp4', 'webm', 'webm-vp9'): fmt = 'mp4'

            p = urllib.parse.urlparse(target)
            if p.username:
                input_url = f'{p.scheme}://{p.hostname}:{p.port}{p.path}'
                if p.query: input_url += '?' + p.query
                auth_header = 'Authorization: Basic ' + base64.b64encode(
                    f'{p.username}:{p.password}'.encode()).decode()
            else:
                input_url = target
                auth_header = None

            # Credentials aus Config zusätzlich als Fallback
            if not auth_header and cfg['username']:
                auth_header = 'Authorization: Basic ' + base64.b64encode(
                    f"{cfg['username']}:{cfg['password']}".encode()).decode()

            kill_ffmpeg()
            ffmpeg_bin, cmd = build_ffmpeg_cmd(input_url, auth_header, fmt)
            if not ffmpeg_bin:
                self.respond(503, b'ffmpeg nicht gefunden.'); return

            content_type = 'video/mp4' if fmt == 'mp4' else 'video/webm'
            try:
                with _ffmpeg_lock:
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
                    _current_proc = proc
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                while True:
                    chunk = proc.stdout.read(32768)
                    if not chunk: break
                    try: self.wfile.write(chunk); self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError): break
            except Exception: pass
            finally: kill_ffmpeg()

        elif parsed.path in ('/', '/index.html'):
            cfg_json = json.dumps({"receiver_ip": cfg['receiver_ip'], "autoconnect": cfg.get('autoconnect', True)})
            html = HTML_TEMPLATE.replace('__CONFIG__', cfg_json)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        else:
            self.respond(404, b'Not found')

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

    print(f'Receiver: {cfg["receiver_ip"]}')
    if cfg.get('username'): print(f'Benutzer: {cfg["username"]}')

    def handler_factory(*args, **kwargs):
        return Handler(*args, config=cfg, **kwargs)

    server = ThreadingHTTPServer(('0.0.0.0', port), handler_factory)
    print(f'IPTV Server läuft auf http://localhost:{port}')
    print('Strg+C zum Beenden')
    threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{port}')).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        kill_ffmpeg()
        print('\nBeendet.')

if __name__ == '__main__':
    main()
