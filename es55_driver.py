import os, io, time, glob, json, math, random, socket, struct, threading, urllib.request, serial, psutil
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps, ImageSequence
import webui_module

_orig_getaddrinfo = socket.getaddrinfo
_HOST_MAP = {
    "geocoding-api." + "open-meteo.com": "188.114.97.2",
    "api." + "open-meteo.com": "188.114.97.2",
}
def _fixed_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    h_str = host.decode("utf-8", errors="ignore") if isinstance(host, bytes) else str(host)
    if h_str in _HOST_MAP:
        return _orig_getaddrinfo(_HOST_MAP[h_str], port, socket.AF_INET, type, proto, flags)
    return _orig_getaddrinfo(host, port, family, type, proto, flags)
socket.getaddrinfo = _fixed_getaddrinfo

PORT = os.getenv("SERIAL_PORT", "/dev/ttyACM0")
DEVICE_PROFILE = os.getenv("DEVICE_PROFILE", "ocypus_es55").strip()
DEVICES_DIR = os.getenv("DEVICES_DIR", "/config/devices").strip()

def load_device_profile():
    prof = {
        "name": "Ocypus Sigma ES55 (960x480)",
        "width": int(os.getenv("SCREEN_WIDTH", "960")),
        "height": int(os.getenv("SCREEN_HEIGHT", "480")),
        "baudrate": 115200,
        "handshake_hex": "55aa0700111701",
        "framing": "uint32_jpeg_crc16",
        "jpeg_quality": 85
    }
    pfile = os.path.join(DEVICES_DIR, DEVICE_PROFILE if DEVICE_PROFILE.endswith(".json") else DEVICE_PROFILE + ".json")
    if os.path.isfile(pfile):
        try:
            prof.update(json.loads(open(pfile, encoding="utf-8").read()))
            print("Profil ecran : " + str(prof.get("name")) + " (" + str(prof.get("width")) + "x" + str(prof.get("height")) + ")", flush=True)
        except Exception as e:
            print("Erreur profil ecran: " + str(e), flush=True)
    return prof

DEV_CFG = load_device_profile()
TARGET_W, TARGET_H = int(DEV_CFG["width"]), int(DEV_CFG["height"])
BAUDRATE = int(DEV_CFG["baudrate"])
HANDSHAKE_BYTES = bytes.fromhex(DEV_CFG["handshake_hex"]) if DEV_CFG.get("handshake_hex") else b""
FRAMING_MODE = DEV_CFG.get("framing", "uint32_jpeg_crc16")
JPEG_QUALITY = int(DEV_CFG.get("jpeg_quality", 85))

