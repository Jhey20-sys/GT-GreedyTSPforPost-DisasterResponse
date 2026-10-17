"""
Builds route_animation.html: an animated map of the greedy (Algorithm 2.7) and
optimal (Held-Karp) tours driving along the real Cagayan de Oro road network.
The page is self-contained and works offline.

Run after build_osm_dataset.py:
    python tsp_route_animation.py
"""

import csv
import json
import math
import os

import networkx as nx
import osmnx as ox
from shapely.geometry import LineString

from build_osm_dataset import GRAPH_FILE
from tsp_greedy_cdo import DATA_DIR, HERE, SITES, greedy_tsp, held_karp, load_weights

OUT_FILE = os.path.join(HERE, "route_animation.html")
MAJOR_ROADS = {"trunk", "primary", "secondary", "tertiary", "trunk_link", "primary_link", "secondary_link"}
WIDTH_PX = 640


def build_data():
    G = ox.load_graphml(GRAPH_FILE)
    with open(os.path.join(DATA_DIR, "nodes.csv"), newline="", encoding="utf-8") as f:
        osm = [int(r["osm_node"]) for r in csv.DictReader(f)]
    W = load_weights()
    greedy, g_total = greedy_tsp(W, 0)
    opt, o_total = held_karp(W, 0)

    k = math.cos(math.radians(SITES[0][2]))
    lons = [s[3] for s in SITES]
    lats = [s[2] for s in SITES]
    pad = 0.004
    x0, x1, y0, y1 = min(lons) - pad, max(lons) + pad, min(lats) - pad, max(lats) + pad
    scale = WIDTH_PX / ((x1 - x0) * k)
    height = (y1 - y0) * scale

    def project(lon, lat):
        return (20 + (lon - x0) * k * scale, 10 + (y1 - lat) * scale)

    def edge_coords(u, v):
        d = min(G[u][v].values(), key=lambda e: e["travel_time"])
        if "geometry" in d:
            return list(d["geometry"].coords)
        return [(G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])]

    def leg(a, b):
        path = nx.shortest_path(G, osm[a], osm[b], weight="travel_time")
        pts = []
        for u, v in zip(path[:-1], path[1:]):
            c = edge_coords(u, v)
            pts.extend(c if not pts else c[1:])
        line = LineString([project(*p) for p in pts]).simplify(0.8)
        return [[round(x, 1), round(y, 1)] for x, y in line.coords]

    def route(tour):
        return [{"a": a, "b": b, "w": W[a][b], "pts": leg(a, b)} for a, b in zip(tour[:-1], tour[1:])]

    roads, seen = [], set()
    for u, v, d in G.edges(data=True):
        hw = d.get("highway")
        hw = hw[0] if isinstance(hw, list) else hw
        if hw not in MAJOR_ROADS or (v, u) in seen:
            continue
        seen.add((u, v))
        coords = d["geometry"].coords if "geometry" in d else edge_coords(u, v)
        pts = [project(*p) for p in coords]
        if all(not (20 <= x <= 660 and 10 <= y <= 10 + height) for x, y in pts):
            continue
        line = LineString(pts).simplify(1.2)
        roads.append("M" + " L".join(f"{x:.0f},{y:.0f}" for x, y in line.coords))

    return {
        "H": round(height + 20),
        "sites": [[round(c, 1) for c in project(s[3], s[2])] for s in SITES],
        "greedy": {"total": g_total, "legs": route(greedy)},
        "opt": {"total": o_total, "legs": route(opt)},
        "roads": " ".join(roads),
    }


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Greedy vs Optimal Route Animation</title>
<style>
:root{--text-primary:#1f1e1d;--text-secondary:#5f5e5a;--surface-1:#f1efe8;--border-strong:rgba(0,0,0,.18);--border-stronger:rgba(0,0,0,.45);--bg:#ffffff;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--text-primary:#ecebe6;--text-secondary:#b4b2a9;--surface-1:#2a2a28;--border-strong:rgba(255,255,255,.22);--border-stronger:rgba(255,255,255,.5);--bg:#1a1a19;color-scheme:dark}}
body{margin:0;background:var(--bg);color:var(--text-primary);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;font-weight:600;margin:0 0 4px}
p.sub{color:var(--text-secondary);font-size:14px;margin:0 0 16px;line-height:1.5}
button{font:inherit;font-size:14px;padding:6px 12px;border-radius:8px;border:1px solid var(--border-strong);background:transparent;color:inherit;cursor:pointer}
button:hover{background:var(--surface-1)}
button.on{background:var(--surface-1);border-color:var(--border-stronger)}
.mc{background:var(--surface-1);border-radius:8px;padding:10px 12px}
.ml{font-size:12px;color:var(--text-secondary);margin:0}
.mv{font-size:20px;font-weight:600;margin:2px 0 0}
.lab{font-size:12px;fill:var(--text-primary);paint-order:stroke;stroke:var(--bg);stroke-width:3px;stroke-linejoin:round}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;vertical-align:-1px}
</style>
</head>
<body>
<main>
<h1>Emergency crew route — Cagayan de Oro</h1>
<p class="sub">Algorithm 2.7 (Greedy) versus the exact optimum (Held–Karp), driven along the real OpenStreetMap road network.</p>
<div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:0 0 12px">
  <button id="bG" class="on" onclick="setTour('greedy')">Greedy (Alg. 2.7)</button>
  <button id="bO" onclick="setTour('opt')">Optimal (Held–Karp)</button>
  <button id="bP" onclick="togglePlay()">Pause</button>
  <button onclick="restart()">Restart</button>
  <span style="font-size:13px;color:var(--text-secondary);margin-left:4px">Speed</span>
  <input type="range" id="spd" min="1" max="5" step="1" value="2" style="flex:1;min-width:90px">
  <span id="spdL" style="font-size:13px;min-width:24px">2×</span>
