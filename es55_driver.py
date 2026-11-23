import os, io, time, glob, json, math, random, socket, struct, threading, urllib.request, serial, psutil
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps, ImageSequence

PORT = os.getenv("SERIAL_PORT", "/dev/ttyACM0")
DEVICE_PROFILE = os.getenv("DEVICE_PROFILE", "ocypus_es55").strip()
DEVICES_DIR = os.getenv("DEVICES_DIR", "/config/devices").strip()

def load_device_profile():
    prof = {"name": "Ocypus ES55", "width": 960, "height": 480, "baudrate": 115200, "handshake_hex": "55aa0700111701", "framing": "uint32_jpeg_crc16", "jpeg_quality": 85}
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

WIDTH = 960
HEIGHT = 480
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
DATE_LANG = os.getenv("DATE_LANG", "fr").strip().lower()
PAGE_ORDER_RAW = os.getenv("PAGE_ORDER", "1,2,3,4,5,6").strip()
NIGHT_MODE = os.getenv("NIGHT_MODE", "true").strip().lower() in ("1", "true", "yes", "on")
NIGHT_BRIGHTNESS = int(os.getenv("NIGHT_BRIGHTNESS", "15"))
CUSTOM_PAGE_BG = os.getenv("CUSTOM_PAGE_BG", "false").strip().lower() in ("1", "true", "yes", "on")
WALLPAPER_SHUFFLE = os.getenv("WALLPAPER_SHUFFLE", "false").strip().lower() in ("1", "true", "yes", "on")
API_PORT = int(os.getenv("API_PORT", "8765"))

def get_page_sequence():
    seq = []
    for part in PAGE_ORDER_RAW.split(","):
        p = part.strip()
        if p in ("1", "2", "3", "4", "5", "6"):
            seq.append(int(p) - 1)
    return seq if seq else [0, 1, 2, 3, 4, 5]

PAGE_SEQ = get_page_sequence()
_c_frames, _c_path, _c_mt, _c_fidx, _s_idx, _l_sw = [], None, 0, 0, 0, time.time()
_p_idx, _l_pw, _paused, _night_override = 0, time.time(), False, None
_w_main, _w_sub, _w_extra, _w_rat, _l_wf, _coords, _sunrise_dt, _sunset_dt = "-- C", "Chargement meteo...", "", 0.5, 0, None, None, None

WMO = {0:"Ciel degage",1:"Peu nuageux",2:"Partiellement nuageux",3:"Couvert",45:"Brouillard",51:"Bruine",61:"Pluie faible",63:"Pluie",65:"Forte pluie",71:"Neige",80:"Averses",95:"Orage"}
JOURS = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
MOIS = ["","Janvier","Fevrier","Mars","Avril","Mai","Juin","Juillet","Aout","Septembre","Octobre","Novembre","Decembre"]
DAYS_EN = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
MONTHS_EN = ["","January","February","March","April","May","June","July","August","September","October","November","December"]

class RemoteHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def do_GET(self):
        global _p_idx, _l_pw, _paused, _night_override
        path = self.path.strip("/").lower()
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
                num = int(path.split("/")[1])
                if 1 <= num <= 6:
                    target = num - 1
                    _p_idx = PAGE_SEQ.index(target) if target in PAGE_SEQ else 0
                    _l_pw = time.time()
                    msg = "Page " + str(num)
            except Exception: pass
        elif path == "" or path == "status":
            msg = json.dumps({"page": PAGE_SEQ[_p_idx % len(PAGE_SEQ)] + 1, "paused": _paused, "night": (NIGHT_MODE if _night_override is None else _night_override)})
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(msg.encode("utf-8"))

def start_api():
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", API_PORT), RemoteHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print("API Telecommande demarree sur le port " + str(API_PORT), flush=True)
    except Exception as e:
            print("API non demarree: " + str(e), flush=True)

