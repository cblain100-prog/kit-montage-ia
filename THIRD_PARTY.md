# Third-party components

What the kit uses that it did not write, and how it gets it. Nothing below is copied into this repository except the fonts.

| Component | Licence | In the repo? | How the kit gets it |
|---|---|---|---|
| Fonts in `assets/fonts` : Inter, Inter Tight, Poppins, Anton, JetBrains Mono, Instrument Serif | SIL Open Font License 1.1 (licence file next to each font) | yes, unmodified | shipped |
| Adobe_Premiere_Pro_MCP by hetpatel-11 (the Premiere connector) | MIT | no | `scripts/install-premiere.sh` clones https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP at commit `12684e37297a702265985dffa7d33629d28074f4` (release 1.2.3) into `vendor/premiere-mcp` and applies `scripts/premiere-mcp-ame-folder.patch` (one line : Media Encoder detected when macOS installs it as a folder) |
| HyperFrames by HeyGen (renders the animations) | Apache-2.0 | no | `npx hyperframes@0.8.103` (pinned : an unpinned version once failed silently) |
| GSAP 3.14.2 (animation library used inside the HyperFrames pages) | GSAP Standard « No Charge » License (https://gsap.com/standard-license), free to use, not an open-source licence | no (redistribution terms unclear) | downloaded by `scripts/install.sh` from npm through jsDelivr into `assets/gsap.min.js` (git-ignored) |
| Whisper models (transcription) : mlx-whisper (Apple GPU) or openai-whisper | MIT | no | `pip install -r requirements.txt` ; the model is downloaded from Hugging Face on first use |
| numpy, scipy, soundfile, Pillow | BSD / MIT-CMU (Pillow) | no | `pip install -r requirements.txt` |
| ffmpeg, Node.js, Python | LGPL/GPL, MIT, PSF | no | Homebrew |
| Music | depends on the track | **no** | `tools/musique.py` downloads Kevin MacLeod tracks (CC BY 4.0, credit line required, written to `assets/music/CREDITS.json`) ; Mixkit / Pixabay / your own tracks with `tools/musique.py add` |
| Sound effects | original | **no** | `tools/make_sfx.py` synthesises them (numpy) at install : original sounds, no credit needed. Replace any of them with your own files (same name) |

Adobe Premiere Pro and Adobe Media Encoder are Adobe products under your own Creative Cloud subscription ; the kit only drives them.
