"""
Performance Innovative Task - Traveling Salesperson Problem (TSP)
Algorithm 2.7: Greedy (Nearest-Neighbor) Approach
Reference: Luna-Garcia, Candano & Caga-anan (2024),
"Performance Analysis of Classical Algorithms for the Traveling Salesman Problem",
The Mindanawan Journal of Mathematics, Vol. 6 (2024), No. 2, pp. 79-111.

Real-life application:
    Post-disaster emergency routing in Cagayan de Oro City.
    An emergency response crew starts at the depot (City Hall), must visit
    every critical emergency site exactly once (hospitals, evacuation
    centers, and an emergency response center), and return to the depot
    while minimizing total round-trip time.

Edge weight definition (directed, because the real road network has one-way streets):
    w(i, j) = travel_time(i, j)  +  clearing_time(i, j)
              (minutes, ACTUAL:      (minutes, ASSUMED:
               shortest path on       disaster scenario
               OpenStreetMap roads)   damage classes)

Run order:
    1. python build_osm_dataset.py      (downloads OSM roads, writes data/*.csv)
    2. python tsp_greedy_cdo.py         (runs Algorithm 2.7 on that dataset)
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
TRAVEL_TIME_CSV = os.path.join(DATA_DIR, "travel_time_osm_min.csv")

# -----------------------------------------------------------------------------
# 1. NODES (depot = index 0)
#    Coordinates: ACTUAL, from OpenStreetMap (Nominatim / Overpass lookups).
#    Damage class: ASSUMED scenario - Cagayan River flooding similar to
#    Tropical Storm Sendong (2011); riverside sites have the worst access roads.
#        0 = clear road, 5 = minor debris, 20 = major obstruction (minutes)
# -----------------------------------------------------------------------------
SITES = [
    # (name,                                   category,    lat,      lon,       damage)
    ("Cagayan de Oro City Hall (DEPOT)",       "depot",     8.47695, 124.64117,  0),
    ("Northern Mindanao Medical Center",       "hospital",  8.48539, 124.64964,  0),
    ("J. R. Borja Memorial City Hospital",     "hospital",  8.48171, 124.62809,  5),
    ("Capitol University Hospital",            "hospital",  8.47905, 124.67268,  0),
    ("Maria Reyna-Xavier Univ. Hospital",      "hospital",  8.47631, 124.65520,  0),
    ("Balulang Elementary School (evac)",      "evac",      8.44344, 124.63451, 20),
    ("Macasandig Multipurpose Covered Court",  "evac",      8.46535, 124.64478, 20),
    ("Carmen National High School (evac)",     "evac",      8.46950, 124.63234,  5),
    ("West City Central School (evac)",        "evac",      8.47350, 124.63686,  5),
    ("Philippine Red Cross - CDO Chapter",     "emergency", 8.48477, 124.64926,  0),
]
NODES = [s[0] for s in SITES]
N = len(SITES)


def load_travel_time():
    """ACTUAL DATA: OSM shortest-path driving times (minutes), built by build_osm_dataset.py."""
    if not os.path.exists(TRAVEL_TIME_CSV):
        raise SystemExit(f"Missing {TRAVEL_TIME_CSV}\nRun:  python build_osm_dataset.py")
    with open(TRAVEL_TIME_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))[1:]
    return [[float(x) for x in row[1:]] for row in rows]


def clearing_time():
    """ASSUMED DATA: clearing an edge costs the worse damage class of its two endpoints."""
    damage = [s[4] for s in SITES]
    return [[0 if i == j else max(damage[i], damage[j]) for j in range(N)] for i in range(N)]


def load_weights():
    """Combined weight matrix W[i][j] = travel + clearing (minutes)."""
    travel = load_travel_time()
    clear = clearing_time()
    return [[round(travel[i][j] + clear[i][j], 1) for j in range(N)] for i in range(N)]


# -----------------------------------------------------------------------------
# 2. ALGORITHM 2.7  --  Greedy (Nearest-Neighbor) Approach for TSP
#    Pseudocode (from the paper):
#       Input:  cities + pairwise distances
#       1. Begin at an arbitrary city
#       2. while not all cities visited:
#            find nearest unvisited city, travel to it, mark visited
#       3. Return to the starting city
#       Output: complete tour + total distance
#    Time complexity: O(n^2)
# -----------------------------------------------------------------------------
def greedy_tsp(weights, start=0):
    n = len(weights)
    visited = [False] * n
    tour = [start]
    visited[start] = True
    total = 0
    current = start

    while len(tour) < n:
        # Find the nearest unvisited city (locally optimal choice)
        next_city = -1
        best = float("inf")
        for j in range(n):
            if not visited[j] and weights[current][j] < best:
                best = weights[current][j]
                next_city = j
        tour.append(next_city)
        visited[next_city] = True
        total += best
        current = next_city

    # Close the loop: return to the starting city
    total += weights[current][start]
    tour.append(start)
    return tour, round(total, 1)


# -----------------------------------------------------------------------------
# 3. OPTIMALITY CHECK (not part of Algorithm 2.7)
#    Exact optimum via Held-Karp dynamic programming (paper Algorithm 2.2),
#    O(n^2 2^n) - feasible here because n = 10. Used only to measure greedy's gap.
# -----------------------------------------------------------------------------
def held_karp(weights, start=0):
    n = len(weights)
    others = [c for c in range(n) if c != start]
    dp = {(1 << k, k): (weights[start][others[k]], None) for k in range(len(others))}
    for mask in range(1, 1 << len(others)):
        for k in range(len(others)):
            if not mask & (1 << k) or (mask, k) not in dp:
                continue
            cost = dp[(mask, k)][0]
            for nxt in range(len(others)):
                if mask & (1 << nxt):
                    continue
                key = (mask | (1 << nxt), nxt)
                cand = cost + weights[others[k]][others[nxt]]
                if key not in dp or cand < dp[key][0]:
                    dp[key] = (cand, k)
    full = (1 << len(others)) - 1
    last = min(range(len(others)), key=lambda k: dp[(full, k)][0] + weights[others[k]][start])
    total = dp[(full, last)][0] + weights[others[last]][start]
    path, mask, k = [], full, last
    while k is not None:
        path.append(others[k])
        mask, k = mask ^ (1 << k), dp[(mask, k)][1]
    return [start] + path[::-1] + [start], round(total, 1)


# -----------------------------------------------------------------------------
# 4. OUTPUT
# -----------------------------------------------------------------------------
def recalculate(tour, weights):
    """Independent check: sum edge weights along the tour."""
    return round(sum(weights[tour[k]][tour[k + 1]] for k in range(len(tour) - 1)), 1)


def print_report(tour, total, weights):
    travel = load_travel_time()
    clear = clearing_time()
    print("=" * 92)
    print("ALGORITHM 2.7 - GREEDY (NEAREST-NEIGHBOR) APPROACH FOR TSP")
    print("Application: Post-disaster emergency routing, Cagayan de Oro City (OpenStreetMap roads)")
    print("=" * 92)

    print("\nTour sequence:")
    for step, idx in enumerate(tour):
        marker = "  (return)" if step == len(tour) - 1 else ""
        print(f"  Step {step:>2}: [{idx}] {NODES[idx]}{marker}")

    print("\nEdge-by-edge breakdown (minutes):")
    print(f"  {'From':<38} {'To':<38} {'travel':>6} {'clear':>5} {'w':>6}")
    for k in range(len(tour) - 1):
        i, j = tour[k], tour[k + 1]
        print(f"  {NODES[i]:<38} {NODES[j]:<38} {travel[i][j]:>6.1f} {clear[i][j]:>5} {weights[i][j]:>6.1f}")

    print("\nVerification:")
    print(f"  Every node visited exactly once : {sorted(tour[:-1]) == list(range(N))}")
    print(f"  Returns to starting node        : {tour[0] == tour[-1]}")
    print(f"  Reported total time             : {total:.1f} minutes")
    print(f"  Recomputed total time           : {recalculate(tour, weights):.1f} minutes")

    print("\nConclusion:")
    print("  Greedy produces an APPROXIMATE (heuristic) solution.")
    print("  It does NOT guarantee the global optimum - see paper Theorem 2.7.")
    print("=" * 92)


if __name__ == "__main__":
    W = load_weights()
    tour, total = greedy_tsp(W, start=0)
    print_report(tour, total, W)

    # Greedy from every node shows the sensitivity-to-starting-city limitation.
    # Each closed tour is a cycle, so its cost is valid for the depot as well.
    print("\nSensitivity to starting city (greedy from each node):")
    for s in range(N):
        _, cost = greedy_tsp(W, start=s)
        print(f"  start = {s} ({NODES[s][:36]:<36}) -> total = {cost:.1f} min")

    opt_tour, opt_total = held_karp(W, start=0)
    gap = 100 * (total - opt_total) / opt_total
    print("\nOptimality check (exact Held-Karp DP, paper Algorithm 2.2):")
    print(f"  Optimal tour : {' -> '.join(map(str, opt_tour))}")
    print(f"  Optimal total: {opt_total:.1f} min   (recomputed {recalculate(opt_tour, W):.1f})")
    print(f"  Greedy total : {total:.1f} min   -> greedy is {gap:.1f}% above optimal")
