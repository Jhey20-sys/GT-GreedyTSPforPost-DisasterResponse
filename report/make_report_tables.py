import csv
import os
import sys

PROJECT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJECT, "report", "tables.tex")
sys.path.insert(0, PROJECT)
from tsp_greedy_cdo import (N, SITES, clearing_time, greedy_tsp, held_karp,  # noqa: E402
                            load_travel_time, load_weights)

T = load_travel_time()
CL = clearing_time()
W = load_weights()
with open(os.path.join(PROJECT, "data", "distance_osm_km.csv"), encoding="utf-8") as f:
    KM = [[float(x) for x in r[1:]] for r in list(csv.reader(f))[1:]]
with open(os.path.join(PROJECT, "data", "nodes.csv"), encoding="utf-8") as f:
    NODES = list(csv.DictReader(f))

SHORT = ["City Hall", "NMMC", "J.R. Borja", "Capitol Univ.", "Maria Reyna", "Balulang ES",
         "Macasandig CC", "Carmen NHS", "West City CS", "Red Cross"]
CAT = {"depot": "Depot", "hospital": "Hospital", "evac": "Evacuation", "emergency": "Response hub"}
FULL = ["Cagayan de Oro City Hall", "Northern Mindanao Medical Center", "J. R. Borja Memorial City Hospital",
        "Capitol University Hospital", "Maria Reyna--Xavier University Hospital", "Balulang Elementary School",
        "Macasandig Multipurpose Covered Court", "Carmen National High School", "West City Central School",
        "Philippine Red Cross -- CDO Chapter"]

def fmt(x, d=1):
    return f"{x:.{d}f}"

def matrix(M, d, caption, label, bold_diag=True):
    head = " & ".join(f"\\textbf{{{j}}}" for j in range(N))
    rows = []
    for i in range(N):
        cells = ["--" if i == j else fmt(M[i][j], d) for j in range(N)]
        rows.append(f"\\textbf{{{i}}} & " + " & ".join(cells) + r" \\")
    return (f"\\begin{{table}}[H]\\centering\\small\n\\caption{{{caption}}}\\label{{{label}}}\n"
            f"\\begin{{tabular}}{{c|{'r' * N}}}\n\\toprule\nfrom $\\backslash$ to & {head} \\\\\n\\midrule\n"
            + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")

out = []
out.append("% Generated from the project dataset by make_report_tables.py -- do not edit by hand.\n")

# Sites table
rows = []
for i, r in enumerate(NODES):
    rows.append(f"{i} & {FULL[i]} & {CAT[r['category']]} & {float(r['lat']):.5f} & {float(r['lon']):.5f} & "
                f"{r['assumed_damage_min']} & {r['snap_distance_m']} \\\\")
out.append("\\newcommand{\\SitesTable}{\n\\begin{table}[H]\\centering\\small\n"
           "\\caption{The ten vertices: real coordinates (OpenStreetMap), assumed damage class, and distance to the nearest road intersection.}\\label{tab:sites}\n"
           "\\setlength{\\tabcolsep}{4pt}\n\\begin{tabular}{clllrrr}\n\\toprule\n\\# & Site & Category & Latitude & Longitude & $d_i$ (min) & Snap (m) \\\\\n\\midrule\n"
           + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}}\n")

out.append("\\newcommand{\\TravelMatrix}{" + matrix(T, 1, "Actual travel-time matrix $t(i,j)$ in minutes: fastest path on the OpenStreetMap drive network (row = from, column = to).", "tab:travel") + "}\n")
out.append("\\newcommand{\\DistanceMatrix}{" + matrix(KM, 2, "Road distance in kilometres along the same fastest paths.", "tab:distance") + "}\n")
out.append("\\newcommand{\\ClearingMatrix}{" + matrix(CL, 0, "Assumed clearing-time matrix $c(i,j)=\\max(d_i,d_j)$ in minutes.", "tab:clearing") + "}\n")
out.append("\\newcommand{\\WeightMatrix}{" + matrix(W, 1, "Combined weight matrix $w(i,j)=t(i,j)+c(i,j)$ in minutes, used by Algorithm 2.7.", "tab:weights") + "}\n")

