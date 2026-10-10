# kit-montage-ia : instructions for Claude

A montage kit for YouTube talking-head videos (16:9, read at the teleprompter or not), filmed with one or two phones, edited in the creator's own style, assembled and exported by Adobe Premiere Pro through an MCP connector. The user is usually not a developer : talk to them in French, with « tu », one question at a time, no jargon, and never ask them to paste a prompt or edit a file.

## Install (when the user gives you this repository's link)

1. Clone it into its own folder, not inside another project : `git clone https://github.com/cblain100-prog/kit-montage-ia ~/kit-montage-ia` (if that folder exists, `git -C ~/kit-montage-ia pull`).
2. Run `bash ~/kit-montage-ia/scripts/install.sh` (about 10 minutes the first time ; tell the user). It installs, only when missing :
   - Homebrew tools : ffmpeg, node (20+), python (3.11+). If Homebrew itself is missing the script stops with the one line the user must paste in Terminal (it asks for their Mac password : you cannot type it). Then run the script again.
   - `.venv/` with `requirements.txt` (numpy, scipy, soundfile, pillow, mlx-whisper on Apple Silicon or openai-whisper on Intel).
   - `assets/gsap.min.js` (GSAP 3.14.2 from npm via jsDelivr ; not redistributed in the repo).
   - `assets/sfx/*.wav` (original sound effects synthesised by `tools/make_sfx.py`).
   - `tools/bin/facebox` (face finder on Apple Vision, compiled with swiftc ; if swiftc is missing : `xcode-select --install`).
   - HyperFrames 0.8.103 through npx (pinned).
   - The two skills, symlinked into `~/.claude/skills/` (`create-style`, `montage`), the seven agents of `agents/` copied into `~/.claude/agents/` (an existing file is never overwritten ; `--agents-dir` to change the folder), and the kit path in `~/.config/kit-montage-ia/kit_dir` (skills and agents read it). Use `--skills-dir <project>/.claude/skills` to install them for one project only, `--no-skills` to skip.
   - The Premiere connector, when Premiere Pro is installed : `scripts/install-premiere.sh` clones https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP at commit `f5e95e30787f85ec90b181e5b4a0ac38f68546ad` (release 1.2.8, security-audited ; never from npm) into `vendor/premiere-mcp`, applies `scripts/premiere-mcp-ame-folder.patch`, builds it. Hardening : `/tmp/premiere-mcp-bridge` created 700 (stops if it exists and is not the user's), `~/.premiere-mcp-bridge/config.json` merged with `{"telemetry": false, "updateCheck": false}`, CEP debug mode, the panel copied by the kit (not upstream `install-macos.sh`, which edits Claude Desktop's config), registration `claude mcp add premiere-pro -s user -e PREMIERE_TEMP_DIR=/tmp/premiere-mcp-bridge -e PREMIERE_MCP_TELEMETRY=0 -e DO_NOT_TRACK=1 -e PREMIERE_MCP_UPDATE_CHECK=0 -e PREMIERE_MCP_TOOLSET=full -- node <kit>/vendor/premiere-mcp/dist/index.js` (an existing `premiere-pro` entry is kept unless `--force-register`), and `permissions.deny` for `mcp__premiere-pro__execute_extendscript`, `mcp__premiere-pro__delete_preview_files`, `mcp__premiere-pro__invoke_tool` merged into `~/.claude/settings.json` (backup first, idempotent). Undo : `scripts/uninstall-premiere.sh`.
3. Verify : `~/kit-montage-ia/.venv/bin/python ~/kit-montage-ia/tools/check.py`. Every « MANQUE » line names its fix. « ATTENTION » lines are optional (music not downloaded yet, Premiere bridge not started).
4. Tell the user the two settings to make once in Premiere Pro (in French) :
   - Premiere Pro > Réglages > Plug-ins : cocher « Activer le mode développeur », puis quitter et relancer Premiere.
   - Fenêtre > Extensions > MCP Bridge (CEP) : le pont démarre seul à l'ouverture du panneau ; vérifier Temp Directory = `/tmp/premiere-mcp-bridge` ; « Start Bridge » seulement si le panneau affiche « Stopped ».