def get_active_brightness():
    nm = NIGHT_MODE if _night_override is None else _night_override
    if not nm: return BRIGHTNESS
    now_dt = datetime.now()
    if _sunrise_dt is not None and _sunset_dt is not None:
        return NIGHT_BRIGHTNESS if (now_dt < _sunrise_dt or now_dt >= _sunset_dt) else BRIGHTNESS
    if now_dt.hour >= 21 or now_dt.hour < 7 or (now_dt.hour == 7 and now_dt.minute < 30):
        return NIGHT_BRIGHTNESS
    return BRIGHTNESS

def update_weather():
    global _w_main, _w_sub, _w_extra, _w_rat, _l_wf, _coords, _sunrise_dt, _sunset_dt
    if time.time() - _l_wf < 900: return
    _l_wf = time.time()
    try:
        wu, cn = WEATHER_URL, WEATHER_CITY
        if not wu:
            if _coords is None:
                u = "https://open-meteo.com" + urllib.request.quote(WEATHER_CITY) + "&count=1&language=fr&format=json"
                g = json.loads(urllib.request.urlopen(u, timeout=5).read().decode())
                if g.get("results"):
                    r = next(iter(g["results"]))
                    _coords = (r["latitude"], r["longitude"], r["name"])
            if _coords:
                lat, lon, cn = _coords
                wu = f"https://open-meteo.com{lat}&longitude={lon}&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m&daily=temperature_2m_min,temperature_2m_max,sunrise,sunset&timezone=auto"
        elif "apparent_temperature" not in wu and "://open-meteo.com" in wu:
            wu += "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m&daily=temperature_2m_min,temperature_2m_max,sunrise,sunset"
        if wu:
            data = json.loads(urllib.request.urlopen(wu, timeout=5).read().decode())
            cur, daily = data.get("current", data), data.get("daily", {})
            sr, ss = daily.get("sunrise", []), daily.get("sunset", [])
            if sr and ss:
                try:
                    _sunrise_dt = datetime.fromisoformat(next(iter(sr)))
                    _sunset_dt = datetime.fromisoformat(next(iter(ss)))
                except Exception: pass
            t = float(cur.get("temperature_2m", cur.get("temp", 0.0)))
            app_t, hum, wind = cur.get("apparent_temperature"), cur.get("relative_humidity_2m", "--"), cur.get("wind_speed_10m")
            desc = WMO.get(int(cur.get("weather_code", -1)), "Variable")
            tmin, tmax = next(iter(daily.get("temperature_2m_min", [])), None), next(iter(daily.get("temperature_2m_max", [])), None)
            ress = f" (Ress. {app_t:.0f}\u00b0)" if app_t is not None else ""
            _w_main = f"{t:.1f}\u00b0C{ress}"
            _w_sub = f"{cn} | {desc}" + (f" | Vent {wind:.0f} km/h" if wind is not None else "")
            _w_extra = (f"Min {tmin:.0f}\u00b0 / Max {tmax:.0f}\u00b0 | " if (tmin is not None and tmax is not None) else "") + f"Humidite {hum}%"
            _w_rat = min(1.0, max(0.05, (t + 5.0) / 40.0))
    except Exception: pass

def find_page_bg(pnum):
    if not WALLPAPER_DIR or not os.path.isdir(WALLPAPER_DIR): return None
    for ext in ("gif","jpg","jpeg","png","webp","GIF","JPG","PNG"):
        cand = os.path.join(WALLPAPER_DIR, f"page{pnum}.{ext}")
        if os.path.isfile(cand): return cand
    return None

