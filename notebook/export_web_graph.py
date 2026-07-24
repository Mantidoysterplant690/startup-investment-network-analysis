"""
Export the innermost k-core of the bipartite investor-company network as a
compact JSON for the browser-based interactive explorer (docs/index.html).

The full graph has 22k nodes — far too many to render or read in a browser.
The 6-core (~516 nodes) is "the heart of the ecosystem" from the report, and
is both small enough to render smoothly and the most interesting subgraph.

Run:  python export_web_graph.py
"""
import json
import os
import networkx as nx

HERE = os.path.dirname(os.path.abspath(__file__))
GML = os.path.join(HERE, "..", "data", "full_bipartite_graph.gml")
OUT = os.path.join(HERE, "..", "docs", "graph.json")

G = nx.read_gml(GML)
print(f"full graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# --- innermost k-core (drop isolates first; core_number needs no self-loops) ---
G.remove_edges_from(nx.selfloop_edges(G))
core = nx.core_number(G)
kmax = max(core.values())
core_nodes = [n for n, c in core.items() if c == kmax]
H = G.subgraph(core_nodes).copy()
print(f"{kmax}-core: {H.number_of_nodes()} nodes, {H.number_of_edges()} edges")

# --- degree in the FULL graph (a node's true reach) & total capital ($) ---
full_deg = dict(G.degree())
capital = {n: 0.0 for n in H}
for u, v, d in G.edges(data=True):
    w = d.get("weight", 0) or 0
    if u in capital:
        capital[u] += w
    if v in capital:
        capital[v] += w

# --- community detection on the core (for colouring investor cliques) ---
comms = nx.community.louvain_communities(H, seed=42, weight="weight")
comm_of = {n: i for i, c in enumerate(comms) for n in c}
print(f"communities in core: {len(comms)}")

# Layout is computed client-side by Cytoscape.js (cose) — 516 nodes render fast
# and keeping it in the browser avoids a heavy numpy/scipy dependency here.
def clean(v):
    # pandas leaves NaN floats / "nan" strings — invalid JSON, normalize to None
    if v is None:
        return None
    if isinstance(v, float) and v != v:  # NaN
        return None
    if isinstance(v, str) and v.strip().lower() in ("", "nan", "unknown"):
        return None
    return v

nodes = []
for n, d in H.nodes(data=True):
    nodes.append({
        "id": n,
        "label": d.get("name") or n,
        "type": d.get("node_type"),          # investor | company
        "category": clean(d.get("category")),
        "region": clean(d.get("region")),
        "deg": full_deg[n],                    # reach in the full ecosystem
        "coreDeg": H.degree(n),                # ties within the core
        "capital": round(capital[n] / 1e9, 3), # total capital, $B
        "community": comm_of[n],
    })

edges = [{
    "source": u, "target": v,
    "weight": round((d.get("weight", 0) or 0) / 1e9, 3),
} for u, v, d in H.edges(data=True)]

meta = {
    "kcore": kmax,
    "nodes": len(nodes),
    "edges": len(edges),
    "communities": len(comms),
    "investors": sum(1 for n in nodes if n["type"] == "investor"),
    "companies": sum(1 for n in nodes if n["type"] == "company"),
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"meta": meta, "nodes": nodes, "edges": edges}, f,
              ensure_ascii=False, allow_nan=False)
print("wrote", OUT, "-", meta)