WIDTH, HEIGHT = 960, 480
BRIGHTNESS = int(os.getenv("SCREEN_BRIGHTNESS", "80"))
ROTATION = int(os.getenv("SCREEN_ROTATION", "0"))
INTERVAL = float(os.getenv("REFRESH_INTERVAL", "1"))
WALLPAPER_DIR = os.getenv("WALLPAPER_DIR", "/config/wallpapers")
SLIDESHOW_INTERVAL = int(os.getenv("SLIDESHOW_INTERVAL", "600"))
PAGE_SWITCH_INTERVAL = int(os.getenv("PAGE_SWITCH_INTERVAL", "30"))
BG_DIM = int(os.getenv("BG_DIM", "35"))
WEATHER_CITY = os.getenv("WEATHER_CITY", "Paris")
WEATHER_URL = os.getenv("WEATHER_URL", "").strip()
CLOCK_MODE = os.getenv("CLOCK_MODE", "analog").strip().lower()
CLOCK_COLOR = os.getenv("CLOCK_COLOR", "#3498db").strip()
HOUR_COLOR = os.getenv("HOUR_COLOR", "#ffffff").strip()
MIN_COLOR = os.getenv("MIN_COLOR", "#3498db").strip()
HOUR_WIDTH = int(os.getenv("HOUR_WIDTH", "10"))
MIN_WIDTH = int(os.getenv("MIN_WIDTH", "7"))
SEC_WIDTH = int(os.getenv("SEC_WIDTH", "3"))
CLOCK_NUMBERS = os.getenv("CLOCK_NUMBERS", "cardinal").strip().lower()
DIAL_COLOR = os.getenv("DIAL_COLOR", "#ffffff").strip()
DATE_COLOR = os.getenv("DATE_COLOR", "#3498db").strip()
DIAL_WIDTH = int(os.getenv("DIAL_WIDTH", "5"))
TICK_WIDTH = int(os.getenv("TICK_WIDTH", "5"))
NUM_SIZE = int(os.getenv("NUM_SIZE", "25"))
CLOCK_DATE_BOX = os.getenv("CLOCK_DATE_BOX", "true").strip().lower() in ("1", "true", "yes", "on")
CLOCK_SUB_DIG = os.getenv("CLOCK_SUB_DIG", "false").strip().lower() in ("1", "true", "yes", "on")
ALERT_ENABLED = os.getenv("ALERT_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
DIAL_LOGO = os.getenv("DIAL_LOGO", "unraid").strip().lower()
DIAL_LOGO_OPACITY = int(os.getenv("DIAL_LOGO_OPACITY", "65"))
DATE_LANG = os.getenv("DATE_LANG", "fr").strip().lower()
PAGE_ORDER_RAW = os.getenv("PAGE_ORDER", "1,2,3,4,5,6,7,8").strip()
NIGHT_MODE = os.getenv("NIGHT_MODE", "true").strip().lower() in ("1", "true", "yes", "on")
NIGHT_BRIGHTNESS = int(os.getenv("NIGHT_BRIGHTNESS", "15"))
CUSTOM_PAGE_BG = os.getenv("CUSTOM_PAGE_BG", "false").strip().lower() in ("1", "true", "yes", "on")
WALLPAPER_SHUFFLE = os.getenv("WALLPAPER_SHUFFLE", "false").strip().lower() in ("1", "true", "yes", "on")
API_PORT = int(os.getenv("API_PORT", "8799"))

def get_page_sequence():
    seq = []
    for part in PAGE_ORDER_RAW.split(","):
        p = part.strip()
        if p in ("1", "2", "3", "4", "5", "6", "7", "8"):
            seq.append(int(p) - 1)
    return seq if seq else [0, 1, 2, 3, 4, 5]

PAGE_SEQ = get_page_sequence()
_c_frames, _c_path, _c_mt, _c_fidx, _s_idx, _l_sw = [], None, 0, 0, 0, time.time()
_p_idx, _l_pw, _paused, _night_override = 0, time.time(), False, None
_dial_logo_cache = (None, 0, 0)
_hist_cpu, _hist_ram, _hist_net = [], [], []
_w_main, _w_sub, _w_extra, _w_rat, _l_wf, _coords, _sunrise_dt, _sunset_dt = "-- °C", "Chargement meteo...", "", 0.5, 0, None, None, None
_w_code, _w_is_day = 0, 1
_w_hourly, _w_daily = [], []

WMO = {0:"Ciel degage",1:"Peu nuageux",2:"Partiellement nuageux",3:"Couvert",45:"Brouillard",51:"Bruine",61:"Pluie faible",63:"Pluie",65:"Forte pluie",71:"Neige",80:"Averses",95:"Orage"}
JOURS = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
MOIS = ["","Janvier","Fevrier","Mars","Avril","Mai","Juin","Juillet","Aout","Septembre","Octobre","Novembre","Decembre"]
DAYS_EN = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
MONTHS_EN = ["","January","February","March","April","May","June","July","August","September","October","November","December"]

webui_module.apply_saved_settings(globals())

class RemoteHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        global DIAL_LOGO, _dial_logo_cache
        ln = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(ln)
        if self.path.startswith("/upload_wp"):
            ctype = self.headers.get("Content-Type", "")
            if "boundary=" in ctype:
                b_str = ctype.split("boundary=", 1).pop().strip().strip('"')
                boundary = ("--" + b_str).encode("utf-8")
                for part in raw.split(boundary):
                    if b"filename=" in part and b"\r\n\r\n" in part:
                        hdr, fdata = part.split(b"\r\n\r\n", 1)
                        if fdata.endswith(b"\r\n"):
                            fdata = fdata[:-2]
                        fname = "wall_" + str(int(time.time())) + ".jpg"
                        for seg in hdr.decode("utf-8", errors="ignore").split(";"):
                            if "filename=" in seg:
                                raw_fn = os.path.basename(seg.split("=", 1).pop().strip().strip('"'))
                                if raw_fn:
                                    fname = raw_fn
                        if len(fdata) > 10:
                            os.makedirs("/config/wallpapers", exist_ok=True)
                            open(os.path.join("/config/wallpapers", fname), "wb").write(fdata)
                            break
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if self.path.startswith("/upload_logo"):
            ctype = self.headers.get("Content-Type", "")
            if "boundary=" in ctype:
                b_str = ctype.split("boundary=", 1).pop().strip().strip('"')
                boundary = ("--" + b_str).encode("utf-8")
                for part in raw.split(boundary):
                    if b"filename=" in part and b"\r\n\r\n" in part:
                        fdata = part.split(b"\r\n\r\n", 1).pop()
                        if fdata.endswith(b"\r\n"):
                            fdata = fdata[:-2]
                        if len(fdata) > 10:
                            open("/config/dial_logo.png", "wb").write(fdata)
                            DIAL_LOGO = "custom"
                            _dial_logo_cache = (None, 0, 0)
                            if os.path.isfile("/config/settings.json"):
                                try:
                                    s = json.loads(open("/config/settings.json", encoding="utf-8").read())
                                    s["DIAL_LOGO"] = "custom"
                                    open("/config/settings.json", "w", encoding="utf-8").write(json.dumps(s, indent=2))
                                except Exception:
                                    pass
                            break
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        body = raw.decode("utf-8", errors="ignore")
        webui_module.save_web_settings(body, globals())
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def do_GET(self):
        global _p_idx, _l_pw, _paused, _night_override
        path = self.path.split("?")[0].strip("/").lower()
        if path == "":
            html = webui_module.render_html(globals(), PAGE_SEQ[_p_idx % len(PAGE_SEQ)] + 1, _paused)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return
        if path == "del_wp" and "f=" in self.path:
            import urllib.parse
            fn = os.path.basename(urllib.parse.unquote(self.path.split("f=", 1).pop().split("&").pop(0)))
            fp = os.path.join("/config/wallpapers", fn)
            if os.path.isfile(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if path == "preview.jpg":
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            self.wfile.write(webui_module._last_jpeg)
            return
        if path == "icon.png" and os.path.isfile("/config/icon.png"):
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(open("/config/icon.png", "rb").read())
            return

        msg = "OK"
        if path == "next":
            _p_idx, _l_pw = (_p_idx + 1) % len(PAGE_SEQ), time.time()
            msg = "Page suivante"
        elif path == "prev":
            _p_idx, _l_pw = (_p_idx - 1) % len(PAGE_SEQ), time.time()
            msg = "Page precedente"
        elif path == "pause":
            _paused = not _paused
            _l_pw = time.time()
            msg = "Pause: " + str(_paused)
        elif path == "night/toggle":
            cur_n = NIGHT_MODE if _night_override is None else _night_override
            _night_override = not cur_n
            msg = "Mode nuit: " + str(_night_override)
        elif path.startswith("page/"):
            try:
                num = int(path.split("/").pop())
                if 1 <= num <= 8:
                    target = num - 1
                    _p_idx = PAGE_SEQ.index(target) if target in PAGE_SEQ else 0
                    _l_pw = time.time()
                    msg = "Page " + str(num)
            except Exception:
                pass
        elif path == "status":
            msg = json.dumps({
                "page": PAGE_SEQ[_p_idx % len(PAGE_SEQ)] + 1,
                "paused": _paused,
                "night": (NIGHT_MODE if _night_override is None else _night_override)
            })
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(msg.encode("utf-8"))

def start_api():
    for p in range(API_PORT, API_PORT + 20):
        try:
            srv = ThreadingHTTPServer(("0.0.0.0", p), RemoteHandler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            print(f"Interface Web & API demarrees sur le port {p}", flush=True)
            return
        except OSError:
            continue

def get_active_brightness():
    nm = NIGHT_MODE if _night_override is None else _night_override
    if not nm:
        return BRIGHTNESS
    now_dt = datetime.now()
    if _sunrise_dt is not None and _sunset_dt is not None:
        return NIGHT_BRIGHTNESS if (now_dt < _sunrise_dt or now_dt >= _sunset_dt) else BRIGHTNESS
    if now_dt.hour >= 21 or now_dt.hour < 7 or (now_dt.hour == 7 and now_dt.minute < 30):
        return NIGHT_BRIGHTNESS
    return BRIGHTNESS

def _om_get_json(host, path_query):
    import ssl, http.client
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    # Connexion directe par IP (188.114.97.2) avec SNI TLS exact -> zero DNS requis
    raw_sock = socket.create_connection(("188.114.97.2", 443), timeout=6)
    tls_sock = ctx.wrap_socket(raw_sock, server_hostname=host)
    conn = http.client.HTTPSConnection(host, timeout=6, context=ctx)
    conn.sock = tls_sock
    conn.request("GET", path_query, headers={"Host": host, "User-Agent": "OcypusES55/1.0", "Accept": "application/json"})
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()
    return json.loads(body)

def update_weather():
    global _w_main, _w_sub, _w_extra, _w_rat, _l_wf, _coords, _sunrise_dt, _sunset_dt, _w_code, _w_hourly, _w_daily
    if _w_hourly and _w_daily and (time.time() - _l_wf < 900):
        return
    if (not _w_hourly or not _w_daily) and (time.time() - _l_wf < 15):
        return
    _l_wf = time.time()
    try:
        city_clean = str(WEATHER_CITY or "Paris").strip()
        if _coords is None:
            g = _om_get_json("geocoding-api." + "open-meteo.com", "/v1/search?name=" + urllib.request.quote(city_clean) + "&count=1&language=fr&format=json")
            res_list = g.get("results") or []
            if res_list:
                r = next(iter(res_list))
                _coords = (r["latitude"], r["longitude"], r["name"])
        if _coords:
            lat, lon, cn = _coords
            pq = f"/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m&hourly=temperature_2m,weather_code,precipitation_probability&daily=weather_code,temperature_2m_min,temperature_2m_max,precipitation_probability_max,sunrise,sunset&forecast_days=7&timezone=auto"
            data = _om_get_json("api." + "open-meteo.com", pq)
            cur, daily = data.get("current", {}), data.get("daily", {})
            sr, ss = daily.get("sunrise", []), daily.get("sunset", [])
            if sr and ss:
                try:
                    _sunrise_dt = datetime.fromisoformat(next(iter(sr)))
                    _sunset_dt = datetime.fromisoformat(next(iter(ss)))
                except Exception:
                    pass
            t = float(cur.get("temperature_2m", 0.0))
            app_t = cur.get("apparent_temperature")
            hum = cur.get("relative_humidity_2m", "--")
            wind = cur.get("wind_speed_10m")
            _w_code = int(cur.get("weather_code", 0))
            desc = WMO.get(_w_code, "Variable")
            tmin = next(iter(daily.get("temperature_2m_min", [])), None)
            tmax = next(iter(daily.get("temperature_2m_max", [])), None)
            ress = f" (Ress. {app_t:.0f}°)" if app_t is not None else ""
            _w_main = f"{t:.1f}°C{ress}"
            _w_sub = f"{cn} | {desc}" + (f" | Vent {wind:.0f} km/h" if wind is not None else "")
            _w_extra = (f"Min {tmin:.0f}° / Max {tmax:.0f}° | " if (tmin is not None and tmax is not None) else "") + f"Humidite {hum}%"
            _w_rat = min(1.0, max(0.05, (t + 5.0) / 40.0))
            hr = data.get("hourly", {})
            now_iso = datetime.now().strftime("%Y-%m-%dT%H:00")
            new_h = []
            for ts_s, tp_v, cd_v, pr_v in zip(hr.get("time", []), hr.get("temperature_2m", []), hr.get("weather_code", []), hr.get("precipitation_probability", [])):
                if ts_s >= now_iso:
                    hh_lbl = ts_s.split("T").pop()[:5] if "T" in ts_s else ts_s[-5:]
                    new_h.append((hh_lbl, float(tp_v), int(cd_v or 0), int(pr_v or 0)))
                    if len(new_h) >= 8:
                        break
            if new_h:
                _w_hourly = new_h

            J_SHORT = ("Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim")
            D_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
            new_d = []
            for idx_day, (dt_s, dc_v, mn_v, mx_v, pr_v) in enumerate(zip(
                daily.get("time", []),
                daily.get("weather_code", []),
                daily.get("temperature_2m_min", []),
                daily.get("temperature_2m_max", []),
                daily.get("precipitation_probability_max", [])
            )):
                try:
                    wd_i = datetime.fromisoformat(dt_s).weekday()
                    dlbl = ("Auj." if DATE_LANG != "en" else "Today") if idx_day == 0 else (D_SHORT[wd_i] if DATE_LANG == "en" else J_SHORT[wd_i])
                except Exception:
                    dlbl = dt_s[-5:]
                new_d.append((dlbl, int(dc_v or 0), float(mn_v), float(mx_v), int(pr_v or 0)))
            if new_d:
                _w_daily = new_d[:7]
            print(f"Meteo OK ({cn}) : {_w_main} | {len(_w_hourly)}h & {len(_w_daily)}j", flush=True)
    except Exception as e:
        print("Erreur meteo Page 2 :", repr(e), flush=True)

def find_page_bg(pnum):
    if not WALLPAPER_DIR or not os.path.isdir(WALLPAPER_DIR):
        return None
    for ext in ("gif","jpg","jpeg","png","webp","GIF","JPG","PNG"):
        cand = os.path.join(WALLPAPER_DIR, f"page{pnum}.{ext}")
        if os.path.isfile(cand):
            return cand
    return None

def load_bg(cur_p=0):
    global _c_frames, _c_path, _c_mt, _c_fidx, _s_idx, _l_sw
    tp = find_page_bg(cur_p + 1) if CUSTOM_PAGE_BG else None
    if not tp:
        all_fs = sum([glob.glob(os.path.join(WALLPAPER_DIR, e)) for e in ("*.gif","*.jpg","*.jpeg","*.png","*.webp","*.GIF","*.JPG","*.PNG")], []) if os.path.isdir(WALLPAPER_DIR) else []
        other_fs = [f for f in all_fs if not os.path.basename(f).lower().startswith(("page1.","page2.","page3.","page4.","page5.","page6."))]
        fs = sorted(list(set(other_fs if other_fs else all_fs)))
        if not fs:
            return Image.new("RGBA", (WIDTH, HEIGHT), (14, 17, 23, 255))
        if len(fs) > 1 and (time.time() - _l_sw) >= max(5, SLIDESHOW_INTERVAL):
            _s_idx = random.choice([i for i in range(len(fs)) if i != _s_idx]) if WALLPAPER_SHUFFLE else ((_s_idx + 1) % len(fs))
            _l_sw = time.time()
        if _s_idx >= len(fs):
            _s_idx = 0
        tp = fs[_s_idx]
    try:
        mt = os.path.getmtime(tp)
        if not _c_frames or tp != _c_path or mt != _c_mt:
            im = Image.open(tp)
            frames = []
            for fr in ImageSequence.Iterator(im):
                fit = ImageOps.fit(fr.convert("RGB"), (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
                if BG_DIM > 0:
                    fit = ImageEnhance.Brightness(fit).enhance(max(0.1, 1.0 - BG_DIM / 100.0))
                frames.append(fit.convert("RGBA"))
            _c_frames, _c_path, _c_mt, _c_fidx = frames[:60], tp, mt, 0
        frame = _c_frames[_c_fidx % len(_c_frames)]
        _c_fidx = (_c_fidx + 1) % len(_c_frames)
        return frame.copy()
    except Exception:
        return Image.new("RGBA", (WIDTH, HEIGHT), (14, 17, 23, 255))

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "IP inconnue"

def get_cpu_t():
    try:
        ts = psutil.sensors_temperatures()
        for k in ("coretemp","k10temp","zenpower","acpitz"):
            if k in ts and ts[k]:
                return int(ts[k][0].current)
    except Exception:
        pass
    return None

def get_disks():
    ts, act = [], 0
    if os.path.isfile("/unraid_emhttp/disks.ini"):
        try:
            for l in open("/unraid_emhttp/disks.ini", encoding="utf-8", errors="ignore"):
                l = l.strip()
                if l.startswith('temp="'):
                    v = l.split('"')[1]
                    if v.isdigit():
                        ts.append(int(v))
                elif l.startswith('color="') and "green-on" in l:
                    act += 1
        except Exception:
            pass
    if ts:
        mx = max(ts)
        return mx, f"{mx}\u00b0C", f"Moy: {sum(ts)/len(ts):.0f}\u00b0C | {act} actif(s)", min(1.0, mx / 60.0)
    return 0, "Veille", f"{act} disque(s) actif(s)", 0.1

def get_unraid_var():
    info = {"mdState": "INCONNU", "mdResync": "0", "mdResyncPos": "0", "mdResyncSize": "1", "sbSynced": "0", "sbSyncErrs": "0"}
    if os.path.isfile("/unraid_emhttp/var.ini"):
        try:
            for l in open("/unraid_emhttp/var.ini", encoding="utf-8", errors="ignore"):
                if "=" in l:
                    k, v = l.strip().split("=", 1)
                    if k in info:
                        info[k] = v.strip('"')
        except Exception:
            pass
    up_sec = int(time.time() - psutil.boot_time())
    days, rem = divmod(up_sec, 86400)
    hours, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    up_str = f"{days}j {hours}h {mins}m"
    load1, load5, _ = os.getloadavg()
    if info["mdResync"] != "0" and info["mdResync"] != "":
        try:
            pct = (float(info["mdResyncPos"]) / max(1.0, float(info["mdResyncSize"]))) * 100.0
            par_main, par_sub, par_rat = f"Sync {pct:.1f}%", "Verification parite en cours", pct / 100.0
        except Exception:
            par_main, par_sub, par_rat = "En cours", "Verification parite", 0.5
    else:
        errs = info["sbSyncErrs"]
        try:
            ts_sync = int(info["sbSynced"])
            dt_sync = datetime.fromtimestamp(ts_sync).strftime("%d/%m/%Y") if ts_sync > 0 else "N/A"
        except Exception:
            dt_sync = "N/A"
        par_main = "Valide (0 err)" if errs == "0" else f"{errs} erreur(s)"
        par_sub = f"Dernier controle : {dt_sync}"
        par_rat = 1.0 if errs == "0" else 0.2
    return up_str, f"Load: {load1:.2f} / {load5:.2f}", info["mdState"], par_main, par_sub, par_rat
def get_docker():
    if not os.path.exists("/var/run/docker.sock"):
        return "N/A", "Socket absente", 0.0
    try:
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.settimeout(1.5)
        c.connect("/var/run/docker.sock")
        c.sendall(b"GET /containers/json?all=1 HTTP/1.0\r\nHost: localhost\r\n\r\n")
        r = b""
        while True:
            ch = c.recv(4096)
            if not ch:
                break
            r += ch
        c.close()
        cs = json.loads(r[r.find(b"\r\n\r\n") + 4:].decode("utf-8", errors="ignore"))
        tot, run = len(cs), sum(1 for x in cs if x.get("State") == "running")
        return f"{run} / {tot}", f"{tot - run} arrete(s)", (run / tot if tot > 0 else 0.0)
    except Exception:
        return "Erreur", "Lecture Docker", 0.0

def get_running_dockers():
    if not os.path.exists("/var/run/docker.sock"):
        return [], 0
    try:
        host_ip = get_ip()
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.settimeout(1.5)
        c.connect("/var/run/docker.sock")
        c.sendall(b"GET /containers/json HTTP/1.0\r\nHost: localhost\r\n\r\n")
        r = b""
        while True:
            ch = c.recv(4096)
            if not ch:
                break
            r += ch
        c.close()
        cs = json.loads(r[r.find(b"\r\n\r\n") + 4:].decode("utf-8", errors="ignore"))
        items = []
        for x in cs:
            names = x.get("Names") or ["/inconnu"]
            name = names[0].lstrip("/")
            nets = x.get("NetworkSettings", {}).get("Networks", {})
            c_ip = ""
            net_mode = x.get("HostConfig", {}).get("NetworkMode", "") or "host"
            for n_info in nets.values():
                ip_val = n_info.get("IPAddress", "")
                if ip_val and not ip_val.startswith("172."):
                    c_ip = ip_val
                    break
            if not c_ip:
                c_ip = host_ip
            ports = x.get("Ports", [])
            pub = sorted(list(set(str(p["PublicPort"]) for p in ports if "PublicPort" in p)))
            priv = sorted(list(set(str(p["PrivatePort"]) for p in ports if "PrivatePort" in p)))
            if pub:
                addr = f"{c_ip}:{pub[0]}" + (f" (+{len(pub)-1})" if len(pub) > 1 else "")
            elif priv:
                addr = f"{c_ip}:{priv[0]}" + (f" (+{len(priv)-1})" if len(priv) > 1 else "")
            else:
                addr = f"{c_ip} ({net_mode})"
            items.append((name, addr))
        items.sort(key=lambda t: t[0].lower())
        return items, len(items)
    except Exception:
        return [], 0

def get_unraid_vms():
    if not os.path.isdir("/unraid_vms_xml"):
        return [], 0, 0
    vms = []
    try:
        for fn in os.listdir("/unraid_vms_xml"):
            if fn.endswith(".xml"):
                vn = fn[:-4]
                vms.append((vn, os.path.isfile(os.path.join("/unraid_vms_run", vn + ".pid"))))
        vms.sort(key=lambda x: (not x[1], x[0].lower()))
        return vms, sum(1 for _, r in vms if r), len(vms)
    except Exception:
        return [], 0, 0

def draw_weather_icon(draw, cx, cy):
    c = _w_code
    has_rain = c in (51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99)
    has_snow = c in (71, 73, 75, 77, 85, 86)
    has_thunder = c in (95, 96, 99)
    is_fog = c in (45, 48)
    has_cloud = c in (2, 3, 45, 48, 51, 53, 55, 61, 63, 65, 71, 73, 75, 80, 81, 82, 85, 86, 95)

    def draw_cloud(ox, oy, col=(225, 235, 248, 250)):
        draw.ellipse([ox - 38, oy - 13, ox - 4, oy + 21], fill=col)
        draw.ellipse([ox - 21, oy - 28, ox + 21, oy + 15], fill=col)
        draw.ellipse([ox + 6, oy - 15, ox + 40, oy + 19], fill=col)
        draw.rectangle([ox - 24, oy + 2, ox + 25, oy + 21], fill=col)

    # Soleil (degage ou partiellement nuageux)
    if c in (0, 1, 2):
        sx, sy = (cx - 15, cy - 14) if c in (1, 2) else (cx, cy)
        sr = 24 if c in (1, 2) else 32
        s_col = (255, 204, 51, 255)
        for a in range(0, 360, 45):
            rad_a = math.radians(a)
            draw.line([sx + (sr + 5) * math.cos(rad_a), sy + (sr + 5) * math.sin(rad_a),
                       sx + (sr + 15) * math.cos(rad_a), sy + (sr + 15) * math.sin(rad_a)], fill=s_col, width=4)
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=s_col)

    # Brouillard ou Nuage
    if is_fog:
        for fy in (-18, -6, 6, 18):
            draw.line([cx - 34, cy + fy, cx + 34, cy + fy], fill=(200, 210, 225, 230), width=4)
    elif has_cloud or c == 1:
        draw_cloud(cx + (8 if c in (1, 2) else 0), cy - 4)

    # Pluie, Neige ou Orage
    if has_rain:
        for rx_off in (-18, 0, 18):
            draw.line([cx + rx_off, cy + 23, cx + rx_off - 7, cy + 37], fill=(56, 189, 248, 255), width=4)
    if has_snow:
        for sx_off in (-18, 0, 18):
            draw.ellipse([cx + sx_off - 4, cy + 24, cx + sx_off + 4, cy + 32], fill=(255, 255, 255, 255))
            draw.ellipse([cx + sx_off - 9, cy + 35, cx + sx_off - 3, cy + 41], fill=(220, 240, 255, 240))
    if has_thunder:
        draw.polygon([(cx + 3, cy + 17), (cx - 8, cy + 33), (cx + 2, cy + 33), (cx - 5, cy + 47), (cx + 12, cy + 27), (cx + 3, cy + 27)], fill=(250, 204, 21, 255))

def draw_clock_page(draw, f_xl, f_md, f_sm, rx, tx):
    global _dial_logo_cache
    dtn = datetime.now()
    wd, mn = dtn.weekday(), dtn.month
    date_str = f"{DAYS_EN[wd]}, {MONTHS_EN[mn]} {dtn.day}, {dtn.year}" if DATE_LANG == "en" else f"{JOURS[wd]} {dtn.day} {MOIS[mn]} {dtn.year}"
    draw.rounded_rectangle([20, 20, 450, HEIGHT - 24], radius=18, fill=(18, 22, 30, 175), outline=(255, 255, 255, 45), width=2)
    if CLOCK_MODE == "digital":
        hx_d = DATE_COLOR.lstrip("#")
        dt_rgb = tuple(int(hx_d[i:i+2], 16) for i in (0, 2, 4)) + (255,) if len(hx_d) == 6 else (52, 152, 219, 255)
        draw.text((42, 38), date_str, fill=dt_rgb, font=f_md)
        try:
            f_huge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 110)
        except Exception:
            f_huge = f_xl
        hx = CLOCK_COLOR.lstrip("#")
        bar_rgb = tuple(int(hx[i:i+2], 16) for i in (0, 2, 4)) + (240,) if len(hx) == 6 else (52, 152, 219, 240)
        draw.text((42, 85), dtn.strftime("%H:%M"), fill=(255, 255, 255, 255), font=f_huge)

        # Afficher le logo (personnalise ou Unraid) dans l'espace libere sous HH:MM
        alpha_factor = max(0.1, min(1.0, int(DIAL_LOGO_OPACITY) / 100.0))
        if DIAL_LOGO == "custom" and os.path.isfile("/config/dial_logo.png"):
            try:
                mt_l = os.path.getmtime("/config/dial_logo.png")
                c_img, c_mt, c_op = _dial_logo_cache
                if c_img is None or c_mt != mt_l or c_op != DIAL_LOGO_OPACITY:
                    lim = Image.open("/config/dial_logo.png").convert("RGBA")
                    lim.thumbnail((135, 135), Image.Resampling.LANCZOS)
                    r_ch, g_ch, b_ch, a_ch = lim.split()
                    a_ch = a_ch.point(lambda p: int(p * alpha_factor))
                    lim = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))
                    _dial_logo_cache = (lim, mt_l, DIAL_LOGO_OPACITY)
                else:
                    lim = c_img
                lw, lh = lim.size
                ov.alpha_composite(lim, (235 - lw // 2, 295 - lh // 2))
            except Exception:
                pass
        elif DIAL_LOGO == "unraid":
            bars = (
                (-48, -22, 22, (226, 40, 40)),
                (-36,  -5, 22, (231, 56, 38)),
                (-24, -15,  5, (236, 72, 36)),
                (-12, -22, -2, (241, 88, 34)),
                (  0,  -8, 12, (245, 104, 33)),
                ( 12, -22, -2, (248, 118, 32)),
                ( 24, -15,  5, (251, 130, 34)),
                ( 36,  -5, 22, (253, 140, 38)),
                ( 48, -22, 22, (255, 148, 42)),
            )
            ly = 295
            a_val = int(235 * alpha_factor)
            for bx_off, y_top, y_bot, rgb in bars:
                r_b, g_b, b_b = rgb
                draw.rectangle([235 + bx_off - 3, ly + y_top, 235 + bx_off + 3, ly + y_bot], fill=(r_b, g_b, b_b, a_val))

        bx, by, bw, bh = 42, HEIGHT - 66, 386, 20
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=10, fill=(255, 255, 255, 35))
        fill_w = max(12, int(bw * (dtn.second / 59.0))) if dtn.second > 0 else 12
        draw.rounded_rectangle([bx, by, bx + fill_w, by + bh], radius=10, fill=bar_rgb)
    else:
        def hex_rgba(h_str, def_rgb):
            h_c = h_str.lstrip("#")
            if len(h_c) == 6:
                return (int(h_c[0:2], 16), int(h_c[2:4], 16), int(h_c[4:6], 16), 255)
            return def_rgb

        dial_rgb = hex_rgba(DIAL_COLOR, (255, 255, 255, 255))
        rd, gd, bd, _ = dial_rgb
        dial_dim = (rd, gd, bd, 95)
        hr_rgb = hex_rgba(HOUR_COLOR, (255, 255, 255, 255))
        mn_rgb = hex_rgba(MIN_COLOR, (52, 152, 219, 255))
        sec_rgb = hex_rgba(CLOCK_COLOR, (231, 76, 60, 255))

        cx, cy, rad = 235, 238, 175
        draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(14, 18, 26, 215), outline=dial_rgb, width=max(1, int(DIAL_WIDTH)))
        for m in range(60):
            ang = math.radians(m * 6 - 90)
            r1, r2 = rad - (18 if m % 5 == 0 else 9), rad - max(3, int(DIAL_WIDTH // 2))
            draw.line([cx + r1 * math.cos(ang), cy + r1 * math.sin(ang), cx + r2 * math.cos(ang), cy + r2 * math.sin(ang)],
                      fill=(dial_rgb if m % 5 == 0 else dial_dim), width=(max(1, int(TICK_WIDTH)) if m % 5 == 0 else max(1, int(TICK_WIDTH // 2))))

        if CLOCK_NUMBERS in ("cardinal", "all"):
            try:
                f_num = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", max(12, int(NUM_SIZE)))
            except Exception:
                f_num = f_sm
            num_r = rad - (24 + int(NUM_SIZE * 0.55))
            for h_num in range(1, 13):
                if CLOCK_NUMBERS == "cardinal" and h_num not in (12, 3, 6, 9):
                    continue
                if CLOCK_DATE_BOX and h_num == 3:
                    continue
                n_ang = math.radians(h_num * 30 - 90)
                nx, ny = cx + num_r * math.cos(n_ang), cy + num_r * math.sin(n_ang)
                txt = str(h_num)
                bx0, by0, bx1, by1 = draw.textbbox((0, 0), txt, font=f_num)
                draw.text((nx - (bx1 - bx0) / 2, ny - (by1 - by0) / 2 - 2), txt, fill=dial_rgb, font=f_num)

        if CLOCK_DATE_BOX:
            MOIS_3 = ("", "JAN", "FEV", "MAR", "AVR", "MAI", "JUN", "JUL", "AOU", "SEP", "OCT", "NOV", "DEC")
            MON_3 = ("", "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
            m_txt = MON_3[mn] if DATE_LANG == "en" else MOIS_3[mn]
            d_txt = f"{dtn.day:02d}"
            try:
                f_box = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
            except Exception:
                f_box = f_sm
            bx1, by1 = cx + 62, cy - 13
            draw.rounded_rectangle([bx1, by1, bx1 + 30, by1 + 26], radius=4, fill=(255, 255, 255, 245), outline=(40, 45, 55, 255), width=1)
            draw.rounded_rectangle([bx1 + 34, by1, bx1 + 78, by1 + 26], radius=4, fill=(255, 255, 255, 245), outline=(40, 45, 55, 255), width=1)
            x0a, y0a, x1a, y1a = draw.textbbox((0, 0), d_txt, font=f_box)
            x0b, y0b, x1b, y1b = draw.textbbox((0, 0), m_txt, font=f_box)
            draw.text((bx1 + 15 - (x1a - x0a) / 2, by1 + 13 - (y1a - y0a) / 2 - 1), d_txt, fill=(10, 12, 16, 255), font=f_box)
            draw.text((bx1 + 56 - (x1b - x0b) / 2, by1 + 13 - (y1b - y0b) / 2 - 1), m_txt, fill=(10, 12, 16, 255), font=f_box)

        if CLOCK_SUB_DIG:
            try:
                f_subd = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 19)
            except Exception:
                f_subd = f_sm
            stxt = dtn.strftime("%H:%M")
            sx0a, sy0a, sx1a, sy1a = draw.textbbox((0, 0), stxt, font=f_subd)
            sw, sh = sx1a - sx0a, sy1a - sy0a
            sx0, sy0 = cx - sw // 2 - 8, cy + 52
            draw.rounded_rectangle([sx0, sy0, sx0 + sw + 16, sy0 + sh + 10], radius=6, fill=(10, 14, 22, 220), outline=dial_dim, width=1)
            draw.text((cx - sw / 2, sy0 + 4), stxt, fill=dial_rgb, font=f_subd)

        # Logo du cadran (Unraid integre ou image personnalisee /config/dial_logo.png)
        alpha_factor = max(0.1, min(1.0, int(DIAL_LOGO_OPACITY) / 100.0))
        if DIAL_LOGO == "custom" and os.path.isfile("/config/dial_logo.png"):
            try:
                mt_l = os.path.getmtime("/config/dial_logo.png")
                c_img, c_mt, c_op = _dial_logo_cache
                if c_img is None or c_mt != mt_l or c_op != DIAL_LOGO_OPACITY:
                    lim = Image.open("/config/dial_logo.png").convert("RGBA")
                    lim.thumbnail((88, 88), Image.Resampling.LANCZOS)
                    r_ch, g_ch, b_ch, a_ch = lim.split()
                    a_ch = a_ch.point(lambda p: int(p * alpha_factor))
                    lim = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))
                    _dial_logo_cache = (lim, mt_l, DIAL_LOGO_OPACITY)
                else:
                    lim = c_img
                lw, lh = lim.size
                ov.alpha_composite(lim, (cx - lw // 2, cy - 52 - lh // 2))
            except Exception:
                pass
        elif DIAL_LOGO == "unraid":
            # Reproduction fidèle du logo officiel Unraid à 9 barres verticales (dégradé rouge -> orange)
            # Format : (decalage_x, y_haut, y_bas, (R, G, B))
            bars = (
                (-40, -18, 18, (226, 40, 40)),   # Barre 1 (Grande gauche)
                (-30,  -4, 18, (231, 56, 38)),   # Barre 2 (Basse)
                (-20, -12,  4, (236, 72, 36)),   # Barre 3 (Flottante haute)
                (-10, -18, -2, (241, 88, 34)),   # Barre 4 (Pic gauche)
                (  0,  -6, 10, (245, 104, 33)),  # Barre 5 (Centre)
                ( 10, -18, -2, (248, 118, 32)),  # Barre 6 (Pic droit)
                ( 20, -12,  4, (251, 130, 34)),  # Barre 7 (Flottante haute)
                ( 30,  -4, 18, (253, 140, 38)),  # Barre 8 (Basse)
                ( 40, -18, 18, (255, 148, 42)),  # Barre 9 (Grande droite)
            )
            ly = cy - 46
            a_val = int(235 * alpha_factor)
            for bx_off, y_top, y_bot, rgb in bars:
                r_b, g_b, b_b = rgb
                draw.rectangle([cx + bx_off - 2, ly + y_top, cx + bx_off + 2, ly + y_bot], fill=(r_b, g_b, b_b, a_val))

        h_ang = math.radians(((dtn.hour % 12) + dtn.minute / 60.0) * 30 - 90)
        draw.line([cx, cy, cx + 92 * math.cos(h_ang), cy + 92 * math.sin(h_ang)], fill=hr_rgb, width=max(1, int(HOUR_WIDTH)))
        m_ang = math.radians((dtn.minute + dtn.second / 60.0) * 6 - 90)
        draw.line([cx, cy, cx + 136 * math.cos(m_ang), cy + 136 * math.sin(m_ang)], fill=mn_rgb, width=max(1, int(MIN_WIDTH)))
        s_ang = math.radians(dtn.second * 6 - 90)
        tx_back, ty_back = cx - 28 * math.cos(s_ang), cy - 28 * math.sin(s_ang)
        draw.line([tx_back, ty_back, cx + 152 * math.cos(s_ang), cy + 152 * math.sin(s_ang)], fill=sec_rgb, width=max(1, int(SEC_WIDTH)))
        draw.ellipse([tx_back - 5, ty_back - 5, tx_back + 5, ty_back + 5], fill=sec_rgb)
        c_rad = max(7, int(max(HOUR_WIDTH, MIN_WIDTH) * 0.9))
        draw.ellipse([cx - c_rad, cy - c_rad, cx + c_rad, cy + c_rad], fill=hr_rgb)
        draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=sec_rgb)

    draw.rounded_rectangle([470, 20, WIDTH - 20, 275], radius=18, fill=(18, 22, 30, 175), outline=(255, 255, 255, 45), width=2)
    draw_weather_icon(draw, WIDTH - 74, 112)
    try:
        f_wbig = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except Exception:
        f_wbig = f_xl
    t_only = _w_main.split(" (").pop(0)
    ress_only = "(" + _w_main.split(" (").pop() if " (" in _w_main else ""
    draw.text((492, 36), t_only, fill=(255, 255, 255, 255), font=f_wbig)
    if ress_only:
        draw.text((492, 86), ress_only, fill=(180, 200, 225, 255), font=f_sm)
    draw.text((492, 130), _w_sub, fill=(215, 225, 240, 255), font=f_sm)
    draw.text((492, 162), _w_extra, fill=(185, 200, 220, 255), font=f_sm)
    bx, by, bw, bh = 492, 216, WIDTH - 534, 18
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=9, fill=(255, 255, 255, 35))
    draw.rounded_rectangle([bx, by, bx + max(10, int(bw * _w_rat)), by + bh], radius=9, fill=(241, 196, 15, 235))

    draw.rounded_rectangle([470, 292, WIDTH - 20, HEIGHT - 24], radius=18, fill=(18, 22, 30, 175), outline=(255, 255, 255, 45), width=2)
    draw.text((492, 312), ("NETWORK & SYSTEM" if DATE_LANG == "en" else "RESEAU & SYSTEME"), fill=(155, 89, 182, 255), font=f_md)
    draw.text((492, 355), f"\u2193 {rx:.1f} Mo/s   \u2191 {tx:.1f} Mo/s", fill=(255, 255, 255, 255), font=f_md)
    draw.text((492, 398), f"CPU: {psutil.cpu_percent(interval=None):.0f}%  |  RAM: {psutil.virtual_memory().percent:.0f}%", fill=(215, 225, 240, 255), font=f_sm)

def get_detailed_disks():
    res = []
    if not os.path.isfile("/unraid_emhttp/disks.ini"):
        return res
    try:
        cur = {}
        for line in open("/unraid_emhttp/disks.ini", encoding="utf-8", errors="ignore"):
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                if cur.get("name"):
                    res.append(cur)
                cur = {"name": s[1:-1].strip(chr(34))}
            elif "=" in s:
                k, v = s.split("=", 1)
                cur[k.strip()] = v.strip().strip('"')
        if cur.get("name"):
            res.append(cur)
    except Exception:
        pass
    out = []
    for d in res:
        nm = d.get("name", "")
        dev = d.get("device", "")
        if not dev and d.get("status") == "DISK_NP":
            continue
        t_raw = d.get("temp", "*")
        t_val = int(t_raw) if t_raw.isdigit() else None
        spundown = (t_val is None or d.get("color", "").endswith("blink"))
        sz_kb = int(d.get("size", 0)) if d.get("size", "0").isdigit() else 0
        fs_free = int(d.get("fsFree", 0)) if d.get("fsFree", "0").isdigit() else 0
        fs_size = int(d.get("fsSize", 0)) if d.get("fsSize", "0").isdigit() else 0
        pct = ((fs_size - fs_free) / fs_size) if fs_size > 0 else 0.0
        out.append((nm, t_val, spundown, pct, sz_kb))
    return out

def draw_sparkline(draw, x, y, w, h, hist, col):
    if len(hist) < 2:
        return
    pts = []
    step = w / max(1, len(hist) - 1)
    for idx, val in enumerate(hist):
        v_clamped = max(0.0, min(1.0, float(val)))
        px = x + idx * step
        py = y + h - (v_clamped * h)
        pts.append((px, py))
    draw.line(pts, fill=col, width=3)

def draw_disks_page(draw, f_xl, f_md, f_sm):
    disks = get_detailed_disks()
    draw.rounded_rectangle([20, 20, WIDTH - 20, HEIGHT - 24], radius=18, fill=(18, 22, 30, 178), outline=(255, 255, 255, 45), width=2)
    draw.text((42, 32), f"ETAT INDIVIDUEL DES DISQUES UNRAID ({len(disks)})", fill=(56, 189, 248, 255), font=f_md)
    if not disks:
        draw.text((42, 100), "Fichier disks.ini non disponible", fill=(215, 225, 240, 255), font=f_sm)
        return
    for i, (nm, t_val, spundown, pct, sz_kb) in enumerate(disks[:12]):
        col_i, row_i = i // 6, i % 6
        dx, dy = 42 + col_i * 450, 78 + row_i * 59
        dot_c = (148, 163, 184, 220) if spundown else ((231, 76, 60, 255) if (t_val and t_val >= 48) else (46, 204, 113, 255))
        draw.ellipse([dx, dy + 8, dx + 13, dy + 21], fill=dot_c)
        lbl = nm.capitalize()
        draw.text((dx + 22, dy + 2), lbl[:14], fill=(255, 255, 255, 255), font=f_md)
        st_txt = "Veille (Spindown)" if spundown else f"{t_val}°C  |  {int(pct * 100)}% plein"
        t_col = (148, 163, 184, 230) if spundown else ((231, 76, 60, 255) if (t_val and t_val >= 48) else ((243, 156, 18, 255) if (t_val and t_val >= 42) else (200, 215, 235, 255)))
        draw.text((dx + 175, dy + 5), st_txt, fill=t_col, font=f_sm)
        if pct > 0:
            draw.rounded_rectangle([dx + 22, dy + 35, dx + 410, dy + 43], radius=4, fill=(255, 255, 255, 30))
            draw.rounded_rectangle([dx + 22, dy + 35, dx + 22 + max(6, int(388 * pct)), dy + 43], radius=4, fill=dot_c)

def draw_alert_overlay(draw, f_xl, f_md, alerts):
    if not alerts:
        return
    blink = (int(time.time() * 2) % 2 == 0)
    bg_c = (185, 28, 28, 235) if blink else (127, 29, 29, 235)
    bd_c = (254, 202, 202, 255) if blink else (248, 113, 113, 255)
    draw.rounded_rectangle([35, 70, WIDTH - 35, HEIGHT - 70], radius=24, fill=bg_c, outline=bd_c, width=5)
    draw.text((70, 105), "⚠️ ALERTE CRITIQUE SERVEUR UNRAID", fill=(255, 255, 255, 255), font=f_xl)
    for idx_a, msg_a in enumerate(alerts[:3]):
        draw.text((70, 195 + idx_a * 52), "• " + msg_a, fill=(254, 240, 138, 255), font=f_md)


def draw_mini_weather(draw, cx, cy, c, sc=0.65):
    has_rain = c in (51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99)
    has_snow = c in (71, 73, 75, 77, 85, 86)
    has_thunder = c in (95, 96, 99)
    is_fog = c in (45, 48)
    has_cloud = c in (2, 3, 45, 48, 51, 53, 55, 61, 63, 65, 71, 73, 75, 80, 81, 82, 85, 86, 95)

    if c in (0, 1, 2):
        sx, sy = (cx - int(8 * sc), cy - int(8 * sc)) if c in (1, 2) else (cx, cy)
        sr = int((14 if c in (1, 2) else 18) * sc)
        s_col = (255, 204, 51, 255)
        for a in range(0, 360, 45):
            ra = math.radians(a)
            draw.line([sx + (sr + 3) * math.cos(ra), sy + (sr + 3) * math.sin(ra),
                       sx + (sr + 8) * math.cos(ra), sy + (sr + 8) * math.sin(ra)], fill=s_col, width=2)
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=s_col)

    if is_fog:
        for fy in (-8, 0, 8):
            draw.line([cx - 16, cy + fy, cx + 16, cy + fy], fill=(200, 210, 225, 230), width=2)
    elif has_cloud or c == 1:
        ox, oy = cx + (int(4 * sc) if c in (1, 2) else 0), cy - int(2 * sc)
        col = (225, 235, 248, 250)
        draw.ellipse([ox - int(22 * sc), oy - int(8 * sc), ox - int(2 * sc), oy + int(12 * sc)], fill=col)
        draw.ellipse([ox - int(12 * sc), oy - int(16 * sc), ox + int(12 * sc), oy + int(8 * sc)], fill=col)
        draw.ellipse([ox + int(3 * sc), oy - int(9 * sc), ox + int(23 * sc), oy + int(11 * sc)], fill=col)
        draw.rectangle([ox - int(14 * sc), oy + int(1 * sc), ox + int(14 * sc), oy + int(12 * sc)], fill=col)

    if has_rain:
        for rx_o in (-8, 0, 8):
            draw.line([cx + rx_o, cy + int(12 * sc), cx + rx_o - 4, cy + int(22 * sc)], fill=(56, 189, 248, 255), width=2)
    if has_snow:
        for sx_o in (-8, 0, 8):
            draw.ellipse([cx + sx_o - 2, cy + int(14 * sc), cx + sx_o + 2, cy + int(18 * sc)], fill=(255, 255, 255, 255))
    if has_thunder:
        draw.line([cx + 2, cy + int(10 * sc), cx - 4, cy + int(22 * sc)], fill=(250, 204, 21, 255), width=2)

def draw_weather_full_page(draw, f_xl, f_md, f_sm):
    try:
        f_xs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        f_xs_r = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
    except Exception:
        f_xs = f_xs_r = f_sm

    # Carte superieure : Heure par heure (8h)
    draw.rounded_rectangle([20, 18, WIDTH - 20, 245], radius=18, fill=(18, 22, 30, 178), outline=(255, 255, 255, 45), width=2)
    title_h = ("HOURLY FORECAST (8H)" if DATE_LANG == "en" else "PREVISIONS HEURE PAR HEURE (8H)")
    draw.text((38, 30), f"{title_h} — {WEATHER_CITY.upper()} ({_w_main.split(' (').pop(0)})", fill=(56, 189, 248, 255), font=f_md)

    if not _w_hourly:
        draw.text((38, 110), "Actualisation des previsions en cours...", fill=(215, 225, 240, 255), font=f_sm)
    else:
        col_w = (WIDTH - 68) // len(_w_hourly)
        for i, (hh_s, tp_v, cd_v, pr_v) in enumerate(_w_hourly):
            cx = 34 + i * col_w + col_w // 2
            if i > 0:
                draw.line([34 + i * col_w, 72, 34 + i * col_w, 232], fill=(255, 255, 255, 25), width=1)
            bx0, _, bx1, _ = draw.textbbox((0, 0), hh_s, font=f_xs)
            draw.text((cx - (bx1 - bx0) / 2, 74), hh_s, fill=(195, 208, 225, 255), font=f_xs)
            draw_mini_weather(draw, cx, 126, cd_v, sc=0.68)
            t_str = f"{tp_v:.0f}°"
            tx0, _, tx1, _ = draw.textbbox((0, 0), t_str, font=f_md)
            draw.text((cx - (tx1 - tx0) / 2, 166), t_str, fill=(255, 255, 255, 255), font=f_md)
            p_str = f"{pr_v}%"
            px0, _, px1, _ = draw.textbbox((0, 0), p_str, font=f_xs_r)
            draw.text((cx - (px1 - px0) / 2, 202), p_str, fill=(56, 189, 248, 240) if pr_v >= 20 else (148, 163, 184, 210), font=f_xs_r)

    # Carte inferieure : Previsions 7 jours
    draw.rounded_rectangle([20, 260, WIDTH - 20, HEIGHT - 22], radius=18, fill=(18, 22, 30, 178), outline=(255, 255, 255, 45), width=2)
    title_d = ("7-DAY FORECAST" if DATE_LANG == "en" else "PREVISIONS SUR 7 JOURS")
    draw.text((38, 270), title_d, fill=(241, 196, 15, 255), font=f_xs)

    if _w_daily:
        d_w = (WIDTH - 68) // len(_w_daily)
        for i, (dlbl, dc_v, mn_v, mx_v, pr_d) in enumerate(_w_daily):
            cx = 34 + i * d_w + d_w // 2
            if i > 0:
                draw.line([34 + i * d_w, 302, 34 + i * d_w, HEIGHT - 32], fill=(255, 255, 255, 25), width=1)
            dx0, _, dx1, _ = draw.textbbox((0, 0), dlbl, font=f_xs)
            draw.text((cx - (dx1 - dx0) / 2, 302), dlbl, fill=(255, 255, 255, 255) if i == 0 else (195, 208, 225, 255), font=f_xs)
            draw_mini_weather(draw, cx, 352, dc_v, sc=0.65)
            mm_str = f"{mn_v:.0f}° / {mx_v:.0f}°"
            mx0, _, mx1, _ = draw.textbbox((0, 0), mm_str, font=f_xs)
            draw.text((cx - (mx1 - mx0) / 2, 390), mm_str, fill=(255, 255, 255, 255), font=f_xs)
            pr_str = f"Pluie {pr_d}%" if DATE_LANG != "en" else f"Rain {pr_d}%"
            rx0, _, rx1, _ = draw.textbbox((0, 0), pr_str, font=f_xs_r)
            draw.text((cx - (rx1 - rx0) / 2, 418), pr_str, fill=(56, 189, 248, 240) if pr_d >= 20 else (148, 163, 184, 200), font=f_xs_r)


def render(pnet, dt):
    global _p_idx, _l_pw
    update_weather()
    if not _paused and (time.time() - _l_pw) >= max(5, PAGE_SWITCH_INTERVAL):
        _p_idx, _l_pw = (_p_idx + 1) % len(PAGE_SEQ), time.time()
    cur_p = PAGE_SEQ[_p_idx % len(PAGE_SEQ)]
    base, ov = load_bg(cur_p), Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    try:
        f_xl = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        f_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        f_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except Exception:
        f_xl = f_md = f_sm = ImageFont.load_default()
    cw, ch, gap, sx, sy = (WIDTH - 60) // 2, (HEIGHT - 60) // 2, 20, 20, 20
    net = psutil.net_io_counters()
    rx = (net.bytes_recv - pnet.bytes_recv) / dt / 1048576.0
    tx = (net.bytes_sent - pnet.bytes_sent) / dt / 1048576.0

    if cur_p == 4:
        vms, act_vm, tot_vm = get_unraid_vms()
        draw.rounded_rectangle([20, 20, WIDTH - 20, HEIGHT - 24], radius=18, fill=(18, 22, 30, 175), outline=(255, 255, 255, 45), width=2)
        draw.text((42, 34), f"MACHINES VIRTUELLES UNRAID ({act_vm} / {tot_vm} ACTIVES)", fill=(52, 152, 219, 255), font=f_md)
        if not vms:
            draw.text((42, 100), "Aucune VM configuree", fill=(215, 225, 240, 255), font=f_sm)
        else:
            for idx_v, (vname, is_run) in enumerate(vms[:12]):
                dx, dy = 42 + (idx_v // 6) * 450, 82 + (idx_v % 6) * 58
                draw.ellipse([dx, dy + 7, dx + 12, dy + 19], fill=((46, 204, 113, 255) if is_run else (231, 76, 60, 255)))
                draw.text((dx + 22, dy), ((vname[:22] + "..") if len(vname) > 24 else vname), fill=(255, 255, 255, 255), font=f_md)
                draw.text((dx + 22, dy + 26), ("Active (En cours)" if is_run else "Arretee"), fill=(180, 195, 215, 255), font=f_sm)
    elif cur_p in (2, 3):
        items, total_run = get_running_dockers()
        offset, page_num = (0, "1/2") if cur_p == 2 else (12, "2/2")
        sub_items = items[offset:offset + 12]
        draw.rounded_rectangle([20, 20, WIDTH - 20, HEIGHT - 24], radius=18, fill=(18, 22, 30, 175), outline=(255, 255, 255, 45), width=2)
        draw.text((42, 34), f"CONTENEURS DOCKER ACTIFS ({total_run}) - PAGE {page_num}", fill=(46, 204, 113, 255), font=f_md)
        if not sub_items:
            draw.text((42, 100), ("Aucun conteneur actif" if cur_p == 2 else "Aucun autre conteneur actif (13-24)"), fill=(215, 225, 240, 255), font=f_sm)
        else:
            for idx_d, (name, addr) in enumerate(sub_items):
                dx, dy = 42 + (idx_d // 6) * 450, 82 + (idx_d % 6) * 58
                draw.ellipse([dx, dy + 7, dx + 12, dy + 19], fill=(46, 204, 113, 255))
                draw.text((dx + 22, dy), ((name[:22] + "..") if len(name) > 24 else name), fill=(255, 255, 255, 255), font=f_md)
                draw.text((dx + 22, dy + 26), addr, fill=(180, 195, 215, 255), font=f_sm)
    elif cur_p == 7:
        draw_weather_full_page(draw, f_xl, f_md, f_sm)
    elif cur_p == 6:
        draw_disks_page(draw, f_xl, f_md, f_sm)
    elif cur_p == 1:
        draw_clock_page(draw, f_xl, f_md, f_sm, rx, tx)
    else:
        if cur_p == 5:
            up_s, load_s, md_st, par_m, par_s, par_r = get_unraid_var()
            cards = [
                ("UPTIME SERVEUR", up_s, load_s, 0.85, (52, 152, 219, 235), False),
                ("PARITE UNRAID", par_m, par_s, par_r, ((46, 204, 113, 235) if par_r >= 0.99 else (231, 76, 60, 235)), par_r < 0.5),
                ("STATUT ARRAY", md_st, f"IP: {get_ip()}", (1.0 if md_st == "STARTED" else 0.2), ((46, 204, 113, 235) if md_st == "STARTED" else (231, 76, 60, 235)), md_st != "STARTED"),
                ("DEBIT RESEAU", f"\u2193 {rx:.1f}  \u2191 {tx:.1f} Mo/s", "Interface principale", min(1.0, (rx + tx) / 125.0), (155, 89, 182, 235), False)
            ]
        else:
            cpu, mem = psutil.cpu_percent(interval=None), psutil.virtual_memory()
            cpu_t = get_cpu_t()
            dsk = psutil.disk_usage("/mnt/user" if os.path.exists("/mnt/user") else "/")
            max_dt, dtm, dts, dtr = get_disks()
            c_col = (231, 76, 60, 235) if (cpu > 85 or (cpu_t and cpu_t > 80)) else ((243, 156, 18, 235) if (cpu > 70 or (cpu_t and cpu_t > 70)) else (30, 144, 255, 235))
            d_col = (231, 76, 60, 235) if dsk.percent > 90 else ((243, 156, 18, 235) if dsk.percent > 80 else (46, 204, 113, 235))
            t_col = (231, 76, 60, 235) if max_dt >= 48 else ((243, 156, 18, 235) if max_dt >= 42 else (52, 152, 219, 235))
            cards = [
                ("UNRAID CPU", f"{cpu:.1f}%", f"Temp: {cpu_t if cpu_t else 'N/A'}\u00b0C ({psutil.cpu_count()} threads)", cpu / 100.0, c_col, (cpu > 85 or (cpu_t and cpu_t > 80))),
                ("MEMOIRE RAM", f"{mem.percent:.1f}%", f"{mem.used / 1073741824:.1f} / {mem.total / 1073741824:.1f} Go", mem.percent / 100.0, ((231, 76, 60, 235) if mem.percent > 90 else (46, 204, 113, 235)), mem.percent > 90),
                ("ARRAY UNRAID", f"{dsk.percent:.1f}%", f"{dsk.free / 1099511627776:.2f} To libres", dsk.percent / 100.0, d_col, dsk.percent > 90),
                ("TEMP. DISQUES", dtm, dts, dtr, t_col, max_dt >= 48)
            ]
        global _hist_cpu, _hist_ram, _hist_net
        if cur_p == 0:
            _hist_cpu = (_hist_cpu + [cpu / 100.0])[-60:]
            _hist_ram = (_hist_ram + [mem.percent / 100.0])[-60:]
        elif cur_p == 5:
            _hist_net = (_hist_net + [min(1.0, (rx + tx) / 125.0)])[-60:]
        for i, (t, mv, sv, r, bar_c, alert) in enumerate(cards):
            x0, y0 = sx + (i % 2) * (cw + gap), sy + (i // 2) * (ch + gap)
            draw.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], radius=18, fill=(18, 22, 30, 165), outline=((231, 76, 60, 220) if alert else (255, 255, 255, 45)), width=(3 if alert else 2))
            draw.text((x0 + 22, y0 + 18), t, fill=(195, 208, 225, 255), font=f_md)
            draw.text((x0 + 22, y0 + 58), mv, fill=(255, 255, 255, 255), font=f_xl)
            draw.text((x0 + 22, y0 + 125), sv, fill=(215, 225, 240, 255), font=f_sm)
            bx, by, bw, bh = x0 + 22, y0 + ch - 42, cw - 44, 18
            draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=9, fill=(255, 255, 255, 35))
            draw.rounded_rectangle([bx, by, bx + max(10, int(bw * min(1.0, max(0.0, r)))), by + bh], radius=9, fill=bar_c)
            if cur_p == 0 and i == 0:
                draw_sparkline(draw, x0 + cw - 155, y0 + 22, 130, 52, _hist_cpu, c_col)
            elif cur_p == 0 and i == 1:
                draw_sparkline(draw, x0 + cw - 155, y0 + 22, 130, 52, _hist_ram, (46, 204, 113, 235))
            elif cur_p == 5 and i == 3:
                draw_sparkline(draw, x0 + cw - 155, y0 + 22, 130, 52, _hist_net, (155, 89, 182, 235))

    if ALERT_ENABLED:
        crit_alerts = []
        ct_now = get_cpu_t()
        if ct_now and ct_now >= 90:
            crit_alerts.append(f"Surchauffe Processeur CPU : {ct_now}°C (Seuil 90°C)")
        mdt_now, _, _, _ = get_disks()
        if mdt_now >= 50:
            crit_alerts.append(f"Surchauffe Disque Dur : {mdt_now}°C (Seuil 50°C)")
        _, _, md_now, _, _, _ = get_unraid_var()
        if md_now not in ("STARTED", "INCONNU"):
            crit_alerts.append(f"Statut Array Unraid anormal : {md_now}")
        if crit_alerts:
            draw_alert_overlay(draw, f_xl, f_md, crit_alerts)

    for p in range(len(PAGE_SEQ)):
        cx, cy = (WIDTH // 2) - ((len(PAGE_SEQ) - 1) * 10) + (p * 20), HEIGHT - 8
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=((255, 255, 255, 220) if p == (_p_idx % len(PAGE_SEQ)) else (255, 255, 255, 70)))

    img = Image.alpha_composite(base, ov).convert("RGB")
    act_br = get_active_brightness()
    if 0 <= act_br < 100:
        img = ImageEnhance.Brightness(img).enhance(max(0.05, act_br / 100.0))
    if (TARGET_W, TARGET_H) != (WIDTH, HEIGHT):
        img = img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
    pbuf = io.BytesIO(); img.save(pbuf, format="JPEG", quality=85); webui_module._last_jpeg = pbuf.getvalue()
    if ROTATION != 0:
        img = img.rotate(ROTATION, expand=True)
    return img, net

def main():
    start_api()
    threading.Thread(target=update_weather, daemon=True).start()
    pnet, ptime, fc = psutil.net_io_counters(), time.time(), 0
    psutil.cpu_percent(interval=None)
    while True:
        try:
            print("Connexion " + str(DEV_CFG.get("name")) + " sur " + str(PORT) + " (" + str(TARGET_W) + "x" + str(TARGET_H) + ")...", flush=True)
            with serial.Serial(PORT, BAUDRATE, timeout=1, write_timeout=2, rtscts=False, dsrdtr=False) as ser:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                if HANDSHAKE_BYTES:
                    ser.write(HANDSHAKE_BYTES)
                    ser.flush()
                    time.sleep(0.15)
                while True:
                    now = time.time()
                    img, pnet = render(pnet, max(0.1, now - ptime))
                    ptime = now
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=JPEG_QUALITY, subsampling=2)
                    jd = buf.getvalue()
                    if FRAMING_MODE == "raw_jpeg":
                        ser.write(jd)
                    elif FRAMING_MODE == "uint32_jpeg":
                        ser.write(struct.pack("<I", len(jd)) + jd)
                    else:
                        ser.write(struct.pack("<I", len(jd)) + jd + struct.pack("<H", sum(jd) & 0xFFFF))
                    ser.flush()
                    fc += 1
                    if fc <= 3 or fc % 60 == 0:
                        print(f"Trame #{fc} affichee ({len(jd)} octets)", flush=True)
                    time.sleep(INTERVAL)
        except Exception as e:
            print(f"Attente reconnexion ({e})...", flush=True)
            time.sleep(2)

if __name__ == "__main__":
    main()
