# Audit produit — CyberScribe

Date : **2026-09-15**  
Version auditée : **1.4.0** (updater EXE, installateur Inno, dossier modèles configurable)

## Synthèse

CyberScribe est une application Windows **locale** de dictée vocale → texte, centrée sur le **systray**, avec raccourci global et collage automatique. Le code est concentré dans un monolithe Python (`CyberScribe.py` + `updater.py`), packagé en **un seul EXE** via PyInstaller, distribué par **tags GitHub** (`v*` → release + `CyberScribe.exe`).

| Critère | Évaluation |
|--------|------------|
| Proposition de valeur | Claire : offline, confidentialité, simplicité F8 |
| Maturité technique (v1.2+) | Bonne : mutex, config validée, shutdown propre, CI |
| Dette / complexité | Faible volume de fichiers, logique lisible |
| Distribution | Release GitHub : EXE portable + installateur Inno Setup |
| Mises à jour (avant v1.3) | Manuelles (re-téléchargement) |
| Mises à jour (v1.3+) | **Updater intégré** pour l’EXE packagé |
| Modèles (v1.4) | `models_dir` dans config ; migration déplacer/copier depuis l’UI |

## Architecture

```
Utilisateur (hotkey F8)
    → AudioRecorder (PyAudio, WAV temp)
    → Transcriber (faster-whisper, models/)
    → pyperclip + pynput (Ctrl+V)
Systray (pystray) + Tk (overlay, settings)
Config atomique (config.json à côté de l’EXE)
```

**Points forts**

- Transcription **100 % locale** ; logs sans contenu dicté.
- **Mono-instance** (mutex Windows) — évite les conflits de hotkey.
- **Config** : clés connues uniquement, écriture atomique `.tmp` + `os.replace`.
- **Profils** fast / balanced / accurate mappés sur paramètres Whisper + VAD.
- **CI** : build reproductible, asset VAD Silero injecté dans l’EXE.

**Risques / limites connus**

| Risque | Impact | Mitigation actuelle |
|--------|--------|---------------------|
| Collage Ctrl+V dans la fenêtre active | Moyen (UX / sécurité contextuelle) | Documenté ; pas de collage des erreurs |
| Dépendance GPU / CUDA optionnelle | Perf variable | Détection `nvidia-smi`, repli CPU |
| Taille EXE + modèles Whisper | Disque, premier lancement | Modèles dans `models/` gitignoré |
| PyInstaller onefile | Temps de démarrage, antivirus | Choix assumé pour simplicité |
| Pas de signature Authenticode | SmartScreen, confiance | À traiter côté release (hors code) |
| API GitHub pour updates | Rate limit, offline | Échec gracieux + opt-out config |

## Parcours utilisateur

1. Lancement → splash → chargement Whisper en arrière-plan.
2. Tray « Prêt » → F8 enregistre → overlay + bips → re-F8 transcrit + colle.
3. Configuration : hotkey, langue, modèle, device, profil, durée max.
4. **v1.3** : vérification optionnelle des releases GitHub ; installation in-place de l’EXE.

## Qualité code (échantillon)

- Gestion d’erreurs cohérente (`log` / `log_error`, tray notify).
- Threads : enregistrement, transcription, chargement modèle, update check — file `queue` pour le thread Tk principal (correct pour l’UI).
- Arrêt : plus de `os._exit` brutal ; nettoyage micro, hotkey, tray.

**Pistes non engagées**

- Checklist de tests manuels v1.2/v1.3 sur machine Windows réelle.
- Signature code, installateur MSI, canal beta.
- Checksum affiché dans l’UI (déjà vérifié côté téléchargement si `.sha256` en release).

## Updater installateur (v1.3) — conception

### Objectif

Permettre à un utilisateur qui a déployé **`CyberScribe.exe` portable** (dossier avec `config.json` et `models/`) de **passer à une nouvelle release** sans retélécharger manuellement depuis le navigateur, tout en **préservant** config et modèles (ils ne sont pas touchés).

### Contrainte Windows

Un processus ne peut pas remplacer son propre fichier `.exe` en cours d’exécution. Stratégie classique :

1. Télécharger `CyberScribe.update.exe` dans le même répertoire que l’EXE live.
2. Générer `_cyberscribe_apply_update.cmd` qui :
   - attend la fin du processus `CyberScribe.exe` ;
   - renomme l’ancien binaire en `.bak` (si présent) ;
   - promeut le fichier `.update.exe` → `CyberScribe.exe` ;
   - relance l’application ;
   - supprime le script.
3. L’app lance le `.cmd` en processus détaché puis quitte proprement.

### Source de vérité

- `GET https://api.github.com/repos/nico2511/CyberScribe/releases/latest`
- Asset attendu : `CyberScribe.exe`
- Asset optionnel : `CyberScribe.exe.sha256` (hex seul, généré en CI) — vérification après téléchargement.

### Sécurité pragmatique

- Téléchargement **uniquement** depuis l’API release (URL d’asset GitHub).
- Taille minimale de fichier (garde-fou anti-page d’erreur HTML).
- SHA-256 si le sidecar est publié (CI v1.3+).
- Pas de téléchargement arbitraire d’URL utilisateur.

### UX

- Case « Vérifier automatiquement au démarrage » (`check_updates` dans `config.json`).
- Entrée menu tray + bouton dans Configuration.
- Notification tray si une version plus récente est détectée (check différé ~8 s après démarrage).
- En mode `python CyberScribe.py` : consultation des versions possible, **pas** de swap d’EXE.

### Fichiers

| Fichier | Rôle |
|---------|------|
| `updater.py` | API release, téléchargement, script d’application |
| `CyberScribe.py` | Intégration UI / tray / cycle de vie |
| `.github/workflows/build.yml` | Publie `.exe` + `.sha256` |

## Recommandations release

1. Tag `v1.3.0` pour activer l’updater côté clients déjà en 1.2.x (ils verront la nouvelle version).
2. Conserver **le nom d’asset** `CyberScribe.exe` stable.
3. Envisager **signature Authenticode** sur l’EXE pour réduire les alertes SmartScreen.
4. Exécuter les scénarios de test manuels (dictée, update, migration modèles).
