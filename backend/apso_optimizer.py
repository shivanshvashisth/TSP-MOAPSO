import random
import math
import numpy as np

# ─── Pareto dominance ────────────────────────────────────────────────────────

def dominates(s1, s2):
    return all(a <= b for a, b in zip(s1, s2)) and any(a < b for a, b in zip(s1, s2))


def update_archive(archive, pos, scores, max_size=200):
    """
    Non-dominated archive update with crowding-distance cap.
    Keeps at most max_size solutions. When full, removes the most
    crowded solution (shortest average distance to its neighbours
    in objective space) to maintain spread.
    """
    if any(math.isinf(s) or math.isnan(s) for s in scores):
        return False
    for s, _ in archive:
        if dominates(s, scores):
            return False
    archive[:] = [(s, p) for s, p in archive if not dominates(scores, s)]
    archive.append((scores, list(pos)))

    if len(archive) > max_size:
        # Remove the solution with smallest crowding distance
        _trim_archive(archive, max_size)
    return True


def _crowding_distance(archive):
    """Compute crowding distance for each solution in the archive."""
    n    = len(archive)
    n_obj = len(archive[0][0])
    dist = [0.0] * n
    for obj in range(n_obj):
        vals    = sorted(range(n), key=lambda i: archive[i][0][obj])
        obj_min = archive[vals[0]][0][obj]
        obj_max = archive[vals[-1]][0][obj]
        span    = obj_max - obj_min if obj_max != obj_min else 1e-9
        dist[vals[0]]  = float('inf')
        dist[vals[-1]] = float('inf')
        for k in range(1, n - 1):
            dist[vals[k]] += (archive[vals[k+1]][0][obj] -
                              archive[vals[k-1]][0][obj]) / span
    return dist


def _trim_archive(archive, max_size):
    while len(archive) > max_size:
        dist    = _crowding_distance(archive)
        min_idx = min(range(len(archive)), key=lambda i: dist[i])
        archive.pop(min_idx)


# ─── Distance matrix ─────────────────────────────────────────────────────────

def build_dist_matrix(nodes_list, graph):
    n   = len(nodes_list)
    INF = float('inf')
    dm  = [[INF] * n for _ in range(n)]
    for i, u in enumerate(nodes_list):
        dm[i][i] = 0
        for j, v in enumerate(nodes_list):
            if i != j:
                edge = graph.get(u, {}).get(v)
                dm[i][j] = edge['dist'] if edge else INF
    return dm


# ─── Tour operations ─────────────────────────────────────────────────────────

def nn_tour(start_idx, dm, n):
    """Nearest-neighbour greedy tour."""
    visited           = [False] * n
    tour              = [start_idx]
    visited[start_idx] = True
    for _ in range(n - 1):
        cur            = tour[-1]
        best_d, best_j = float('inf'), -1
        for j in range(n):
            if not visited[j] and dm[cur][j] < best_d:
                best_d, best_j = dm[cur][j], j
        tour.append(best_j)
        visited[best_j] = True
    return tour


def two_opt(tour, dm, max_passes=5):
    """
    2-opt local search — runs until no improvement or max_passes exhausted.
    Operates on index tour (list of ints). Returns improved tour.
    """
    n        = len(tour)
    best     = tour[:]
    for _ in range(max_passes):
        improved = False
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                a, b = best[i-1], best[i]
                c, d = best[j],   best[(j+1) % n]
                if dm[a][b] + dm[c][d] > dm[a][c] + dm[b][d] + 1e-10:
                    best[i:j+1] = best[i:j+1][::-1]
                    improved     = True
        if not improved:
            break
    return best


def double_bridge(tour):
    """
    Double-bridge 4-opt perturbation.
    Splits tour into 4 segments and reconnects them in a different order.
    This creates a new tour that 2-opt cannot reach from the original —
    key for escaping local optima.
    """
    n  = len(tour)
    if n < 8:
        return tour[:]
    # Pick 4 cut points in sorted order
    cuts = sorted(random.sample(range(1, n), 3))
    a, b, c = cuts
    # Reconnect as: seg0 + seg2 + seg1 + seg3
    seg0 = tour[:a]
    seg1 = tour[a:b]
    seg2 = tour[b:c]
    seg3 = tour[c:]
    return seg0 + seg2 + seg1 + seg3


def tour_length(tour, dm):
    n = len(tour)
    return sum(dm[tour[i]][tour[(i+1) % n]] for i in range(n))


def tour_to_position(tour, n):
    """
    Encode tour as a position vector in [0,1]^n.
    City at rank k gets value k/n + moderate jitter.
    Larger jitter (±0.04) keeps particles spread out after NN init.
    """
    pos = [0.0] * n
    for rank, city in enumerate(tour):
        pos[city] = rank / n + random.uniform(-0.04, 0.04)
    return [max(0.0, min(1.0, v)) for v in pos]


