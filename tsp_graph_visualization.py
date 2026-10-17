"""
Visualizations for the Algorithm 2.7 (Greedy) TSP application, built on the
OpenStreetMap dataset produced by build_osm_dataset.py.

Figures written to ./figures:
    1_weighted_graph.png   complete directed weighted graph (vertices at real coordinates)
    2_greedy_tour.png      greedy tour highlighted on the graph, in visit order
    3_weight_matrices.png  travel (actual) + clearing (assumed) = combined weight matrix W
    4_greedy_route_map.png greedy tour drawn on the real Cagayan de Oro road network
    5_greedy_vs_optimal_map.png  greedy tour vs exact optimum (Held-Karp) on the road map
"""

import csv
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
from matplotlib.lines import Line2D

from build_osm_dataset import GRAPH_FILE
from tsp_greedy_cdo import (DATA_DIR, HERE, N, SITES, clearing_time, greedy_tsp,
                            held_karp, load_travel_time, load_weights)

OUT_DIR = os.path.join(HERE, "figures")
os.makedirs(OUT_DIR, exist_ok=True)

SHORT = [
    "City Hall\n(Depot)",
    "NMMC",
    "J.R. Borja\nHospital",
    "Capitol Univ.\nHospital",
    "Maria Reyna\nHospital",
    "Balulang\nElem. School",
    "Macasandig\nCovered Court",
    "Carmen\nNat'l High School",
    "West City\nCentral School",
    "Red Cross\nCDO",
]
COLORS = {"depot": "#d62728", "hospital": "#1f77b4", "evac": "#2ca02c", "emergency": "#ff7f0e"}
LEGEND_LABELS = {"depot": "Depot (City Hall)", "hospital": "Hospital",
                 "evac": "Evacuation center", "emergency": "Emergency response"}
CATEGORY = [s[1] for s in SITES]

# Label offsets in points (dx, dy) so labels of nearby sites do not collide.
LABEL_OFFSET = {i: (0, -24) for i in range(N)}
LABEL_OFFSET.update({1: (0, 26), 9: (34, -20)})
LABEL_VA = {1: "bottom"}

# Graph-figure positions: real coordinates in km from the depot. NMMC and Red Cross
# are only ~80 m apart, so they are nudged apart slightly to keep both visible.
LAT0, LON0 = SITES[0][2], SITES[0][3]
POS = {i: ((s[3] - LON0) * 111.32 * math.cos(math.radians(LAT0)), (s[2] - LAT0) * 110.57)
       for i, s in enumerate(SITES)}
POS[1] = (POS[1][0] + 0.10, POS[1][1] + 0.22)
POS[9] = (POS[9][0] - 0.10, POS[9][1] - 0.22)


def node_legend():
    return [Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS[c], markeredgecolor="black",
                   markersize=11, label=LEGEND_LABELS[c]) for c in COLORS]


def label_sites(ax, xy):
    for i in range(N):
        ax.annotate(SHORT[i], xy[i], xytext=LABEL_OFFSET[i], textcoords="offset points",
                    ha="center", va=LABEL_VA.get(i, "top"), fontsize=8.5, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))


def draw_graph_nodes(ax, G):
    nx.draw_networkx_nodes(G, POS, ax=ax, node_size=900, edgecolors="black",
                           node_color=[COLORS[CATEGORY[i]] for i in G.nodes])
    nx.draw_networkx_labels(G, POS, ax=ax, labels={i: str(i) for i in G.nodes},
                            font_color="white", font_weight="bold", font_size=11)
    label_sites(ax, POS)


