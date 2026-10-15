#!/usr/bin/env python3
"""Turn what the creator did in the studio into HIS style, so the next video never needs the same correction
(the promise of the video : « chaque retour devient une règle dans son mode d'emploi, il ne refait plus les erreurs »).

Sources, per video project :
  - projects/<slug>/review/studio-log.json : what he changed himself in the studio (written by review/montage_api.py) :
    music levels, cuts (with the words they removed) ;
  - projects/<slug>/review/<video>.json : his comments.
The style : looks/<plan.look>/look.json, field "rules" = his « mode d'emploi », read by the montage skill before every video.

  python3 tools/learn.py <slug>                 report : what is applied automatically, what Claude must turn into a rule
  python3 tools/learn.py <slug> --auto          apply only what needs no judgement (music levels set in the studio)
  python3 tools/learn.py <slug> --rule "<règle>" [--quote "<sa phrase>"] --from C<id>,L<n>
                                                add a rule to his style and mark those comments / studio actions learned
  python3 tools/learn.py <slug> --local --from C<id>,L<n> [--why "<pourquoi>"]
                                                mark items as specific to this video (no rule)
  python3 tools/learn.py --pending [--look <name>]
                                                every project of that style with something not learned yet
"""
import argparse, glob, json, os, sys, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.join(HERE, "projects")


def P(slug, *a):
    return os.path.join(PROJ, slug, *a)


def load(f, default):
    return json.load(open(f)) if os.path.exists(f) else default


def look_name(slug):
    return load(P(slug, "plan.json"), {}).get("look")


def look_path(name):
    return os.path.join(HERE, "looks", name, "look.json")


def learned_path(slug):
    return P(slug, "review", "learned.json")


def items(slug):
    """Studio actions (L<n>) and comments (C<id>) of a project, with their learned status."""
    learned = load(learned_path(slug), {})
    out = []
    for n, e in enumerate(load(P(slug, "review", "studio-log.json"), [])):
        out.append({"id": f"L{n}", "src": "studio", "e": e, "done": e.get("learned") or learned.get(f"L{n}")})
    for f in sorted(glob.glob(P(slug, "review", "*.json"))):
        if os.path.basename(f) in ("studio-log.json", "learned.json"):
            continue
        d = load(f, {})
        for c in d.get("comments", []):
            out.append({"id": f"C{c['id']}", "src": os.path.basename(f), "e": c, "done": learned.get(f"C{c['id']}")})
    return out


def mark(slug, ids, value):
    learned = load(learned_path(slug), {})
    for i in ids:
        learned[i] = value
    os.makedirs(os.path.dirname(learned_path(slug)), exist_ok=True)
    json.dump(learned, open(learned_path(slug), "w"), indent=1, ensure_ascii=False)


def add_rule(name, text, quote=None, replace=None):
    """A correction replaces the rule it contradicts (replace = the start of the old rule's text), never piles up."""
    lp = look_path(name)
    look = load(lp, {})
    rule = f"{time.strftime('%Y-%m-%d')} · {text}" + (f" « {quote} »" if quote else "")
    rules = look.setdefault("rules", [])
    if replace:
        rules[:] = [r for r in rules if not r.split(" · ", 1)[-1].startswith(replace)]
    if not any(r.split(" · ", 1)[-1].startswith(text) for r in rules):
        rules.append(rule)
        json.dump(look, open(lp, "w"), indent=1, ensure_ascii=False)
        return rule
    return None


def auto(slug, name):
    """Music levels set in the studio become the style's levels (they need no judgement)."""
    lp = look_path(name); look = load(lp, {})
    done = []
    for it in items(slug):
        e = it["e"]
        if it["done"] or it["src"] != "studio" or e.get("kind") != "music":
            continue
        role = "intro" if e.get("role") == "intro" else "body"
        mu = look.setdefault("music", {}).setdefault(role, {})
        old = mu.get("under_lu")
        mu["under_lu"] = round(float(e["to"]), 1)
        mu[f"_why_studio"] = f"{time.strftime('%Y-%m-%d')} : réglé dans le studio sur « {slug} » ({e.get('track', '')}), {old} -> {mu['under_lu']} dB sous la voix"
        done.append((it["id"], role, old, mu["under_lu"]))
    if done:
        json.dump(look, open(lp, "w"), indent=1, ensure_ascii=False)
        for i, role, old, new in done:
            lab = "Musique de l'intro" if role == "intro" else "Musique du corps"
            add_rule(name, f"{lab} à {new} dB sous la voix (réglée par lui dans le studio, avant {old})", replace=lab)
        mark(slug, [d[0] for d in done], "auto: niveau de musique dans le style")
    return done


