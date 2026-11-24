import os
import json
from urllib.parse import parse_qs

SETTINGS_FILE = "/config/settings.json"
_last_jpeg = b""


def apply_saved_settings(g):
    if os.path.isfile(SETTINGS_FILE):
        try:
            saved = json.loads(open(SETTINGS_FILE, encoding="utf-8").read())
            for k, v in saved.items():
                if k in g:
                    g[k] = v
            if "PAGE_ORDER_RAW" in saved and "get_page_sequence" in g:
                g["PAGE_SEQ"] = g["get_page_sequence"]()
        except Exception as e:
            print("Erreur lecture settings.json:", e, flush=True)


def save_web_settings(raw_body, g):
    qs = parse_qs(raw_body)

    def gv(k, d):
        return qs.get(k, [d])[0]

    cfg = {
        "BRIGHTNESS": int(gv("BRIGHTNESS", g.get("BRIGHTNESS", 80))),
        "NIGHT_MODE": "NIGHT_MODE" in qs,
        "NIGHT_BRIGHTNESS": int(gv("NIGHT_BRIGHTNESS", g.get("NIGHT_BRIGHTNESS", 15))),
        "PAGE_ORDER_RAW": gv("PAGE_ORDER_RAW", g.get("PAGE_ORDER_RAW", "1,2,3,4,5,6,7,8")).strip(),
        "PAGE_SWITCH_INTERVAL": int(gv("PAGE_SWITCH_INTERVAL", g.get("PAGE_SWITCH_INTERVAL", 30))),
        "CLOCK_MODE": gv("CLOCK_MODE", g.get("CLOCK_MODE", "analog")),
        "CLOCK_COLOR": gv("CLOCK_COLOR", g.get("CLOCK_COLOR", "#3498db")).strip(),
        "HOUR_COLOR": gv("HOUR_COLOR", g.get("HOUR_COLOR", "#ffffff")).strip(),
        "MIN_COLOR": gv("MIN_COLOR", g.get("MIN_COLOR", "#3498db")).strip(),
        "HOUR_WIDTH": int(gv("HOUR_WIDTH", g.get("HOUR_WIDTH", 10))),
        "MIN_WIDTH": int(gv("MIN_WIDTH", g.get("MIN_WIDTH", 7))),
        "SEC_WIDTH": int(gv("SEC_WIDTH", g.get("SEC_WIDTH", 3))),
        "CLOCK_NUMBERS": gv("CLOCK_NUMBERS", g.get("CLOCK_NUMBERS", "cardinal")),
        "DIAL_COLOR": gv("DIAL_COLOR", g.get("DIAL_COLOR", "#ffffff")).strip(),
        "DATE_COLOR": gv("DATE_COLOR", g.get("DATE_COLOR", "#3498db")).strip(),
        "DIAL_WIDTH": int(gv("DIAL_WIDTH", g.get("DIAL_WIDTH", 5))),
        "TICK_WIDTH": int(gv("TICK_WIDTH", g.get("TICK_WIDTH", 5))),
        "NUM_SIZE": int(gv("NUM_SIZE", g.get("NUM_SIZE", 25))),
        "CLOCK_DATE_BOX": "CLOCK_DATE_BOX" in qs,
        "CLOCK_SUB_DIG": "CLOCK_SUB_DIG" in qs,
        "ALERT_ENABLED": "ALERT_ENABLED" in qs,
        "DATE_LANG": gv("DATE_LANG", g.get("DATE_LANG", "fr")),
        "WEATHER_CITY": gv("WEATHER_CITY", g.get("WEATHER_CITY", "Paris")).strip(),
        "CUSTOM_PAGE_BG": "CUSTOM_PAGE_BG" in qs,
        "WALLPAPER_SHUFFLE": "WALLPAPER_SHUFFLE" in qs,
        "SLIDESHOW_INTERVAL": int(gv("SLIDESHOW_INTERVAL", g.get("SLIDESHOW_INTERVAL", 600))),
        "BG_DIM": int(gv("BG_DIM", g.get("BG_DIM", 35))),
        "ROTATION": int(gv("ROTATION", g.get("ROTATION", 0))),
    }
    g.update(cfg)
    g["_coords"] = None
    g["_l_wf"] = 0
    g["_c_frames"] = []
    if "get_page_sequence" in g:
        g["PAGE_SEQ"] = g["get_page_sequence"]()
    try:
        open(SETTINGS_FILE, "w", encoding="utf-8").write(json.dumps(cfg, indent=2))
    except Exception as e:
        print("Erreur ecriture settings.json:", e, flush=True)


