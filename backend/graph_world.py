import networkx as nx
import math
import os

# ─── Default 8-node graph ─────────────────────────────────────────────────────
nodes = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

edges = [
    ('A', 'B', {'dist': 12, 'cost': 22, 'time':  6, 'type': 'highway'}),
    ('B', 'C', {'dist': 10, 'cost': 18, 'time':  5, 'type': 'highway'}),
    ('C', 'D', {'dist': 14, 'cost':  6, 'time': 22, 'type': 'local'}),
    ('D', 'E', {'dist': 11, 'cost':  5, 'time': 20, 'type': 'local'}),
    ('E', 'F', {'dist': 13, 'cost': 20, 'time':  7, 'type': 'highway'}),
    ('F', 'G', {'dist': 10, 'cost':  4, 'time': 18, 'type': 'local'}),
    ('G', 'H', {'dist': 12, 'cost': 19, 'time':  6, 'type': 'highway'}),
    ('H', 'A', {'dist': 11, 'cost':  5, 'time': 21, 'type': 'local'}),
    ('A', 'E', {'dist': 20, 'cost': 10, 'time': 14, 'type': 'scenic'}),
    ('B', 'F', {'dist': 18, 'cost':  8, 'time': 13, 'type': 'scenic'}),
    ('C', 'G', {'dist': 22, 'cost': 11, 'time': 15, 'type': 'scenic'}),
    ('D', 'H', {'dist': 19, 'cost':  9, 'time': 14, 'type': 'scenic'}),
    ('A', 'D', {'dist': 16, 'cost': 14, 'time': 10, 'type': 'scenic'}),
    ('B', 'E', {'dist': 15, 'cost': 24, 'time':  8, 'type': 'highway'}),
    ('C', 'F', {'dist': 17, 'cost': 12, 'time': 11, 'type': 'scenic'}),
    ('G', 'A', {'dist': 21, 'cost':  7, 'time': 16, 'type': 'scenic'}),
]

G = nx.DiGraph()
G.add_nodes_from(nodes)
for s, t, data in edges:
    G.add_edge(s, t, **data)
    G.add_edge(t, s, **data)

graph_dict = nx.to_dict_of_dicts(G)


# ─── TSPLIB loader ────────────────────────────────────────────────────────────

def _nint(x):
    """TSPLIB integer rounding: nint(x) = int(x + 0.5).
    This matches the TSPLIB95 spec exactly — NOT Python's banker's round()."""
    return int(x + 0.5)


def _euc_2d(c1, c2):
    """EUC_2D: TSPLIB spec — nint(sqrt((x1-x2)^2 + (y1-y2)^2))"""
    return _nint(math.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2))


def _ceil_2d(c1, c2):
    """CEIL_2D: ceiling of euclidean distance."""
    return math.ceil(math.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2))


def _geo_dist(c1, c2):
    """GEO: TSPLIB geographic distance in km."""
    def to_rad(coord):
        deg  = int(coord)
        mins = coord - deg
        return math.pi * (deg + 5.0 * mins / 3.0) / 180.0
    lat1, lon1 = to_rad(c1[0]), to_rad(c1[1])
    lat2, lon2 = to_rad(c2[0]), to_rad(c2[1])
    RRR = 6378.388
    q1  = math.cos(lon1 - lon2)
    q2  = math.cos(lat1 - lat2)
    q3  = math.cos(lat1 + lat2)
    return int(RRR * math.acos(max(-1.0, min(1.0, 0.5 * ((1+q1)*q2 - (1-q1)*q3)))) + 1.0)


def _att_dist(c1, c2):
    """ATT (pseudo-Euclidean) distance."""
    dx  = c1[0] - c2[0]
    dy  = c1[1] - c2[1]
    rij = math.sqrt((dx*dx + dy*dy) / 10.0)
    tij = _nint(rij)
    return tij + 1 if tij < rij else tij


def _dist_fn_for(edge_weight_type):
    return {
        'EUC_2D':  _euc_2d,
        'CEIL_2D': _ceil_2d,
        'GEO':     _geo_dist,
        'ATT':     _att_dist,
    }.get(edge_weight_type.strip(), _euc_2d)


def load_tsplib(filepath: str):
    """
    Parse a TSPLIB .tsp file.
    Supports EUC_2D, CEIL_2D, GEO, ATT edge weight types.

    Returns
    -------
    node_ids     : list[str]   — city IDs in file order
    graph_dict   : dict        — full adjacency dict with dist/cost/time/type
    coords       : dict        — {node_id: (x, y)} for rendering
    known_optimal: list|None   — optimal tour node IDs if .opt.tour exists
    """
    coords           = {}
    edge_weight_type = 'EUC_2D'
    in_coord_section = False
    known_optimal    = None

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if ':' in line:
                key, _, val = line.partition(':')
                key = key.strip().upper()
                val = val.strip()
                if key == 'EDGE_WEIGHT_TYPE':
                    edge_weight_type = val
            if line.upper() == 'NODE_COORD_SECTION':
                in_coord_section = True
                continue
            if line.upper() in ('EOF', 'TOUR_SECTION', 'EDGE_WEIGHT_SECTION'):
                in_coord_section = False
                continue
            if in_coord_section:
                parts = line.split()
                if len(parts) >= 3:
                    node_id = parts[0]
                    x, y    = float(parts[1]), float(parts[2])
                    coords[node_id] = (x, y)

    if not coords:
        raise ValueError("No NODE_COORD_SECTION found in file. "
                         "Only EUC_2D/GEO/ATT/CEIL_2D formats are supported.")

    # Try loading known-optimal tour from .opt.tour file
    opt_path = filepath.replace('.tsp', '.opt.tour')
    if os.path.exists(opt_path):
        try:
            tour_nodes = []
            in_tour = False
            with open(opt_path) as f:
                for line in f:
                    line = line.strip()
                    if line.upper() == 'TOUR_SECTION':
                        in_tour = True
                        continue
                    if line in ('-1', 'EOF'):
                        break
                    if in_tour and line.lstrip('-').isdigit():
                        tour_nodes.append(line)
            if tour_nodes:
                known_optimal = tour_nodes
        except Exception:
            pass

    dist_fn  = _dist_fn_for(edge_weight_type)
    node_ids = list(coords.keys())
    n        = len(node_ids)

    print(f"TSPLIB: {n} nodes, edge_weight_type={edge_weight_type}")

    # Build complete directed graph
    G2 = nx.DiGraph()
    G2.add_nodes_from(node_ids)

    for i in range(n):
        u  = node_ids[i]
        xu, yu = coords[u]
        for j in range(n):
            if i == j:
                continue
            v      = node_ids[j]
            xv, yv = coords[v]
            d      = dist_fn((xu, yu), (xv, yv))

            # Synthesise cost and time from distance.
            # Use a deterministic hash so the same pair always gets the same
            # synthetic weights — no randomness that changes on each load.
            h    = abs(hash(u + '|' + v)) % 100
            cost = max(1, _nint(d * 0.35 + h * 0.05))
            time = max(1, _nint(d * 0.07 + (h % 10) * 0.3))

            G2.add_edge(u, v, dist=d, cost=cost, time=time, type='tsplib')

    return node_ids, nx.to_dict_of_dicts(G2), coords, known_optimal