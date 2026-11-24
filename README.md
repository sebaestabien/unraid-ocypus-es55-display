# Unraid Ocypus Sigma ES55 Display Driver

Pilote Linux & Docker complet pour écran USB **Ocypus Sigma ES55 (960×480)** sur serveur **Unraid**, incluant une **interface Web de configuration complète (`WebUI`)**, un aperçu vidéo en direct et **8 pages de monitoring** 100 % personnalisables.

### ✨ Fonctionnalités principales

* **Interface Web de configuration (`http://<IP>:8799/`)** : Panneau de contrôle graphique avec sauvegarde persistante (`settings.json`), aperçu vidéo en temps réel redressé à 0° et boutons d'action rapide (Page suivante/précédente, Pause, Mode Nuit).
* **8 pages modulables (ordre et durée personnalisables)** :
  1. **Système Unraid** : Charge CPU, température processeur, mémoire RAM, occupation Array et température maximale des disques avec **courbes d'historique temps réel (Sparklines)**.
  2. **Horloge & Météo locale** : Mode **Analogique horloger** (couleurs/épaisseurs des 3 aiguilles, chiffres du cadran, guichet date `[JJ] [MOIS]`, logo Unraid ou logo PNG personnalisé importable en un clic) ou mode **Numérique XXL** avec date personnalisable et barre de progression des secondes. Météo locale automatique configurée depuis l'interface Web (`WEATHER_CITY`).
  3. **Conteneurs Docker actifs (Page 1/2)** : Liste des conteneurs en cours d'exécution avec leurs adresses IP et ports.
  4. **Conteneurs Docker actifs (Page 2/2)** : Suite des conteneurs actifs (13 à 24).
  5. **Machines Virtuelles (VMs)** : État en direct des VMs Unraid (Active / Arrêtée).
  6. **Array, Parité & Réseau** : Uptime serveur, état de la parité, statut de l'Array et **courbe temps réel du débit réseau**.
  7. **Détail individuel des disques Unraid** : État de chaque disque (`Parity`, `Disk 1..N`, `Cache`) avec température, jauge de remplissage et indicateur Actif / Veille (Spindown).
  8. **Météo complète (Heure par heure & 7 jours)** : Prévisions détaillées sur les 8 prochaines heures et tendance sur 7 jours (icônes vectorielles, températures Min/Max et probabilité de pluie).
* **Alertes visuelles critiques** : Bandeau d'alerte rouge clignotant automatique en cas de surchauffe CPU (`>= 90 °C`), surchauffe disque (`>= 50 °C`) ou anomalie de l'Array.
* **Galerie de fonds d'écran & GIF animés** : Import et suppression de vos images ou GIF directement depuis le navigateur (`/config/wallpapers/`), avec fond dédié par page optionnel.
* **Mode Nuit Solaire automatique** : Réduction automatique de la luminosité selon les heures réelles de lever et coucher du soleil de votre ville.

> 🌤️ **Météo automatique :** La ville météo se configure directement depuis l'interface Web (`WEATHER_CITY`), sans clé API ni variable supplémentaire requise.
