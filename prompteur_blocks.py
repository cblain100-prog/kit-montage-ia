"""Insert blocks for prompteur.py : each kind turns one plan insert into a HyperFrames page.

Every block returns (html, cues): a HyperFrames page 1920x1080 and its sound cues [(sfx file, seconds into the insert, dB)]
(those built-in sounds are used only when the creator's style says so : look.sound.insert_sounds).
`rel(anchor)` turns a spoken anchor ('mot@123.4', rush time) into seconds from the insert's start.

Colours and title font come from the creator's style (look.json « brand », set by set_brand) : accent, background,
title_family ; neutral white / near-black / Inter until the style gives them. Which kinds a video uses is the creator's
choice and the montage's : the kit imposes none.

Full-screen kinds (opaque): term, still, diamonds, alert, doc, logo, wall, tokens, bullets, ytcard, scene.
Overlay kinds (transparent, over the face): caption, nametag, keyword (style simple or gras), icon.
"""
import html as H
import json
import os

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
FONTS = ("InterTight-var.ttf", "inter-var.woff2", "jetbrainsmono-400.woff2", "jetbrainsmono-700.woff2", "instrument-serif-italic.woff2",
         "Poppins-Light.ttf", "Poppins-Medium.ttf", "Poppins-SemiBold.ttf", "Poppins-ExtraBold.ttf", "Anton-Regular.ttf")
OVERLAYS = {"caption", "nametag", "keyword", "icon"}
W, HH = 1920, 1080
OR = "#FFFFFF"  # accent colour : neutral white until the look's brand.accent is set (set_brand)
BG = "#040404"
TITLE = "Inter"  # family of the keyword / title font, from the look's brand.title_family
EXTRA_FONTS = []  # [{"family", "file", "weight"}] from the look's brand.fonts (files in assets/fonts)


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(c):
    return "#" + "".join(f"{max(0, min(255, int(round(v)))):02X}" for v in c)


def shade(h, f):
    """f > 0 : towards white, f < 0 : towards black."""
    r = _rgb(h)
    return _hex([v + (255 - v) * f if f > 0 else v * (1 + f) for v in r])


def rgba(h, a):
    r, g, b = _rgb(h)
    return f"rgba({r},{g},{b},{a})"


def set_brand(brand):
    """brand = {"accent": "#hex", "background": "#hex", "title_family": "...", "fonts": [{"family", "file", "weight"}]}."""
    global OR, BG, TITLE, EXTRA_FONTS
    brand = brand or {}
    OR = brand.get("accent") or OR
    BG = brand.get("background") or BG
    EXTRA_FONTS = brand.get("fonts") or []
    TITLE = brand.get("title_family") or TITLE


def fonts():
    """Font files copied next to every insert (the bundled ones plus the brand's)."""
    return list(FONTS) + [f["file"] for f in EXTRA_FONTS]


def extra_css():
    """The brand's fonts, and the stage lit in the brand's background colour."""
    stage = f".stage{{background:radial-gradient(ellipse 70% 60% at 50% 42%,{shade(BG, .1)} 0%,{BG} 55%,{shade(BG, -.5)} 100%)}}"
    return stage + "".join(f"@font-face{{font-family:'{f['family']}';src:url('assets/fonts/{f['file']}');font-weight:{f.get('weight', '100 900')};font-display:block}}"
                   for f in EXTRA_FONTS)


# style key -> font file, to measure a line on the real glyphs (punch_layer)
STYLE_FILE = {"s": "Poppins-Medium.ttf", "t": "Poppins-Light.ttf", "b": "Poppins-ExtraBold.ttf", "c": "Anton-Regular.ttf"}


def fit_px(text, st, px, room):
    """Largest size <= px at which the line fits in `room` px (real glyph advances + letter-spacing)."""
    from PIL import ImageFont
    ls = float(PSTYLE[st][4].replace("em", "") or 0)
    width = lambda p: ImageFont.truetype(os.path.join(FONT_DIR, STYLE_FILE[st]), p).getlength(text) + ls * p * (len(text) - 1)
    while px > 20 and width(px) > room:
        px -= 2
    return px

CSS = f"""@font-face{{font-family:'Inter';src:url('assets/fonts/inter-var.woff2') format('woff2');font-weight:100 900;font-display:block}}
@font-face{{font-family:'JB';src:url('assets/fonts/jetbrainsmono-400.woff2') format('woff2');font-weight:400;font-display:block}}
@font-face{{font-family:'JB';src:url('assets/fonts/jetbrainsmono-700.woff2') format('woff2');font-weight:700;font-display:block}}
@font-face{{font-family:'Poppins';src:url('assets/fonts/Poppins-Light.ttf');font-weight:300;font-display:block}}
@font-face{{font-family:'Poppins';src:url('assets/fonts/Poppins-Medium.ttf');font-weight:500;font-display:block}}
@font-face{{font-family:'Poppins';src:url('assets/fonts/Poppins-SemiBold.ttf');font-weight:600;font-display:block}}
@font-face{{font-family:'Poppins';src:url('assets/fonts/Poppins-ExtraBold.ttf');font-weight:800;font-display:block}}
@font-face{{font-family:'InterTight';src:url('assets/fonts/InterTight-var.ttf');font-weight:100 900;font-display:block}}
@font-face{{font-family:'Anton';src:url('assets/fonts/Anton-Regular.ttf');font-weight:400;font-display:block}}
.pl{{white-space:nowrap;color:#fff;text-shadow:0 0 70px rgba(0,0,0,.45),0 4px 26px rgba(0,0,0,.6),0 1px 3px rgba(0,0,0,.5)}}
.pw{{display:inline-block}}
*{{box-sizing:border-box}}html,body{{margin:0;width:{W}px;height:{HH}px;overflow:hidden;background:transparent}}
#root{{position:relative;width:{W}px;height:{HH}px;overflow:hidden}}
.stage{{position:absolute;inset:0;background:radial-gradient(ellipse 70% 60% at 50% 42%,#24201c 0%,#0d0c0b 55%,#040404 100%)}}
.vig{{position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse 80% 75% at 50% 50%,transparent 55%,rgba(0,0,0,.65) 100%)}}
.hv{{font-family:'Inter';font-weight:850;letter-spacing:-.045em;line-height:.95;color:#fff;white-space:nowrap}}
.c{{position:absolute;left:0;right:0;text-align:center}}
"""


