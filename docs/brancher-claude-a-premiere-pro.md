# Brancher Claude à Premiere Pro

Ce guide explique seulement comment brancher Claude Code à Premiere Pro, pour que Claude puisse poser ta timeline, tes zooms, ta musique et exporter ta vidéo à ta place. Compte 20 à 30 minutes la première fois, ensuite c'est réglé.

Tu n'as aucune commande à taper : Claude fait la partie technique, toi tu fais quelques clics dans Premiere.

## Ce qu'il te faut

- Un **Mac** (M1, M2, M3, M4 de préférence). Le kit ne marche pas sur Windows.
- **Claude Code**, connecté à ton compte Claude.
- **Premiere Pro** et **Media Encoder** (abonnement Adobe, 7 jours d'essai gratuit). Media Encoder sert à exporter la vidéo.
- Environ 10 Go de place libre.

## 1. Installer Premiere Pro (avant le kit)

Installe Premiere **avant** le kit : c'est pendant l'installation du kit que Premiere est branché à Claude.

1. Va sur [adobe.com/fr/products/premiere.html](https://www.adobe.com/fr/products/premiere.html) et clique sur **Essai gratuit**. La formule « Premiere » seule suffit.
2. Installe l'application **Adobe Creative Cloud**, puis, dedans, **Premiere Pro** et **Media Encoder** (bouton **Installer**).
3. Ouvre Premiere une première fois, puis referme-le.

Tu veux juste tester ? Annule avant la fin des 7 jours sur [account.adobe.com/plans](https://account.adobe.com/plans) et tu ne paies rien.

## 2. Installer le kit (c'est lui qui branche Premiere)

Ouvre Claude Code et écris :

> Installe le kit de montage : https://github.com/cblain100-prog/kit-montage-ia

Compte une dizaine de minutes. Il te demandera peut-être de coller une ligne et de taper ton mot de passe de Mac (pour installer Homebrew) : c'est normal, suis ses instructions.

Pour Premiere, Claude fait tout seul :

- il installe le **connecteur** entre Claude et Premiere ([Adobe_Premiere_Pro_MCP](https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP), version 1.2.8, toujours la même version, vérifiée) ;
- il ajoute dans Premiere le panneau **MCP Bridge**, qui reçoit les ordres de Claude ;
- il déclare le connecteur dans Claude Code ;
- il le **verrouille** : pas d'envoi de statistiques, et trois outils risqués du connecteur interdits à Claude.

À la fin, il te dit que l'installation est terminée.

## 3. Régler Premiere (une seule fois)

1. Ouvre Premiere. Dans le menu **Premiere** (en haut à gauche) > **Préférences** > **Plug-ins**, coche **« Activer le mode de développement »**.
2. **Quitte Premiere et relance-le** (le réglage ne compte qu'au démarrage suivant).
3. Ouvre un projet, ou crée-en un vide.
4. Menu **Fenêtre** > **Extensions** > **MCP Bridge (CEP)**. Le panneau s'ouvre et le pont démarre tout seul.
5. Le panneau doit afficher **« Connected »** et **« Premiere Pro: Ready »**. S'il reste sur **« Disconnected »**, clique sur **Start Bridge**.

Premiere en anglais ? C'est **Preferences** > **Plugins**, puis **« Enable developer mode »**, et **Window** > **Extensions** > **MCP Bridge (CEP)**.

## 4. Relancer Claude Code

Quitte Claude Code et relance-le : c'est à ce moment-là qu'il charge le connecteur Premiere (et les commandes `/create-style` et `/montage`).

C'est branché. À chaque montage, garde Premiere ouvert avec un projet et le panneau MCP Bridge ouvert.

## Si ça bloque

- **MCP Bridge n'apparaît pas dans Fenêtre > Extensions** : vérifie que « Activer le mode de développement » est coché et que tu as bien relancé Premiere après.
- **Tu as installé Premiere après le kit** : tape `/montage`, il voit que Premiere n'est pas branché et s'en occupe.
- **Le panneau reste sur « Disconnected »** : le champ **Temp Directory** doit contenir `/tmp/premiere-mcp-bridge`. Corrige-le si besoin, clique sur **Save Configuration**, puis sur **Start Bridge**.
- **Tu avais déjà branché un autre connecteur Premiere avant** : le kit le garde tel quel. Pour le remplacer par la version verrouillée du kit, écris à Claude : « Lance `bash ~/kit-montage-ia/scripts/install-premiere.sh --force-register` ».
- **Premiere ne répond pas pendant un montage** : le kit te livre quand même ta vidéo, plus un fichier à importer dans Premiere (**Fichier** > **Importer**) pour retoucher ton projet.

## Tout enlever

Écris à Claude : « Lance `bash ~/kit-montage-ia/scripts/uninstall-premiere.sh` ». Il retire le connecteur de Claude Code, les trois interdictions, le panneau de Premiere, et remet comme avant le réglage d'Adobe qui autorise les extensions non signées.

## Et ensuite

Une fois Premiere branché : `/create-style` pour créer ton style de montage (une seule fois), puis `/montage` à chaque vidéo. Tout est expliqué dans le [README du kit](../README.md).
