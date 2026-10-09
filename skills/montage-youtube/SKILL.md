---
name: montage-youtube
description: Monte une vidéo YouTube 16:9 où tu parles face caméra (lue au prompteur ou non), filmée avec un ou deux téléphones, dans TON style (le fichier créé par le skill style-de-montage) : dérush à l'oreille, cadrages qui alternent, zooms, bruitages, musique, mots-clés et animations HyperFrames écrites par des agents en parallèle, timeline posée et exportée par Premiere Pro via le connecteur, vérification par une équipe d'agents, puis le studio où tu commentes, coupes et règles la musique. Installe ce qui manque au premier lancement. Utiliser quand l'utilisateur dit "/montage-youtube", "monte ma vidéo", "monte ma vidéo YouTube", "fais le montage de mes rushes", ou donne un dossier de rushes paysage à monter. Pas pour un reel vertical.
---

# Monter une vidéo YouTube avec le kit de montage

Tu montes la vidéo de l'utilisateur de bout en bout. Il n'écrit aucun prompt : tu poses tes questions toi-même, **une seule à la fois**, en français, en le tutoyant, sans jargon (et si un mot technique est inévitable, tu l'expliques en une demi-phrase). Tu appliques son style (`looks/<nom>/look.json`), tu ne réinventes pas un style.

## 0. Trouver le kit et vérifier l'installation

```bash
KIT="$(cat ~/.config/kit-montage-ia/kit_dir 2>/dev/null)"; [ -d "$KIT" ] || KIT="${CLAUDE_PLUGIN_ROOT}"
cd "$KIT" && PY="$KIT/.venv/bin/python" && $PY tools/check.py
```

- Si `KIT` est vide, ou si le kit vient d'être ajouté comme plugin (dossier `~/.claude/plugins/...`) : clone-le dans un dossier à lui, `git clone https://github.com/cblain100-prog/kit-montage-ia ~/kit-montage-ia`, puis `bash ~/kit-montage-ia/scripts/install.sh`. Jamais de projets dans le dossier du plugin (il est remplacé à chaque mise à jour).
- Une ligne « MANQUE » : lance `bash scripts/install.sh` (environ 10 minutes la première fois, annonce-le). Homebrew absent : donne-lui la ligne à coller dans le Terminal (elle demande son mot de passe de Mac, toi tu ne peux pas la taper).
- Premiere installé mais pont pas encore réglé : dis-lui ces deux réglages, une seule fois, puis continue (le montage n'attend pas Premiere, il en a besoin seulement à l'étape 8) :
  1. Premiere Pro > Réglages > Plug-ins : coche « Activer le mode développeur », puis quitte et relance Premiere.
  2. Fenêtre > Extensions > MCP Bridge (CEP) : Temp Directory = `/tmp/premiere-mcp-bridge`, « Save Configuration », puis « Start Bridge ».
- Pas de Premiere : le kit monte quand même avec ffmpeg (même montage, mais pas de projet Premiere à retoucher). Dis-le une fois.

**Le style** : `ls looks/`. Un seul style perso (autre que `exemple`) : c'est lui. Plusieurs : demande lequel. Aucun : propose de lancer d'abord le skill `style-de-montage` (10 à 20 minutes, une seule fois) ; s'il préfère monter tout de suite, prends `exemple` et dis-le.

## 1. Les rushes

Première question, mot pour mot : **« Où sont tes vidéos ? »** (un dossier, ou glisse les fichiers ici).

- Liste les vidéos du dossier avec leur durée (`ffprobe`). Une vidéo = un téléphone. Deux vidéos de même durée à peu près = deux téléphones. Plus : demande lesquelles.
- Deux téléphones : sors une image de chacune (`ffmpeg -ss 10 -i X -frames:v 1 /tmp/x.jpg`), regarde-les : la caméra **de face** (il regarde l'objectif) est la caméra A, celle de côté la B. Le son est pris automatiquement sur celle qui a le meilleur son (le micro).
- Puis, une question : **« T'as le texte de ta vidéo (ton script ou ton prompteur) ? Glisse-le ici, sinon dis non. »** Il sert à repérer les phrases dites deux fois et à bien écrire les noms propres.

## 2. Le projet

```bash
$PY tools/projet.py yt-<sujet-court> <video-de-face> [<video-de-cote>] --look <nom-du-style> --title "<titre>"
```

Lis les avertissements : vidéo verticale (le kit fait du 16:9 : dis-lui de filmer en paysage), pas en 4K (les plans serrés seront plus doux), synchro pas fiable (vérifie à l'oreille), voix qui sature (micro trop près de la bouche : à corriger au prochain tournage). Mets dans `plan.whisper_prompt` les noms propres et le jargon du script (outils, marques, son prénom).

## 3. Transcription (environ 1 min pour 1 à 2 min de rush)

```bash
nohup $PY tools/transcribe.py <slug> > projects/<slug>/work/transcribe.log 2>&1 &
```

Toujours en tâche de fond avec `nohup` pour un rush long (les tâches de fond normales s'arrêtent au bout de 2 h). Attends la ligne « words in » du journal, pas la fin d'un `pgrep` (la boucle d'attente se trouverait elle-même).

## 4. Le dérush à l'oreille (`plan.keep`)

`$PY prompteur.py words <slug>` affiche le texte avec les temps. `plan.keep` = la liste des bonnes prises, dans l'ordre : `["mot@12.3", "mot@18.9", "note"]` (le mot dit le plus près de ce temps).

- **Toujours la dernière prise complète** de chaque phrase. Il a appris à marquer un silence et à reprendre la phrase : la reprise est après.
- **Jamais se fier au texte seul** : Whisper fusionne les faux départs et les phrases dites deux fois. Lance `$PY prompteur.py takes <slug>` (chaque prise retranscrite seule) et `$PY prompteur.py gaps <slug>` (chaque trou de plus de 0,5 s écouté seul), et écoute chaque passage douteux avec `$PY tools/hear.py <slug> <début> <fin>` (temps de la vidéo montée) ou `$PY tools/energy.py <slug> <début> <fin>` (niveau du son dans le rush).
- Une reprise qui continue la même phrase : `{"join": true}` sur la prise suivante (sinon un petit blanc casse la phrase).
- Couper net avant un mot avalé : `"src:<temps>"` + `{"strict_end": true}`, posé APRÈS l'extinction réelle du mot (lis le niveau avec `energy.py`, jamais la fin donnée par Whisper).
- Une erreur dite au prompteur (un chiffre faux) se coupe, et tu le signales.
- La toute dernière phrase : coupe juste après le dernier mot, avant toute inspiration.

Puis `$PY prompteur.py cut <slug>` : il affiche la durée moyenne par caméra. Avec deux téléphones elle doit rester entre 4 et 7 s (on coupe toutes les 2 à 3 s, mais en recadrant sur la même caméra). Avec un téléphone, chaque coupe passe de large à serré à très serré. Le premier plan est toujours de face (`first_angle`). Puis `$PY prompteur.py base <slug>`.

## 5. Visuels et mots-clés (30 à 40 minutes, annonce-le)

`ffmpeg -y -i projects/<slug>/work/base.wav -ac 1 -ar 16000 projects/<slug>/work/base16.wav && $PY prompteur.py outwords <slug>` (la voix montée retranscrite : relis-la, chaque mot affiché se cale dessus).

`plan.inserts` : un visuel par idée concrète, posé sur le mot exact (`"at": "mot@123.4"`, `"until"` ou `"dur"`). Les types prêts sont décrits en tête de `prompteur_blocks.py` (`keyword`, `diamonds` pour les numéros de chapitre, `bullets`, `doc` pour une vraie page web, `term` pour un vrai terminal, `still`, `wall`, `logo`, `icon`, `scene` pour une animation sur mesure). Règles :
- **Mots-clés** : seulement SES mots, tels qu'il les dit, seulement les importants (chiffre, prix, contraste, notion clé), 1 à 4 mots, chacun sur son mot dit ; jamais sa phrase entière, jamais un texte inventé, jamais sur un visuel plein écran (le moteur les retire tout seul). Style du look : `keywords.style` (`chrome` = `"kind": "keyword", "style": "chrome"`, `kinetic` = `"kind": "keyword"`, `none` = aucun).
- **Tout illustrer en vrai** : un mail, un post, un tableau, une page : la chose elle-même (capture, interface redessinée), jamais une liste de texte sur une image générique. Une action dite à l'oral (« va dans Réglages ») se montre en vraies captures, étape par étape. Une preuve montre exactement ce qu'il dit (le bon chiffre, la vraie page).
- **Jamais de look « fait par l'IA »** : pas de carte blanche arrondie avec ombre, petite étiquette, gros chiffre et sous-titre en italique. Fonds sombres avec de la profondeur, peu de texte, l'image porte l'idée.
- Un visuel ne revient pas quelques secondes plus tard ; une carte n'est jamais coupée à moitié par un zoom ; aucun écran vide en tête de visuel ; un compteur affiche le chiffre au moment où il le dit ; un nom inventé à l'écran (client, mail) ne doit jamais tomber sur une vraie personne.
- **Animations sur mesure par des agents en parallèle** : pour chaque partie de la vidéo, lance un agent (outil Agent, en parallèle dans le même message) qui écrit son module dans `projects/<slug>/` (`partie1.py`, `partie2.py`... avec une fonction `inserts()` qui renvoie ses inserts `kind: scene`), jamais dans les fichiers partagés du kit ; chacun rend des aperçus et les regarde image par image avant de rendre la main ; toi tu les assembles dans `plan.inserts` (un petit `projects/<slug>/build_inserts.py` qui réécrit `plan.inserts`, relancé par chaque reconstruction). Les agents peuvent atteindre la limite de session : relance-les par message (ils gardent leur contexte) plutôt que de tout refaire.

Puis `$PY prompteur.py inserts <slug>` (il signale les plans de visage de moins de 1 s) et `$PY prompteur.py render <slug>` (4 animations à la fois).

## 6. Musique

`$PY tools/music_plan.py <slug> --open-stop "mot@t" --open-back "mot@t" --close "mot@t" [--cut "mot@t"] --outro "mot@t"` : le hook d'ouverture (montée, silence sous la phrase choc, impact), la fin d'intro (cymbale à l'envers, puis voix seule), un morceau neuf à chaque carte de chapitre, fondu sur la conclusion et rien sous l'appel à l'action. La musique s'ancre toujours sur des mots ou des cartes (`ins:<id>`), jamais sur des temps de sortie (sinon elle se décale à la moindre coupe). Palette vide : `$PY tools/musique.py get sombre` puis `$PY tools/musique.py palette <look> <fichiers>` (ou sans musique s'il n'en veut pas). Écoute le début, les coupures et la fin d'intro.

## 7. Bruitages

Ceux du look (un pop par mot-clé, un whoosh par visuel, un clic par coupe). Un bruitage se coupe à 0,5 s au plus sous une phrase calme (un long riser ou un glitch s'entend comme un grésillement). Les sons sont dans `assets/sfx` (générés par le kit, remplaçables).

## 8. Premiere monte et exporte (environ 25 minutes pour une vidéo complète, jamais annoncer moins)

```bash
$PY -c "import sys; sys.path.insert(0,'premiere'); import paths; print(paths.heartbeat_age())"   # moins de 60 s = pont actif
pgrep -f premiere/build_timeline.py                                                              # rien = Premiere libre
nohup $PY -u premiere/build_timeline.py <slug> --name <slug>-v1 --export > projects/<slug>/work/premiere.log 2>&1 &
```

Un projet Premiere neuf par version (`projects/<slug>/premiere/<slug>-vN.prproj`) : un seul projet qui accumule les imports finit par ne plus répondre. Plans sur V1 avec les zooms du look en images-clés, animations plein écran sur V2, mots-clés au-dessus (ProRes 4444, Premiere refuse le WebM transparent), voix, un clip par bruitage, musique baissée sous la voix, export Media Encoder, puis -14 LUFS. Chaque fichier passe sous un nom unique calculé sur son contenu (Premiere garde la durée d'un fichier d'après son chemin, même dans un projet neuf). Media Encoder peut échouer en silence : le script vérifie la durée de l'export et le journal de Media Encoder ; s'il s'arrête, lis le message.

**Pont coupé** (signe de vie de plus de 60 s) ou un autre montage en cours : ne pilote jamais l'interface de Premiere à l'aveugle. Chemin de secours, même montage : `$PY tools/look_ffmpeg.py <slug> && $PY prompteur.py compose <slug> <slug>-v1`.

## 9. Vérification (15 minutes)

- `$PY tools/qa_measure.py <slug>` (chaque raccord mesuré : fin de mot mangée, attaque coupée, trop de blanc), `$PY tools/redites.py <slug>` (phrases dites deux fois, à écouter), `$PY tools/qa_pack.py <slug> <slug>-v1 [script]` (le dossier de preuves `work/qa/`), `$PY tools/flashes.py projects/<slug>/renders/<slug>-v1.mp4` (une image isolée), `$PY prompteur.py joints <slug> <slug>-v1`, `$PY prompteur.py verbatim <slug>`, `$PY prompteur.py sheet <slug> <slug>-v1` (planche regardée en entier).
- **L'équipe de vérification** : lance en parallèle trois agents (outil Agent) avec `work/qa/` : un pour les raccords de voix (mot mangé, redite, coupe brutale ; il écoute avec `tools/hear.py`), un pour les visuels (sur leur mot, lisibles, aucune info privée à l'écran ; il regarde `work/qa/strips/`), un spectateur qui découvre la vidéo et dit ce qui ne se comprend pas. Chaque défaut « de jugement » passe par un quatrième agent sceptique qui essaie de le réfuter. Corrige les défauts confirmés, puis contrôle toi-même image par image ce qui a changé.

## 10. Livrer dans le studio

```bash
OUT=$($PY -c "import montage as M; print(M.output_dir())"); cp projects/<slug>/renders/<slug>-v1.mp4 "$OUT/"
nohup $PY review/serve.py "$OUT/<slug>-v1.mp4" --slug <slug> > projects/<slug>/review/serve.log 2>&1 &
```

Le studio s'ouvre dans le navigateur (http://localhost:4700). Explique-lui en 4 lignes : C pour commenter à l'instant précis, la timeline sous la vidéo (S pour couper, clic sur un morceau puis Suppr, Cmd+Z), l'onglet Musique pour régler chaque morceau, et « Reconstruire » (environ 25 minutes, la version suivante s'ouvre seule). Donne le chemin de la vidéo, le chemin du projet Premiere, et les **crédits à coller dans la description** (lignes « credit » des musiques utilisées, `assets/music/CREDITS.json`).

## 11. Les retours, à chaque version

- Avant chaque passe, relis `projects/<slug>/review/<vidéo>.json`, même s'il n'a pas cliqué « J'ai fini ». Applique toute la liste d'un coup.
- **Chaque retour devient une règle de son style** : un réglage chiffré va dans la bonne valeur de `looks/<nom>/look.json` (en remplaçant l'ancienne, jamais deux valeurs qui se contredisent), une règle de goût va dans `look.rules` avec la date et sa phrase à lui. La vidéo suivante en profite sans qu'il le redise.
- Ses coupes et ses réglages de musique faits dans le studio sont déjà dans `plan.json` : ils survivent à chaque reconstruction. Ne lui demande jamais de retoucher dans Premiere avant la version finale : la timeline y est recréée à chaque version.

## Pièges déjà rencontrés (ne pas les refaire)

- Pause de 0,75 s entre deux phrases : « trop d'espace ». Le look garde 0,38 s dans une phrase, 0,30 à 0,55 s entre deux prises.
- Fin de mot mangée par le fondu : la fin d'une prise se pose au moins 0,28 s après la fin réelle du son.
- Caméra qui change à chaque coupe : ça donne le tournis. On coupe souvent, on change de caméra rarement.
- Après chaque modification de code, vérifie la syntaxe (`$PY -c "import ast; ast.parse(open('fichier.py').read())"`) avant de lancer une chaîne longue.
- `xargs -I` sur macOS plafonne la longueur de commande : passe par un petit script (`xargs -n 1 script.sh`).
- La page du studio et tout ce qui dure plus de 2 h se lancent avec `nohup`.
- Ne jamais annoncer une durée trop courte : animations et recherche de preuves 30 à 40 minutes, une passe machine 25, la vérification 15.

## Ce que tu confirmes à la fin

La vidéo (chemin), le lien du studio, le projet Premiere, ce qui a changé point par point depuis la version précédente, ce que les agents ont trouvé et corrigé, ce qui reste à trancher, et les crédits pour la description.
