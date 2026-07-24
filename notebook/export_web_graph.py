"""
Export k-core subgraphs of the bipartite investor-company network as compact
JSON for the browser explorer (docs/).

  docs/graph.json    the innermost 6-core  (516 nodes)  -> 2D analytical view
  docs/graph3d.json  the wider 4-core    (~3.8k nodes) -> 3D "galaxy" view

The full 22k-node graph is far too large to render in a browser; the k-cores are
both the most interesting subgraphs and small enough to stay smooth.

Run:  python export_web_graph.py
"""
import json
import os
import networkx as nx

HERE = os.path.dirname(os.path.abspath(__file__))
GML = os.path.join(HERE, "..", "data", "full_bipartite_graph.gml")
DOCS = os.path.join(HERE, "..", "docs")


def clean(v):
    # pandas leaves NaN floats / "nan" strings — invalid JSON, normalize to None
    if v is None:
        return None
    if isinstance(v, float) and v != v:  # NaN
        return None
    if isinstance(v, str) and v.strip().lower() in ("", "nan", "unknown"):
        return None
    return v


def export_core(G, core, full_deg, capital_full, kmin, out_name):
    core_nodes = [n for n, c in core.items() if c >= kmin]
    H = G.subgraph(core_nodes).copy()

    comms = nx.community.louvain_communities(H, seed=42, weight="weight")
    comm_of = {n: i for i, c in enumerate(comms) for n in c}

    nodes = [{
        "id": n,
        "label": d.get("name") or n,
        "type": d.get("node_type"),
        "category": clean(d.get("category")),
        "region": clean(d.get("region")),
        "deg": full_deg[n],           # reach in the full ecosystem
        "coreDeg": H.degree(n),       # ties within this core
        "capital": round(capital_full[n] / 1e9, 3),
        "community": comm_of[n],
    } for n, d in H.nodes(data=True)]

    edges = [{
        "source": u, "target": v,
        "weight": round((d.get("weight", 0) or 0) / 1e9, 3),
    } for u, v, d in H.edges(data=True)]

    meta = {
        "kcore": kmin,
        "nodes": len(nodes),
        "edges": len(edges),
        "communities": len(comms),
        "investors": sum(1 for n in nodes if n["type"] == "investor"),
        "companies": sum(1 for n in nodes if n["type"] == "company"),
    }

    out = os.path.join(DOCS, out_name)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "nodes": nodes, "edges": edges}, f,
                  ensure_ascii=False, allow_nan=False)
    print("wrote", out_name, "-", meta)


def main():
    G = nx.read_gml(GML)
    print(f"full graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    G.remove_edges_from(nx.selfloop_edges(G))

    core = nx.core_number(G)
    full_deg = dict(G.degree())

    # total capital per node = sum of incident edge weights (in the FULL graph)
    capital_full = {n: 0.0 for n in G}
    for u, v, d in G.edges(data=True):
        w = d.get("weight", 0) or 0
        capital_full[u] += w
        capital_full[v] += w

    os.makedirs(DOCS, exist_ok=True)
    export_core(G, core, full_deg, capital_full, 6, "graph.json")    # 2D core
    export_core(G, core, full_deg, capital_full, 4, "graph3d.json")  # 3D galaxy


if __name__ == "__main__":
    main()
