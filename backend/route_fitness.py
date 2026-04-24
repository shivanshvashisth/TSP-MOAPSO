import numpy as np

# No graph_world import. Graph is always injected as a parameter.

def evaluate_route(route, graph):
    """
    Sum dist/cost/time along the closed tour route → route[0].
    Returns a score dict, or None if any edge is missing.
    """
    scores = {'dist': 0, 'cost': 0, 'time': 0}
    n = len(route)
    for i in range(n):
        u = route[i]
        v = route[(i + 1) % n]
        edge = graph.get(u, {}).get(v)
        if edge is None:
            return None
        scores['dist'] += edge['dist']
        scores['cost'] += edge['cost']
        scores['time'] += edge['time']
    return scores


def objective_function(particle_position, graph, nodes_list, start_node):
    """
    Decode a continuous PSO position vector into a tour and score it.
    The smallest value in position maps to the first city visited, etc.
    (smallest-position-value encoding — standard for continuous TSP PSO).
    """
    sorted_indices = np.argsort(particle_position)
    route = [nodes_list[i] for i in sorted_indices]

    # Rotate so start_node is first
    if start_node in route:
        idx   = route.index(start_node)
        route = route[idx:] + route[:idx]

    scores = evaluate_route(route, graph)
    if scores is None:
        return (float('inf'), float('inf'), float('inf'))

    return (scores['dist'], scores['cost'], scores['time'])