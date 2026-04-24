import uvicorn
import numpy as np
import math
import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from functools import partial

from apso_optimizer import run_apso
from route_fitness import objective_function
from graph_world import graph_dict as _default_graph_dict, nodes as _default_nodes, load_tsplib

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Live graph state ──────────────────────────────────────────────────────────
_state = {
    "graph_dict":    _default_graph_dict,
    "nodes_list":    list(_default_nodes),
    "coords":        None,
    "known_optimal": None,
    "source":        "default",
}

class ApsoParams(BaseModel):
    pop_size:   int = 50
    max_iter:   int = 100
    start_node: str = "A"


def decode_position(position, nodes_list):
    return [nodes_list[i] for i in np.argsort(position)]


@app.get("/")
def read_root():
    return {"message": "Multi-Objective TSP Solver API", "source": _state["source"]}


@app.post("/solve/apso")
def solve_apso(params: ApsoParams):
    graph      = _state["graph_dict"]
    nodes_list = _state["nodes_list"]
    n_nodes    = len(nodes_list)

    print(f"\n{'='*60}")
    print(f"source={_state['source']} | nodes={n_nodes} | "
          f"pop={params.pop_size} | iter={params.max_iter} | start={params.start_node}")
    print(f"{'='*60}")

    if params.start_node not in nodes_list:
        raise HTTPException(
            status_code=422,
            detail=f"start_node '{params.start_node}' not in graph. "
                   f"First 10 nodes: {nodes_list[:10]}"
        )

    try:
        fitness_func = partial(
            objective_function,
            graph=graph,
            nodes_list=nodes_list,
            start_node=params.start_node,
        )

        # Pass graph + nodes_list so run_apso can build NN init positions
        archive = run_apso(
            pop_size     = params.pop_size,
            max_iter     = params.max_iter,
            fitness_func = fitness_func,
            n_nodes      = n_nodes,
            graph        = graph,
            nodes_list   = nodes_list,
        )

        results = []
        for (scores_tuple, position_vector) in archive:
            if any(math.isinf(s) or math.isnan(s) for s in scores_tuple):
                continue
            route = decode_position(position_vector, nodes_list)
            if params.start_node in route:
                idx   = route.index(params.start_node)
                route = route[idx:] + route[:idx]
            results.append({
                "route": route,
                "scores": {
                    "dist": round(scores_tuple[0], 2),
                    "cost": round(scores_tuple[1], 2),
                    "time": round(scores_tuple[2], 2),
                },
            })

        # TSPLIB benchmark gap
        benchmark = None
        if _state["known_optimal"] and results:
            opt_tour = _state["known_optimal"]
            opt_dist, valid = 0, True
            for i in range(len(opt_tour)):
                u    = opt_tour[i]
                v    = opt_tour[(i+1) % len(opt_tour)]
                edge = graph.get(u, {}).get(v)
                if edge:
                    opt_dist += edge["dist"]
                else:
                    valid = False; break
            if valid and opt_dist > 0:
                best_dist = min(r["scores"]["dist"] for r in results)
                gap_pct   = round((best_dist - opt_dist) / opt_dist * 100, 2)
                benchmark = {
                    "known_optimal_dist": opt_dist,
                    "solver_best_dist":   best_dist,
                    "gap_percent":        gap_pct,
                }

        print(f"Done — {len(results)} Pareto solutions.")
        return {
            "status":         "success",
            "solution_count": len(results),
            "solutions":      results,
            "benchmark":      benchmark,
        }

    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/structure")
def get_graph_structure():
    graph  = _state["graph_dict"]
    coords = _state["coords"]
    nodes, edges = [], []

    for node_id in graph:
        entry = {"data": {"id": node_id}}
        if coords and node_id in coords:
            entry["data"]["x"] = coords[node_id][0]
            entry["data"]["y"] = coords[node_id][1]
        nodes.append(entry)

    added = set()
    for src, nbrs in graph.items():
        for tgt, w in nbrs.items():
            key = tuple(sorted([src, tgt]))
            if key not in added:
                edges.append({"data": {
                    "id": f"{src}-{tgt}", "source": src, "target": tgt,
                    "dist": w.get("dist",0), "cost": w.get("cost",0),
                    "time": w.get("time",0), "type": w.get("type","local"),
                }})
                added.add(key)

    return {
        "nodes": nodes, "edges": edges,
        "source": _state["source"],
        "node_count": len(nodes), "edge_count": len(edges),
        "has_coords": coords is not None,
        "known_optimal": _state["known_optimal"] is not None,
    }


@app.post("/graph/load-tsplib")
async def load_tsplib_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".tsp"):
        raise HTTPException(status_code=400, detail="Must be a .tsp file")

    with tempfile.NamedTemporaryFile(suffix=".tsp", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        node_ids, gd, coords, known_opt = load_tsplib(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Parse error: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    if len(node_ids) > 150:
        raise HTTPException(status_code=413,
            detail=f"Too large ({len(node_ids)} nodes). Keep it ≤150 for reasonable runtime.")

    _state.update({
        "graph_dict":    gd,
        "nodes_list":    node_ids,
        "coords":        coords,
        "known_optimal": known_opt,
        "source":        file.filename,
    })
    print(f"Loaded {file.filename}: {len(node_ids)} nodes, optimal={'yes' if known_opt else 'no'}")

    return {
        "status": "loaded", "filename": file.filename,
        "node_count": len(node_ids),
        "edge_count": sum(len(v) for v in gd.values()),
        "has_coords": True,
        "known_optimal": known_opt is not None,
        "nodes_preview": node_ids[:10],
    }


@app.post("/graph/reset")
def reset_graph():
    _state.update({
        "graph_dict":    _default_graph_dict,
        "nodes_list":    list(_default_nodes),
        "coords":        None,
        "known_optimal": None,
        "source":        "default",
    })
    return {"status": "reset", "node_count": len(_default_nodes)}


if __name__ == "__main__":
    uvicorn.run("api_main:app", host="127.0.0.1", port=8000, reload=True)