"""
Builds the ACTUAL travel-time dataset for the TSP from the OpenStreetMap road network.

Steps:
    1. Download the drivable road network around the sites (OSMnx -> Overpass API).
    2. Keep the largest strongly connected component, so every site can reach every other.
    3. Assign a speed to each road segment and compute its travel time
       (length / speed). OSM "maxspeed" tags are used where present;
       otherwise the urban speeds in HWY_SPEEDS (an assumption) are used.
    4. Snap each site to its nearest road intersection.
    5. Run Dijkstra's shortest path between every ordered pair of sites.

Outputs (data/):
    nodes.csv                 site coordinates, snapped OSM node, snap distance
    travel_time_osm_min.csv   n x n driving time matrix (minutes)  <- used by the TSP
    distance_osm_km.csv       n x n road distance along those same routes (km)
    cdo_drive.graphml         cached road network (re-used on later runs)

Road data (c) OpenStreetMap contributors, ODbL.
"""

import csv
import math
import os

import networkx as nx
import osmnx as ox

from tsp_greedy_cdo import DATA_DIR, N, SITES, TRAVEL_TIME_CSV

GRAPH_FILE = os.path.join(DATA_DIR, "cdo_drive.graphml")
BBOX_PAD_DEG = 0.02  # ~2.2 km margin so detours around the sites stay inside the map
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api",
    "https://overpass.private.coffee/api",
    "https://overpass.kumi.systems/api",
    "https://maps.mail.ru/osm/tools/overpass/api",
]

# ASSUMED typical urban speeds (km/h) for Cagayan de Oro traffic, by OSM road class.
HWY_SPEEDS = {
    "motorway": 60, "motorway_link": 40,
    "trunk": 40, "trunk_link": 30,
    "primary": 35, "primary_link": 25,
    "secondary": 30, "secondary_link": 25,
    "tertiary": 25, "tertiary_link": 20,
    "unclassified": 20, "residential": 20,
    "living_street": 10, "service": 15,
}
FALLBACK_SPEED = 20


def load_graph():
    if os.path.exists(GRAPH_FILE):
        print(f"Using cached road network: {GRAPH_FILE}")
        return ox.load_graphml(GRAPH_FILE)

    lats = [s[2] for s in SITES]
    lons = [s[3] for s in SITES]
    bbox = (min(lons) - BBOX_PAD_DEG, min(lats) - BBOX_PAD_DEG,
            max(lons) + BBOX_PAD_DEG, max(lats) + BBOX_PAD_DEG)
    G = None
    for url in OVERPASS_MIRRORS:
        ox.settings.overpass_url = url
        ox.settings.overpass_rate_limit = url == OVERPASS_MIRRORS[0]
        print(f"Downloading OSM drive network for bbox {bbox} from {url} ...")
        try:
            G = ox.graph_from_bbox(bbox, network_type="drive")
            break
        except Exception as e:  # public servers are often busy; try the next mirror
            print(f"  failed: {str(e).splitlines()[0]}")
    if G is None:
        raise SystemExit("All Overpass servers failed; try again in a few minutes.")
    G = ox.truncate.largest_component(G, strongly=True)
    G = ox.add_edge_speeds(G, hwy_speeds=HWY_SPEEDS, fallback=FALLBACK_SPEED)
    G = ox.add_edge_travel_times(G)
    os.makedirs(DATA_DIR, exist_ok=True)
    ox.save_graphml(G, GRAPH_FILE)
    return G


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def snap_sites(G):
    coords = [(n, d["y"], d["x"]) for n, d in G.nodes(data=True)]
    snapped = []
    for _, _, lat, lon, _ in SITES:
        node, y, x = min(coords, key=lambda c: haversine_m(lat, lon, c[1], c[2]))
        snapped.append((node, haversine_m(lat, lon, y, x)))
    return snapped


def fastest_edge(G, u, v):
    return min(G[u][v].values(), key=lambda d: d["travel_time"])


def route_length_m(G, path):
    return sum(fastest_edge(G, u, v)["length"] for u, v in zip(path[:-1], path[1:]))


def write_matrix(path, matrix, fmt):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["from\\to"] + list(range(N)))
        for i, row in enumerate(matrix):
            w.writerow([i] + [fmt.format(x) for x in row])


def main():
    G = load_graph()
    print(f"Road network: {G.number_of_nodes()} intersections, {G.number_of_edges()} directed road segments")

    snapped = snap_sites(G)
    osm_nodes = [s[0] for s in snapped]

    minutes = [[0.0] * N for _ in range(N)]
    km = [[0.0] * N for _ in range(N)]
    for i in range(N):
        seconds, paths = nx.single_source_dijkstra(G, osm_nodes[i], weight="travel_time")
        for j in range(N):
            if i != j:
                minutes[i][j] = round(seconds[osm_nodes[j]] / 60, 1)
                km[i][j] = round(route_length_m(G, paths[osm_nodes[j]]) / 1000, 2)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "nodes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "name", "category", "lat", "lon", "assumed_damage_min",
                    "osm_node", "snap_distance_m"])
        for i, (name, cat, lat, lon, dmg) in enumerate(SITES):
            w.writerow([i, name, cat, lat, lon, dmg, osm_nodes[i], round(snapped[i][1])])
    write_matrix(TRAVEL_TIME_CSV, minutes, "{:.1f}")
    write_matrix(os.path.join(DATA_DIR, "distance_osm_km.csv"), km, "{:.2f}")

    print("\nSite -> nearest road intersection:")
    for i, (node, dist) in enumerate(snapped):
        print(f"  [{i}] {SITES[i][0]:<40} OSM node {node:<12} {dist:6.0f} m away")

    diffs = [abs(minutes[i][j] - minutes[j][i]) for i in range(N) for j in range(i + 1, N)]
    print(f"\nOne-way streets: {sum(d > 0 for d in diffs)} of {len(diffs)} site pairs have "
          f"different times each direction (max difference {max(diffs):.1f} min)")
    print(f"Saved dataset to {DATA_DIR}")


if __name__ == "__main__":
    main()