def position_to_tour(position, nodes_list, start_node):
    """Decode a position vector to a tour list of node IDs."""
    indices = list(np.argsort(position))
    route   = [nodes_list[i] for i in indices]
    if start_node in route:
        idx   = route.index(start_node)
        route = route[idx:] + route[:idx]
    return route


# ─── Fuzzy adaptive parameter control ────────────────────────────────────────

def membership_function(f, S1, S2, S3, S4):
    if f <= 0.2:
        return 'Convergence', 0, 0, 1, 0
    elif f < 0.3:
        if (-5*f + 1.5) > (10*f - 2) and (S2 or S3):
            return 'Convergence', 0, 0, 1, 0
        return 'Exploitation', 0, 1, 0, 0
    elif f <= 0.4:
        return 'Exploitation', 0, 1, 0, 0
    elif f < 0.6:
        if (-5*f + 3) > (5*f - 2) and (S1 or S2):
            return 'Exploitation', 0, 0, 1, 0
        return 'Exploration', 1, 0, 0, 0
    elif f <= 0.7:
        return 'Exploration', 1, 0, 0, 0
    elif f < 0.8:
        if (-10*f + 8) > (5*f - 3.5) and (S1 or S4):
            return 'Exploration', 1, 0, 0, 0
        return 'Jumping', 0, 0, 0, 1
    else:
        return 'Jumping', 0, 0, 0, 1


def shrink_coeff(c1, c2):
    fi = c1 + c2
    if fi == 0:
        return 2.0, 2.0
    if (c1 <= 0 or c1 >= 4) or (c2 <= 0 or c2 >= 4) or not (3 <= fi <= 4):
        c1 = c1 / fi * 4.0
        c2 = c2 / fi * 4.0
    return c1, c2


def change_c1c2(c1, c2, f, S1, S2, S3, S4):
    member, S1, S2, S3, S4 = membership_function(f, S1, S2, S3, S4)
    cfg = {
        'Exploration':  ( 1, -1, random.uniform(0.05, 0.10)),
        'Exploitation': ( 1, -1, random.uniform(0.01, 0.05)),
        'Convergence':  ( 1,  1, random.uniform(0.01, 0.05)),
        'Jumping':      (-1,  1, random.uniform(0.05, 0.10)),
    }
    if member not in cfg:
        return c1, c2, S1, S2, S3, S4
    K1, K2, delta = cfg[member]
    c1, c2 = shrink_coeff(c1 + K1*delta, c2 + K2*delta)
    return c1, c2, S1, S2, S3, S4


# ─── Diversity metric ────────────────────────────────────────────────────────

def calculate_f(swarm, archive):
    """Fuzzy diversity index f in [0,1]. 0 = converged, 1 = fully spread."""
    if not archive or len(swarm) < 2:
        return 0.5
    positions      = np.array([p.position for p in swarm])
    archive_center = np.mean([s[1] for s in archive], axis=0)
    n              = len(positions)

    d_vals = []
    for i in range(n):
        diffs = positions - positions[i]
        d_vals.append(np.sqrt((diffs**2).sum(axis=1)).sum() / max(n - 1, 1))

    dmin, dmax = min(d_vals), max(d_vals)
    if dmax == dmin:
        return 0.0   # fully converged — trigger Jumping

    dists_to_centre = np.sqrt(((positions - archive_center)**2).sum(axis=1))
    g = int(np.argmin(dists_to_centre))
    return (d_vals[g] - dmin) / (dmax - dmin)


def calculate_w(f):
    return max(0.4, min(0.9, 1.0 / (1.0 + 1.5 * math.exp(-2.6 * f))))


# ─── Particle ────────────────────────────────────────────────────────────────

