# Assets : polices, bruitages, musiques

## Polices (`fonts/`)

Toutes sous licence SIL Open Font License 1.1 (le fichier de licence est à côté de chaque police) : Inter, Inter Tight, Poppins, Anton, JetBrains Mono, Instrument Serif. Tu peux ajouter la police de ta marque ici (avec son fichier de licence) : le skill `style-de-montage` le fait pour une police Google Fonts.

## Bruitages (`sfx/`, pas dans le dépôt)

`tools/make_sfx.py` les fabrique à l'installation : pop, whoosh, clics, frappe au clavier, montées, impacts, cymbale à l'envers. Ce sont des sons originaux, sans crédit à mettre. Pour en changer un, remplace le fichier par un autre WAV du même nom. Sources gratuites :

- Mixkit, bruitages gratuits sans crédit : https://mixkit.co/free-sound-effects/ (licence : https://mixkit.co/license/)
- Pixabay, bruitages : https://pixabay.com/sound-effects/ (licence : https://pixabay.com/service/license-summary/)

Garde les bruitages courts (0,5 s au plus pour ceux qui tombent sous une phrase calme).

## Musiques (`music/`, pas dans le dépôt)

Aucune musique n'est livrée (chaque morceau a sa licence). `tools/musique.py` t'aide :

```bash
.venv/bin/python tools/musique.py list                 # le catalogue et ce que tu as déjà
.venv/bin/python tools/musique.py get sombre           # télécharge des morceaux de Kevin MacLeod
.venv/bin/python tools/musique.py add ~/Downloads/morceau.mp3 --credit "..."   # un morceau à toi
.venv/bin/python tools/musique.py palette <ton-style> fichier1.mp3 fichier2.mp3  # les met dans ton style
```

Sources gratuites :

- **Kevin MacLeod** (incompetech.com), licence Creative Commons BY 4.0 : gratuit à condition de mettre la ligne de crédit dans la description YouTube. Exemple : `"Stormfront" Kevin MacLeod (incompetech.com) Licensed under Creative Commons: By Attribution 4.0 License http://creativecommons.org/licenses/by/4.0/`. Le kit garde la ligne de chaque morceau dans `music/CREDITS.json` et te la redonne à chaque montage.
- **Mixkit**, musiques gratuites sans crédit : https://mixkit.co/free-stock-music/ (licence : https://mixkit.co/license/)
- **Pixabay**, musiques gratuites sans crédit : https://pixabay.com/music/ ; quelques morceaux sont déclarés dans Content ID par leur auteur : publie d'abord en non répertorié pour vérifier qu'aucune réclamation n'arrive.
- **YouTube Audio Library** (dans YouTube Studio > Bibliothèque audio) : sûre pour YouTube, certaines pistes demandent un crédit.

Jamais une musique trouvée « sur YouTube » ou un morceau du commerce : ta vidéo serait démonétisée ou bloquée.