def load_bg(cur_p=0):
    global _c_frames, _c_path, _c_mt, _c_fidx, _s_idx, _l_sw
    tp = find_page_bg(cur_p + 1) if CUSTOM_PAGE_BG else None
    if not tp:
        all_fs = sum([glob.glob(os.path.join(WALLPAPER_DIR, e)) for e in ("*.gif","*.jpg","*.jpeg","*.png","*.webp","*.GIF","*.JPG","*.PNG")], []) if os.path.isdir(WALLPAPER_DIR) else []
        other_fs = [f for f in all_fs if not os.path.basename(f).lower().startswith(("page1.","page2.","page3.","page4.","page5.","page6."))]
        fs = sorted(list(set(other_fs if other_fs else all_fs)))
        if not fs: return Image.new("RGBA", (WIDTH, HEIGHT), (14, 17, 23, 255))
        if len(fs) > 1 and (time.time() - _l_sw) >= max(5, SLIDESHOW_INTERVAL):
            _s_idx = random.choice([i for i in range(len(fs)) if i != _s_idx]) if WALLPAPER_SHUFFLE else ((_s_idx + 1) % len(fs))
            _l_sw = time.time()
        if _s_idx >= len(fs): _s_idx = 0
        tp = fs[_s_idx]
    try:
        mt = os.path.getmtime(tp)
        if not _c_frames or tp != _c_path or mt != _c_mt:
            im = Image.open(tp)
            frames = []
            for fr in ImageSequence.Iterator(im):
                fit = ImageOps.fit(fr.convert("RGB"), (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
                if BG_DIM > 0: fit = ImageEnhance.Brightness(fit).enhance(max(0.1, 1.0 - BG_DIM/100.0))
                frames.append(fit.convert("RGBA"))
            _c_frames, _c_path, _c_mt, _c_fidx = frames[:60], tp, mt, 0
        frame = _c_frames[_c_fidx % len(_c_frames)]
        _c_fidx = (_c_fidx + 1) % len(_c_frames)
        return frame.copy()
    except Exception:
        return Image.new("RGBA", (WIDTH, HEIGHT), (14, 17, 23, 255))

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception: return "IP inconnue"

def get_cpu_t():
    try:
        ts = psutil.sensors_temperatures()
        for k in ("coretemp","k10temp","zenpower","acpitz"):
            if k in ts and ts[k]: return int(ts[k][0].current)
    except Exception: pass
    return None

def get_disks():
    ts, act = [], 0
    if os.path.isfile("/unraid_emhttp/disks.ini"):
        try:
            for l in open("/unraid_emhttp/disks.ini", encoding="utf-8", errors="ignore"):
                l = l.strip()
                if l.startswith('temp="'):
                    v = l.split('"')[1]
                    if v.isdigit(): ts.append(int(v))
                elif l.startswith('color="') and "green-on" in l: act += 1
        except Exception: pass
    if ts:
        mx = max(ts)
        return mx, f"{mx}\u00b0C", f"Moy: {sum(ts)/len(ts):.0f}\u00b0C | {act} actif(s)", min(1.0, mx/60.0)
    return 0, "Veille", f"{act} disque(s) actif(s)", 0.1

def get_unraid_var():
    info = {"mdState": "INCONNU", "mdResync": "0", "mdResyncPos": "0", "mdResyncSize": "1", "sbSynced": "0", "sbSyncErrs": "0"}
    if os.path.isfile("/unraid_emhttp/var.ini"):
        try:
            for l in open("/unraid_emhttp/var.ini", encoding="utf-8", errors="ignore"):
                if "=" in l:
                    k, v = l.strip().split("=", 1)
                    if k in info: info[k] = v.strip('"')
        except Exception: pass
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
        except Exception: dt_sync = "N/A"
        par_main = "Valide (0 err)" if errs == "0" else f"{errs} erreur(s)"
        par_sub = f"Dernier controle : {dt_sync}"
        par_rat = 1.0 if errs == "0" else 0.2
    return up_str, f"Load: {load1:.2f} / {load5:.2f}", info["mdState"], par_main, par_sub, par_rat

def get_docker():
    if not os.path.exists("/var/run/docker.sock"): return "N/A", "Socket absente", 0.0
    try:
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); c.settimeout(1.5); c.connect("/var/run/docker.sock")
        c.sendall(b"GET /containers/json?all=1 HTTP/1.0\r\nHost: localhost\r\n\r\n"); r = b""
        while True:
            ch = c.recv(4096)
            if not ch: break
            r += ch
        c.close(); cs = json.loads(r[r.find(b"\r\n\r\n")+4:].decode("utf-8", errors="ignore"))
        tot, run = len(cs), sum(1 for x in cs if x.get("State") == "running")
        return f"{run} / {tot}", f"{tot - run} arrete(s)", (run/tot if tot > 0 else 0.0)
    except Exception: return "Erreur", "Lecture Docker", 0.0

def get_running_dockers():
    if not os.path.exists("/var/run/docker.sock"): return [], 0
    try:
        host_ip = get_ip()
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); c.settimeout(1.5); c.connect("/var/run/docker.sock")
        c.sendall(b"GET /containers/json HTTP/1.0\r\nHost: localhost\r\n\r\n"); r = b""
        while True:
            ch = c.recv(4096)
            if not ch: break
            r += ch
        c.close(); cs = json.loads(r[r.find(b"\r\n\r\n")+4:].decode("utf-8", errors="ignore"))
        items = []
        for x in cs:
            name = next(iter(x.get("Names") or []), "/inconnu").lstrip("/")
            nets = x.get("NetworkSettings", {}).get("Networks", {})
            c_ip = ""
            net_mode = x.get("HostConfig", {}).get("NetworkMode", "") or "host"
            for n_info in nets.values():
                ip_val = n_info.get("IPAddress", "")
                if ip_val and not ip_val.startswith("172."): c_ip = ip_val; break
            if not c_ip: c_ip = host_ip
            ports = x.get("Ports", [])
            pub = sorted(list(set(str(p["PublicPort"]) for p in ports if "PublicPort" in p)))
            priv = sorted(list(set(str(p["PrivatePort"]) for p in ports if "PrivatePort" in p)))
            if pub: addr = f"{c_ip}:{next(iter(pub))}" + (f" (+{len(pub)-1})" if len(pub) > 1 else "")
            elif priv: addr = f"{c_ip}:{next(iter(priv))}" + (f" (+{len(priv)-1})" if len(priv) > 1 else "")
            else: addr = f"{c_ip} ({net_mode})"
            items.append((name, addr))
        items.sort(key=lambda t: next(iter(t)).lower())
        return items, len(items)
    except Exception: return [], 0

