#!/usr/bin/env python3
"""Wrap each src/section-*.html fragment in the shared Geist Light shell.

Every output page is a standalone file (inline CSS + JS, no shared assets).
Run from anywhere:  python3 l_victor/build.py

Fragment header (first line), a JSON object inside an HTML comment:
  <!-- {"id": "1.1", "title": "Dear Simon", "prev": null, "next": "section-1.2.html"} -->

Fragment markup:
  <h2 class="scene">Victor's Room</h2>          scene slug
  <div class="letter">...</div>                  Dear Simon voiceover
  <section class="node" data-node="ID">          decision node
    <p class="prompt">...</p>
    <button data-pick="a" data-fx='{"felix":1}'>...</button>
  </section>
  <div class="branch" data-node="ID" data-pick="a">...</div>   shown for that pick
  <div class="gate" data-node="ID">...</div>                     shown once ID is picked
  <div class="cond" data-if="honesty>=1">...</div>               state-dependent text
     atoms: stat>=n, stat<=n, stat>n, stat<n, nodeId=pick, nodeId!=pick
     join with & (and) or | (or); & binds tighter.
Stats: honesty, felix, mia, benji. Node ids are global across sections.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"

SHELL = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Love, Victor · __TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#ffffff; --surface:#fafafa; --border:#eaeaea; --border-strong:#d4d4d4;
  --fg:#171717; --fg-2:#4d4d4d; --fg-3:#8f8f8f; --accent:#000000;
  --sans:"Geist",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"Geist Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--sans);font-size:17px;line-height:1.7;-webkit-font-smoothing:antialiased}
main{max-width:640px;margin:0 auto;padding:48px 16px 96px}
header{margin-bottom:40px;padding-bottom:24px;border-bottom:1px solid var(--border)}
.kicker{font-family:var(--mono);font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--fg-3);margin:0 0 8px}
h1{font-size:32px;line-height:1.2;font-weight:600;letter-spacing:-.03em;margin:0}
h2.scene{font-family:var(--mono);font-size:12px;font-weight:500;letter-spacing:.04em;text-transform:uppercase;color:var(--fg-3);margin:48px 0 16px;display:flex;align-items:center;gap:12px}
h2.scene::after{content:"";flex:1;height:1px;background:var(--border)}
p{margin:0 0 1.1em}
em{font-style:italic}
.letter{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:20px 20px 4px;margin:24px 0}
.letter::before{content:"Dear Simon";display:block;font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--fg-3);margin-bottom:10px}
.letter.reply::before{content:"Dear Victor"}
.letter p{font-size:16px;color:var(--fg-2)}
.node{border:1px solid var(--border);background:var(--surface);border-radius:8px;padding:16px;margin:32px 0}
.node .prompt{font-size:15px;color:var(--fg-2);margin:0 0 12px}
.node button{display:block;width:100%;text-align:left;font:inherit;font-size:15px;line-height:1.5;color:var(--fg);background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:12px 14px;margin:8px 0 0;cursor:pointer;transition:border-color .15s,opacity .15s}
.node button:hover:not(:disabled){border-color:var(--accent)}
.node button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.node button.picked{border-color:var(--accent);box-shadow:inset 3px 0 0 var(--accent)}
.node button:disabled:not(.picked){opacity:.4;cursor:default}
.node button:disabled.picked{cursor:default}
.branch{border-left:2px solid var(--border);padding-left:16px;margin:0 0 1.1em}
.branch,.gate,.cond{display:none}
.branch.on,.gate.on{display:block}
.cond.on{display:block}
span.cond.on{display:inline}
nav.foot{margin-top:56px;padding-top:24px;border-top:1px solid var(--border);display:none;gap:12px;flex-wrap:wrap;align-items:center}
nav.foot.on{display:flex}
a.btn,button.btn{font:inherit;font-size:14px;font-weight:500;text-decoration:none;border-radius:6px;padding:10px 16px;cursor:pointer;border:1px solid var(--border);background:var(--bg);color:var(--fg)}
a.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
a.btn:hover,button.btn:hover{border-color:var(--accent)}
a.btn.primary:hover{background:#333}
.tools{margin-top:24px;display:flex;gap:12px;flex-wrap:wrap}
details.notes{margin-top:32px;border:1px solid var(--border);border-radius:8px;background:var(--surface)}
details.notes summary{cursor:pointer;padding:12px 16px;font-family:var(--mono);font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--fg-3)}
details.notes dl{margin:0;padding:0 16px 12px;display:grid;grid-template-columns:auto 1fr;gap:6px 16px;font-size:14px}
details.notes dt{color:var(--fg-2)}
details.notes dd{margin:0;font-family:var(--mono);color:var(--fg)}
@media (max-width:480px){body{font-size:16px}h1{font-size:26px}main{padding-top:32px}}
</style>
</head>
<body data-section="__ID__">
<main>
<header>
  <p class="kicker">Love, Victor · Season 1 · Episode 1 · Section __ID__</p>
  <h1>__TITLE__</h1>
</header>
<article id="story">
__BODY__
</article>
<nav class="foot" id="foot">
  __PREV__
  __NEXT__
</nav>
<details class="notes">
  <summary>Notes to self</summary>
  <dl id="notes"></dl>
</details>
<div class="tools">
  <button class="btn" type="button" id="redo">Replay this section</button>
  __RESET__
</div>
</main>
<script>
(function(){
  var KEY = 'love-victor:state:v1';
  var SECTION = document.body.getAttribute('data-section');
  var STATS = ['honesty','felix','mia','benji'];
  var LABELS = {honesty:'Honest with myself', felix:'Felix', mia:'Mia', benji:'Benji'};

  function readStore(){ try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch(e){ return null; } }
  function writeStore(s){ try { localStorage.setItem(KEY, JSON.stringify(s)); } catch(e){} }
  function encode(s){ try { return btoa(unescape(encodeURIComponent(JSON.stringify(s)))); } catch(e){ return ''; } }
  function decode(t){ try { return JSON.parse(decodeURIComponent(escape(atob(t)))); } catch(e){ return null; } }

  var state = readStore() || {picks:{}};
  if (!state.picks) state.picks = {};
  var m = location.hash.match(/s=([^&]+)/);
  if (m) {
    var h = decode(m[1]);
    if (h && h.picks) for (var k in h.picks) state.picks[k] = h.picks[k];
    writeStore(state);
  }

  function stats(){
    var t = {}; STATS.forEach(function(k){ t[k] = 0; });
    for (var id in state.picks) {
      var fx = state.picks[id].fx || {};
      for (var k in fx) t[k] = (t[k] || 0) + fx[k];
    }
    return t;
  }
  function atom(a, st){
    var r = a.trim().match(/^(\w+)\s*(>=|<=|!=|=|>|<)\s*(-?\w+)$/);
    if (!r) return false;
    var key = r[1], op = r[2], val = r[3];
    if (STATS.indexOf(key) >= 0) {
      var x = st[key], y = Number(val);
      return op === '>=' ? x >= y : op === '<=' ? x <= y : op === '>' ? x > y : op === '<' ? x < y : op === '=' ? x === y : x !== y;
    }
    var p = state.picks[key] ? state.picks[key].pick : '';
    return op === '!=' ? p !== val : p === val;
  }
  function test(expr, st){
    return expr.split('|').some(function(any){
      return any.split('&').every(function(all){ return atom(all, st); });
    });
  }

  function render(){
    var st = stats();
    var nodes = document.querySelectorAll('.node');
    var allPicked = true;
    nodes.forEach(function(n){
      var id = n.getAttribute('data-node');
      var p = state.picks[id];
      n.querySelectorAll('button').forEach(function(b){
        b.disabled = !!p;
        b.classList.toggle('picked', !!p && p.pick === b.getAttribute('data-pick'));
      });
      if (!p) allPicked = false;
    });
    document.querySelectorAll('.branch').forEach(function(b){
      var p = state.picks[b.getAttribute('data-node')];
      b.classList.toggle('on', !!p && p.pick === b.getAttribute('data-pick'));
    });
    document.querySelectorAll('.gate').forEach(function(g){
      g.classList.toggle('on', !!state.picks[g.getAttribute('data-node')]);
    });
    document.querySelectorAll('.cond').forEach(function(c){
      c.classList.toggle('on', test(c.getAttribute('data-if'), st));
    });
    document.getElementById('foot').classList.toggle('on', allPicked);
    var next = document.getElementById('next');
    if (next) next.setAttribute('href', next.getAttribute('data-href') + '#s=' + encode(state));
    var prev = document.getElementById('prev');
    if (prev) prev.setAttribute('href', prev.getAttribute('data-href') + '#s=' + encode(state));
    var dl = document.getElementById('notes'); dl.innerHTML = '';
    STATS.forEach(function(k){
      var dt = document.createElement('dt'); dt.textContent = LABELS[k];
      var dd = document.createElement('dd'); var v = st[k];
      dd.textContent = v > 0 ? '+' + v : String(v);
      dl.appendChild(dt); dl.appendChild(dd);
    });
  }

  document.getElementById('story').addEventListener('click', function(e){
    var b = e.target.closest('.node button');
    if (!b || b.disabled) return;
    var id = b.closest('.node').getAttribute('data-node');
    var fx = {}; try { fx = JSON.parse(b.getAttribute('data-fx') || '{}'); } catch(err){}
    state.picks[id] = {pick: b.getAttribute('data-pick'), fx: fx, sec: SECTION};
    writeStore(state);
    render();
    var br = document.querySelector('.branch.on[data-node="' + id + '"]') || document.querySelector('.gate.on[data-node="' + id + '"]');
    if (br) br.scrollIntoView({behavior:'smooth', block:'start'});
  });
  document.getElementById('redo').addEventListener('click', function(){
    for (var id in state.picks) if (state.picks[id].sec === SECTION) delete state.picks[id];
    writeStore(state); render(); window.scrollTo({top:0, behavior:'smooth'});
  });
  var reset = document.getElementById('reset');
  if (reset) reset.addEventListener('click', function(){
    state = {picks:{}}; writeStore(state); history.replaceState(null, '', location.pathname); render(); window.scrollTo({top:0});
  });
  render();
})();
</script>
</body>
</html>
"""


