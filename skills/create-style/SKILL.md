---
name: create-style
description: Crée le style de montage de l'utilisateur, à faire avant son premier montage, sans qu'il ait rien à écrire. Pose ses questions une par une (une vidéo montée dont il aime le rendu, la sienne ou une référence, son site ou sa charte, puis de courts extraits A/B/C sur une de ses phrases pour les cadrages, le rythme, les zooms, les bruitages, la musique et les mots à l'écran) et écrit looks/<nom>/look.json, que le skill montage applique ensuite à chaque vidéo. Utiliser quand l'utilisateur dit "/create-style", "crée mon style de montage", "définis mon style", "je veux mon propre montage", "crée mon style", "créer mon style de montage", ou quand le skill montage le lance faute de style.
---

# Créer le style de montage

On ne décrit pas un montage à l'IA avec des mots (« dynamique » ne veut pas dire la même chose pour lui et pour toi) : **on le lui montre, puis il choisit**. Tu poses tes questions toi-même, **une seule à la fois**, en français, en le tutoyant, sans jargon. Il répond par une lettre ou une phrase courte.

**Chaque valeur du style vient de lui** : de la vidéo qu'il donne, de sa charte, ou de ses choix. Tu ne préremplis rien, tu ne proposes aucun goût à toi, et tu ne nommes ni ne reproduis jamais un créateur précis. Les règles de qualité du kit (`rules/qualite.md`) ne sont pas des goûts : elles s'appliquent de toute façon, tu n'as pas à les lui demander.

## 0. Trouver le kit

```bash
KIT="$(cat ~/.config/kit-montage-ia/kit_dir 2>/dev/null)"
SK="$(python3 -c 'import os; print(os.path.realpath(os.path.expanduser("~/.claude/skills/create-style")))' 2>/dev/null)"
for d in "$KIT" "$(dirname "$(dirname "$SK")")" "$HOME/kit-montage-ia" $(find "$HOME" -maxdepth 2 -name kit-montage-ia -type d 2>/dev/null); do [ -d "$d/.venv" ] && KIT="$d" && break; done
if [ -d "$KIT/.venv" ]; then echo "KIT=$KIT"; cd "$KIT"; PY="$KIT/.venv/bin/python"; $PY tools/check.py; else echo "KIT INTROUVABLE"; fi
```

Kit absent ou ligne « MANQUE » : installe-le comme le dit le skill `montage` (étape 0, points 1 et 2), puis reviens ici. Nom du style : sa marque ou son prénom en minuscules, sans espace. `cp -r looks/_modele looks/<nom>` : la structure, toutes les valeurs vides.

## 1. Une vidéo dont il aime le montage

Question : **« T'as une vidéo montée dont t'aimes bien le rendu ? Une des tiennes, ou une vidéo de quelqu'un d'autre dont le montage te plaît. Glisse-la ici, sinon dis non. »**

Si oui :
```bash
$PY tools/analyse_style.py "<vidéo>" --name <nom>
```
(environ 1 minute pour 10 minutes de vidéo). Ouvre la planche (`open projects/_styles/<nom>/style-sheet.jpg`), regarde-la toi aussi, et résume les mesures en 5 lignes simples, sans jamais nommer l'auteur de la vidéo : une coupe toutes les X secondes, plans larges ou serrés, part du temps en visuels plein écran, zooms dans les plans ou non, texte à l'écran souvent ou rarement, musique et à quel niveau sous la voix. Demande : **« C'est bien ce rythme-là que tu veux ? »**

Ce qu'il valide va dans `looks/<nom>/look.json` (avec `_why` : « mesuré sur sa vidéo de référence, validé le <date> ») : `cut.shot_target`, `cut.min_shot`, `cut.max_shot` (valeurs de `style.json` > `suggested_look`), `music.body.under_lu` si une musique est mesurée, `keywords.frequency`. Ce que la vidéo ne tranche pas nettement se décide à l'étape 3.

Si non : tout se décide à l'étape 3.

## 2. Sa charte

Question : **« C'est quoi ton site, ou ta page de vente ? Sinon donne-moi tes couleurs, tes polices et ton logo. »**

- Un site : récupère la page (WebFetch, et `curl -sL` pour le CSS), repère la couleur d'accent (boutons, liens, la couleur vive qui revient), la couleur de fond, les polices (`font-family`, liens Google Fonts), le logo (`<link rel="icon">`, `og:image`, logo de l'en-tête). Montre-le-lui en une ligne et demande si c'est juste.
- Police : si c'est une police Google Fonts (licence OFL), télécharge la graisse grasse depuis `https://github.com/google/fonts` (dossier `ofl/<nom>/`) dans `assets/fonts/`, avec son `OFL.txt` renommé `<Nom>-OFL.txt`, déclare-la dans `brand.fonts` et `brand.title_family`. Police payante ou introuvable : dis-le et propose la plus proche des polices du kit (Inter, Inter Tight, Poppins, Anton), il choisit.
- Logo : `looks/<nom>/logo.<ext>`, chemin dans `brand.logo`.
- `brand.accent`, `brand.background` (fond des visuels plein écran : sa couleur de fond, ou une version sombre si elle est trop claire pour rester lisible, en le lui disant), `brand.site`.

## 3. Les extraits A/B/C (seulement ce qui n'est pas tranché)