def get_unraid_vms():
    if not os.path.isdir("/unraid_vms_xml"): return [], 0, 0
    vms = []
    try:
        for fn in os.listdir("/unraid_vms_xml"):
            if fn.endswith(".xml"):
                vn = fn[:-4]
                vms.append((vn, os.path.isfile(os.path.join("/unraid_vms_run", vn + ".pid"))))
        vms.sort(key=lambda x: (not x[1], next(iter(x)).lower()))
        return vms, sum(1 for _, r in vms if r), len(vms)
    except Exception: return [], 0, 0

def draw_clock_page(draw, f_xl, f_md, f_sm, rx, tx):
    dtn = datetime.now()
    wd, mn = dtn.weekday(), dtn.month
    date_str = f"{DAYS_EN[wd]}, {MONTHS_EN[mn]} {dtn.day}, {dtn.year}" if DATE_LANG == "en" else f"{JOURS[wd]} {dtn.day} {MOIS[mn]} {dtn.year}"
    draw.rounded_rectangle([20, 20, 450, HEIGHT-24], radius=18, fill=(18,22,30,175), outline=(255,255,255,45), width=2)
    if CLOCK_MODE == "digital":
        draw.text((42, 42), ("LOCAL TIME" if DATE_LANG == "en" else "HEURE LOCALE"), fill=(195,208,225,255), font=f_md)
        try: f_huge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 76)
        except Exception: f_huge = f_xl
        draw.text((42, 145), dtn.strftime("%H:%M"), fill=(255,255,255,255), font=f_huge)
        draw.text((42, 240), ": " + dtn.strftime("%S") + " sec", fill=(52,152,219,255), font=f_xl)
        draw.text((42, 330), date_str, fill=(215,225,240,255), font=f_md)
    else:
        cx, cy, rad = 235, 238, 175
        draw.ellipse([cx-rad, cy-rad, cx+rad, cy+rad], fill=(14,18,26,210), outline=(255,255,255,90), width=3)
        for m in range(60):
            ang = math.radians(m * 6 - 90)
            r1, r2 = rad - (18 if m % 5 == 0 else 8), rad - 4
            draw.line([cx+r1*math.cos(ang), cy+r1*math.sin(ang), cx+r2*math.cos(ang), cy+r2*math.sin(ang)], fill=((255,255,255,230) if m%5==0 else (255,255,255,90)), width=(3 if m%5==0 else 1))
        h_ang = math.radians(((dtn.hour % 12) + dtn.minute / 60.0) * 30 - 90)
        draw.line([cx, cy, cx + 95*math.cos(h_ang), cy + 95*math.sin(h_ang)], fill=(255,255,255,255), width=7)
        m_ang = math.radians((dtn.minute + dtn.second / 60.0) * 6 - 90)
        draw.line([cx, cy, cx + 138*math.cos(m_ang), cy + 138*math.sin(m_ang)], fill=(52,152,219,255), width=5)
        s_ang = math.radians(dtn.second * 6 - 90)
        draw.line([cx - 20*math.cos(s_ang), cy - 20*math.sin(s_ang), cx + 152*math.cos(s_ang), cy + 152*math.sin(s_ang)], fill=(231,76,60,255), width=2)
        draw.ellipse([cx-7, cy-7, cx+7, cy+7], fill=(255,255,255,255))
    draw.rounded_rectangle([470, 20, WIDTH-20, 275], radius=18, fill=(18,22,30,175), outline=(255,255,255,45), width=2)
    draw.text((492, 36), date_str, fill=(52,152,219,255), font=f_md)
    draw.text((492, 78), _w_main, fill=(255,255,255,255), font=f_xl)
    draw.text((492, 138), _w_sub, fill=(215,225,240,255), font=f_sm)
    if _w_extra: draw.text((492, 170), _w_extra, fill=(170,210,255,255), font=f_sm)
    bx, by, bw, bh = 492, 222, (WIDTH - 534), 16
    draw.rounded_rectangle([bx,by,bx+bw,by+bh], radius=8, fill=(255,255,255,35))
    draw.rounded_rectangle([bx,by,bx+max(10,int(bw*_w_rat)),by+bh], radius=8, fill=(241,196,15,235))
    dkm, dks, dkr = get_docker()
    draw.rounded_rectangle([470, 293, WIDTH-20, HEIGHT-24], radius=18, fill=(18,22,30,175), outline=(255,255,255,45), width=2)
    draw.text((492, 310), f"DOCKER : {dkm} ({dks})", fill=(46,204,113,255), font=f_md)
    draw.text((492, 352), f"IP Serveur : {get_ip()}", fill=(255,255,255,255), font=f_md)
    draw.text((492, 392), f"Reseau : \u2193 {rx:.1f} Mo/s  |  \u2191 {tx:.1f} Mo/s", fill=(215,225,240,255), font=f_sm)

