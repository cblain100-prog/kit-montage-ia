# projects/

Un dossier par vidéo, créé par `tools/projet.py <slug> <vidéo de face> [<vidéo de côté>]`. Rien de ce dossier ne part sur GitHub (il est ignoré par git) : tes rushes, tes transcriptions et tes rendus restent sur ton Mac.

```
projects/<slug>/
  plan.json        le plan de montage (source de vérité) : prises gardées, visuels, bruitages, musique
  assets/          liens vers les rushes, voix extraite, transcription, edl.json (les morceaux coupés)
  inserts/         une page HyperFrames par visuel
  work/            fichiers intermédiaires (plans caméra, voix montée, visuels rendus, vérifications)
  renders/         les versions montées et les planches de contrôle
  premiere/        un projet Premiere par version
  review/          les commentaires du studio, un fichier par version
```

`plan.exemple.json` montre un plan complet, champ par champ (les clés `_doc` sont des explications, le moteur les ignore).

Les dossiers `style-<nom>/` (extrait pour les vidéos de choix) et `_styles/<nom>/` (analyse de ta vidéo) viennent du skill `create-style`.
