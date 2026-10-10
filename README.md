# Le kit de montage IA

Ta vidéo YouTube montée par Claude Code et Premiere Pro, dans **ton** style.

Tu filmes, tu donnes tes vidéos à Claude Code, et il fait le montage : il trie tes prises à l'oreille, alterne les cadrages, ajoute les zooms, les bruitages, la musique, les mots-clés et les animations, pose toute la timeline dans Premiere Pro et l'exporte. Ensuite tu corriges dans un petit studio dans ton navigateur (commentaires, coupes, volume de la musique), et chaque correction rend la vidéo suivante meilleure.

Tu n'as aucun prompt à écrire : les deux skills te posent leurs questions, une à la fois.

## Ce qu'il te faut

- Un **Mac** (Apple Silicon conseillé : M1, M2, M3, M4...).
- **Claude Code** installé, avec un abonnement Claude. **L'abonnement Max est conseillé** : un montage complet demande beaucoup d'échanges avec Claude (animations écrites par plusieurs agents en parallèle, vérifications).
- **Adobe Creative Cloud** avec **Premiere Pro** et **Media Encoder** (c'est Premiere qui monte et exporte ; sans lui, le kit monte quand même avec ffmpeg, mais tu n'as pas de projet Premiere à retoucher).
- Un ou deux téléphones pour filmer, en **paysage**, en **4K** si possible, et un micro (cravate ou micro posé, un peu éloigné de la bouche pour que la voix ne sature pas).
- Environ 10 Go de place libre.

## Installer

Ouvre Claude Code et dis-lui :

> Installe le kit de montage : https://github.com/cblain100-prog/kit-montage-ia

Il clone ce dépôt, installe ce qui manque (ffmpeg, Python, Node, le connecteur Premiere, les polices, des bruitages, de quoi récupérer des musiques libres, les deux skills et les agents de vérification) et vérifie que tout marche. Compte une dizaine de minutes. Il te demandera peut-être de coller une ligne dans le Terminal (pour Homebrew, qui demande ton mot de passe de Mac).

Puis, une seule fois, dans Premiere Pro :

1. **Premiere Pro > Réglages > Plug-ins** : coche « Activer le mode développeur », puis quitte et relance Premiere.
2. **Fenêtre > Extensions > MCP Bridge (CEP)** : le pont démarre tout seul à l'ouverture du panneau. Vérifie juste que Temp Directory = `/tmp/premiere-mcp-bridge` (sinon corrige-le et « Save Configuration ») ; si le panneau affiche « Stopped », clique « Start Bridge ».

À chaque montage, Premiere doit être ouvert avec le panneau MCP Bridge ouvert. Si le pont ne répond pas, le kit livre quand même la vidéo (ffmpeg) et un fichier XML de la timeline : dans Premiere, Fichier > Importer, et tu as ton projet à retoucher.

## Utiliser

1. **Ton style d'abord, une seule fois** : dis à Claude Code « crée mon style de montage » (skill `create-style`). Le kit n'a aucun style à lui : tout vient de toi. Il te demande une vidéo montée dont tu aimes le rendu (la tienne ou une autre), ton site ou ta charte, puis il te montre une de tes phrases montée de plusieurs façons (A, B, C) pour les cadrages, le rythme, les zooms, les bruitages, la musique et les mots à l'écran. Tu réponds par une lettre, ou « la B, mais parfois la C ». Il écrit ton fichier de style. Sans lui, le montage ne démarre pas.
2. **Chaque vidéo** : dis « monte ma vidéo » (skill `montage`). Il te demande où sont tes vidéos, applique ton style et les règles de qualité du kit ([rules/qualite.md](rules/qualite.md) : pas de fin de mot coupée, pas d'image qui flashe, rien de privé à l'écran, volume aux normes de YouTube...), fait vérifier la vidéo par une équipe d'agents, puis t'ouvre le studio.
3. **Le studio** : touche C pour commenter à l'instant précis, la timeline sous la vidéo pour couper (S, Suppr, Cmd+Z), l'onglet Musique pour régler le volume, et « Reconstruire » pour la version suivante.

Une première version complète prend du temps : environ 30 à 40 minutes pour les animations, 25 minutes de montage machine, 15 minutes de vérification.

## Bien filmer pour un montage facile

- Le téléphone en face de toi, en 4K : c'est ce qui permet de zoomer sur toi sans que l'image devienne floue.
- Un micro, un peu éloigné de la bouche.
- Quand tu te trompes, ne recommence pas depuis le début : marque deux secondes de silence et reprends la phrase. Claude garde la dernière prise complète.
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

## Ce que fait cette version (0.3)

- Un ou deux téléphones, vidéo YouTube 16:9 où tu parles face caméra.
- Mac uniquement.
- Premiere Pro pour le montage final (sinon ffmpeg en secours, plus un fichier XML à importer dans Premiere).
- Pas encore : DaVinci Resolve, CapCut, Windows, les reels verticaux.

## Crédits et licence

Créé par Colin Blain (Entrepreneurs 2.0), sous licence MIT ([LICENSE](LICENSE)). Le connecteur Premiere est le projet libre [Adobe_Premiere_Pro_MCP](https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP) (MIT), les animations sont rendues par HyperFrames (Apache-2.0). Toutes les briques et leurs licences : [THIRD_PARTY.md](THIRD_PARTY.md).