def finish_graph_axes(ax, fig, handles, path):
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=9)
    ax.set_aspect("equal")
    ax.margins(0.08)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def fig_weighted_graph(W):
    G = nx.Graph()
    G.add_nodes_from(range(N))
    labels = {}
    for i in range(N):
        for j in range(i + 1, N):
            G.add_edge(i, j)
            labels[(i, j)] = f"{W[i][j]:g}" if W[i][j] == W[j][i] else f"{W[i][j]:g}/{W[j][i]:g}"
    fig, ax = plt.subplots(figsize=(14, 11))
    nx.draw_networkx_edges(G, POS, ax=ax, edge_color="#9a9a9a", width=0.8, alpha=0.6)
    nx.draw_networkx_edge_labels(G, POS, ax=ax, edge_labels=labels, font_size=6.5,
                                 bbox=dict(boxstyle="round,pad=0.1", fc="#fffbe6", ec="none", alpha=0.9))
    draw_graph_nodes(ax, G)
    ax.set_title("Weighted Graph Model - Post-Disaster Emergency Routing, Cagayan de Oro\n"
                 "10 vertices at real coordinates; w(i,j) = OSM travel time + assumed clearing time (min)\n"
                 "One-way streets make it directed: label 'a/b' = w(i->j)/w(j->i) for i<j", fontsize=11)
    return finish_graph_axes(ax, fig, node_legend(), os.path.join(OUT_DIR, "1_weighted_graph.png"))


def fig_greedy_tour(W, tour, total):
    G = nx.complete_graph(N)
    fig, ax = plt.subplots(figsize=(14, 11))
    nx.draw_networkx_edges(G, POS, ax=ax, edge_color="#cccccc", width=0.6, alpha=0.5)
    tour_edges = list(zip(tour[:-1], tour[1:]))
    D = nx.DiGraph(tour_edges)
    nx.draw_networkx_edges(D, POS, ax=ax, edgelist=tour_edges, edge_color="#7b2cbf", width=2.8,
                           arrows=True, arrowstyle="-|>", arrowsize=22, node_size=900,
                           connectionstyle="arc3,rad=0.08")
    for k, (u, v) in enumerate(tour_edges, start=1):
        (x1, y1), (x2, y2) = POS[u], POS[v]
        ax.text((x1 + x2) / 2, (y1 + y2) / 2, f"#{k}: {W[u][v]:g}", fontsize=8.5, ha="center",
                va="center", color="#4a148c", fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#7b2cbf", lw=0.8))
    draw_graph_nodes(ax, G)
    ax.set_title("Algorithm 2.7 Greedy (Nearest-Neighbor) Tour from the Depot\n"
                 f"Route: {' -> '.join(map(str, tour))}     Total = {total:.1f} minutes", fontsize=12)
    handles = node_legend() + [Line2D([0], [0], color="#7b2cbf", lw=2.8, label="Greedy tour (#k = step, min)")]
    return finish_graph_axes(ax, fig, handles, os.path.join(OUT_DIR, "2_greedy_tour.png"))


def fig_weight_matrices(W):
    panels = [
        (load_travel_time(), "Travel time - ACTUAL\n(OpenStreetMap shortest paths)", "Blues"),
        (clearing_time(), "Clearing time - ASSUMED\n(damage class scenario)", "Oranges"),
        (W, "Combined weight W = travel + clearing\n(used by Algorithm 2.7)", "YlOrRd"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(24, 8.5))
    for ax, (M, title, cmap) in zip(axes, panels):
        vmax = max(max(r) for r in M) or 1
        im = ax.imshow(M, cmap=cmap, vmin=0, vmax=vmax)
        ax.set_xticks(range(N), labels=[str(i) for i in range(N)])
        ax.set_yticks(range(N), labels=[f"{i} {SHORT[i].replace(chr(10), ' ')}" for i in range(N)], fontsize=8.5)
        ax.set_xlabel("to"), ax.set_ylabel("from")
        for i in range(N):
            for j in range(N):
                ax.text(j, i, f"{M[i][j]:g}", ha="center", va="center", fontsize=8.5,
                        color="white" if M[i][j] > vmax * 0.6 else "black")
        ax.set_title(title, fontsize=12)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="minutes")
    fig.suptitle("Weight matrices (minutes), Cagayan de Oro emergency sites", fontsize=14)
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "3_weight_matrices.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ----------------------------------------------------------------------------- road maps
def load_osm_nodes():
    with open(os.path.join(DATA_DIR, "nodes.csv"), newline="", encoding="utf-8") as f:
        return [int(r["osm_node"]) for r in csv.DictReader(f)]


def draw_road_map(ax, R, osm_nodes, tour, title, cmap_name):
    ox.plot_graph(R, ax=ax, node_size=0, edge_color="#c8c8c8", edge_linewidth=0.6,
                  bgcolor="white", show=False, close=False)
    cmap = plt.get_cmap(cmap_name)
    legs = list(zip(tour[:-1], tour[1:]))
    for k, (u, v) in enumerate(legs, start=1):
        path = nx.shortest_path(R, osm_nodes[u], osm_nodes[v], weight="travel_time")
        xs = [R.nodes[n]["x"] for n in path]
        ys = [R.nodes[n]["y"] for n in path]
        color = cmap(0.5 + 0.5 * (k - 1) / (len(legs) - 1))
        ax.plot(xs, ys, color=color, lw=3.2, alpha=0.9, solid_capstyle="round", zorder=3)
        mid = len(path) // 2
        ax.text(xs[mid], ys[mid], f"#{k}", fontsize=7.5, fontweight="bold", color=color, ha="center",
                va="center", zorder=7, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, lw=1.2))
    lons = [s[3] for s in SITES]
    lats = [s[2] for s in SITES]
    for i in range(N):  # dashed connector from the building to its snapped road node
        ax.plot([lons[i], R.nodes[osm_nodes[i]]["x"]], [lats[i], R.nodes[osm_nodes[i]]["y"]],
                ls=":", color="black", lw=1, zorder=4)
    ax.scatter(lons, lats, s=170, c=[COLORS[c] for c in CATEGORY], edgecolors="black", zorder=8)
    for i in range(N):
        ax.text(lons[i], lats[i], str(i), fontsize=7.5, fontweight="bold", color="white",
                ha="center", va="center", zorder=9)
    label_sites(ax, list(zip(lons, lats)))
    pad = 0.006
    ax.set_xlim(min(lons) - pad, max(lons) + pad)
    ax.set_ylim(min(lats) - pad, max(lats) + pad)
    ax.set_title(title, fontsize=11.5)