</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin:0 0 12px">
  <div class="mc"><p class="ml">Step</p><p class="mv" id="mStep">0 / 10</p></div>
  <div class="mc" style="grid-column:span 2"><p class="ml">Current leg</p><p class="mv" id="mLeg" style="font-size:16px;line-height:1.5">Ready at City Hall</p></div>
  <div class="mc"><p class="ml">Elapsed time</p><p class="mv" id="mTot">0.0 min</p></div>
</div>
<svg width="100%" id="map" role="img" aria-label="Animated route map">
  <path id="roads" fill="none" stroke="var(--border-strong)" stroke-width="0.8" stroke-linecap="round"/>
  <polyline id="ghost" fill="none" stroke-width="2" stroke-dasharray="4 5" stroke-linecap="round" stroke-linejoin="round" opacity="0.45"/>
  <polyline id="trail" fill="none" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
  <g id="sites"></g>
  <g id="labels"></g>
  <circle id="car" r="7" stroke="var(--bg)" stroke-width="2.5"/>
</svg>
<div style="display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--text-secondary);margin:8px 0 0">
  <span><span class="dot" style="background:#D85A30"></span> Depot</span>
  <span><span class="dot" style="background:#378ADD"></span> Hospital</span>
  <span><span class="dot" style="background:#BA7517"></span> Evacuation site</span>
  <span><span class="dot" style="background:#D4537E"></span> Response hub</span>
  <span>Marker time is proportional to each leg's weight (travel + clearing).</span>