Il faut une phrase à lui, filmée brute. Question : **« Pour te montrer les versions, il me faut une phrase à toi, filmée face caméra, pas montée : glisse un rush, même de 20 secondes. »** (S'il a déjà donné un rush, reprends-le sans redemander. S'il filme avec deux téléphones, demande les deux fichiers.)

Prépare l'extrait une fois :
```bash
$PY tools/projet.py style-<nom> "<rush>" ["<rush de côté>"] --look <nom>
$PY tools/transcribe.py style-<nom>
$PY prompteur.py words style-<nom>
```
Mets dans `plan.keep` UNE phrase complète de 8 à 15 s (`[["mot@t1", "mot@t2"]]`), puis `$PY prompteur.py cut style-<nom> && $PY prompteur.py base style-<nom>`. Choisis 1 ou 2 mots forts dits ensemble (un chiffre, une notion clé) pour `--words "MOT@t,MOT@t"`.

Une vidéo de choix à la fois, dans cet ordre, en sautant ce qui est déjà tranché. Les options sont volontairement neutres et très différentes :

| Choix | Commande | Options | Ce que tu écris dans son style |
|---|---|---|---|
| Cadrages | `$PY tools/choix.py style-<nom> cadrages` | A un seul cadrage, B large et serré, C large, serré, très serré | `framing.one_camera` (ou `two_cameras`) : `cycle`, `zoom` et `first` de l'option choisie (affichés par `tools/choix.py`) |
| Rythme | `$PY tools/choix.py style-<nom> rythme` | A coupes entre les phrases, B une coupe toutes les 4 s, C toutes les 2 s avec pauses courtes | `cut` : les valeurs de l'option choisie (affichées par `tools/choix.py`) ; avec deux téléphones, demande ensuite « tu veux changer de caméra souvent, ou rester plusieurs secondes sur la même ? » et écris `cut.cam_hold` |
| Zooms | `$PY tools/choix.py style-<nom> zooms --words ...` | A aucun, B léger, C marqué sur le mot fort | A : `zoom.default` 100 à 100. B : `zoom.default` 100 à 104, `alternate` true. C : 100 à 108, `alternate` true, `zoom.accent` enabled, 100 à 115, `accent_words` = ses mots forts habituels |
| Bruitages | `$PY tools/choix.py style-<nom> sons --words ...` | A aucun, B doux, C marqués | A : `sound.cues` vide. B : `{"on": "every face cut", "file": "click-soft.wav", "db": -30}`. C : `click-soft.wav` -25 à chaque coupe, `whoosh-short.wav` -24 à l'entrée d'un visuel (`visual entrance`), `pop.wav` -21 sur un mot à l'écran (`keyword or icon pop`), `insert_sounds` true |
| Musique | `$PY tools/musique.py get trio` (une fois) puis `$PY tools/choix.py style-<nom> musique` | trois ambiances différentes (calme, énergique, tension) | le morceau choisi dans `music.palette` (`$PY tools/musique.py palette <nom> <fichiers>`), puis demande « la musique, plus forte, pareil, ou plus discrète ? » : `music.intro.under_lu` et `music.body.under_lu` (16 pareil, 12 plus forte, 20 plus discrète). « Aucune » : refais avec d'autres morceaux de la même ambiance (`musique.py get <ambiance>`) ou ses propres morceaux (`musique.py add`), ou palette vide (pas de musique) |
| Mots à l'écran | `$PY tools/choix.py style-<nom> mots --words ...` | A aucun, B simples, C en gras | `keywords.style` = `none`, `simple` ou `gras`, puis demande « souvent ou rarement ? » pour `keywords.frequency` |

Après chaque vidéo : ouvre-la (`open <fichier>`), dis en une ligne ce que montrent A, B, C, attends sa réponse. Une réponse mixte (« la B, mais parfois la C ») se traduit telle quelle (par exemple zoom léger par défaut, zoom marqué seulement sur les mots forts). Rien ne lui plaît : refais un extrait avec des réglages entre deux options, jusqu'à ce qu'il dise oui. Il ne sait pas : laisse la valeur vide (le kit ne fera pas cet effet) et dis-le.

Ensuite, deux questions courtes, seulement s'il a une musique : **« Tu veux un petit effet sonore au tout début de la vidéo, et un changement de musique à chaque partie ? »** Oui : `music.intro.open` = `{"riser": "hook-riser-1.wav", "impact": "hook-impact-1.wav", "start_hit": false}` et/ou `music.change_on_chapter` true. Et **« À la fin, la musique s'arrête pendant ton appel à l'action ? »** Oui : `music.outro` = `{"fade": 2.0}`.

## 4. Écrire et valider

- Écris `looks/<nom>/look.json` : même structure que `looks/_modele/look.json`, chaque valeur choisie avec un `_why` qui cite sa réponse et la date, `name` rempli. Vérifie que c'est du JSON valide (`$PY -c "import json; json.load(open('looks/<nom>/look.json'))"`).
- Résume-le en 7 lignes au plus : cadrages, rythme, zooms, bruitages, musique, mots à l'écran, couleurs et police.
- Demande : **« Je garde ce style ? »** Il corrige un point : tu changes cette valeur et tu remontres le résumé. Il valide : dis-lui que le skill `montage` l'appliquera à chaque vidéo, et que ses retours dans le studio l'affineront.
- Supprime le projet d'essai (`rm -rf projects/style-<nom>`), garde `projects/_styles/<nom>/`.