def page(cid, body, js, dur, fade_in=True, fade_out=False, opaque=True):  # no fade to black at the end : one black frame before the face (v17, 4 times)
    js_in = "tl.fromTo('#stg',{opacity:0},{opacity:1,duration:.12,ease:'none'},0);" if fade_in else ""
    js_out = f"tl.to('#stg',{{opacity:0,duration:.12,ease:'none'}},{dur - 0.12:.3f});" if fade_out else ""
    bg = f'<div style="position:absolute;inset:0;background:{BG}"></div>' if opaque else ""
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{cid}</title>
<script src="assets/gsap.min.js"></script><style>{CSS}{extra_css()}</style></head><body>
<div id="root" data-composition-id="{cid}" data-start="0" data-duration="{dur:.3f}" data-width="{W}" data-height="{HH}">
<div id="k_clip" class="clip" data-start="0" data-duration="{dur:.3f}" data-track-index="1" style="position:absolute;inset:0">{bg}<div id="stg" style="position:absolute;inset:0">{body}</div></div>
</div><script>
const tl=gsap.timeline({{paused:true}});
{js_in}
{js}
{js_out}
tl.set({{}},{{}},{dur:.3f});
window.__timelines=window.__timelines||{{}};window.__timelines["{cid}"]=tl;
</script></body></html>"""


def t_of(rel, v, default=0.0):
    """Seconds into the insert. A number = already relative; "src:159.96" = a time in camera B's rush (a word that the
    full-rush transcript merged away); "mot@123.4" = a spoken word. (v3 bug: a bare rush time was read as relative,
    so the last two bullets never showed.)"""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if v.startswith("src:"):
        return rel(float(v[4:]))
    return rel(v)


def drift(sel, dur, s0=1.0, s1=1.06, x=0, y=0):
    """Slow push-in over the whole insert (stills and UI always breathe)."""
    return f"tl.fromTo('{sel}',{{scale:{s0},x:0,y:0}},{{scale:{s1},x:{x},y:{y},duration:{dur:.2f},ease:'none'}},0);"


# ------------------------------------------------------------------ term: a real terminal screen (captured as JSON cells)
NAMED = {"default": "#d9d4cf", "black": "#000000", "red": "#e06c75", "green": "#87d787", "brown": "#ffd700", "blue": "#61afef",
         "magenta": "#ff87af", "cyan": "#56b6c2", "white": "#ffffff"}


def _col(c, bg=False):
    if c == "default":
        return None if bg else NAMED["default"]
    if c in NAMED:
        return NAMED[c]
    c = "#" + c
    return {"#d78787": "#D97757"}.get(c, c)  # the 256-colour capture rounds this orange: put the real one back


def term(ins, dur, rel, assets):
    """ins.rows = [[capture.json, row, {"old": "new"}?], ...] or ["", text, colour] for a typed line; ins.reveal = {index: anchor};
    ins.focus = {row: index, at: anchor, scale}: accent-coloured frame round that line + gentle push towards it."""
    fs, lh = ins.get("font", 24), ins.get("font", 24) * 1.42
    grids, lines = {}, []
    for k, r in enumerate(ins["rows"]):
        if r[0] == "type":  # the prompt line the speaker "types" into (see ins.type)
            lines.append(f'<div class="ln" id="r{k}"><span style="color:#d9d4cf">\u276f </span><span id="tp{k}" style="color:#fff"></span>'
                         f'<span style="display:inline-block;width:.6em;height:1.05em;background:#d9d4cf;vertical-align:-.15em;margin-left:2px"></span></div>')
            continue
        if r[0] == "":
            lines.append(f'<div class="ln" id="r{k}" style="color:{r[2] if len(r) > 2 else "#fff"}">{H.escape(r[1])}</div>')
            continue
        f, y = r[0], r[1]
        g = grids.setdefault(f, json.load(open(os.path.join(assets, f))))
        cells = g[y]
        text = "".join(c[0] for c in cells)
        for old, new in (r[2] if len(r) > 2 else {}).items():
            i = text.find(old)
            if i >= 0:
                fg = cells[i][1:]
                new_cells = [[ch] + list(fg) for ch in new]
                cells = cells[:i] + new_cells + cells[i + len(old):]
                text = "".join(c[0] for c in cells)
        if k in ins.get("lstrip", []):  # a right-aligned line (the limit warning) moved to the left edge
            while cells and cells[0][0] == " ":
                cells = cells[1:]
        cells = cells[:ins.get("cols", 110)]
        spans, cur, buf = [], None, ""
        for ch_, fg, bg, bold in [(c[0], c[1], c[2], c[3]) for c in cells]:
            st = f"color:{_col(fg)};" + (f"background:{_col(bg, True)};" if _col(bg, True) else "") + ("font-weight:700;" if bold else "")
            if st != cur and buf:
                spans.append(f'<span style="{cur}">{H.escape(buf)}</span>'); buf = ""
            cur, buf = st, buf + ch_
        if buf.rstrip():
            spans.append(f'<span style="{cur}">{H.escape(buf.rstrip())}</span>')
        lines.append(f'<div class="ln" id="r{k}">{"".join(spans) or "&nbsp;"}</div>')
    n = len(lines)
    ph = n * lh + 70
    pw = min(1760, ins.get("cols", 110) * fs * 0.62 + 110)
    style = (f"<style>.ln{{font-family:'JB';font-size:{fs}px;line-height:{lh:.1f}px;height:{lh:.1f}px;white-space:pre;color:#d9d4cf}}"
             f"#panel{{position:absolute;left:50%;top:50%;width:{pw:.0f}px;height:{ph:.0f}px;margin-left:{-pw / 2:.0f}px;margin-top:{-ph / 2:.0f}px;"
             f"background:#0e0e0e;border:1px solid #2a2725;border-radius:14px;padding:35px 46px;overflow:hidden;"
             f"box-shadow:0 50px 120px rgba(0,0,0,.8),0 0 0 1px rgba(255,255,255,.03),0 0 140px {rgba(OR, .10)}}}</style>")
    ov = bool(ins.get("overlay"))  # pop-up over the face cam (the face stays visible)
    if ov:
        style = style.replace("top:50%;", f"top:{ins.get('y', 700)}px;").replace(f"margin-top:{-ph / 2:.0f}px;", "margin-top:0px;")
    body = [style, "" if ov else '<div class="stage"></div>', '<div id="cam" style="position:absolute;inset:0"><div id="panel">', "".join(lines)]
    js, cues = [], []
    for k, at in (ins.get("reveal") or {}).items():
        t = t_of(rel, at)
        js.append(f"tl.set('#r{k}',{{opacity:0}},0);tl.fromTo('#r{k}',{{opacity:0,y:6}},{{opacity:1,y:0,duration:.18}},{t:.3f});")
    for k, (at, txt) in (ins.get("type") or {}).items():  # typed into the prompt line, character by character
        t = t_of(rel, at)
        for j in range(len(txt) + 1):
            js.append(f"tl.set('#tp{k}',{{textContent:{json.dumps(txt[:j])}}},{t + j * 0.028:.3f});")
        cues.append(("typing.wav", t, -26))
    f = ins.get("focus")
    if f:
        t, row = t_of(rel, f["at"]), int(f["row"])
        top = 35 + row * lh - ph / 2
        body.append(f'<div id="fx" style="position:absolute;left:30px;right:30px;top:{35 + row * lh - 6:.0f}px;height:{lh + 12:.0f}px;'
                    f'border:3px solid {OR};border-radius:10px;box-shadow:0 0 40px {rgba(OR, .55)},inset 0 0 30px {rgba(OR, .15)};opacity:0"></div>')
        sc = f.get("scale", 1.14)
        js.append(f"tl.fromTo('#fx',{{opacity:0,scaleX:.96}},{{opacity:1,scaleX:1,duration:.22,ease:'power2.out'}},{t:.3f});")
        if not ins.get("overlay"):  # a pop-up over the face never moves: only the frame appears
            js.append(f"tl.to('#cam',{{scale:{sc},y:{-top * (sc - 1) - top * 0.35:.0f},duration:.9,ease:'power2.inOut'}},{t:.3f});")
        cues.append(("pop.wav", t - 0.05, -21))
    elif not ov:
        js.append(drift("#cam", dur, 1.0, 1.05))
    body.append('</div></div>' + ("" if ov else '<div class="vig"></div>'))
    if ov:
        js.append("tl.fromTo('#panel',{opacity:0,scale:.82,y:40},{opacity:1,scale:1,y:0,duration:.38,ease:'back.out(1.9)'},0.0);")
        js.append(f"tl.to('#panel',{{opacity:0,scale:.95,y:20,duration:.22,ease:'power2.in'}},{dur - 0.24:.3f});")
        cues.append(("pop.wav", -0.04, -20))
    if ins.get("blur"):  # teaser: the real screen, unreadable until the end of the video
        js.append(f"tl.set('#panel',{{filter:'blur({ins['blur']}px)'}},0);")
    if ins.get("punch"):
        b, cj, cc = punch_layer(ins["punch"], rel, ins.get("_words", []), y=ins.get("punch_y", 900))
        body.append(b); js += cj; cues += cc
    elif ins.get("caption"):
        b, cj, cc = caption_layer(ins["caption"], rel)
        body.append(b); js += cj; cues += cc
    if ov:
        return page(ins["id"], "".join(body), "\n".join(js), dur, fade_in=False, fade_out=False, opaque=False), cues
    return page(ins["id"], "".join(body), "\n".join(js), dur, fade_in=ins.get("fade_in", True)), cues


# ------------------------------------------------------------------ still: cinematic image, slow push
def still(ins, dur, rel, assets):
    o = ins.get("origin", "50% 45%")
    body = (f'<div id="ph" style="position:absolute;inset:-2%;background:url(assets/{os.path.basename(ins["src"])}) center/cover;transform-origin:{o}"></div>'
            '<div class="vig"></div>')
    js = [drift("#ph", dur, ins.get("from", 1.0), ins.get("to", 1.08))]
    cues = [("whoosh-short.wav", -0.08, -27)] if ins.get("whoosh", True) else []
    if ins.get("punch"):
        b, cj, cc = punch_layer(ins["punch"], rel, ins.get("_words", []), x=ins.get("x", W / 2), y=ins.get("y", 840), align=ins.get("align", "center"))
        body += b; js += cj; cues += cc
    elif ins.get("caption"):
        b, cj, cc = caption_layer(ins["caption"], rel)
        body += b; js += cj; cues += cc
    return page(ins["id"], body, "\n".join(js), dur, fade_in=False), cues


# ------------------------------------------------------------------ punch: the validated editorial captions (editorial captions)
# A whole sentence posed in one block is hard to read : every text is in the editorial caption style :
# Poppins, each word blurs in at the exact moment it is said (word timings of the edited voice),
# the key words huge in mixed weights (thin / extra-bold / condensed Anton), soft halo, never a box.
PSTYLE = {"s": ("Poppins", 500, 52, 1.15, "0"), "t": ("Poppins", 300, 130, .95, "-.01em"),
          "b": ("Poppins", 800, 130, .95, "-.03em"), "c": ("Anton", 400, 170, 1.0, ".005em")}


def _norm(w):
    import re, unicodedata
    w = unicodedata.normalize("NFC", w.lower()).replace("’", "'")
    return re.sub(r"[^\w'-]", "", w).strip("'-")


def word_times(tokens, words, t0):
    """Each token gets the start of the next spoken word with the same spelling (or the same first 4 letters) after t0;
    a token not heard (Whisper spelling) follows the previous one by 0.14 s."""
    out, t, i = [], t0 - 0.35, 0
    for tok in tokens:
        n = _norm(tok)
        hit = None
        for j in range(i, len(words)):
            wn, wt = words[j]
            if wt < t - 0.05:
                continue
            if wt > t + 3.0:
                break
            if wn == n or (len(n) >= 4 and wn[:4] == n[:4]):
                hit = j
                break
        if hit is None:
            t = (out[-1] + 0.14) if out else max(t0, 0.02)
        else:
            t, i = words[hit][1], hit + 1
        out.append(max(t, 0.0))
    return out


def punch_layer(lines, rel, words, x=W / 2, y=HH * 0.78, align="center", width=None):
    """lines = [[style s|t|b|c, text, px?, colour?, at?], ...]; anchored at (x, y) = centre of the block."""
    room = width or {"center": 2 * min(x, W - x) - 0.1 * W, "left": W - x - 0.05 * W, "right": x - 0.05 * W}[align]
    tx = {"center": "-50%", "left": "0", "right": "-100%"}[align]
    body, js, k, last = [f'<div style="position:absolute;left:{x:.0f}px;top:{y:.0f}px;transform:translate({tx},-50%);text-align:{align}">'], [], 0, 0.0
    for ln in lines:
        st, text = ln[0], ln[1]
        font, wt, px, lh, ls = PSTYLE[st]
        px = ln[2] if len(ln) > 2 and ln[2] else px
        shown = text.upper() if st == "c" else text
        px = fit_px(shown, st, px, room)
        col = ln[3] if len(ln) > 3 and ln[3] else "#fff"
        t0 = t_of(rel, ln[4], last) if len(ln) > 4 and ln[4] is not None else last
        toks = shown.split(" ")
        # a line the creator dictated (not word for word what is said) rolls in on its own from its anchor
        ts = [t0 + 0.09 * i for i in range(len(toks))] if len(ln) > 5 and ln[5] == "free" else word_times(toks, words, t0)
        last = ts[-1] + 0.12 if ts else last
        spans = []
        for tok, t in zip(toks, ts):
            spans.append(f'<span class="pw" id="pw{k}" style="opacity:0">{H.escape(tok)}</span>')
            js.append(f"tl.fromTo('#pw{k}',{{opacity:0,filter:'blur(16px)',y:22,scale:1.08}},{{opacity:1,filter:'blur(0px)',y:0,scale:1,duration:.16,ease:'power2.out'}},{t:.3f});")
            k += 1
        body.append(f'<div class="pl" style="font-family:\'{font}\';font-weight:{wt};font-size:{px}px;line-height:{lh};letter-spacing:{ls};color:{col}">'
                    + "&nbsp;".join(spans) + "</div>")
    body.append("</div>")
    return "".join(body), js, []


# ------------------------------------------------------------------ caption: heavy white keyword low on the face 
def caption_layer(lines, rel, bottom=110):
    """lines = [{t, at, color?, size?}] stacked bottom-up; each word pops on its own with a soft blur."""
    body, js, cues = [], [], []
    y = bottom
    for i, l in enumerate(reversed(lines)):
        k = len(lines) - 1 - i
        sz = l.get("size", 92)
        words = l["t"].split(" ")
        spans = "".join(f'<span class="w{k}" style="display:inline-block;opacity:0">{H.escape(w)}</span>' + ("&nbsp;" if j < len(words) - 1 else "")
                        for j, w in enumerate(words))
        body.append(f'<div class="c" style="bottom:{y}px"><div class="hv" style="font-size:{sz}px;color:{l.get("color", "#fff")};'
                    f'text-shadow:0 6px 30px rgba(0,0,0,.85),0 2px 6px rgba(0,0,0,.9)">{spans}</div></div>')
        y += sz * 1.02
    for k, l in enumerate(lines):
        t = t_of(rel, l.get("at"), 0.05)
        step = l.get("step", 0.09)
        js.append(f"document.querySelectorAll('.w{k}').forEach((e,i)=>tl.fromTo(e,{{opacity:0,y:18,filter:'blur(10px)'}},"
                  f"{{opacity:1,y:0,filter:'blur(0px)',duration:.22,ease:'power3.out'}},{t:.3f}+i*{step}));")
    return "".join(body), js, cues


def caption(ins, dur, rel, assets):
    if ins.get("punch"):
        b, js, cues = punch_layer(ins["punch"], rel, ins.get("_words", []), y=ins.get("y", 840))
    else:
        b, js, cues = caption_layer(ins["lines"], rel, ins.get("bottom", 110))
    js.append(f"tl.to('#stg',{{opacity:0,duration:.15}},{dur - 0.15:.3f});")
    return page(ins["id"], b, "\n".join(js), dur, fade_in=False, fade_out=False, opaque=False), cues


def nametag(ins, dur, rel, assets):
    body = (f'<div style="position:absolute;left:110px;bottom:120px">'
            f'<div id="nm" class="hv" style="font-family:Poppins;font-weight:800;letter-spacing:-.025em;font-size:64px;text-shadow:0 4px 24px rgba(0,0,0,.8)">{H.escape(ins["name"])}</div>'
            f'<div id="bar" style="width:120px;height:6px;background:{OR};margin:14px 0 12px;transform-origin:left"></div>'
            f'<div id="sub" style="font-family:Poppins;font-weight:500;font-size:30px;color:rgba(255,255,255,.88);letter-spacing:-.01em;text-shadow:0 2px 14px rgba(0,0,0,.8)">{H.escape(ins.get("sub", ""))}</div></div>')
    js = ["tl.fromTo('#nm',{opacity:0,x:-30},{opacity:1,x:0,duration:.35,ease:'power3.out'},0.02);",
          "tl.fromTo('#bar',{scaleX:0},{scaleX:1,duration:.4,ease:'power3.out'},0.15);",
          "tl.fromTo('#sub',{opacity:0,y:10},{opacity:1,y:0,duration:.3},0.3);",
          f"tl.to('#stg',{{opacity:0,duration:.2}},{dur - 0.2:.3f});"]
    return page(ins["id"], body, "\n".join(js), dur, fade_in=False, fade_out=False, opaque=False), []


# ------------------------------------------------------------------ diamonds: numbered steps
def diamond_svg(n, size, idx):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 100 100" style="display:block;overflow:visible">'
            f'<defs><linearGradient id="dg{idx}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{shade(OR, .3)}"/><stop offset=".55" stop-color="{OR}"/>'
            f'<stop offset="1" stop-color="{shade(OR, -.3)}"/></linearGradient></defs>'
            f'<rect x="18" y="18" width="64" height="64" rx="7" transform="rotate(45 50 50)" fill="url(#dg{idx})" '
            f'style="filter:drop-shadow(0 10px 22px {rgba(OR, .45)})"/>'
            f'<rect x="23" y="23" width="54" height="54" rx="5" transform="rotate(45 50 50)" fill="none" stroke="rgba(255,255,255,.35)" stroke-width="1.5"/>'
            f'<text x="50" y="51" text-anchor="middle" dominant-baseline="central" font-family="Inter" font-weight="800" font-size="36" fill="#fff">{n}</text></svg>')


def diamonds(ins, dur, rel, assets):
    """mode row: N numbered diamonds pop left to right + title + sub.
    mode one: one numbered diamond + label beside it."""
    body, js = ['<div class="stage"></div>'], []
    cues = [("whoosh-short.wav", -0.08, -26)]
    if ins.get("mode", "row") == "row":
        n, size = ins["n"], ins.get("size", 150)
        t0, step = t_of(rel, ins.get("at_row"), 0.08), ins.get("step", 0.07)
        row = "".join(f'<div class="dm" style="opacity:0">{diamond_svg(i + 1, size, i)}</div>' for i in range(n))
        body.append(f'<div class="c" style="top:250px;display:flex;justify-content:center;gap:{size * 0.12:.0f}px">{row}</div>')
        js.append(f"document.querySelectorAll('.dm').forEach((e,i)=>tl.fromTo(e,{{opacity:0,scale:.3,y:40}},{{opacity:1,scale:1,y:0,duration:.32,ease:'back.out(2.2)'}},{t0:.3f}+i*{step}));")
        cues += [("pop.wav", t0 + i * step - 0.04, -27) for i in range(n)]
        if ins.get("title"):
            tt = t_of(rel, ins.get("at_title"), t0 + n * step)
            body.append(f'<div class="c" style="top:510px"><div class="hv" id="tt" style="font-family:Poppins;font-weight:800;letter-spacing:-.03em;font-size:150px;opacity:0">{H.escape(ins["title"])}</div></div>')
            js.append(f"tl.fromTo('#tt',{{opacity:0,y:30,filter:'blur(14px)'}},{{opacity:1,y:0,filter:'blur(0px)',duration:.35,ease:'power3.out'}},{tt:.3f});")
        if ins.get("sub"):
            ts = t_of(rel, ins.get("at_sub"), t0 + n * step + 0.4)
            body.append(f'<div class="c" style="top:690px"><div class="hv" id="sb" style="font-family:Poppins;font-weight:300;letter-spacing:0;font-size:64px;color:rgba(255,255,255,.85);opacity:0">{H.escape(ins.get("sub", ""))}</div></div>')
            js.append(f"tl.fromTo('#sb',{{opacity:0,y:16}},{{opacity:1,y:0,duration:.3}},{ts:.3f});")
    else:
        size = ins.get("size", 230)
        lab_px = fit_px(ins["label"], "b", ins.get("label_size", 140), W - size - 260)  # a long label never leaves the frame
        t = t_of(rel, ins.get("at_n"), 0.08)
        tl_ = t_of(rel, ins.get("at_label"), t + 0.25)
        body.append(f'<div style="position:absolute;left:0;right:0;top:0;bottom:0;display:flex;align-items:center;justify-content:center;gap:40px">'
                    f'<div id="d1" style="opacity:0">{diamond_svg(ins["n"], size, 0)}</div>'
                    f'<div class="hv" id="lb" style="font-family:Poppins;font-weight:800;letter-spacing:-.03em;font-size:{lab_px}px;opacity:0">{H.escape(ins["label"])}</div></div>')
        # the diamond is already there on the first frame (2026-10-04 : a card opening on an empty black frame reads as a flash)
        js.append(f"tl.fromTo('#d1',{{opacity:.55,scale:.62,rotation:-22}},{{opacity:1,scale:1,rotation:0,duration:.42,ease:'back.out(2)'}},{min(t, 0.0) if 'at_n' not in ins else t:.3f});")
        js.append(f"tl.fromTo('#lb',{{opacity:0,x:-40,filter:'blur(12px)'}},{{opacity:1,x:0,filter:'blur(0px)',duration:.38,ease:'power3.out'}},{tl_:.3f});")
        cues += [("pop.wav", t - 0.05, -21)]
    js.append(drift("#stg", dur, 1.0, 1.04))
    body.append('<div class="vig"></div>')
    return page(ins["id"], "".join(body), "\n".join(js), dur, fade_in=False), cues


# ------------------------------------------------------------------ alert: full-colour card
CLAUDE_ORB = ('<div id="orb" style="position:absolute;left:{x}px;top:{y}px;width:{s}px;height:{s}px;border-radius:50%;'
              'background:radial-gradient(circle at 35% 30%,#ff9a6a,#e8622c 55%,#b8441a);box-shadow:0 30px 80px rgba(0,0,0,.45),inset 0 -10px 30px rgba(0,0,0,.25);'
              'display:flex;align-items:center;justify-content:center"><img src="assets/{src}" style="width:58%;height:58%"></div>')  # ins.orb = a logo file listed in ins.files


def alert(ins, dur, rel, assets):
    """Deep red-orange stage, a giant out-of-focus word behind, an optional logo orb (ins.orb), a heavy white headline + subline."""
    body = (f'<div style="position:absolute;inset:0;background:radial-gradient(ellipse 90% 80% at 70% 30%,#e0452b 0%,#9e1a12 45%,#3d0705 100%)"></div>'
            f'<div id="bgw" class="hv" style="position:absolute;left:-40px;top:250px;font-size:470px;color:rgba(0,0,0,.28);filter:blur(10px)">{H.escape(ins.get("back", ""))}</div>'
            + (CLAUDE_ORB.format(x=330, y=380, s=330, src=os.path.basename(ins["orb"])) if ins.get("orb") else "")
            + f'<div style="position:absolute;right:150px;top:{ins.get("top", 300)}px;text-align:right">'
            f'<div class="hv" id="ti" style="font-size:{ins.get("size", 140)}px;opacity:0">{H.escape(ins["title"])}</div>'
            + (f'<div class="hv" id="su" style="font-size:64px;font-weight:650;margin-top:22px;opacity:0;color:rgba(255,255,255,.9)">{H.escape(ins["sub"])}</div>' if ins.get("sub") else "")
            + '</div><div class="vig"></div>')
    t = t_of(rel, ins.get("at_title"), 0.06)
    js = [drift("#bgw", dur, 1.0, 1.06, x=-60),
          "tl.fromTo('#orb',{scale:.6,opacity:0,rotation:-60},{scale:1,opacity:1,rotation:0,duration:.45,ease:'back.out(1.8)'},0.02);" if ins.get("orb") else "",
          f"tl.fromTo('#ti',{{opacity:0,x:60,filter:'blur(12px)'}},{{opacity:1,x:0,filter:'blur(0px)',duration:.35,ease:'power3.out'}},{t:.3f});"]
    if ins.get("sub"):
        js.append(f"tl.fromTo('#su',{{opacity:0,y:14}},{{opacity:1,y:0,duration:.3}},{t_of(rel, ins.get('at_sub'), t + 0.35):.3f});")
    return page(ins["id"], body, "\n".join(js), dur, fade_in=False), [("whoosh.wav", -0.1, -24), ("pop.wav", t - 0.05, -20)]


# ------------------------------------------------------------------ doc: real web page in 3D depth on black
def doc(ins, dur, rel, assets):
    """ins.src capture, ins.view = [x, y, w, h] region shown (capture px), ins.marks = [{x,y,w,h,at}] highlighter,
    ins.tilt = [rotY, rotX] degrees."""
    x0, y0, vw, vh = ins["view"]
    k = 1400 / vw
    try:  # the capture's real width (a page can render narrower than 1600 px: marks would drift)
        from PIL import Image
        img_w = Image.open(os.path.join(os.path.dirname(assets), ins["src"])).size[0]
    except Exception:
        img_w = 1600
    ry, rx = ins.get("tilt", [-16, 7])
    marks, js, cues = "", [], [("whoosh-short.wav", -0.08, -26)]
    for i, m in enumerate(ins.get("marks", [])):
        marks += (f'<div id="m{i}" style="position:absolute;left:{(m["x"] - x0) * k:.0f}px;top:{(m["y"] - y0) * k:.0f}px;width:{m["w"] * k:.0f}px;'
                  f'height:{m["h"] * k:.0f}px;background:{rgba(OR, .30)};border-bottom:5px solid {OR};transform-origin:left center;mix-blend-mode:multiply"></div>')
        js.append(f"tl.fromTo('#m{i}',{{scaleX:0}},{{scaleX:1,duration:.45,ease:'power2.out'}},{t_of(rel, m['at']):.3f});")
        cues.append(("click-soft.wav", t_of(rel, m["at"]), -21))
    body = ('<div class="stage"></div><div style="position:absolute;inset:0;perspective:1800px">'
            f'<div id="pg" style="position:absolute;left:260px;top:{(HH - vh * k) / 2:.0f}px;width:1400px;height:{vh * k:.0f}px;overflow:hidden;border-radius:10px;'
            f'transform:rotateY({ry}deg) rotateX({rx}deg);box-shadow:0 60px 140px rgba(0,0,0,.85),0 0 0 1px rgba(255,255,255,.06)">'
            f'<img src="assets/{os.path.basename(ins["src"])}" style="position:absolute;left:{-x0 * k:.0f}px;top:{-y0 * k:.0f}px;width:{img_w * k:.0f}px">{marks}</div></div>'
            '<div class="vig"></div>')
    js.append(f"tl.fromTo('#pg',{{rotationY:{ry - 6},rotationX:{rx + 3},scale:.92,opacity:.85}},{{rotationY:{ry},rotationX:{rx},scale:1,opacity:1,duration:.35,ease:'power3.out'}},0);")  # no black first frames (intro review)
    js.append(f"tl.to('#pg',{{rotationY:{ry + 7},scale:1.05,duration:{max(dur - 0.5, .5):.2f},ease:'none'}},0.5);")
    return page(ins["id"], body, "\n".join(js), dur, fade_in=False), cues


# ------------------------------------------------------------------ logo: a logo on black
def logo(ins, dur, rel, assets):
    """A logo on black (ins.src = the image, listed in ins.files) and the name under it (ins.word)."""
    body = ('<div class="stage" style="background:#050505"></div>'
            f'<div class="c" style="top:330px"><img id="lg" src="assets/{os.path.basename(ins["src"])}" style="width:200px;height:200px;object-fit:contain;opacity:0"></div>'
            f'<div class="c" style="top:560px"><div id="nm" style="font-family:Georgia,serif;font-size:96px;color:#f4efe9;opacity:0;letter-spacing:-.01em">{H.escape(ins.get("word", ""))}</div></div>')
    js = ["tl.fromTo('#lg',{opacity:0,scale:.5,rotation:-90},{opacity:1,scale:1,rotation:0,duration:.55,ease:'back.out(1.6)'},0.05);",
          "tl.fromTo('#nm',{opacity:0,y:20},{opacity:1,y:0,duration:.35},0.35);", drift("#stg", dur, 1.0, 1.05)]
    return page(ins["id"], body, "\n".join(js), dur, fade_in=False), [("pop.wav", 0.0, -21)]


# ------------------------------------------------------------------ wall: proof (a grid of real captures, blurred where private)
def wall(ins, dur, rel, assets):
    imgs = "".join(f'<div class="tile" style="opacity:0;border-radius:10px;overflow:hidden;box-shadow:0 30px 70px rgba(0,0,0,.7)">'
                   f'<img src="assets/{os.path.basename(s)}" style="display:block;width:100%"></div>' for s in ins["srcs"])
    body = ('<div class="stage"></div><div style="position:absolute;inset:0;perspective:2000px">'
            f'<div id="grid" style="position:absolute;left:{(W - ins.get("grid_w", 1680)) / 2:.0f}px;top:{ins.get("grid_top", 150)}px;width:{ins.get("grid_w", 1680)}px;display:grid;grid-template-columns:repeat({ins.get("cols", 3)},1fr);gap:{ins.get("gap", 26)}px;'
            f'transform:rotateX(14deg) rotateZ(-3deg)">{imgs}</div></div>'
            '<div style="position:absolute;inset:0;background:radial-gradient(ellipse 55% 45% at 50% 52%,rgba(0,0,0,.72),rgba(0,0,0,.25))"></div>'
            f'<div class="c" style="top:{ins.get("big_top", 330)}px"><div class="hv" id="big" style="font-size:{ins.get("big_size", 300)}px;opacity:0">{H.escape(ins.get("big", ""))}</div></div>'
            f'<div class="c" style="top:{ins.get("sub_top", 650)}px"><div class="hv" id="sub" style="font-size:{ins.get("sub_size", 72)}px;font-weight:650;opacity:0">{H.escape(ins.get("sub", ""))}</div></div>'
            '<div class="vig"></div>')
    if ins.get("punch"):
        a = body.index('<div class="c" style="top:'); b2 = body.index('<div class="vig"></div>')
        pb, pj, _ = punch_layer(ins["punch"], rel, ins.get("_words", []), y=ins.get("y", 540))
        body = body[:a] + pb + body[b2:]
        js = ["document.querySelectorAll('.tile').forEach((e,i)=>tl.fromTo(e,{opacity:.5,y:40,scale:.94},{opacity:1,y:0,scale:1,duration:.3,ease:'power3.out'},i*0.02));",
              f"tl.fromTo('#grid',{{y:0}},{{y:-60,duration:{dur:.2f},ease:'none'}},0);"] + pj
        return page(ins["id"], body, "\n".join(js), dur, fade_in=False), [("whoosh-short.wav", -0.08, -25)]
    tb = t_of(rel, ins.get("at_big"), 0.35)
    js = ["document.querySelectorAll('.tile').forEach((e,i)=>tl.fromTo(e,{opacity:.4,y:60,scale:.9},{opacity:1,y:0,scale:1,duration:.35,ease:'power3.out'},i*0.02));",  # v12 QA : the wall started on a near-black frame
          f"tl.fromTo('#grid',{{y:0}},{{y:-60,duration:{dur:.2f},ease:'none'}},0);",
          f"tl.fromTo('#big',{{opacity:0,scale:1.25,filter:'blur(16px)'}},{{opacity:1,scale:1,filter:'blur(0px)',duration:.4,ease:'power3.out'}},{tb:.3f});",
          f"tl.fromTo('#sub',{{opacity:0,y:16}},{{opacity:1,y:0,duration:.3}},{t_of(rel, ins.get('at_sub'), tb + 0.35):.3f});"]
    return page(ins["id"], body, "\n".join(js), dur, fade_in=False), [("whoosh-short.wav", -0.08, -25), ("pop.wav", tb - 0.05, -20)]


# ------------------------------------------------------------------ tokens: a real tokenizer view (coloured pieces)
def tokens(ins, dur, rel, assets):
    cols = [rgba(OR, .35), "rgba(97,175,239,.35)", "rgba(135,215,135,.35)", "rgba(255,135,175,.35)", "rgba(255,215,0,.30)"]
    spans = "".join(f'<span class="tk" style="opacity:0;background:{cols[i % 5]};border-radius:6px;padding:2px 3px;margin:0 1px">{H.escape(p).replace(" ", "&nbsp;")}</span>'
                    for i, p in enumerate(ins["parts"]))
    body = ('<div class="stage"></div>'
            + (f'<div class="c" style="top:200px"><div style="font-family:JB;font-size:30px;color:#8f8a84;letter-spacing:.02em">{H.escape(ins["label"])}</div></div>' if ins.get("label") else "") +
            f'<div class="c" style="top:340px"><div id="tx" style="display:inline-block;font-family:JB;font-size:{ins.get("font", 64)}px;color:#f2ede8;line-height:1.5">{spans}</div></div>'
            f'<div class="c" style="top:620px"><div class="hv" id="cap" style="font-size:{ins.get("caption", {}).get("size", 120)}px;opacity:0">{H.escape(ins.get("caption", {}).get("t", ""))}</div></div>'
            '<div class="vig"></div>')
    t0, step = t_of(rel, ins.get("at_parts"), 0.25), ins.get("step", 0.13)
    if ins.get("punch"):
        a = body.index('<div class="c" style="top:620px">'); b2 = body.index('<div class="vig"></div>')
        pb, pj, _ = punch_layer(ins["punch"], rel, ins.get("_words", []), y=ins.get("y", 720))
        body = body[:a] + pb + body[b2:]
        js = [f"document.querySelectorAll('.tk').forEach((e,i)=>tl.fromTo(e,{{opacity:0,y:12}},{{opacity:1,y:0,duration:.16}},{t0:.3f}+i*{step}));",
              drift("#stg", dur, 1.0, 1.04)] + pj
        cues = [("whoosh-short.wav", -0.08, -26)] + [("key-press.wav", t0 + i * step, -27) for i in range(len(ins["parts"]))]
        return page(ins["id"], body, "\n".join(js), dur, fade_in=False), cues
    tc = t_of(rel, ins.get("caption", {}).get("at"), t0 + len(ins["parts"]) * step + 0.3)
    js = [f"document.querySelectorAll('.tk').forEach((e,i)=>tl.fromTo(e,{{opacity:0,y:12}},{{opacity:1,y:0,duration:.16}},{t0:.3f}+i*{step}));",
          f"tl.fromTo('#cap',{{opacity:0,y:24,filter:'blur(12px)'}},{{opacity:1,y:0,filter:'blur(0px)',duration:.35,ease:'power3.out'}},{tc:.3f});",
          drift("#stg", dur, 1.0, 1.04)]
    cues = [("whoosh-short.wav", -0.08, -26)] + [("key-press.wav", t0 + i * step, -27) for i in range(len(ins["parts"]))] + [("pop.wav", tc - 0.05, -21)]
    return page(ins["id"], body, "\n".join(js), dur, fade_in=False), cues


# ------------------------------------------------------------------ bullets: an enumeration said aloud, one bullet per item
def bullets(ins, dur, rel, assets):
    """Still image on the right (slow push), dark gradient on the left, a title then one bullet per spoken item, verbatim."""
    num = ins.get("numbered")
    mark = lambda i: (f'<div style="flex:none">{diamond_svg(i + 1, ins.get("size", 84) * 1.05, 100 + i)}</div>' if num else
                      f'<i style="width:22px;height:22px;border-radius:50%;background:{OR};box-shadow:0 0 24px {rgba(OR, .7)};flex:none;display:block"></i>')
    items = "".join(f'<div class="bl" id="b{i}" style="display:flex;align-items:center;gap:{18 if num else 30}px;margin-top:{ins.get("gap", 34)}px;opacity:0">'
                    + mark(i) +
                    f'<span class="hv" style="font-family:Poppins;font-weight:800;letter-spacing:-.025em;font-size:{ins.get("size", 84)}px;white-space:normal">{H.escape(it["t"])}</span></div>' for i, it in enumerate(ins["items"]))
    bg = (f'<div id="ph" style="position:absolute;inset:-2%;background:url(assets/{os.path.basename(ins["src"])}) center/cover;transform-origin:{ins.get("origin", "60% 40%")}"></div>'
          '<div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(4,4,4,.93) 0%,rgba(4,4,4,.82) 42%,rgba(4,4,4,.15) 75%,rgba(4,4,4,0) 100%)"></div>'
          if ins.get("src") else '<div class="stage" id="ph"></div>')
    body = (bg +
            '<div class="vig"></div>'
            f'<div style="position:absolute;left:{ins.get("left", 130)}px;top:{ins.get("top", 200)}px;width:{ins.get("width", 1050)}px">'
            + (f'<div class="hv" id="ttl" style="font-family:Poppins;font-weight:500;letter-spacing:0;font-size:{ins.get("title_size", 52)}px;color:rgba(255,255,255,.85);white-space:normal;opacity:0">{H.escape(ins["title"]["t"])}</div>' if ins.get("title") else "")
            + items + '</div>')
    js, cues = [drift("#ph", dur, 1.0, 1.07)], [("whoosh-short.wav", -0.08, -27)]
    if ins.get("title"):
        js.append(f"tl.fromTo('#ttl',{{opacity:0,y:16}},{{opacity:1,y:0,duration:.3}},{t_of(rel, ins['title'].get('at'), 0.05):.3f});")
    for i, it in enumerate(ins["items"]):
        t = t_of(rel, it.get("at"), 0.3 + 0.4 * i)
        if ins.get("_words"):  # on the exact spoken word
            t = word_times([it["t"].split(" ")[0]], ins["_words"], t)[0]
        js.append(f"tl.fromTo('#b{i}',{{opacity:0,x:-40,filter:'blur(10px)'}},{{opacity:1,x:0,filter:'blur(0px)',duration:.3,ease:'power3.out'}},{t:.3f});")
        cues.append(("pop.wav", t - 0.05, -23))
    return page(ins["id"], body, "\n".join(js), dur, fade_in=False), cues


# ------------------------------------------------------------------ ytcard: one of the creator's own YouTube videos (real thumbnail + title)
def ytcard(ins, dur, rel, assets):
    body = ('<div class="stage"></div>'
            f'<div id="cd" style="position:absolute;left:50%;top:50%;width:1080px;margin-left:-540px;margin-top:-370px;opacity:0">'
            f'<div style="position:relative;border-radius:22px;overflow:hidden;box-shadow:0 50px 120px rgba(0,0,0,.8)">'
            f'<img src="assets/{os.path.basename(ins["src"])}" style="display:block;width:100%">'
            '<div style="position:absolute;left:50%;top:50%;width:150px;height:104px;margin:-52px 0 0 -75px;border-radius:26px;background:#ff0033;display:flex;align-items:center;justify-content:center">'
            '<div style="width:0;height:0;border-left:42px solid #fff;border-top:26px solid transparent;border-bottom:26px solid transparent;margin-left:8px"></div></div></div>'
            f'<div style="font-family:Poppins;font-weight:700;font-size:46px;color:#fff;margin-top:30px;letter-spacing:-.01em">{H.escape(ins["title"])}</div>'
            f'<div style="font-family:Poppins;font-weight:500;font-size:30px;color:rgba(255,255,255,.6);margin-top:8px">{H.escape(ins.get("channel", ""))}</div></div>'
            '<div class="vig"></div>')
    js = ["tl.fromTo('#cd',{opacity:0,y:60,scale:.92},{opacity:1,y:0,scale:1,duration:.45,ease:'power3.out'},0.02);", drift("#cd", dur, 1.0, 1.03)]
    return page(ins["id"], body, "\n".join(js), dur, fade_in=False), [("whoosh-short.wav", -0.08, -25)]


# ------------------------------------------------------------------ scene: a hand-made illustration (HTML) on the dark stage
def scene(ins, dur, rel, assets):
    """ins.html = body markup (images copied through ins.files, referenced as assets/<name>), ins.js = GSAP lines where
    {{anchor}} becomes seconds into the insert ({{src:238.4}}, {{0.3}}). Built in the project (build_inserts.py) for the
    concrete things the speaker names (a post, a mail, a spreadsheet) : each one illustrated, never a list of text."""
    import re as _re
    js = _re.sub(r"\{\{(.*?)\}\}", lambda m: f"{t_of(rel, float(m.group(1)) if _re.fullmatch(r'[0-9.]+', m.group(1)) else m.group(1)):.3f}",
                 ins.get("js", "").replace("{{dur}}", f"{dur:.3f}"))
    ov = bool(ins.get("overlay"))  # pop-up over the face cam (a short label at a precise x,y) : no dark stage, no camera push
    ins = dict(ins, html=ins["html"].replace("{{dur}}", f"{dur:.3f}"))  # a <video> (ins.face : assets/face.mp4) spans the insert
    if ov:
        body = ins["html"]
        cues = [(c[0], t_of(rel, c[1]), c[2]) for c in ins.get("cues", [])]
        return page(ins["id"], body, js, dur, fade_in=False, fade_out=False, opaque=False), cues
    body = ('<div class="stage"></div><div id="cam" style="position:absolute;inset:0">' + ins["html"] + '</div>'
            + ('' if ins.get("face") else '<div class="vig"></div>'))  # no darkened corners over his own shot : they vanished at the hand-back (v19)
    js = drift("#cam", dur, 1.0, ins.get("push", 1.04)) + "\n" + js
    cues = [("whoosh-short.wav", -0.08, -26)] + [(c[0], t_of(rel, c[1]), c[2]) for c in ins.get("cues", [])]  # "src:" anchors too
    # a scene with the speaker's own video ends on his full-frame shot : no fade to black at the end (v16 at 0:58, one black frame)
    return page(ins["id"], body, js, dur, fade_in=False, fade_out=ins.get("fade_out", False)), cues


# ------------------------------------------------------------------ keyword : one or two strong words, huge, on the face cam
def keyword_gras(ins, dur, rel, assets):
    """Keyword style « gras » : heavy capitals in the title font on the chest, white with a faint fall-off, the strong word
    in the accent colour with a glow, a soft dark veil on the lower half while it shows. Spoken words only, each landing as
    it is said. ins.words = [[text, anchor, "acc"?]]."""
    sz = ins.get("size", 116)
    yc = ins.get("yc", 902)  # 83.5 % of the height : under the chin
    spans, js, cues = "", [], []
    first = None
    for i, w in enumerate(ins["words"]):
        txt, at = w[0], t_of(rel, w[1], 0.0)
        first = at if first is None else first
        acc = len(w) > 2
        fill = (f"linear-gradient(180deg,{shade(OR, .18)} 0%,{OR} 55%,{shade(OR, -.08)} 100%)" if acc else "linear-gradient(180deg,#FFFFFF 0%,#FFFFFF 48%,#D9D4CD 100%)")
        flt = (f"drop-shadow(0 2px 1.5px {rgba(shade(OR, -.75), .35)}) drop-shadow(0 0 22px {rgba(OR, .55)}) drop-shadow(0 10px 22px rgba(0,0,0,.35))" if acc
               else "drop-shadow(0 2px 1.5px rgba(0,0,0,.35)) drop-shadow(0 10px 22px rgba(0,0,0,.45))")
        spans += (f'<span id="k{i}" style="display:inline-block;margin:0 .11em;opacity:0;background:{fill};-webkit-background-clip:text;'
                  f'background-clip:text;color:transparent;filter:{flt}">{H.escape(txt)}</span>')
        if ins.get("br_after") == i:  # a chosen line break
            spans += "<br>"
        js.append(f"tl.fromTo('#k{i}',{{opacity:0,y:12,scale:1.06,filter:'blur(14px)'}},{{opacity:1,y:0,scale:1,filter:'blur(0px)',duration:.17,ease:'power3.out'}},{max(at - 0.04, 0):.3f});")
        js.append(f"tl.set('#k{i}',{{filter:'none'}},{max(at - 0.04, 0) + 0.18:.3f});")
    cues.append(("whoosh-short.wav", max(first - 0.1, 0), -26))
    body = (f'<div id="scrim" style="position:absolute;left:0;right:0;bottom:0;height:52%;opacity:0;'
            f'background:linear-gradient(to top,rgba(0,0,0,.50) 0%,rgba(0,0,0,.275) 45%,rgba(0,0,0,0) 100%)"></div>'
            f'<div style="position:absolute;left:0;right:0;top:{yc - sz * 0.6:.0f}px;text-align:center">'
            f'<div style="display:inline-block;font-family:{TITLE};font-weight:900;letter-spacing:-.03em;text-transform:uppercase;'
            f'font-size:{sz}px;line-height:1.05;max-width:1560px;white-space:normal">{spans}</div></div>')
    js.insert(0, f"tl.fromTo('#scrim',{{opacity:0}},{{opacity:1,duration:.24,ease:'power3.out'}},{max(first - 0.1, 0):.3f});")
    js.append(f"tl.to('#stg',{{opacity:0,scale:.96,duration:.16,ease:'power3.in'}},{dur - 0.16:.3f});")
    return page(ins["id"], body, "\n".join(js), dur, fade_in=False, fade_out=False, opaque=False), cues


def keyword(ins, dur, rel, assets):
    if ins.get("style") == "gras":
        return keyword_gras(ins, dur, rel, assets)
    # style « simple » (default) :
    """Kinetic keywords (keywords yes, never the whole sentence) : ins.words =
    [[text, anchor, color?]] each word lands on its spoken word (scale 1.35 -> 1, blur -> sharp, a short whoosh), the
    block sits low on the chest (ins.y) and leaves with the insert. Never the whole sentence."""
    y = ins.get("y", 760)
    sz = ins.get("size", 120)
    spans, js, cues = "", [], []
    for i, w in enumerate(ins["words"]):
        txt, at = w[0], t_of(rel, w[1], 0.0)
        col = w[2] if len(w) > 2 else "#fff"
        spans += (f'<span id="k{i}" style="display:inline-block;margin:0 .14em;opacity:0;color:{col};'
                  f'text-shadow:0 0 60px rgba(0,0,0,.55),0 6px 30px rgba(0,0,0,.7),0 0 26px {rgba(OR, .55) if col != "#fff" else "rgba(0,0,0,0)"}">{H.escape(txt)}</span>')
        js.append(f"tl.fromTo('#k{i}',{{opacity:0,scale:1.35,filter:'blur(10px)'}},{{opacity:1,scale:1,filter:'blur(0px)',duration:.18,ease:'power3.out'}},{max(at - 0.03, 0):.3f});")
        cues.append(("whoosh-short.wav", max(at - 0.08, 0), -24))
    body = (f'<div class="c" style="top:{y}px"><div style="display:inline-block;font-family:{TITLE};font-weight:700;letter-spacing:-.02em;'
            f'font-size:{sz}px;line-height:1">{spans}</div></div>')
    js.append(f"tl.to('#stg',{{opacity:0,duration:.12}},{dur - 0.12:.3f});")
    return page(ins["id"], body, "\n".join(js), dur, fade_in=False, fade_out=False, opaque=False), cues


# ------------------------------------------------------------------ icon : the logo of what he names pops next to him
def icon(ins, dur, rel, assets):
    """A logo / icon (ins.src, in the project's assets) pops beside the face when it is named (the
    tool logos glowing next to the speaker) : back-out bounce, soft glow, slow float, a pop sound."""
    x, y, sz = ins.get("x", 1380), ins.get("y", 330), ins.get("size", 220)
    at = t_of(rel, ins.get("at_pop"), 0.0)
    body = (f'<div id="ic" style="position:absolute;left:{x}px;top:{y}px;width:{sz}px;height:{sz}px;border-radius:{sz * 0.24:.0f}px;'
            f'background:{ins.get("bg", OR)};display:flex;align-items:center;justify-content:center;opacity:0;'
            f'box-shadow:0 0 60px {ins.get("glow", rgba(OR, .75))},0 20px 50px rgba(0,0,0,.5)">'
            f'<img src="assets/{os.path.basename(ins["src"])}" style="width:{sz * ins.get("inner", 0.62):.0f}px;height:{sz * ins.get("inner", 0.62):.0f}px"></div>')
    js = [f"tl.fromTo('#ic',{{opacity:0,scale:.3,rotation:-14}},{{opacity:1,scale:1,rotation:0,duration:.35,ease:'back.out(2.2)'}},{at:.3f});",
          f"tl.to('#ic',{{y:-14,duration:{max(dur - at - .5, .3):.2f},ease:'sine.inOut'}},{at + .35:.3f});",
          f"tl.to('#stg',{{opacity:0,duration:.15}},{dur - 0.15:.3f});"]
    return page(ins["id"], body, "\n".join(js), dur, fade_in=False, fade_out=False, opaque=False), [("pop.wav", at - 0.02, -20)]


KINDS = dict(keyword=keyword, icon=icon, scene=scene, ytcard=ytcard, bullets=bullets, term=term, still=still, caption=caption, nametag=nametag, diamonds=diamonds, alert=alert, doc=doc, logo=logo, wall=wall, tokens=tokens)


def build(ins, dur, rel, assets):
    return KINDS[ins["kind"]](ins, dur, rel, assets)
