# Pilote Unraid pour Ocypus Sigma ES55 (960x480)

Pilote Linux autonome sous Docker pour l'écran USB **Ocypus Sigma ES55** (`33c3:7789` sur `/dev/ttyACM0`).

## 1. Architecture des fichiers
* `/mnt/user/appdata/ocypus-es55-build/es55_driver.py` : Script principal (protocole USB, rendu graphique, sondes Unraid, météo et API HTTP).
* `/mnt/user/appdata/ocypus-es55-build/Dockerfile` : Recette de compilation de l'image Docker `ocypus-es55-config:latest`.
* `/mnt/user/appdata/ocypus-es55-build/wallpapers/` : Dossier des fonds d'écran (`.jpg`, `.png`, `.webp` et `.gif` animés).
* `/boot/config/plugins/dockerMan/templates-user/my-ocypus-es55.xml` : Modèle XML sauvegardé pour restaurer le conteneur en 1 clic dans Unraid.

## 2. Les 6 Pages disponibles (`PAGE_ORDER`)
1. **Page 1 — Matériel & Stockage :** Charge/Température CPU, RAM, espace libre Array, température max/moyenne des disques (sans les sortir de veille) + alertes visuelles orange/rouge.
2. **Page 2 — Horloge, Date & Météo :** Horloge analogique ou numérique XXL, date FR/EN, météo Open-Meteo (température, ressenti, vent, humidité, min/max), compteur Docker et IP serveur.
3. **Page 3 — Conteneurs Docker (1 à 12) :** Liste des conteneurs actifs avec IP locale et ports.
4. **Page 4 — Conteneurs Docker (13 à 24) :** Suite de la liste des conteneurs actifs.
5. **Page 5 — Machines Virtuelles Unraid :** Statut actif/arrêté en direct de toutes vos VMs.
6. **Page 6 — Système & Parité :** Uptime du serveur, Load Average, statut de l'Array et dernière vérification de parité.

## 3. Variables configurables dans l'UI Unraid (Docker > Edit)

| Variable | Défaut | Description |
| :--- | :--- | :--- |
| `SERIAL_PORT` | `/dev/ttyACM0` | Port série USB de l'écran |
| `SCREEN_BRIGHTNESS` | `80` | Luminosité de jour (`0` à `100`) |
| `NIGHT_MODE` | `true` | Active la baisse de luminosité du coucher au lever du soleil (`true`/`false`) |
| `NIGHT_BRIGHTNESS` | `15` | Luminosité la nuit (`0` à `100`) |
| `PAGE_ORDER` | `1,2,3,4,5,6` | Ordre et sélection des pages affichées |
| `PAGE_SWITCH_INTERVAL` | `30` | Temps d'affichage par page (en secondes) |
| `CLOCK_MODE` | `analog` | Style de l'horloge Page 2 (`analog` ou `digital`) |
| `DATE_LANG` | `fr` | Langue de la date Page 2 (`fr` ou `en`) |
| `WEATHER_CITY` | `Paris` | Ville pour la météo et les heures de lever/coucher du soleil |
| `WEATHER_URL` | *(vide)* | URL API Open-Meteo personnalisée (optionnel) |
| `CUSTOM_PAGE_BG` | `false` | Active les fonds dédiés par page (`page1.jpg` à `page6.jpg`) |
| `WALLPAPER_SHUFFLE` | `false` | Lecture aléatoire du diaporama (`true`/`false`) |
| `SLIDESHOW_INTERVAL` | `600` | Secondes entre deux fonds d'écran (`600` = 10 min) |
| `BG_DIM` | `35` | Assombrissement du fond d'écran (`0` à `90` %) |
| `SCREEN_ROTATION` | `0` | Rotation de l'affichage (`0`, `90`, `180`, `270`) |
| `API_PORT` | `8799` | Port de la télécommande HTTP locale |
| `TZ` | `Europe/Paris` | Fuseau horaire |

## 4. Commandes de télécommande HTTP (Port `8799`)
* `http://192.168.1` : État JSON en direct
* `http://192.168.1` : Page suivante
* `http://192.168.1` : Page précédente
* `http://192.168.1` *(à `6`)* : Afficher directement une page précise
* `http://192.168.1` : Mettre en pause / reprendre le défilement
* `http://192.168.1` : Basculer manuellement le mode nuit/jour

## 5. Recompiler après une modification du script
```bash
cd /mnt/user/appdata/ocypus-es55-build
docker build -t ocypus-es55-config:latest . && docker image prune -f
```
