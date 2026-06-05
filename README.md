# IPTV Player — Enigma2 Client

Ein lokaler Webserver als IPTV-Client für Enigma2-Receiver (Dreambox, VU+, GigaBlue, Octagon u.a.).  
Bouquets und Sender werden direkt vom Receiver geladen, Streams werden via ffmpeg für den Browser transkodiert.

---

## Voraussetzungen

- **Python 3.8+** — [python.org](https://www.python.org/downloads/)
- **ffmpeg** — [ffmpeg.org/download.html](https://ffmpeg.org/download.html)  
  ffmpeg muss im PATH verfügbar sein (nach der Installation ggf. neu starten).
- Enigma2-Receiver mit aktiviertem **OpenWebif**-Plugin im lokalen Netzwerk.

In einem Linux-System kann man `ffmpeg` auch über `apt` installieren:

```
sudo apt-get install -y ffmpeg
```

---

## Installation

1. Repository clonen:
   ```
  git clone https://github.com/Michdo93/Enigma2-IPTV-Client
  cd Enigma2-IPTV-Client
   ```

2. Im Ordner ein virtuelles Python-Environment erstellen:

   ```bash
   python3 -m venv .
   ```

   Unter Windows:

   ```powershell
   python -m venv .
   ```

3. Environment aktivieren:

   **Linux / macOS:**

   ```bash
   source bin/activate
   ```

   **Windows (PowerShell):**

   ```powershell
   .\Scripts\Activate.ps1
   ```

   **Windows (CMD):**

   ```cmd
   Scripts\activate.bat
   ```

---

## Konfiguration

Die Datei `iptv_config.json` vor dem ersten Start anpassen:

```json
{
  "receiver_ip": "192.168.0.X",
  "username": "",
  "password": "",
  "port": 8765,
  "autoconnect": true
}
```

| Parameter | Beschreibung |
|---|---|
| `receiver_ip` | IP-Adresse des Enigma2-Receivers |
| `username` | OpenWebif-Benutzername (leer lassen falls keine Auth) |
| `password` | OpenWebif-Passwort (leer lassen falls keine Auth) |
| `port` | Lokaler Port des IPTV-Servers (Standard: 8765) |
| `autoconnect` | Beim Start automatisch mit Receiver verbinden |

---

## Starten

```bash
python iptv_server.py
```

Der Browser öffnet sich automatisch auf `http://localhost:8765`.

Unter Linux kann man einen Service anlegen, der dauerhaft läuft. Man verschiebt zunächst den Ordner und erstellt dann die benötigte Service Datei:

```
sudo mv Enigma2-IPTV-Client /opt
sudo chown -R $USER:$USER /opt/Enigma2-IPTV-Client
sudo nano /etc/systemd/system/enigma2-iptv-client.service
```

Dann tragen wir folgendes ein:

```
[Unit]
Description=Enigma2 IPTV Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<USERNAME>
WorkingDirectory=/opt/Enigma2-IPTV-Client
ExecStart=/opt/Enigma2-IPTV-Client/bin/python iptv.py
Restart=on-failure
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Nachdem die Datei gespeichert wurde, startet man den Service:

```
sudo systemctl daemon-reload
sudo systemctl enable enigma2-iptv-client
sudo systemctl start enigma2-iptv-client
```

---

## Bedienung

- **Bouquet-Leiste** oben: zwischen Senderlisten wechseln
- **Senderliste** links: Sender antippen zum Abspielen
- **Senderliste ein-/ausblenden**: Pfeil-Button am linken Videorand, oder `Escape` / `Tab`
- **Sender suchen**: Suchfeld oben in der Senderliste
- **Zappen**: Pfeiltasten `↑` / `↓`

---

## Netzwerk

Der Server läuft auf `0.0.0.0` — er ist also im gesamten lokalen Netzwerk erreichbar.  
Andere Geräte (z.B. Smart TV mit Browser) können die Oberfläche über  
`http://<IP-des-PCs>:8765` aufrufen.

Die Zugangsdaten aus der `iptv_config.json` werden **nur serverseitig** verwendet  
und sind im Browser nie sichtbar.

---

## Technischer Hintergrund

| Komponente | Funktion |
|---|---|
| Python HTTPServer | Lokaler Proxy-Server |
| `/proxy` | Holt M3U-Playlists und API-Antworten vom Receiver |
| `/transcode` | Tunnelt MPEG-TS-Stream durch ffmpeg → fragmentiertes MP4 |
| ffmpeg | Remux MPEG-TS zu frag. MP4 (`-c:v copy`, kein Re-encode) |
| Browser | Spielt fragmentiertes MP4 nativ ab (Chrome, Firefox, Edge, Safari) |

Der Video-Stream wird **nicht neu enkodiert** (`-c:v copy`) — lediglich der Container  
wird von MPEG-TS zu fragmentiertem MP4 umgewandelt. Die CPU-Last ist daher minimal.  
Audio wird von AC3 (Satellit) zu AAC konvertiert, da AC3 in Browsern nicht unterstützt wird.