class Particle:
    def __init__(self, n_dims, fitness_func, init_position=None):
        self.n_dims        = n_dims
        self.fitness_func  = fitness_func

        if init_position is not None:
            self.position = list(init_position)
        else:
            self.position = [random.random() for _ in range(n_dims)]

        # Velocity range scaled to dimension size — key fix vs old ±0.1
        vmax = 1.0 / n_dims
        self.velocity   = [random.uniform(-vmax, vmax) for _ in range(n_dims)]
        self.best_pos   = list(self.position)
        self.best_score = self.fitness_func(self.position)

    def update_velocity(self, gbest_pos, w, c1, c2):
        vmax = 1.0 / self.n_dims      # velocity clamped per dimension
        for i in range(self.n_dims):
            cog = c1 * random.random() * (self.best_pos[i] - self.position[i])
            soc = c2 * random.random() * (gbest_pos[i]     - self.position[i])
            v   = w * self.velocity[i] + cog + soc
            self.velocity[i] = max(-vmax, min(vmax, v))   # clamp velocity

    def update_position(self):
        for i in range(self.n_dims):
            self.position[i] += self.velocity[i]
            if self.position[i] > 1.0:
                self.position[i] = 2.0 - self.position[i]   # reflect
                self.velocity[i] *= -0.5
            elif self.position[i] < 0.0:
                self.position[i] = -self.position[i]          # reflect
                self.velocity[i] *= -0.5
            self.position[i] = max(0.0, min(1.0, self.position[i]))

        new_score = self.fitness_func(self.position)
        if not dominates(self.best_score, new_score):
            self.best_score = new_score
            self.best_pos   = list(self.position)
            return True
        return False

    def reinitialise(self, new_position):
        """Hard reset — used during diversity restart."""
        self.position   = list(new_position)
        vmax            = 1.0 / self.n_dims
        self.velocity   = [random.uniform(-vmax, vmax) for _ in range(self.n_dims)]
        new_score       = self.fitness_func(self.position)
        if not dominates(self.best_score, new_score):
            self.best_score = new_score
            self.best_pos   = list(self.position)


# ─── Main entry point ────────────────────────────────────────────────────────

