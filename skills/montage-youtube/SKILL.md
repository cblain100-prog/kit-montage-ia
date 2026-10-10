---
name: montage-youtube
description: Monte une vidéo YouTube 16:9 où l'utilisateur parle face caméra (lue au prompteur ou non), filmée avec un ou deux téléphones, en appliquant SON style de montage (créé avant avec le skill style-de-montage, obligatoire) et les règles de qualité du kit. Dérush à l'oreille, cadrages, zooms, bruitages, musique et mots à l'écran selon son style, animations HyperFrames écrites par des agents en parallèle, timeline posée et exportée par Premiere Pro via le connecteur, vérification par l'équipe d'agents du kit, puis le studio où il commente, coupe et règle la musique. Installe ce qui manque au premier lancement. Utiliser quand l'utilisateur dit "/montage-youtube", "monte ma vidéo", "monte ma vidéo YouTube", "fais le montage de mes rushes", ou donne un dossier de rushes paysage à monter. Pas pour un reel vertical.
---

# Monter une vidéo YouTube avec le kit de montage

Tu montes la vidéo de l'utilisateur de bout en bout. Il n'écrit aucun prompt : tu poses tes questions toi-même, **une seule à la fois**, en français, en le tutoyant, sans jargon (un mot technique inévitable s'explique en une demi-phrase).

Deux sources, et seulement elles :
- **Son style** (`looks/<son-style>/look.json`) : tout ce qui est goût (rythme, pauses, cadrages, zooms, bruitages, musique, mots à l'écran, couleurs, police). Tu l'appliques, tu n'ajoutes jamais tes propres goûts ni ceux d'un autre créateur. Une valeur vide dans son style = on ne fait pas (pas de zoom, pas de bruitage, pas de musique, pas de mot à l'écran).
- **Les règles de qualité** (`rules/qualite.md`) : ce qui vaut pour toutes les vidéos (dernière prise complète, jamais de fin de mot coupée, aucun flash, textes = mots dits, rien de privé à l'écran, -14 LUFS, vérification avant de livrer, pièges de Premiere). Lis-les en entier avant de commencer.

## 0. Trouver le kit, vérifier l'installation et le style

```bash
KIT="$(cat ~/.config/kit-montage-ia/kit_dir 2>/dev/null)"; [ -d "$KIT/.venv" ] || KIT="$HOME/kit-montage-ia"
cd "$KIT" && PY="$KIT/.venv/bin/python" && $PY tools/check.py
```

- Pas de `.venv` dans `$KIT` (kit pas encore installé, ou seulement ajouté comme plugin dans `~/.claude/plugins/...`) : clone-le dans un dossier à lui, `git clone https://github.com/cblain100-prog/kit-montage-ia ~/kit-montage-ia`, puis `bash ~/kit-montage-ia/scripts/install.sh`. Jamais de projets dans le dossier du plugin.
- Une ligne « MANQUE » : `bash scripts/install.sh` (environ 10 minutes la première fois, annonce-le). Homebrew absent : donne-lui la ligne à coller dans le Terminal (elle demande son mot de passe de Mac).
- **Le style d'abord, toujours.** `$PY -c "import montage as M; print(M.personal_looks())"`. Liste vide : tu ne montes pas. Dis-lui en une phrase : « Avant ton premier montage, on crée ton style de montage, c'est lui que j'appliquerai à chaque vidéo. » puis lance le skill `style-de-montage` (s'il n'apparaît pas dans tes skills, lis `$KIT/skills/style-de-montage/SKILL.md` et suis-le) ; tu reviens ici quand il l'a validé. Plusieurs styles : demande lequel. Un seul : c'est lui.
- Lignes « ATTENTION » de skills ou d'agents : relance `bash scripts/install.sh --no-premiere` (rapide, il n'ajoute que ce qui manque).
- Pont Premiere inactif alors que le panneau est installé : dis-lui seulement d'ouvrir Premiere et de cliquer « Start Bridge » dans Fenêtre > Extensions > MCP Bridge (CEP) avant l'étape 7. Panneau jamais réglé : dis-lui ces deux réglages, une seule fois, puis continue (Premiere ne sert qu'à l'étape 7) :
  1. Premiere Pro > Réglages > Plug-ins : coche « Activer le mode développeur », puis quitte et relance Premiere.
  2. Fenêtre > Extensions > MCP Bridge (CEP) : Temp Directory = `/tmp/premiere-mcp-bridge`, « Save Configuration », puis « Start Bridge ».
- Pas de Premiere : le kit monte quand même avec ffmpeg (même montage, sans projet Premiere à retoucher). Dis-le une fois.

## 1. Les rushes

Première question, mot pour mot : **« Où sont tes vidéos ? »** (un dossier, ou glisse les fichiers ici).

- Liste les vidéos avec leur durée (`ffprobe`). Une vidéo = un téléphone ; deux vidéos de durée proche = deux téléphones ; plus : demande lesquelles.
- Deux téléphones : sors une image de chacune (`ffmpeg -ss 10 -i X -frames:v 1 /tmp/x.jpg`) et regarde-les : celle où il regarde l'objectif est la caméra A (de face), l'autre la B. Le son est pris sur celle qui a le meilleur son.
- Puis : **« T'as le texte de ta vidéo (ton script ou ton prompteur) ? Glisse-le ici, sinon dis non. »** Il sert à repérer les phrases dites deux fois et à bien écrire les noms propres.

## 2. Le projet

```bash
$PY tools/projet.py yt-<sujet-court> <video-de-face> [<video-de-cote>] --look <son-style> --title "<titre>"
```

Il copie dans `plan.json` les cadrages et le rythme de son style. Lis les avertissements : vidéo verticale (le kit fait du 16:9), pas en 4K (cadrages serrés plus doux), synchro pas fiable (vérifie à l'oreille), voix qui sature (à corriger au prochain tournage). Mets dans `plan.whisper_prompt` les noms propres et le jargon du script.

## 3. Transcription

`nohup $PY tools/transcribe.py <slug> > projects/<slug>/work/transcribe.log 2>&1 &` (environ 1 min pour 1 à 2 min de rush). Attends la ligne « words in » du journal.

## 4. Le dérush à l'oreille (`plan.keep`)

`$PY prompteur.py words <slug>` affiche le texte avec les temps. `plan.keep` = les bonnes prises dans l'ordre : `["mot@12.3", "mot@18.9", "note"]`.
- La dernière prise complète de chaque phrase ; chaque passage douteux s'écoute : `$PY prompteur.py takes <slug>`, `$PY prompteur.py gaps <slug>`, `$PY tools/hear.py <slug> <début> <fin>`, `$PY tools/energy.py <slug> <début> <fin>`. Jamais le texte de Whisper seul.
- Une reprise qui continue la même phrase : `{"join": true}`. Couper net avant un mot avalé : `"src:<temps>"` + `{"strict_end": true}`, après l'extinction réelle du mot.
- Puis `$PY prompteur.py cut <slug>` et `$PY prompteur.py base <slug>`. Le rythme (pauses, durée des plans, changements de caméra) vient de son style ; tu ne le changes pas.

## 5. Visuels et mots à l'écran (30 à 40 minutes, annonce-le)

`ffmpeg -y -i projects/<slug>/work/base.wav -ac 1 -ar 16000 projects/<slug>/work/base16.wav && $PY prompteur.py outwords <slug>` (relis le texte monté).

`plan.inserts` : un visuel par idée concrète, posé sur le mot exact. Types prêts en tête de `prompteur_blocks.py` ; couleurs et police viennent de son style (`brand`).
- **Mots à l'écran** : seulement si son style en veut (`keywords.style` = `simple` ou `gras`, `"kind": "keyword", "style": ...`), à la fréquence de son style ; toujours ses mots, tels qu'il les dit, chacun sur son mot.
- Les règles de `rules/qualite.md` : vraie image avant image générée, preuve exacte, rien de privé, rien qu'il n'a pas cité, texte court et lisible.
- **Animations sur mesure par l'agent `kit-montage-animateur`** : un agent par partie de la vidéo, lancés en parallèle dans le même message (outil Agent, `subagent_type: kit-montage-animateur`). Donne à chacun : le slug, sa partie (temps, phrases avec leurs ancres), le nom de son module (`projects/<slug>/partieN.py`), ce que chaque visuel doit montrer et le nom du style. Ils n'écrivent jamais dans les fichiers partagés ; toi tu assembles leurs `inserts()` dans `plan.inserts` via `projects/<slug>/build_inserts.py` (relancé par chaque reconstruction). Un agent qui atteint la limite de session : relance-le par message.
- Puis `$PY prompteur.py inserts <slug>` et `$PY prompteur.py render <slug>`.

## 6. Musique et bruitages

- `$PY tools/music_plan.py <slug> [--open-stop ... --open-back ...] [--close ...] [--outro ...]` : n'utilise que ce que son style a choisi (palette, niveaux, changement aux chapitres, ouverture, fin d'intro, fondu de fin). Palette vide : pas de musique. Passe les options `--open-*`, `--close`, `--outro` seulement si son style a la section correspondante.
- Les bruitages sont ceux de son style (`sound.cues`) ; aucun s'il n'en a pas choisi.
- Donne-lui les **crédits** des musiques utilisées pour sa description (le script les affiche).

## 7. Premiere monte et exporte (environ 25 minutes pour une vidéo complète)

```bash
$PY -c "import sys; sys.path.insert(0,'premiere'); import paths; print(paths.heartbeat_age())"   # moins de 60 s = pont actif
pgrep -f premiere/build_timeline.py                                                              # rien = Premiere libre
nohup $PY -u premiere/build_timeline.py <slug> --name <slug>-v1 --export > projects/<slug>/work/premiere.log 2>&1 &
```

Un projet Premiere neuf par version, noms de fichiers uniques, ProRes 4444 pour la transparence, export vérifié : c'est fait par le script (voir les pièges de `rules/qualite.md`). Pont coupé ou Premiere occupé : jamais l'interface à l'aveugle, chemin de secours `$PY tools/look_ffmpeg.py <slug> && $PY prompteur.py compose <slug> <slug>-v1`.

## 8. Vérification (15 minutes)

- `$PY tools/qa_measure.py <slug>`, `$PY tools/redites.py <slug>`, `$PY tools/qa_pack.py <slug> <slug>-v1 [script]`, `$PY tools/flashes.py projects/<slug>/renders/<slug>-v1.mp4`, `$PY prompteur.py joints <slug> <slug>-v1`, `$PY prompteur.py verbatim <slug>`, `$PY prompteur.py sheet <slug> <slug>-v1` (planche regardée en entier).
- **L'équipe de vérification du kit**, en parallèle dans le même message : `kit-montage-coupes` (les raccords signalés, par lots), `kit-montage-redites`, `kit-montage-visuels` (les visuels, par lots), `kit-montage-spectateur`. Chaque constat de base « jugement » passe par `kit-montage-sceptique`. Puis `kit-montage-chef` fusionne et range les corrections. Corrige les défauts confirmés et contrôle toi-même image par image ce qui a changé.

## 9. Livrer dans le studio

```bash
OUT=$($PY -c "import montage as M; print(M.output_dir())"); cp projects/<slug>/renders/<slug>-v1.mp4 "$OUT/"
nohup $PY review/serve.py "$OUT/<slug>-v1.mp4" --slug <slug> > projects/<slug>/review/serve.log 2>&1 &
```

Le studio s'ouvre (http://localhost:4700). Explique en 4 lignes : C pour commenter à l'instant précis, la timeline (S pour couper, clic puis Suppr, Cmd+Z), l'onglet Musique, et « Reconstruire » (environ 25 minutes, la version suivante s'ouvre seule). Donne le chemin de la vidéo, celui du projet Premiere, et les crédits pour la description.

## 10. Les retours, à chaque version

- Avant chaque passe, relis `projects/<slug>/review/<vidéo>.json`, même sans « J'ai fini ». Applique toute la liste d'un coup.
- **Chaque retour de goût devient une règle de SON style** : un réglage chiffré change la valeur dans `looks/<son-style>/look.json` (en remplaçant l'ancienne), une préférence va dans `look.rules` avec la date et sa phrase. La vidéo suivante en profite.
- Ses coupes et ses réglages de musique faits dans le studio sont déjà dans `plan.json`. Jamais de retouche dans Premiere avant la version finale : la timeline y est recréée à chaque version.

## Ce que tu confirmes à la fin

La vidéo (chemin), le lien du studio, le projet Premiere, ce qui a changé depuis la version précédente, ce que les agents ont trouvé et corrigé, ce qui reste à trancher, les crédits pour la description.