5. Restart note : skills and agents added during the session appear after Claude Code restarts. Then the first step is always « crée mon style de montage ».

The repo is also a Claude Code plugin (`.claude-plugin/`) : `claude plugin marketplace add cblain100-prog/kit-montage-ia` then `claude plugin install kit-montage-ia@kit-montage-ia`. The plugin brings the skills and the agents ; the skills still clone and install the kit in `~/kit-montage-ia` (never keep projects in the plugin cache).

## Layout

```
prompteur.py          the engine : words, cut, base, inserts, render, compose, sheet + checks (takes, gaps, outwords, verbatim, joints)
prompteur_blocks.py   the insert kinds (HyperFrames pages), brand colours from the look
montage.py            paths, kit.config.json (output_dir, default ~/Downloads ; premiere_projects ; browser)
music.py              synthesised stings, track looping
fastwhisper.py        Whisper on the Apple GPU (mlx), openai-whisper fallback
tools/                projet.py (new project from 1 or 2 videos : sync, faces, voice), transcribe.py, export_xml.py (FCP 7 XML for Premiere), redites.py, hear.py,
                      energy.py, music_plan.py, musique.py, make_sfx.py, look_ffmpeg.py (ffmpeg fallback), qa_measure.py,
                      qa_pack.py, flashes.py, analyse_style.py, choix.py (A/B/C choice videos), check.py, facebox.swift
premiere/             build_timeline.py (whole timeline + export), apply_look.py (zoom keys), ppclient.py, ppbatch.py, paths.py, zoom_variants.py
review/               the studio : serve.py, montage_api.py, index.html, rebuild.sh (full rebuild, Premiere or ffmpeg fallback)
looks/_modele/        the empty structure of a style ; the user's style is looks/<name>/look.json (git-ignored), built by create-style
rules/qualite.md      universal quality rules (not taste) applied to every video
agents/               kit-montage-coupes, -redites, -visuels, -spectateur, -sceptique, -chef (verification), -animateur (animations)
skills/               create-style (once, ALWAYS first), montage (each video, refuses to start without a personal style)
projects/             one folder per video (git-ignored) ; plan.exemple.json documents every field
assets/               fonts (OFL, shipped), sfx and music (generated or downloaded, git-ignored)
```

Always run Python through the kit's venv : `cd <kit> && .venv/bin/python ...`.

## Rules

- The skills are the procedure : follow `skills/montage/SKILL.md` and `skills/create-style/SKILL.md`.
- Never commit or upload the user's videos, transcripts, projects, looks or `kit.config.json`.
- Order : the creator's style first (create-style), then the montage. Every taste value (rhythm, pauses, framings, zooms, sound effects, music, words on screen, colours, fonts) comes only from their style ; an empty value means the effect is not used. The kit ships no style values of its own, and never names or reproduces a specific creator.
- Universal quality rules (`rules/qualite.md`) apply to every video ; they are not taste.
- No music or sound effect file is ever added to the repository (licences).
- Change the engine only for rules that apply to every video ; per-video choices go in `projects/<slug>/plan.json`, per-creator choices in `looks/<name>/look.json`.
- After editing any Python file, check the syntax (`.venv/bin/python -c "import ast; ast.parse(open('f.py').read())"`) before a long run.
- Premiere : one new project per version, never drive its interface blindly when the bridge heartbeat (`/tmp/premiere-mcp-bridge/bridge-heartbeat.json`) is older than 60 s : use the ffmpeg fallback (`tools/look_ffmpeg.py` then `prompteur.py compose`) plus `tools/export_xml.py` (FCP 7 XML the user imports in Premiere). Never call the denied tools (`execute_extendscript`, `delete_preview_files`, `invoke_tool`) ; avoid the tools with open upstream bugs listed in the skill.
- Long jobs (transcription of a long rush, the studio page, a Premiere build) run with `nohup` : background tasks stop after 2 hours.
- Verify every render visually (`prompteur.py sheet`, `tools/flashes.py`) before calling it done.
