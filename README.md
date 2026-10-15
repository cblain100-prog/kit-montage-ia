# Kit de montage Premiere Pro

Claude x Premiere Pro : ta vidéo YouTube montée automatiquement, dans **ton** style. Gratuit. Le guide pas à pas est aussi dans mon Skool : https://www.skool.com/colin-lab-1969/about

Tu filmes, tu donnes tes vidéos à Claude Code, et il fait le montage : il trie tes prises à l'oreille, alterne les cadrages, ajoute les zooms, les bruitages, la musique, les mots-clés et les animations, pose toute la timeline dans Premiere Pro et l'exporte. Ensuite tu corriges dans un petit studio dans ton navigateur (commentaires, coupes, volume de la musique), et chaque correction rend la vidéo suivante meilleure.

Dedans : le skill `create-style` (ton style de montage, une seule fois), le skill `montage` (dérush à l'oreille, animations, Premiere Pro, vérification), les agents qui fabriquent et vérifient les animations, et le studio où tu fais tes retours.

Tu n'as aucun prompt à écrire : les deux skills te posent leurs questions, une à la fois.

## Ce qu'il te faut

- Un **Mac** (Apple Silicon conseillé : M1, M2, M3, M4...). Le kit ne marche pas sur Windows.
- **Claude Code** installé, avec un abonnement Claude. **L'abonnement Max est conseillé** : un montage complet demande beaucoup d'échanges avec Claude (animations écrites par plusieurs agents en parallèle, vérifications). Pour monter, choisis le modèle **Opus 5.5** avec l'effort au **maximum** (`/model`, puis `/effort`).
- **Adobe Creative Cloud** avec **Premiere Pro** et **Media Encoder** (c'est Premiere qui monte et exporte ; sans lui, le kit monte quand même avec ffmpeg, mais tu n'as pas de projet Premiere à retoucher).
- Un ou deux téléphones pour filmer, en **paysage**, en **4K** si possible, et un micro (cravate ou micro posé, un peu éloigné de la bouche pour que la voix ne sature pas).
- Environ 10 Go de place libre.

## Installer

Ouvre Claude Code et dis-lui :

> Installe le kit de montage : https://github.com/cblain100-prog/kit-montage-ia

Il clone ce dépôt, installe ce qui manque (ffmpeg, Python, Node, le connecteur Premiere, les polices, des bruitages, de quoi récupérer des musiques libres, les deux skills et les agents de vérification) et vérifie que tout marche. Compte une dizaine de minutes. Il te demandera peut-être de coller une ligne dans le Terminal (pour Homebrew, qui demande ton mot de passe de Mac).

Quand c'est fini, **quitte Claude Code et relance-le** : les commandes `/create-style` et `/montage` apparaissent à ce moment-là.

Puis, une seule fois, dans Premiere Pro (le pas à pas en images est dans mon guide sur Skool : https://www.skool.com/colin-lab-1969/about) :

1. **Premiere Pro > Réglages > Plug-ins** : coche « Activer le mode développeur », puis quitte et relance Premiere.
2. **Fenêtre > Extensions > MCP Bridge (CEP)** : le pont démarre tout seul à l'ouverture du panneau. Vérifie juste que Temp Directory = `/tmp/premiere-mcp-bridge` (sinon corrige-le et « Save Configuration ») ; si le panneau affiche « Stopped », clique « Start Bridge ».

À chaque montage, Premiere doit être ouvert avec le panneau MCP Bridge ouvert. Si le pont ne répond pas, le kit livre quand même la vidéo (ffmpeg) et un fichier XML de la timeline : dans Premiere, Fichier > Importer, et tu as ton projet à retoucher.

## Utiliser, en 4 étapes

1. **Tourner** : voir « Bien filmer » juste en dessous. Dépose ta ou tes vidéos dans un dossier.
2. **Ton style, une seule fois** : tape `/create-style`. Le kit n'a aucun style à lui : tout vient de toi. Il te demande :
   - une vidéo de référence : une des tiennes, ou celle d'un créateur dont tu aimes le montage ;
   - ta charte (couleurs, polices, logo), ou à défaut ton site ou ta page de vente ;
   - puis il te montre de petits extraits A, B, C de quelques secondes : la même phrase montée de plusieurs façons (cadrages, zooms, bruitages, musiques, mots à l'écran). Tu dis ce que tu aimes et ce que tu n'aimes pas (« la B, mais parfois la C »), il refait des extraits jusqu'à ce que ce soit bon.
   Claude enregistre tes choix dans ton fichier de style. Sans lui, le montage ne démarre pas.
3. **Le montage, à chaque vidéo** : choisis Opus 5.5 avec l'effort au maximum, puis tape `/montage`. Il te demande où sont tes vidéos, puis il fait tout :
   - le dérush à l'oreille : il écoute, réécoute chaque passage douteux et coupe au bon endroit ;
   - les animations avec HyperFrames (un outil gratuit) : plusieurs agents en parallèle, chacun fait une animation, la regarde image par image et la corrige ;
   - puis il prend le contrôle de Premiere Pro : il pose les plans, les zooms, les animations, les bruitages et la musique (baissée quand tu parles), et il exporte ;
   - une équipe d'agents vérifie la vidéo avant de te la livrer ([rules/qualite.md](rules/qualite.md) : pas de fin de mot coupée, pas d'image qui flashe, rien de privé à l'écran, volume aux normes de YouTube...).
   Compte environ 45 minutes à 1 heure pour une vidéo d'une dizaine de minutes : tu peux faire autre chose pendant ce temps.
4. **Le studio** : dès que le montage est fini, il s'ouvre tout seul dans ton navigateur, avec ta vidéo dedans.
   - **C** : commenter à l'instant précis (le commentaire se cale tout seul au bon moment de la vidéo).
   - **S** pour couper, clic sur un morceau puis **Suppr** pour l'enlever, **Cmd+Z** pour annuler.
   - Onglet **Musique** : le volume de chaque morceau.
   - **« Reconstruire »** applique tout de suite tes coupes et tes réglages de musique (environ 25 minutes, la nouvelle version s'ouvre seule).
   - Pour tes commentaires : clique **« J'ai fini »**, puis écris **« c'est fait »** à Claude dans Claude Code. Il lit chaque commentaire, corrige, refait passer la vidéo dans Premiere et rouvre le studio sur la nouvelle version.

Chaque retour devient une règle de ton style, le « mode d'emploi » que Claude relit à chaque vidéo : il ne refait plus la même erreur à la vidéo suivante. Les premières vidéos demandent plusieurs allers-retours, les suivantes de moins en moins.

Pour retoucher un détail à la main, ouvre le projet Premiere de la version finale et modifie ce que tu veux. Fais-le seulement sur la version finale : chaque nouvelle version recrée un projet Premiere neuf, et une retouche faite avant serait perdue.

## Bien filmer pour un montage facile

- Le téléphone en face de toi, en 4K : c'est ce qui permet de zoomer sur toi sans que l'image devienne floue.
- Un micro, un peu éloigné de la bouche.
- Quand tu te trompes, ne recommence pas depuis le début : marque quelques secondes de silence et reprends là où tu en étais. Claude garde la dernière prise complète.
- Avec deux téléphones : un de face (le principal), un de côté. Le kit les synchronise tout seul grâce au son.

## Musiques et bruitages

Aucune musique n'est livrée dans le dépôt (chaque morceau a sa licence). Le kit sait télécharger des morceaux libres de Kevin MacLeod (gratuit avec une ligne de crédit dans ta description, que le kit te redonne à chaque montage), et tu peux ajouter tes propres morceaux (Mixkit, Pixabay, etc.). Les bruitages sont fabriqués par le kit : ils sont à toi. Détails : [assets/README.md](assets/README.md).

## Le connecteur Premiere et ta sécurité

Le kit pilote Premiere avec un connecteur libre ([Adobe_Premiere_Pro_MCP](https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP), version 1.2.8). Il a été audité : pas de logiciel malveillant, mais quelques réglages risqués par défaut. L'installation du kit les verrouille :

- il est installé depuis une version précise du code source, jamais depuis npm ni « la dernière version » ;
- le dossier d'échange avec Premiere (`/tmp/premiere-mcp-bridge`) est réservé à ton compte : le panneau exécute toute commande déposée dedans ;
- l'envoi de statistiques d'usage et la vérification de mises à jour sont coupés (`~/.premiere-mcp-bridge/config.json` et les réglages du connecteur) ;
- trois outils du connecteur sont **interdits à Claude** dans `~/.claude/settings.json` (une copie de sauvegarde est faite avant, rien d'autre n'est modifié) : `execute_extendscript` (il exécute n'importe quel script dans Premiere, avec accès à tes fichiers), `delete_preview_files` (il efface les fichiers de n'importe quel dossier) et `invoke_tool` (il permettrait de contourner les deux premiers). Les scripts du kit, eux, utilisent encore `execute_extendscript` pour poser des centaines d'images-clés d'un coup, mais avec des scripts écrits dans le kit et envoyés par son propre programme (`premiere/ppbatch.py`), pas par Claude.

Pour tout enlever : `bash scripts/uninstall-premiere.sh`. Il retire le connecteur de Claude Code, les trois interdictions, le panneau de Premiere, et remet le « mode développeur » des extensions Adobe (`PlayerDebugMode`) comme avant : ce mode autorise Premiere à charger n'importe quelle extension non signée, l'installation l'active pour le panneau du connecteur (`--keep-debug-mode` pour le laisser si une autre extension en a besoin).

## Tes données

Tes rushes, tes transcriptions, tes montages et ton style restent sur ton Mac : le dossier `projects/` et ton style ne partent jamais sur GitHub. Le kit n'utilise aucune clé d'API : il passe par ton abonnement Claude Code.

## Ce que fait cette version (0.4)

- Un ou deux téléphones, vidéo YouTube 16:9 où tu parles face caméra.
- Mac uniquement.
- Premiere Pro pour le montage final (sinon ffmpeg en secours, plus un fichier XML à importer dans Premiere).
- Pas encore : DaVinci Resolve, CapCut, Windows, les reels verticaux.

## Crédits et licence

Créé par Colin Blain (Entrepreneurs 2.0), sous licence MIT ([LICENSE](LICENSE)). Le connecteur Premiere est le projet libre [Adobe_Premiere_Pro_MCP](https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP) (MIT), les animations sont rendues par HyperFrames (Apache-2.0). Toutes les briques et leurs licences : [THIRD_PARTY.md](THIRD_PARTY.md).