</div>
<p class="sub" style="margin-top:12px;font-size:12px">Road data © OpenStreetMap contributors (ODbL).</p>
</main>
<script>
const D=__DATA__;
const NAMES=["City Hall","NMMC","J.R. Borja","Capitol Univ.","Maria Reyna","Balulang ES","Macasandig CC","Carmen NHS","West City CS","Red Cross"];
const CAT=["#D85A30","#378ADD","#378ADD","#378ADD","#378ADD","#BA7517","#BA7517","#BA7517","#BA7517","#D4537E"];
const LAB=[[-12,4,"end"],[10,-6,"start"],[0,-12,"middle"],[0,24,"middle"],[0,24,"middle"],[12,4,"start"],[12,4,"start"],[-12,4,"end"],[-12,4,"end"],[12,12,"start"]];
const COL={greedy:"#7F77DD",opt:"#1D9E75"};
const NS="http://www.w3.org/2000/svg";
const MS_PER_MIN=110;
document.getElementById('map').setAttribute('viewBox','0 0 680 '+D.H);
document.getElementById('roads').setAttribute('d',D.roads);
const sg=document.getElementById('sites'),lg=document.getElementById('labels'),dots=[];
D.sites.forEach(([x,y],i)=>{
  const c=document.createElementNS(NS,'circle');c.setAttribute('cx',x);c.setAttribute('cy',y);c.setAttribute('r',i===0?9:7);
  c.setAttribute('fill',CAT[i]);c.setAttribute('stroke','var(--bg)');c.setAttribute('stroke-width','2');sg.appendChild(c);dots.push(c);
  const t=document.createElementNS(NS,'text');t.setAttribute('class','lab');t.setAttribute('x',x+LAB[i][0]);t.setAttribute('y',y+LAB[i][1]);
  t.setAttribute('text-anchor',LAB[i][2]);t.textContent=i+' '+NAMES[i];lg.appendChild(t);
});
let tour='greedy',legs,elapsed=0,playing=true,last=null;
function plen(p){let s=0;for(let i=1;i<p.length;i++)s+=Math.hypot(p[i][0]-p[i-1][0],p[i][1]-p[i-1][1]);return s}
function pointAt(p,f){const L=plen(p)*f;let s=0;for(let i=1;i<p.length;i++){const d=Math.hypot(p[i][0]-p[i-1][0],p[i][1]-p[i-1][1]);
  if(s+d>=L){const r=d?(L-s)/d:0;return{pt:[p[i-1][0]+r*(p[i][0]-p[i-1][0]),p[i-1][1]+r*(p[i][1]-p[i-1][1])],idx:i}}s+=d}
  return{pt:p[p.length-1],idx:p.length}}
function setTour(t){tour=t;document.getElementById('bG').classList.toggle('on',t==='greedy');document.getElementById('bO').classList.toggle('on',t==='opt');
  legs=D[t].legs;const col=COL[t];['ghost','trail'].forEach(id=>document.getElementById(id).setAttribute('stroke',col));
  document.getElementById('car').setAttribute('fill',col);
  document.getElementById('ghost').setAttribute('points',legs.flatMap(l=>l.pts).map(p=>p.join(',')).join(' '));restart()}
function restart(){elapsed=0;last=null;draw()}
function draw(){
  let acc=0,k=0,minutes=0,trail=[];const done=new Set([0]);
  for(k=0;k<legs.length;k++){const w=legs[k].w;if(elapsed<acc+w)break;acc+=w;trail.push(...legs[k].pts);done.add(legs[k].b)}
  let pos,label;
  if(k>=legs.length){pos=legs[legs.length-1].pts.slice(-1)[0];label='Back at City Hall — tour complete';minutes=D[tour].total}
  else{const l=legs[k],f=(elapsed-acc)/l.w,r=pointAt(l.pts,f);trail.push(...l.pts.slice(0,r.idx),r.pt);pos=r.pt;minutes=acc+f*l.w;
    label=NAMES[l.a]+' → '+NAMES[l.b]+' ('+l.w.toFixed(1)+' min)'}
  if(elapsed===0)label='Ready at City Hall';
  document.getElementById('trail').setAttribute('points',trail.map(p=>p.join(',')).join(' '));
  const car=document.getElementById('car');car.setAttribute('cx',pos[0]);car.setAttribute('cy',pos[1]);
  dots.forEach((d,i)=>d.setAttribute('stroke',done.has(i)&&elapsed>0?COL[tour]:'var(--bg)'));
  document.getElementById('mStep').textContent=Math.min(k+(elapsed>0&&k<legs.length?1:0),legs.length)+' / '+legs.length;
  document.getElementById('mLeg').textContent=label;
  document.getElementById('mTot').textContent=minutes.toFixed(1)+' min';
}
function frame(ts){if(playing){if(last!==null){const sp=+document.getElementById('spd').value;elapsed+=(ts-last)*sp/MS_PER_MIN/2;
  if(elapsed>D[tour].total+6)elapsed=0}last=ts;draw()}else last=null;requestAnimationFrame(frame)}
function togglePlay(){playing=!playing;document.getElementById('bP').textContent=playing?'Pause':'Play'}
document.getElementById('spd').oninput=e=>document.getElementById('spdL').textContent=e.target.value+'×';
if(matchMedia('(prefers-reduced-motion: reduce)').matches)togglePlay();
setTour('greedy');requestAnimationFrame(frame);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    data = build_data()
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":"))))
    print("Saved:", OUT_FILE)
