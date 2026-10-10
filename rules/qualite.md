# Règles de qualité du kit

Ces règles valent pour toutes les vidéos, quel que soit le créateur. Ce ne sont pas des goûts : ce sont des défauts qu'un spectateur remarque, ou des pièges techniques. Tout ce qui est une question de goût (rythme des coupes, longueur des pauses, cadrages, zooms, bruitages, musique, mots à l'écran, couleurs, polices, types de visuels) vient UNIQUEMENT du style du créateur (`looks/<son-style>/look.json`), créé avec le skill `create-style`. Jamais d'un autre créateur, jamais d'une valeur par défaut inventée.

## Dérush

- On garde la dernière prise complète de chaque phrase.
- On ne se fie jamais à la transcription seule : Whisper fusionne les faux départs et les phrases dites deux fois. Chaque passage douteux s'écoute (`prompteur.py takes`, `prompteur.py gaps`, `tools/redites.py`, `tools/hear.py`).
- On ne coupe jamais la fin d'un mot : la fin d'une prise se pose après l'extinction réelle du son (mesurée avec `tools/energy.py`), jamais sur la fin donnée par Whisper.
- Une reprise qui continue la même phrase se colle à la première prise sans blanc (`{"join": true}`).
- Une erreur de fait dite au tournage se coupe, et on la signale au créateur.

## Image

- Aucune image isolée (un « flash ») à une coupe ou entre deux visuels : `tools/flashes.py` sur chaque rendu, `prompteur.py joints` pour les raccords des visuels plein écran.
- Un plan de visage visible entre deux visuels dure au moins 1 s (sinon c'est un flash).
- Une carte ou un visuel qui entre reste entier : jamais coupé à moitié par un zoom ou par le bord.
- Pas d'écran vide en tête de visuel.

## Texte et visuels

- Tout texte à l'écran reprend des mots réellement dits (vérifié par `prompteur.py verbatim`). Exceptions : le texte d'une vraie interface, un chiffre dit en lettres affiché en chiffres, un bandeau avec le nom.
- Jamais une phrase entière recopiée à l'écran : le texte affiché est court et lisible (taille, contraste, marge au bord).
- Une vraie image (capture, vraie page, vraie interface redessinée) passe avant une image générée par IA.
- Une preuve montre exactement ce qui est dit (le bon chiffre, la vraie page).
- Rien de privé à l'écran : aucun nom de client réel, e-mail, téléphone, adresse, numéro d'entreprise ou bancaire, clé d'API, titre de discussion privée. Un nom inventé ne doit pas tomber sur une vraie personne.
- On ne montre pas ce que la personne n'a pas cité.

## Son

- La musique reste toujours sous la voix, jamais par-dessus : elle baisse quand la voix parle.
- Volume final : -14 LUFS (la norme de YouTube), crête sous -1,5 dB.
- Une musique a une licence connue (crédit noté dans `assets/music/CREDITS.json` et redonné pour la description). Jamais un morceau du commerce ni une musique trouvée sur YouTube.
- Une voix qui sature se signale au créateur (micro trop près de la bouche).

## Vérifier avant de livrer

- Planche de contrôle regardée en entier (`prompteur.py sheet`), `tools/qa_measure.py`, `tools/redites.py`, `tools/qa_pack.py`, `tools/flashes.py`.
- L'équipe de vérification (agents `kit-montage-coupes`, `kit-montage-redites`, `kit-montage-visuels`, `kit-montage-spectateur`), chaque constat de jugement passé au `kit-montage-sceptique`, puis le `kit-montage-chef`. On corrige les défauts confirmés et on contrôle soi-même image par image ce qui a changé.
- On n'annonce jamais une durée trop courte : animations 30 à 40 minutes, une passe machine environ 25 minutes pour une vidéo complète, la vérification 15 minutes.

## Pièges techniques

- Premiere garde la durée d'un fichier d'après son chemin, même dans un projet neuf : chaque fichier lui est donné sous un nom unique calculé sur son contenu (fait par `premiere/build_timeline.py`). Sinon Media Encoder plante en plein export ou laisse du noir.
- Un projet Premiere neuf par version : un projet qui accumule les imports finit par ne plus répondre.
- Premiere refuse le WebM transparent : les visuels transparents passent en ProRes 4444.
- Media Encoder peut échouer en silence : on vérifie la durée de l'export et son journal (`build_timeline.py` le fait).
- La musique s'ancre sur des mots ou des cartes (`mot@temps`, `ins:<id>`), jamais sur des temps de sortie, sinon elle se décale à la moindre coupe.
- Les tâches longues (transcription d'un long rush, le studio, un montage Premiere) se lancent avec `nohup` : les tâches de fond s'arrêtent au bout de 2 heures.
- Pont Premiere coupé (signe de vie de `/tmp/premiere-mcp-bridge/bridge-heartbeat.json` de plus de 60 s) ou un autre montage en cours : on ne pilote jamais l'interface de Premiere à l'aveugle ; secours : `tools/look_ffmpeg.py` puis `prompteur.py compose` (`review/rebuild.sh` le fait tout seul).
- Une boucle d'attente `until ! pgrep -f "<motif>"` se trouve elle-même : attendre plutôt une ligne du journal.
- Après chaque modification de code : vérifier la syntaxe avant de lancer une chaîne longue.
- `xargs -I` sur macOS plafonne la longueur de commande : passer par un petit script (`xargs -n 1 script.sh`).
