# Third-party components

What the kit uses that it did not write, and how it gets it. Nothing below is copied into this repository except the fonts.

| Component | Licence | In the repo? | How the kit gets it |
|---|---|---|---|
| Fonts in `assets/fonts` : Inter, Inter Tight, Poppins, Anton, JetBrains Mono, Instrument Serif | SIL Open Font License 1.1 (licence file next to each font) | yes, unmodified | shipped |
| Adobe_Premiere_Pro_MCP by hetpatel-11 (the Premiere connector) | MIT | no | `scripts/install-premiere.sh` clones https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP at commit `f5e95e30787f85ec90b181e5b4a0ac38f68546ad` (release 1.2.8, security-audited) into `vendor/premiere-mcp` (never from npm) and applies `scripts/premiere-mcp-ame-folder.patch` (one line : Media Encoder detected when macOS installs it as a folder, upstream issue #103) |
| HyperFrames by HeyGen (renders the animations) | Apache-2.0 | no | `npx hyperframes@0.8.103` (pinned : an unpinned version once failed silently) |
| GSAP 3.14.2 (animation library used inside the HyperFrames pages) | GSAP Standard « No Charge » License (https://gsap.com/standard-license), free to use, not an open-source licence | no (redistribution terms unclear) | downloaded by `scripts/install.sh` from npm through jsDelivr into `assets/gsap.min.js` (git-ignored) |
| Whisper models (transcription) : mlx-whisper (Apple GPU) or openai-whisper | MIT | no | `pip install -r requirements.txt` ; the model is downloaded from Hugging Face on first use |
| OpenTimelineIO 0.18.1 and otio-fcp-adapter 1.0.0 (Academy Software Foundation) | Apache-2.0 | no | `pip install -r requirements.txt` ; `tools/export_xml.py` reads its own XML back with them |
| numpy, scipy, soundfile, Pillow | BSD / MIT-CMU (Pillow) | no | `pip install -r requirements.txt` |
| ffmpeg, Node.js, Python | LGPL/GPL, MIT, PSF | no | Homebrew |
| Music | depends on the track | **no** | `tools/musique.py` downloads Kevin MacLeod tracks (CC BY 4.0, credit line required, written to `assets/music/CREDITS.json`) ; Mixkit / Pixabay / your own tracks with `tools/musique.py add` |
| Sound effects | original | **no** | `tools/make_sfx.py` synthesises them (numpy) at install : original sounds, no credit needed. Replace any of them with your own files (same name) |

## Texts adapted with credit

- `skills/montage/SKILL.md`, « Pièges Premiere » :
  - the Media Encoder completion and `.epr` preset notes are adapted from **Trevor O'Hare Productions, [premiere-uxp-dev-notes](https://github.com/tro2789/premiere-uxp-dev-notes) (`cep/encoder.md`)**, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) ; changes : summarised and translated into French ;
  - the clip reordering trap is summarised from **Maksim Sevostianov, [quadlzzz/premiere-mcp](https://github.com/quadlzzz/premiere-mcp) `docs/api-traps.md`** (MIT, Copyright (c) 2026 Maksim Sevostianov).

Adobe Premiere Pro and Adobe Media Encoder are Adobe products under your own Creative Cloud subscription ; the kit only drives them.
