"""Batched Premiere operations through execute_extendscript (2026-10-04 : one MCP call per keyframe / volume / import made a
full build take ~30 min ; here a few hundred items per call). Same ExtendScript the MCP tools run, in loops."""
import json, os

JS_FIND_PARAM = r'''
function __nm(a){return String(a||"").toLowerCase().replace(/[\s_-]+/g,"");}
function __param(clip, comps, params){
  for (var i=0;i<clip.components.numItems;i++){var c=clip.components[i];var ok=false;
    for (var a=0;a<comps.length;a++) if(__nm(c.displayName)==__nm(comps[a])) ok=true;
    if(!ok) continue;
    for (var j=0;j<c.properties.numItems;j++){for (var b=0;b<params.length;b++) if(__nm(c.properties[j].displayName)==__nm(params[b])) return c.properties[j];}}
  return null;}
'''


def _run(pp, body, timeout_hint=None):
    r = pp("execute_extendscript", script=JS_FIND_PARAM + body)
    if isinstance(r, str):
        r = json.loads(r)
    if not r.get("success", True) and "error" in r:
        raise RuntimeError(str(r)[:400])
    return r


def import_files(pp, paths, bin_name):
    """Imports many files at once and returns {path: nodeId}."""
    out = {}
    for k in range(0, len(paths), 60):
        chunk = paths[k:k + 60]
        body = f'''
var paths = {json.dumps(chunk)};
var root = app.project.rootItem, bin = null;
for (var i=0;i<root.children.numItems;i++) if (root.children[i].name=={json.dumps(bin_name)} && root.children[i].type==2) bin = root.children[i];
if (!bin) bin = root.createBin({json.dumps(bin_name)});
app.project.importFiles(paths, true, bin, false);
var res = {{}};
function walk(it){{ for (var i=0;i<it.children.numItems;i++){{ var c=it.children[i]; if (c.type==2) walk(c); else {{ try {{ var p=c.getMediaPath(); for (var j=0;j<paths.length;j++) if (p==paths[j]) res[p]=c.nodeId; }} catch(e){{}} }} }} }}
walk(bin);
return JSON.stringify({{success:true, ids:res}});'''
        r = _run(pp, body)
        out.update(r.get("ids", {}))
    missing = [p for p in paths if p not in out]
    if missing:
        raise RuntimeError(f"{len(missing)} files not imported, e.g. {missing[:2]}")
    return out


def scale_keys(pp, seq_id, jobs):
    """jobs [(clipNodeId, [(t_clip_s, value), ...])] -> Motion > Scale keys (French UI : Trajectoire > Echelle)."""
    done = 0
    for k in range(0, len(jobs), 30):
        chunk = [[c, ks] for c, ks in jobs[k:k + 30]]
        body = f'''
var jobs = {json.dumps(chunk)}, done = 0, errs = [];
for (var i=0;i<jobs.length;i++){{
  var info = __findClip(jobs[i][0], {json.dumps(seq_id)}); if(!info){{errs.push(jobs[i][0]);continue;}}
  var p = __param(info.clip, ["Trajectoire","Motion","Bewegung","Movimiento","Movimento"], ["Echelle","Échelle","Scale","Skalierung","Escala","Scala"]); if(!p){{errs.push("p"+jobs[i][0]);continue;}}
  p.setTimeVarying(true);
  for (var j=0;j<jobs[i][1].length;j++){{ var t=jobs[i][1][j][0], v=jobs[i][1][j][1]; p.addKey(t); p.setValueAtKey(t, v, true); }}
  done++;
}}
return JSON.stringify({{success:true, done:done, errs:errs}});'''
        r = _run(pp, body)
        if r.get("errs"):
            raise RuntimeError(f"scale keys failed on {r['errs'][:3]}")
        done += r.get("done", 0)
    return done


def volumes(pp, seq_id, jobs):
    """jobs [(clipNodeId, dB)] -> clip Volume > Level, same calibration as the MCP (linear = 10^((dB-15)/20))."""
    done = 0
    for k in range(0, len(jobs), 80):
        chunk = [[c, 10 ** ((db - 15) / 20)] for c, db in jobs[k:k + 80]]
        body = f'''
var jobs = {json.dumps(chunk)}, done = 0, errs = [];
for (var i=0;i<jobs.length;i++){{
  var info = __findClip(jobs[i][0], {json.dumps(seq_id)}); if(!info){{errs.push(jobs[i][0]);continue;}}
  var p = __param(info.clip, ["Volume","Volumen","Lautstärke"], ["Level","Niveau","Nivel","Pegel"]); if(!p){{errs.push("p"+jobs[i][0]);continue;}}
  p.setValue(jobs[i][1], true); done++;
}}
return JSON.stringify({{success:true, done:done, errs:errs}});'''
        r = _run(pp, body)
        if r.get("errs"):
            raise RuntimeError(f"volumes failed on {r['errs'][:3]}")
        done += r.get("done", 0)
    return done
