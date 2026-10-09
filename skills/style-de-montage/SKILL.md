---
name: style-de-montage
description: Crée le style de montage de l'utilisateur, une seule fois, sans qu'il ait rien à écrire. Pose ses questions une par une (une vidéo à lui déjà montée, son site ou sa charte, puis des petites vidéos de choix A/B/C sur une de ses phrases pour les zooms, les bruitages, la musique et les mots à l'écran), et écrit le fichier de style looks/<nom>/look.json que le skill montage-youtube applique ensuite à chaque vidéo. Utiliser quand l'utilisateur dit "/style-de-montage", "crée mon style de montage", "définis mon style", "je veux mon propre montage", ou avant un premier montage quand aucun style perso n'existe.
---

# Créer le style de montage

Le secret pour ne pas revenir sans cesse sur un montage : **on ne décrit pas son montage à l'IA avec des mots** (« dynamique » ne veut pas dire la même chose pour lui et pour toi), **on le lui montre**, puis il choisit. Tu poses tes questions toi-même, **une seule à la fois**, en français, en le tutoyant, sans jargon. Il répond par une lettre ou une phrase courte. Ce skill tourne une fois ; ensuite le style ne bouge plus, sauf les petits réglages que ses retours ajoutent.

**Jamais tu ne proposes de copier le montage d'un autre créateur.** Si la vidéo qu'il donne n'est pas la sienne (une chaîne connue, un autre YouTubeur), tu le dis gentiment et tu passes aux choix : le but, c'est SON style.

## 0. Trouver le kit

```bash
KIT="$(cat ~/.config/kit-montage-ia/kit_dir 2>/dev/null)"; [ -d "$KIT" ] || KIT="${CLAUDE_PLUGIN_ROOT}"
cd "$KIT" && PY="$KIT/.venv/bin/python" && $PY tools/check.py
```

Kit absent ou ligne « MANQUE » : installe-le comme le dit le skill `montage-youtube` (étape 0), puis reviens ici. Choisis le nom du style : son prénom ou sa marque en minuscules (`looks/<nom>/`). Pars d'une copie du style de départ : `cp -r looks/exemple looks/<nom>`. Tout ce qui n'est pas tranché garde la valeur de départ, déjà validée sur de vraies vidéos.

## 1. Sa vidéo à lui

Question, mot pour mot : **« T'as déjà une vidéo montée dont t'aimes bien le rendu ? Glisse-la ici, sinon dis non. »**

Si oui :
```bash
$PY tools/analyse_style.py "<vidéo>" --name <nom>
```
(1 minute environ pour 10 minutes de vidéo). Montre-lui la planche (`projects/_styles/<nom>/style-sheet.jpg`, ouvre-la avec `open`) et résume les mesures en 5 lignes simples : une coupe toutes les X secondes, plans larges ou serrés, part du temps en visuels plein écran, zooms dans les plans ou non, texte à l'écran souvent ou rarement, musique et à quel niveau sous la voix. Regarde aussi la planche toi-même (couleurs des textes, style des visuels).

Ce que tu en tires, dans `looks/<nom>/look.json` (seulement ce qui est net) :
- rythme : `cut.shot_target`, `cut.min_shot`, `cut.max_shot` (valeurs proposées dans `style.json` > `suggested_look`) ;
- zooms : beaucoup d'avancées dans les plans = la poussée lente est son style (`zoom.default` gardé) ; aucune = `zoom.default.from` et `to` à 100 ;
- texte à l'écran : sur moins de 10 % des plans = mots-clés rares ; sur plus de 40 % = fréquents (`keywords.frequency`) ;
- musique : niveau sous la voix (`music.body.under_lu`), ou pas de musique ;
- ce qu'il faut encore trancher (bruitages, style des mots, morceau précis) : étape 3.

Si non : passe à la question 2, tout se tranchera par les choix.

## 2. Sa charte

Question : **« C'est quoi ton site ? Ou donne-moi tes couleurs, tes polices et ton logo. »**

- Un site : récupère la page d'accueil (WebFetch, et `curl -sL` pour le CSS), repère la couleur d'accent (boutons, liens, la couleur vive qui revient), la couleur de fond, les polices (`font-family`, liens Google Fonts) et le logo (`<link rel="icon">`, `og:image`, un `<img>` ou `<svg>` dans l'en-tête). Ne garde que ce qui est sûr, montre-le-lui en une ligne (« accent #1E6BFF, fond blanc, police Montserrat, logo trouvé »).
- Police : si c'est une police Google Fonts (licence OFL), télécharge le fichier TTF de la graisse grasse depuis `https://github.com/google/fonts` (dossier `ofl/<nom>/`) dans `assets/fonts/`, avec son `OFL.txt` renommé `<Nom>-OFL.txt`, et déclare-la dans `brand.fonts` ; `brand.title_family` = son nom. Police payante ou introuvable : garde Inter Tight, et dis-le.
- Logo : enregistre-le dans `looks/<nom>/logo.<ext>` et mets le chemin dans `brand.logo`.
- Écris `brand.accent` (la couleur des mots forts et des losanges), `brand.background` (le fond des visuels plein écran : garde un fond sombre si sa charte est claire, les visuels restent lisibles sur la face cam), `brand.site`.

## 3. Les vidéos de choix (seulement pour ce qui n'est pas tranché)

Il faut une phrase à lui, filmée brute. Question : **« Pour te montrer les versions, il me faut une phrase à toi, filmée face caméra, pas montée : glisse un rush, même de 20 secondes. »** (S'il a donné un rush plus tôt, reprends-le sans redemander.)

Prépare l'extrait une fois :
```bash
$PY tools/projet.py style-<nom> "<rush>" [--look <nom>]
$PY tools/transcribe.py style-<nom>
$PY prompteur.py words style-<nom>
```
Mets dans `plan.keep` UNE phrase complète de 8 à 15 s (`[["mot@t1", "mot@t2"]]`), puis `$PY prompteur.py cut style-<nom> && $PY prompteur.py base style-<nom>`. Choisis 1 ou 2 mots forts dits ensemble (un chiffre, une notion clé) pour `--words "MOT@t,MOT@t"`.

Puis une vidéo de choix à la fois, dans cet ordre, en sautant ce qui est déjà tranché :

| Choix | Commande | Il répond... | Ce que tu écris dans le look |
|---|---|---|---|
| Zooms | `$PY tools/choix.py style-<nom> zooms --words ...` | A coupes seules, B poussée lente, C zoom amorti sur le mot fort, D dézoom rapide | A : `zoom.default.from`=`to`=100, `zoom.accent.enabled` false. B : `zoom.accent.enabled` false. C : valeurs de départ (B + C de temps en temps). D : `zoom.dezoom` gardé, accent gardé. « la B mais parfois la C » = valeurs de départ. |
| Bruitages | `$PY tools/choix.py style-<nom> sons --words ...` | A aucun, B doux, C punchy | A : `sound.cues` vide. B : seulement `every face cut` à -30 dB. C : valeurs de départ. |
| Musique | `$PY tools/musique.py get sombre` (une fois) puis `$PY tools/choix.py style-<nom> musique` | A, B ou C, ou « aucune ne va » | Le morceau choisi dans `music.palette` (`$PY tools/musique.py palette <nom> <fichiers>`), les refusés dans `music.refused` avec sa phrase. « Aucune » : refais avec `get electro` ou `get leger`, ou avec ses propres morceaux (`musique.py add`). Il faut 3 essais parfois : c'est normal. |
| Mots à l'écran | `$PY tools/choix.py style-<nom> mots --words ...` | A aucun, B chromés, C cinétiques | `keywords.style` = `none`, `chrome` ou `kinetic`. |

Après chaque vidéo : ouvre-la (`open <fichier>`), dis en une ligne ce que montrent A, B, C, et attends sa réponse. Une réponse floue (« je sais pas ») : propose ta recommandation (les valeurs de départ) et demande juste « ça te va ? ».

## 4. Écrire et valider

- Écris `looks/<nom>/look.json` (même structure que `looks/exemple/look.json`, chaque choix avec un `_why` qui cite sa réponse et la date). Vérifie que c'est du JSON valide.
- Résume-le en 6 lignes au plus : rythme des coupes, cadrages, zooms, bruitages, musique, mots à l'écran, couleurs et police.
- Demande : **« Je garde ce style ? »** Il corrige un point : tu changes cette valeur, tu remontres le résumé. Il valide : c'est fini. Dis-lui que le skill `montage-youtube` l'appliquera à chaque vidéo, et que ses retours dans le studio l'affineront tout seuls.
- Supprime le projet d'essai si tu n'en as plus besoin (`rm -rf projects/style-<nom>`), garde `projects/_styles/<nom>/` (la planche de sa vidéo).