def render_html(g, cur_page, paused):
    def sel(a, b):
        return "selected" if str(a) == str(b) else ""

    def chk(b):
        return "checked" if b else ""

    pause_txt = "(En pause)" if paused else ""
    wp_html = ""
    if os.path.isdir("/config/wallpapers"):
        files = sorted(f for f in os.listdir("/config/wallpapers") if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")))
        for fn in files:
            wp_html += f'<div style="display:inline-flex;align-items:center;gap:6px;background:#0f172a;border:1px solid #334155;padding:5px 9px;border-radius:6px;margin:3px;font-size:12px"><span>🖼️ {fn}</span><a href="/del_wp?f={fn}" style="color:#f87171;text-decoration:none;font-weight:bold" title="Supprimer">✖</a></div>'
    if not wp_html:
        wp_html = '<span style="color:#94a3b8;font-size:12px">Aucun fond d\'écran dans /config/wallpapers</span>'

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://w3.org' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230f172a' stroke='%2338bdf8' stroke-width='4'/%3E%3Crect x='10' y='15' width='44' height='28' rx='6' fill='%231e293b'/%3E%3Crect x='15' y='21' width='16' height='4' rx='2' fill='%2338bdf8'/%3E%3Crect x='15' y='28' width='13' height='4' rx='2' fill='%2310b981'/%3E%3Ccircle cx='42' cy='29' r='8' fill='none' stroke='%23fff' stroke-width='2.5'/%3E%3Cpath d='M42 29v-5m0 5h4' stroke='%23ef4444' stroke-width='2' stroke-linecap='round'/%3E%3Crect x='24' y='47' width='16' height='6' rx='2' fill='%2338bdf8'/%3E%3C/svg%3E">
<title>Ocypus ES55 - Réglages</title>
<style>
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#f8fafc;max-width:860px;margin:20px auto;padding:15px}}
.card{{background:#1e293b;padding:20px;border-radius:12px;margin-bottom:18px;border:1px solid #334155}}
h1{{margin:0 0 15px;font-size:1.35rem;color:#38bdf8}}
.prev{{width:100%;max-width:640px;border-radius:10px;border:2px solid #475569;display:block;margin:0 auto 15px}}
.btns{{display:flex;gap:8px;flex-wrap:wrap;justify-content:center}}
.btn{{background:#3b82f6;color:#fff;border:none;padding:9px 14px;border-radius:8px;cursor:pointer;font-weight:600;text-decoration:none;font-size:0.9rem}}
.btn:hover{{background:#2563eb}}
.btn-g{{background:#475569}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
label{{display:block;font-size:0.85rem;color:#94a3b8;margin-bottom:4px}}
input[type=text],input[type=number],select{{width:100%;padding:8px;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}
.chk{{display:flex;align-items:center;gap:8px;margin-top:22px;color:#e2e8f0;font-size:0.9rem}}
.save{{background:#10b981;width:100%;padding:12px;font-size:1rem;margin-top:16px}}
.save:hover{{background:#059669}}
@media(max-width:600px){{.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="card">
<h1>🖥️ Aperçu en direct — Page {cur_page} {pause_txt}</h1>
<img id="pv" class="prev" src="/preview.jpg">
<div class="btns">
<button class="btn btn-g" onclick="cmd('/prev')">⏮️ Précédente</button>
<button class="btn" onclick="cmd('/next')">⏭️ Suivante</button>
<button class="btn btn-g" onclick="cmd('/pause')">⏯️ Pause / Lecture</button>
<button class="btn btn-g" onclick="cmd('/night/toggle')">🌙 Basculer Nuit/Jour</button>
</div>
</div>
<form class="card" method="POST" action="/">
<h1>⚙️ Paramètres de l'écran Ocypus ES55</h1>
<div class="grid">
<div><label>Luminosité jour (0-100 %)</label><input type="number" name="BRIGHTNESS" min="0" max="100" value="{g.get('BRIGHTNESS',80)}"></div>
<div><label>Luminosité nuit (0-100 %)</label><input type="number" name="NIGHT_BRIGHTNESS" min="0" max="100" value="{g.get('NIGHT_BRIGHTNESS',15)}"></div>
<div><label>Ville Météo</label><input type="text" name="WEATHER_CITY" value="{g.get('WEATHER_CITY','Paris')}"></div>
<div><label>Ordre des pages (1 à 8)</label><input type="text" name="PAGE_ORDER_RAW" value="{g.get('PAGE_ORDER_RAW','1,2,3,4,5,6')}"></div>
<div><label>Secondes par page</label><input type="number" name="PAGE_SWITCH_INTERVAL" min="5" value="{g.get('PAGE_SWITCH_INTERVAL',30)}"></div>
<div><label>Style horloge (Page 2)</label><select name="CLOCK_MODE"><option value="analog" {sel(g.get('CLOCK_MODE'),'analog')}>Analogique (Aiguilles)</option><option value="digital" {sel(g.get('CLOCK_MODE'),'digital')}>Numérique XXL</option></select></div>
<div><label>Couleur horloge (Barre / Trotteuse)</label><input type="color" name="CLOCK_COLOR" value="{g.get('CLOCK_COLOR','#3498db')}" style="height:38px;padding:2px;width:100%;border-radius:6px;border:1px solid #475569;background:#0f172a;cursor:pointer"></div>
<div><label>Couleur aiguille Heures</label><input type="color" name="HOUR_COLOR" value="{g.get('HOUR_COLOR','#ffffff')}" style="height:38px;padding:2px;width:100%;border-radius:6px;border:1px solid #475569;background:#0f172a;cursor:pointer"></div>
<div><label>Couleur aiguille Minutes</label><input type="color" name="MIN_COLOR" value="{g.get('MIN_COLOR','#3498db')}" style="height:38px;padding:2px;width:100%;border-radius:6px;border:1px solid #475569;background:#0f172a;cursor:pointer"></div>
<div><label>Épaisseur aiguille Heures (px)</label><input type="number" name="HOUR_WIDTH" min="2" max="24" value="{g.get('HOUR_WIDTH',10)}"></div>
<div><label>Épaisseur aiguille Minutes (px)</label><input type="number" name="MIN_WIDTH" min="2" max="20" value="{g.get('MIN_WIDTH',7)}"></div>
<div><label>Épaisseur trotteuse (px)</label><input type="number" name="SEC_WIDTH" min="1" max="12" value="{g.get('SEC_WIDTH',3)}"></div>
<div><label>Chiffres du cadran (Analogique)</label><select name="CLOCK_NUMBERS"><option value="none" {sel(g.get('CLOCK_NUMBERS'),'none')}>Aucun (Minimaliste)</option><option value="cardinal" {sel(g.get('CLOCK_NUMBERS'),'cardinal')}>Points cardinaux (12, 3, 6, 9)</option><option value="all" {sel(g.get('CLOCK_NUMBERS'),'all')}>Tous les chiffres (1 à 12)</option></select></div>
<div><label>Couleur du cadran &amp; graduations</label><input type="color" name="DIAL_COLOR" value="{g.get('DIAL_COLOR','#ffffff')}" style="height:38px;padding:2px;width:100%;border-radius:6px;border:1px solid #475569;background:#0f172a;cursor:pointer"></div>
<div><label>Couleur police de la date</label><input type="color" name="DATE_COLOR" value="{g.get('DATE_COLOR','#3498db')}" style="height:38px;padding:2px;width:100%;border-radius:6px;border:1px solid #475569;background:#0f172a;cursor:pointer"></div>
<div><label>Épaisseur cercle cadran (px)</label><input type="number" name="DIAL_WIDTH" min="1" max="12" value="{g.get('DIAL_WIDTH',5)}"></div>
<div><label>Épaisseur graduations heures (px)</label><input type="number" name="TICK_WIDTH" min="1" max="10" value="{g.get('TICK_WIDTH',5)}"></div>
<div><label>Taille chiffres cadran (px)</label><input type="number" name="NUM_SIZE" min="14" max="34" value="{g.get('NUM_SIZE',25)}"></div>
<div><label>Logo du cadran (Analogique)</label><select name="DIAL_LOGO"><option value="none" {sel(g.get('DIAL_LOGO'),'none')}>Aucun</option><option value="unraid" {sel(g.get('DIAL_LOGO'),'unraid')}>Logo Unraid (Intégré)</option><option value="custom" {sel(g.get('DIAL_LOGO'),'custom')}>Personnalisé (dial_logo.png)</option></select></div>
<div><label>Opacité logo cadran (10-100 %)</label><input type="number" name="DIAL_LOGO_OPACITY" min="10" max="100" value="{g.get('DIAL_LOGO_OPACITY',65)}"></div>
<div><label>Langue Date (Page 2)</label><select name="DATE_LANG"><option value="fr" {sel(g.get('DATE_LANG'),'fr')}>Français</option><option value="en" {sel(g.get('DATE_LANG'),'en')}>English</option></select></div>
<div><label>Rotation écran</label><select name="ROTATION"><option value="0" {sel(g.get('ROTATION'),0)}>0° (Normal)</option><option value="90" {sel(g.get('ROTATION'),90)}>90°</option><option value="180" {sel(g.get('ROTATION'),180)}>180° (Inversé)</option><option value="270" {sel(g.get('ROTATION'),270)}>270°</option></select></div>
<div><label>Secondes entre fonds d'écran</label><input type="number" name="SLIDESHOW_INTERVAL" min="5" value="{g.get('SLIDESHOW_INTERVAL',600)}"></div>
<div><label>Assombrissement fond (0-90 %)</label><input type="number" name="BG_DIM" min="0" max="90" value="{g.get('BG_DIM',35)}"></div>
<div class="chk"><input type="checkbox" name="NIGHT_MODE" {chk(g.get('NIGHT_MODE',True))}> Mode nuit solaire automatique</div>
<div class="chk"><input type="checkbox" name="WALLPAPER_SHUFFLE" {chk(g.get('WALLPAPER_SHUFFLE',False))}> Fonds d'écran aléatoires</div>
<div class="chk"><input type="checkbox" name="CUSTOM_PAGE_BG" {chk(g.get('CUSTOM_PAGE_BG',False))}> Fond dédié par page (page1..page6)</div>
<div class="chk"><input type="checkbox" name="CLOCK_DATE_BOX" {chk(g.get('CLOCK_DATE_BOX',True))}> Guichet date horloger [JJ] [MOIS] (Analogique)</div>
<div class="chk"><input type="checkbox" name="ALERT_ENABLED" {chk(g.get('ALERT_ENABLED',True))}> Alerte visuelle critique (Surchauffe / Erreur Array)</div>
<div class="chk"><input type="checkbox" name="CLOCK_SUB_DIG" {chk(g.get('CLOCK_SUB_DIG',False))}> Mini heure numérique intégrée au cadran</div>
</div>
<button type="submit" class="btn save">💾 Enregistrer et appliquer immédiatement</button>
</form>
<form class="card" method="POST" action="/upload_logo" enctype="multipart/form-data">
<h1>🖼️ Importer un logo personnalisé pour le cadran (PNG transparent recommandé)</h1>
<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
<input type="file" name="logo_file" accept="image/png,image/jpeg,image/webp,image/gif" required style="flex:1;color:#cbd5e1">
<button type="submit" class="btn">📤 Envoyer &amp; activer sur le cadran</button>
</div>
</form>
<form class="card" method="POST" action="/upload_wp" enctype="multipart/form-data">
<h1>🌄 Gestionnaire de fonds d'écran &amp; GIF animés (/config/wallpapers)</h1>
<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px">
<input type="file" name="wp_file" accept="image/png,image/jpeg,image/webp,image/gif" required style="flex:1;color:#cbd5e1">
<button type="submit" class="btn">📤 Ajouter un fond / GIF</button>
</div>
<div>{wp_html}</div>
</form>
<script>
function cmd(u){{fetch(u).then(()=>setTimeout(()=>location.reload(),250));}}
setInterval(()=>{{document.getElementById('pv').src='/preview.jpg?t='+Date.now();}},1500);
</script>
</body>
</html>"""