def fig_route_maps(W, greedy, greedy_total, opt, opt_total):
    R = ox.load_graphml(GRAPH_FILE)
    osm_nodes = load_osm_nodes()
    credit = ("Road data (c) OpenStreetMap contributors (ODbL).   Circles = site index;  "
              "#k boxes = step order (later legs darker, drawn over earlier ones on shared roads).")
    handles = node_legend()

    fig, ax = plt.subplots(figsize=(13, 12))
    draw_road_map(ax, R, osm_nodes, greedy,
                  "Algorithm 2.7 Greedy tour on the real Cagayan de Oro road network\n"
                  f"Route: {' -> '.join(map(str, greedy))}     Total = {greedy_total:.1f} min", "Purples")
    ax.legend(handles=handles, loc="lower right", fontsize=9)
    fig.text(0.5, 0.01, credit, ha="center", fontsize=8.5, color="#555555")
    p1 = os.path.join(OUT_DIR, "4_greedy_route_map.png")
    fig.savefig(p1, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    gap = 100 * (greedy_total - opt_total) / opt_total
    fig, axes = plt.subplots(1, 2, figsize=(22, 10))
    draw_road_map(axes[0], R, osm_nodes, greedy,
                  f"Greedy (Algorithm 2.7): {greedy_total:.1f} min\n{' -> '.join(map(str, greedy))}", "Purples")
    draw_road_map(axes[1], R, osm_nodes, opt,
                  f"Exact optimum (Held-Karp DP): {opt_total:.1f} min\n{' -> '.join(map(str, opt))}", "Greens")
    axes[1].legend(handles=handles, loc="lower right", fontsize=9)
    fig.suptitle(f"Greedy vs optimal tour - greedy is {gap:.1f}% longer", fontsize=15)
    fig.text(0.5, 0.01, credit, ha="center", fontsize=8.5, color="#555555")
    p2 = os.path.join(OUT_DIR, "5_greedy_vs_optimal_map.png")
    fig.savefig(p2, dpi=140, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return p1, p2


if __name__ == "__main__":
    W = load_weights()
    tour, total = greedy_tsp(W, start=0)
    opt, opt_total = held_karp(W, start=0)
    paths = [fig_weighted_graph(W), fig_greedy_tour(W, tour, total), fig_weight_matrices(W),
             *fig_route_maps(W, tour, total, opt, opt_total)]
    for p in paths:
        print("Saved:", p)