def build_one(path: pathlib.Path) -> str:
    text = path.read_text(encoding="utf-8")
    head = re.match(r"\s*<!--\s*(\{.*?\})\s*-->\s*", text, re.S)
    if not head:
        raise SystemExit(f"{path.name}: missing JSON header comment")
    meta = json.loads(head.group(1))
    body = text[head.end():].rstrip() + "\n"
    prev = (f'<a class="btn" id="prev" data-href="{meta["prev"]}" href="{meta["prev"]}">Back</a>'
            if meta.get("prev") else "")
    nxt = (f'<a class="btn primary" id="next" data-href="{meta["next"]}" href="{meta["next"]}">'
           f'{meta.get("next_label", "Continue")}</a>' if meta.get("next") else "")
    reset = ('<button class="btn" type="button" id="reset">Start the episode over</button>'
             if meta.get("reset") else "")
    out = (SHELL.replace("__TITLE__", meta["title"])
                .replace("__ID__", meta["id"])
                .replace("__PREV__", prev)
                .replace("__NEXT__", nxt)
                .replace("__RESET__", reset)
                .replace("__BODY__", body))
    dest = ROOT / f"section-{meta['id']}.html"
    dest.write_text(out, encoding="utf-8")
    return dest.name


def main():
    for path in sorted(SRC.glob("section-*.html")):
        print("built", build_one(path))


if __name__ == "__main__":
    main()