def render(pnet, dt):
    global _p_idx, _l_pw
    update_weather()
    if not _paused and (time.time() - _l_pw) >= max(5, PAGE_SWITCH_INTERVAL):
        _p_idx, _l_pw = (_p_idx + 1) % len(PAGE_SEQ), time.time()
    cur_p = PAGE_SEQ[_p_idx % len(PAGE_SEQ)]
    base, ov = load_bg(cur_p), Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    draw = ImageDraw.Draw(ov)
    try:
        f_xl = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        f_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        f_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except Exception: f_xl = f_md = f_sm = ImageFont.load_default()
    cw, ch, gap, sx, sy = (WIDTH-60)//2, (HEIGHT-60)//2, 20, 20, 20
    net = psutil.net_io_counters()
    rx, tx = (net.bytes_recv-pnet.bytes_recv)/dt/1048576.0, (net.bytes_sent-pnet.bytes_sent)/dt/1048576.0

    if cur_p == 4:
        vms, act_vm, tot_vm = get_unraid_vms()
        draw.rounded_rectangle([20, 20, WIDTH-20, HEIGHT-24], radius=18, fill=(18,22,30,175), outline=(255,255,255,45), width=2)
        draw.text((42, 34), "MACHINES VIRTUELLES UNRAID (" + str(act_vm) + " / " + str(tot_vm) + " ACTIVES)", fill=(52,152,219,255), font=f_md)
        if not vms: draw.text((42, 100), "Aucune VM configuree", fill=(215,225,240,255), font=f_sm)
        else:
            for idx_v, (vname, is_run) in enumerate(vms[:12]):
                dx, dy = 42 + (idx_v // 6) * 450, 82 + (idx_v % 6) * 58
                draw.ellipse([dx, dy+7, dx+12, dy+19], fill=((46,204,113,255) if is_run else (231,76,60,255)))
                draw.text((dx+22, dy), ((vname[:22] + "..") if len(vname) > 24 else vname), fill=(255,255,255,255), font=f_md)
                draw.text((dx+22, dy+26), ("Active (En cours)" if is_run else "Arretee"), fill=(180,195,215,255), font=f_sm)
    elif cur_p in (2, 3):
        items, total_run = get_running_dockers()
        offset, page_num = (0, "1/2") if cur_p == 2 else (12, "2/2")
        sub_items = items[offset:offset+12]
        draw.rounded_rectangle([20, 20, WIDTH-20, HEIGHT-24], radius=18, fill=(18,22,30,175), outline=(255,255,255,45), width=2)
        draw.text((42, 34), "CONTENEURS DOCKER ACTIFS (" + str(total_run) + ") - PAGE " + page_num, fill=(46,204,113,255), font=f_md)
        if not sub_items: draw.text((42, 100), ("Aucun conteneur actif" if cur_p == 2 else "Aucun autre conteneur actif (13-24)"), fill=(215,225,240,255), font=f_sm)
        else:
            for idx_d, (name, addr) in enumerate(sub_items):
                dx, dy = 42 + (idx_d // 6) * 450, 82 + (idx_d % 6) * 58
                draw.ellipse([dx, dy+7, dx+12, dy+19], fill=(46,204,113,255))
                draw.text((dx+22, dy), ((name[:22] + "..") if len(name) > 24 else name), fill=(255,255,255,255), font=f_md)
                draw.text((dx+22, dy+26), addr, fill=(180,195,215,255), font=f_sm)
    elif cur_p == 1:
        draw_clock_page(draw, f_xl, f_md, f_sm, rx, tx)
    else:
        if cur_p == 5:
            up_s, load_s, md_st, par_m, par_s, par_r = get_unraid_var()
            cards = [
                ("UPTIME SERVEUR", up_s, load_s, 0.85, (52,152,219,235), False),
                ("PARITE UNRAID", par_m, par_s, par_r, ((46,204,113,235) if par_r >= 0.99 else (231,76,60,235)), par_r < 0.5),
                ("STATUT ARRAY", md_st, "IP: " + str(get_ip()), (1.0 if md_st == "STARTED" else 0.2), ((46,204,113,235) if md_st == "STARTED" else (231,76,60,235)), md_st != "STARTED"),
                ("DEBIT RESEAU", "\u2193 " + f"{rx:.1f}" + "  \u2191 " + f"{tx:.1f}" + " Mo/s", "Interface principale", min(1.0,(rx+tx)/125.0), (155,89,182,235), False)
            ]
        else:
            cpu, mem = psutil.cpu_percent(interval=None), psutil.virtual_memory()
            cpu_t = get_cpu_t()
            dsk = psutil.disk_usage("/mnt/user" if os.path.exists("/mnt/user") else "/")
            max_dt, dtm, dts, dtr = get_disks()
            c_col = (231,76,60,235) if (cpu > 85 or (cpu_t and cpu_t > 80)) else ((243,156,18,235) if (cpu > 70 or (cpu_t and cpu_t > 70)) else (30,144,255,235))
            d_col = (231,76,60,235) if dsk.percent > 90 else ((243,156,18,235) if dsk.percent > 80 else (46,204,113,235))
            t_col = (231,76,60,235) if max_dt >= 48 else ((243,156,18,235) if max_dt >= 42 else (52,152,219,235))
            cards = [
                ("UNRAID CPU", f"{cpu:.1f}%", "Temp: " + str(cpu_t if cpu_t else "N/A") + "\u00b0C (" + str(psutil.cpu_count()) + " threads)", cpu/100.0, c_col, (cpu > 85 or (cpu_t and cpu_t > 80))),
                ("MEMOIRE RAM", f"{mem.percent:.1f}%", f"{mem.used/1073741824:.1f} / {mem.total/1073741824:.1f} Go", mem.percent/100.0, ((231,76,60,235) if mem.percent > 90 else (46,204,113,235)), mem.percent > 90),
                ("ARRAY UNRAID", f"{dsk.percent:.1f}%", f"{dsk.free/1099511627776:.2f} To libres", dsk.percent/100.0, d_col, dsk.percent > 90),
                ("TEMP. DISQUES", dtm, dts, dtr, t_col, max_dt >= 48)
            ]
        for i, (t, mv, sv, r, bar_c, alert) in enumerate(cards):
            x0, y0 = sx + (i%2)*(cw+gap), sy + (i//2)*(ch+gap)
            draw.rounded_rectangle([x0,y0,x0+cw,y0+ch], radius=18, fill=(18,22,30,165), outline=((231,76,60,220) if alert else (255,255,255,45)), width=(3 if alert else 2))
            draw.text((x0+22,y0+18), t, fill=(195,208,225,255), font=f_md); draw.text((x0+22,y0+58), mv, fill=(255,255,255,255), font=f_xl); draw.text((x0+22,y0+125), sv, fill=(215,225,240,255), font=f_sm)
            bx, by, bw, bh = x0+22, y0+ch-42, cw-44, 18
            draw.rounded_rectangle([bx,by,bx+bw,by+bh], radius=9, fill=(255,255,255,35))
            draw.rounded_rectangle([bx,by,bx+max(10,int(bw*min(1.0,max(0.0,r)))),by+bh], radius=9, fill=bar_c)
    for p in range(len(PAGE_SEQ)):
        cx, cy = (WIDTH//2)-((len(PAGE_SEQ)-1)*10)+(p*20), HEIGHT-8
        draw.ellipse([cx-4,cy-4,cx+4,cy+4], fill=((255,255,255,220) if p==(_p_idx % len(PAGE_SEQ)) else (255,255,255,70)))
    img = Image.alpha_composite(base, ov).convert("RGB")
    act_br = get_active_brightness()
    if 0 <= act_br < 100: img = ImageEnhance.Brightness(img).enhance(max(0.05, act_br/100.0))
    if (TARGET_W, TARGET_H) != (WIDTH, HEIGHT): img = img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
    if (TARGET_W, TARGET_H) != (WIDTH, HEIGHT): img = img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
    if ROTATION != 0: img = img.rotate(ROTATION, expand=True)
    return img, net
def main():
    start_api()
    pnet, ptime, fc = psutil.net_io_counters(), time.time(), 0; psutil.cpu_percent(interval=None)
    while True:
        try:
            print("Connexion " + str(DEV_CFG.get("name")) + " sur " + str(PORT) + " (" + str(TARGET_W) + "x" + str(TARGET_H) + ")...", flush=True)
            with serial.Serial(PORT, BAUDRATE, timeout=1, write_timeout=2, rtscts=False, dsrdtr=False) as ser:
                ser.reset_input_buffer(); ser.reset_output_buffer()
                if HANDSHAKE_BYTES: ser.write(HANDSHAKE_BYTES); ser.flush(); time.sleep(0.15)
                while True:
                    now = time.time(); img, pnet = render(pnet, max(0.1, now - ptime)); ptime = now
                    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=JPEG_QUALITY, subsampling=2); jd = buf.getvalue()
                    ser.write(jd if FRAMING_MODE == "raw_jpeg" else ((struct.pack("<I", len(jd)) + jd) if FRAMING_MODE == "uint32_jpeg" else (struct.pack("<I", len(jd)) + jd + struct.pack("<H", sum(jd) & 0xFFFF)))); ser.flush()
                    fc += 1
                    if fc <= 3 or fc % 60 == 0: print(f"Trame #{fc} affichee ({len(jd)} octets)", flush=True)
                    time.sleep(INTERVAL)
        except Exception as e: print(f"Attente reconnexion ({e})...", flush=True); time.sleep(2)
if __name__ == "__main__": main()