def report(slug, name):
    pend = [it for it in items(slug) if not it["done"]]
    print(f"Style : looks/{name}/look.json ({len(load(look_path(name), {}).get('rules', []))} règles dans son mode d'emploi)")
    if not pend:
        print("Rien en attente : tout ce qu'il a fait dans le studio est déjà retenu."); return pend
    print("À transformer en règle (ou à marquer --local si c'est propre à cette vidéo) :")
    for it in pend:
        e = it["e"]
        if it["src"] == "studio" and e.get("kind") == "cut":
            what = (f"a coupé « {e['removed_words']} »" if e.get("removed_words") else f"a coupé {e.get('dur', '?')} s de silence") if e.get("what") == "range" else f"a supprimé la prise {e.get('take')}"
            print(f"  {it['id']}  [studio {e.get('t')}] {what}")
        elif it["src"] == "studio":
            print(f"  {it['id']}  [studio {e.get('t')}] {e}")
        else:
            print(f"  {it['id']}  [{it['src']} à {e.get('t')} s, {e.get('tag', '')}] {e.get('text', '')}")
    print("Une coupe de silence répétée = des pauses trop longues pour lui (cut.max_pause / pause_keep) ; une coupe de mots = une reprise ou un passage qu'il juge inutile : la règle dit pourquoi, pas où.")
    return pend


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?"); ap.add_argument("--auto", action="store_true")
    ap.add_argument("--rule"); ap.add_argument("--quote"); ap.add_argument("--from", dest="frm", default="")
    ap.add_argument("--local", action="store_true"); ap.add_argument("--why", default="propre à cette vidéo")
    ap.add_argument("--pending", action="store_true"); ap.add_argument("--look")
    ap.add_argument("--replace", help="the start of the rule this one replaces (a correction replaces, never piles up)")
    a = ap.parse_args()
    if a.pending:
        found = 0
        for d in sorted(glob.glob(os.path.join(PROJ, "*", "plan.json"))):
            slug = os.path.basename(os.path.dirname(d))
            if a.look and look_name(slug) != a.look:
                continue
            n = len([it for it in items(slug) if not it["done"]])
            if n:
                found += 1; print(f"{slug} : {n} retour(s) ou réglage(s) pas encore retenu(s) -> python3 tools/learn.py {slug}")
        if not found:
            print("Rien en attente.")
        return
    if not a.slug:
        sys.exit("slug manquant")
    name = a.look or look_name(a.slug)
    if not name or not os.path.exists(look_path(name)):
        sys.exit(f"pas de style pour {a.slug} (plan.look) : lance d'abord le skill create-style")
    ids = [i.strip() for i in a.frm.split(",") if i.strip()]
    if ids == ["all"]:
        ids = [it["id"] for it in items(a.slug) if not it["done"]]
    if a.rule:
        r = add_rule(name, a.rule, a.quote, a.replace)
        print(f"Ajouté à son mode d'emploi : {r}" if r else "Cette règle y était déjà.")
        if ids:
            mark(a.slug, ids, f"règle : {a.rule}")
        return
    if a.local:
        mark(a.slug, ids, f"local : {a.why}"); print(f"{len(ids)} élément(s) marqué(s) propres à cette vidéo."); return
    for i, role, old, new in auto(a.slug, name):
        print(f"Retenu automatiquement : musique {role} {old} -> {new} dB sous la voix ({i})")
    if not a.auto:
        report(a.slug, name)


if __name__ == "__main__":
    main()