# Greedy step table
cur, vis, tot, rows = 0, {0}, 0.0, []
step = 1
while len(vis) < N:
    cand = sorted(((W[cur][j], j) for j in range(N) if j not in vis))
    w, nxt = cand[0]
    tot = round(tot + w, 1)
    cands = ", ".join(f"{j}: {fmt(v)}" for v, j in cand[:3])
    rows.append(f"{step} & {cur} $\\to$ {nxt} & {cands} & {fmt(T[cur][nxt])} & {CL[cur][nxt]} & \\textbf{{{fmt(w)}}} & {fmt(tot)} \\\\")
    vis.add(nxt); cur = nxt; step += 1
w = W[cur][0]; tot = round(tot + w, 1)
rows.append(f"{step} & {cur} $\\to$ 0 & return to depot & {fmt(T[cur][0])} & {CL[cur][0]} & \\textbf{{{fmt(w)}}} & {fmt(tot)} \\\\")
out.append("\\newcommand{\\StepTable}{\n\\begin{table}[H]\\centering\\small\n"
           "\\caption{Trace of Algorithm 2.7 from the depot. At each step the three nearest unvisited sites are listed as \\emph{site: $w$}; the smallest is chosen.}\\label{tab:steps}\n"
           "\\begin{tabular}{clp{5.2cm}rrrr}\n\\toprule\nStep & Leg & Nearest unvisited candidates & $t$ & $c$ & $w$ & Running total \\\\\n\\midrule\n"
           + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}}\n")

# Sensitivity table
rows = []
for s in range(N):
    tour, cost = greedy_tsp(W, start=s)
    rows.append(f"{s} & {SHORT[s]} & {' $\\to$ '.join(map(str, tour))} & {fmt(cost)} \\\\")
out.append("\\newcommand{\\SensitivityTable}{\n\\begin{table}[H]\\centering\\small\n"
           "\\caption{Greedy result when started from each site. Every closed tour is a cycle, so its total is also a valid depot round trip.}\\label{tab:sensitivity}\n"
           "\\begin{tabular}{cllr}\n\\toprule\nStart & Site & Greedy tour & Total (min) \\\\\n\\midrule\n"
           + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}}\n")

# Optimal tour legs
opt, opt_total = held_karp(W, 0)
rows, run = [], 0.0
for a, b in zip(opt[:-1], opt[1:]):
    run = round(run + W[a][b], 1)
    rows.append(f"{a} $\\to$ {b} & {SHORT[a]} $\\to$ {SHORT[b]} & {fmt(T[a][b])} & {CL[a][b]} & {fmt(W[a][b])} & {fmt(run)} \\\\")
out.append("\\newcommand{\\OptimalTable}{\n\\begin{table}[H]\\centering\\small\n"
           "\\caption{Exact optimal tour (Held--Karp dynamic programming), leg by leg.}\\label{tab:optimal}\n"
           "\\begin{tabular}{cllrrr}\n\\toprule\nLeg & Sites & $t$ & $c$ & $w$ & Running total \\\\\n\\midrule\n"
           + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}}\n")

greedy, g_total = greedy_tsp(W, 0)
g_travel = round(sum(T[a][b] for a, b in zip(greedy[:-1], greedy[1:])), 1)
g_clear = sum(CL[a][b] for a, b in zip(greedy[:-1], greedy[1:]))
g_km = round(sum(KM[a][b] for a, b in zip(greedy[:-1], greedy[1:])), 2)
o_km = round(sum(KM[a][b] for a, b in zip(opt[:-1], opt[1:])), 2)
o_travel = round(sum(T[a][b] for a, b in zip(opt[:-1], opt[1:])), 1)
o_clear = sum(CL[a][b] for a, b in zip(opt[:-1], opt[1:]))
for name, val in [("GreedyTotal", fmt(g_total)), ("GreedyTravel", fmt(g_travel)), ("GreedyClear", str(g_clear)),
                  ("GreedyKm", fmt(g_km, 2)), ("OptTotal", fmt(opt_total)), ("OptTravel", fmt(o_travel)),
                  ("OptClear", str(o_clear)), ("OptKm", fmt(o_km, 2)),
                  ("GapPct", fmt(100 * (g_total - opt_total) / opt_total)), ("GapMin", fmt(g_total - opt_total))]:
    out.append(f"\\newcommand{{\\{name}}}{{{val}}}\n")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("".join(out))
print("wrote", OUT)
print("greedy", g_total, "travel", g_travel, "clear", g_clear, "km", g_km)
print("opt", opt_total, "travel", o_travel, "clear", o_clear, "km", o_km)