def run_apso(pop_size, max_iter, fitness_func, n_nodes, graph=None, nodes_list=None):
    """
    Multi-Objective APSO for TSP with:
      - Nearest-neighbour + 2-opt initialisation for quality starting tours
      - Double-bridge perturbation pool for diversity
      - Scaled velocity clamping (vmax = 1/n_nodes)
      - Crowding-distance archive trimming (keeps Pareto front spread)
      - Stagnation detection with forced re-initialisation
      - Periodic 2-opt refinement on archive solutions

    Parameters
    ----------
    pop_size     : swarm size (recommend 100+ for n>20)
    max_iter     : iterations (recommend 300+ for n>20)
    fitness_func : partial(objective_function, graph, nodes_list, start_node)
    n_nodes      : number of cities = particle dimension
    graph        : graph dict (needed for NN init + 2-opt)
    nodes_list   : list of node IDs in insertion order
    """
    w,  c1,  c2    = 0.9, 2.0, 2.0
    S1, S2, S3, S4 = 1,   0,   0,   0
    archive        = []

    # ── Build distance matrix and diverse initial tours ──────────────────────
    dm           = None
    init_positions = []

    if graph is not None and nodes_list is not None and n_nodes > 1:
        dm = build_dist_matrix(nodes_list, graph)

        # 1. NN tours from every city as starting point
        all_starts = list(range(n_nodes))
        random.shuffle(all_starts)
        nn_tours = []
        for s in all_starts:
            t = nn_tour(s, dm, n_nodes)
            nn_tours.append(t)

        # 2. Apply 2-opt to each NN tour to get much better starting quality
        print(f"  Running 2-opt on {len(nn_tours)} NN tours...")
        improved_tours = []
        for t in nn_tours:
            t2 = two_opt(t, dm, max_passes=3)
            improved_tours.append(t2)

        # 3. Deduplicate by tour length — keep diverse tour lengths
        seen_lengths = set()
        diverse_tours = []
        for t in improved_tours:
            tl = round(tour_length(t, dm))
            if tl not in seen_lengths:
                diverse_tours.append(t)
                seen_lengths.add(tl)

        # 4. Generate double-bridge perturbations of the best tours
        #    to fill remaining particle slots with diverse variants
        best_tours = sorted(diverse_tours, key=lambda t: tour_length(t, dm))[:10]
        while len(diverse_tours) < pop_size * 2:
            base = random.choice(best_tours)
            perturbed = double_bridge(base)
            perturbed = two_opt(perturbed, dm, max_passes=2)
            diverse_tours.append(perturbed)

        # 5. Pick pop_size tours — mix of best quality + random diverse
        random.shuffle(diverse_tours)
        selected_tours = diverse_tours[:pop_size]

        for t in selected_tours:
            init_positions.append(tour_to_position(t, n_nodes))

        print(f"  Init: {len(init_positions)} diverse tours "
              f"(lengths {min(round(tour_length(t,dm)) for t in selected_tours)}"
              f"–{max(round(tour_length(t,dm)) for t in selected_tours)})")
    else:
        init_positions = [None] * pop_size
        print(f"  Random init: {pop_size} particles")

    # ── Build swarm ──────────────────────────────────────────────────────────
    swarm = [
        Particle(n_nodes, fitness_func,
                 init_position=init_positions[i] if i < len(init_positions) else None)
        for i in range(pop_size)
    ]
    for p in swarm:
        update_archive(archive, p.best_pos, p.best_score)

    print(f"  Swarm ready | archive={len(archive)} | "
          f"best_dist={min((s[0][0] for s in archive if not math.isinf(s[0][0])), default=float('inf')):.0f}")

    # ── Stagnation tracking ──────────────────────────────────────────────────
    stagnation_counter = 0
    last_best_dist     = float('inf')
    STAGNATION_LIMIT   = max(30, max_iter // 10)   # trigger restart after this many idle iters

    # ── Main loop ────────────────────────────────────────────────────────────
    for it in range(max_iter):
        if not archive:
            break

        for particle in swarm:
            gbest_pos = random.choice(archive)[1]
            particle.update_velocity(gbest_pos, w, c1, c2)
            if particle.update_position():
                update_archive(archive, particle.best_pos, particle.best_score)

        f  = calculate_f(swarm, archive)
        w  = calculate_w(f)
        c1, c2, S1, S2, S3, S4 = change_c1c2(c1, c2, f, S1, S2, S3, S4)

        # ── Stagnation detection & diversity restart ──────────────────────
        finite = [s[0][0] for s in archive if not math.isinf(s[0][0])]
        cur_best = min(finite) if finite else float('inf')

        if cur_best >= last_best_dist - 0.5:
            stagnation_counter += 1
        else:
            stagnation_counter = 0
            last_best_dist     = cur_best

        if stagnation_counter >= STAGNATION_LIMIT:
            # Reinitialise worst 40% of swarm with double-bridge perturbations
            # of the current archive's best solution
            stagnation_counter = 0
            n_reinit  = max(1, pop_size * 2 // 5)
            best_archive_pos = min(archive, key=lambda x: x[0][0])[1]
            best_tour_indices = list(np.argsort(best_archive_pos))

            reinit_positions = []
            for _ in range(n_reinit):
                if dm is not None:
                    perturbed = double_bridge(best_tour_indices)
                    perturbed = two_opt(perturbed, dm, max_passes=2)
                    reinit_positions.append(tour_to_position(perturbed, n_nodes))
                else:
                    reinit_positions.append([random.random() for _ in range(n_nodes)])

            # Sort particles by their best score (worst first) and reinit them
            worst_particles = sorted(swarm, key=lambda p: p.best_score[0], reverse=True)[:n_reinit]
            for p, new_pos in zip(worst_particles, reinit_positions):
                p.reinitialise(new_pos)
                update_archive(archive, p.best_pos, p.best_score)

            if (it + 1) % 10 == 0:
                print(f"  iter {it+1:>4} | RESTART — reinit {n_reinit} particles")

        # ── Periodic 2-opt refinement on archive ─────────────────────────
        # Every 50 iters, run 2-opt on all archive solutions and update if improved
        if dm is not None and (it + 1) % 50 == 0 and (it + 1) < max_iter:
            refined_archive = []
            for scores, pos in archive:
                tour_idx = list(np.argsort(pos))
                improved = two_opt(tour_idx, dm, max_passes=5)
                new_pos  = tour_to_position(improved, n_nodes)
                new_score = fitness_func(new_pos)
                # Take whichever is better in dist (keeping multi-objective)
                if not any(math.isinf(s) for s in new_score) and new_score[0] < scores[0]:
                    refined_archive.append((new_score, new_pos))
                else:
                    refined_archive.append((scores, pos))
            archive.clear()
            for scores, pos in refined_archive:
                update_archive(archive, pos, scores)

        # ── Logging ──────────────────────────────────────────────────────
        if (it + 1) % 50 == 0 or it == 0:
            finite = [s[0][0] for s in archive if not math.isinf(s[0][0])]
            best_d = min(finite) if finite else float('inf')
            print(f"  iter {it+1:>4}/{max_iter} | archive={len(archive):>3} "
                  f"| best_dist={best_d:.0f} | f={f:.3f} | w={w:.3f} "
                  f"| stag={stagnation_counter}")

    # ── Final 2-opt pass on entire archive ───────────────────────────────────
    if dm is not None:
        print("  Final 2-opt refinement pass on archive...")
        final_archive = []
        for scores, pos in archive:
            tour_idx = list(np.argsort(pos))
            improved = two_opt(tour_idx, dm, max_passes=10)
            new_pos  = tour_to_position(improved, n_nodes)
            new_score = fitness_func(new_pos)
            if not any(math.isinf(s) for s in new_score) and new_score[0] < scores[0]:
                final_archive.append((new_score, new_pos))
            else:
                final_archive.append((scores, pos))
        archive.clear()
        for scores, pos in final_archive:
            update_archive(archive, pos, scores)

    finite = [s[0][0] for s in archive if not math.isinf(s[0][0])]
    print(f"  Done | archive={len(archive)} solutions "
          f"| best_dist={min(finite) if finite else 'inf':.0f}")
    return archive