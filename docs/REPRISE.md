# Reprise — CyberScribe

Document de point d’arrêt pour reprendre après une réinstallation système.
Mis à jour le **2026-09-11**.

## État actuel

| Élément | Valeur |
|--------|--------|
| Version code | **1.4.0** (`__version__` dans `CyberScribe.py`) |
| Branche | `main` |
| Dernier commit | `dd0071e` — *fix(core): harden recording, config, and shutdown for v1.2* |
| Release | [v1.2](https://github.com/nico2511/CyberScribe/releases/tag/v1.2) (`CyberScribe.exe` joint) |
| Remote | `https://github.com/nico2511/CyberScribe.git` |
| Working tree | propre et synchronisé avec `origin/main` au moment de la rédaction |

**On s’est arrêté ici :** v1.2.0 est livrée (audit v1.1 → durcissement enregistrement / config / shutdown + CI). Pas de chantier de code ouvert ni de changements locaux non poussés. La suite logique est la **validation manuelle** du plan de test v1.2, puis d’éventuelles idées pour une v1.3.

## Après réinstallation Windows

```powershell
git clone https://github.com/nico2511/CyberScribe.git
cd CyberScribe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy config.example.json config.json
python CyberScribe.py
```

- `config.json` et le dossier `models/` sont **gitignorés** (réglages locaux + modèles Whisper téléchargés).
- EXE prêt à l’emploi : [CyberScribe.exe (v1.2)](https://github.com/nico2511/CyberScribe/releases/download/v1.2/CyberScribe.exe).
- Build local / CI : voir `README.md` et `.github/workflows/build.yml` (tag `v*` → release + artefact).

## Config locale de référence (avant réinstall)

Valeurs qui étaient en place sur la machine (également dans `config.example.json`) :

- hotkey `F8`, langue `fr`, modèle `base`
- device `auto`, compute `int8`, profil `fast`
- `max_record_seconds` : `25`

## Ce qui a été livré en v1.2 (rappel)

- Plus de collage des messages d’erreur de transcription dans la fenêtre active (notification tray)
- Échec micro : overlay ne reste pas bloqué en enregistrement
- Rechargement Whisper quand modèle / device / compute change
- Frames audio thread-safe, WAV temporaires préfixés, config atomique validée
- Arrêt propre (plus de `os._exit`), mutex mono-instance, logs sûrs en `--noconsole`
- Fenêtre settings scrollable, version dans tray/splash, `requirements.txt`
- CI à jour (`checkout@v4`, `setup-python@v5`, `action-gh-release@v2`)
- README aligné (le live streaming avait déjà été retiré)

## Plan de test v1.2 (à valider après réinstall)

- [ ] Premier lancement : splash « modèle en cours de chargement », tray → **Prêt**
- [ ] F8 start/stop : overlay, beeps, collage dans le Bloc-notes
- [ ] Micro refusé / débranché : overlay ne reste pas coincé
- [ ] Changer le modèle dans Configuration : tray « chargement » puis **Prêt**
- [ ] Hotkey invalide → repli sur F8
- [ ] Seconde instance → dialogue « déjà en cours »
- [ ] Confirmé : Actions attache bien `CyberScribe.exe` à la release (déjà le cas pour v1.2)

## Pistes éventuelles pour une prochaine session (v1.3+)

Rien n’est engagé. Idées possibles si on reprend le produit :

1. Boucler et cocher le plan de test ci-dessus sur la machine fraîche
2. UX : feedback plus clair pendant le chargement / la transcription longue
3. Packaging : vérifier encore le chemin Silero VAD dans le build PyInstaller après maj `faster-whisper`
4. Docs / store : description GitHub du dépôt, captures à jour si l’UI a bougé
5. **Updater** : voir `docs/AUDIT_PRODUIT.md` et `updater.py` — tester swap EXE sur Windows après tag `v1.3.0`

## Fichiers clés

- `CyberScribe.py` — application (tray, hotkey, Whisper, overlay, settings)
- `requirements.txt` — dépendances Python
- `config.example.json` — modèle de config (copier vers `config.json`)
- `.github/workflows/build.yml` — build EXE + release sur tag
- `screenshots/sc.png` — capture README
- `app.ico` — icône

## Conversations Cursor liées

- [Project audit and release](1ccfeebf-4f32-40d3-a96b-199e918aef8d) — audit v1.1 → release v1.2
