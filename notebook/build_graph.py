"""
BIL403-503 Donem Projesi - Startup Ekosistemi Yatirimci-Sirket Bipartite Agi
Pipeline test scripti - kucuk NY ornek verisiyle calisir, tam veri geldiginde
sadece dosya yolunu degistirmek yeterli olacak.

Veri kaynagi: crunchbase-investments.csv (Crunchbase Ekim 2013 export, CC-BY-NC)
https://github.com/dsagal/crunchbase-october-2013
"""
import pandas as pd
import networkx as nx
from networkx.algorithms import bipartite
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from collections import Counter
import json

DATA_PATH = "crunchbase-investments-fixed.csv"  # tam veri seti (52,870 kayit)

# --- 1. Veriyi oku ve temizle ---
# Not: Orijinal Crunchbase 2013 dump'i ISO-8859-1 kodlamali ve satirlar CR (\r) ile
# ayrilmis (eski Mac stili); once \n'e cevrilip (crunchbase-investments-fixed.csv)
# sonra pandas ile okunuyor.
df = pd.read_csv(DATA_PATH, encoding="ISO-8859-1", low_memory=False)
df = df.dropna(subset=["company_permalink", "investor_permalink"])
df["raised_amount_usd"] = pd.to_numeric(df["raised_amount_usd"], errors="coerce")

print(f"Toplam yatirim kaydi (satir): {len(df)}")
print(f"Benzersiz sirket: {df['company_permalink'].nunique()}")
print(f"Benzersiz yatirimci: {df['investor_permalink'].nunique()}")

# --- 2. Bipartite graf kur ---
# Dugum kumeleri: bipartite=0 -> yatirimci, bipartite=1 -> sirket
#
# ONEMLI VERI NOTU: Ayni tuzel kisilik (ornegin PayPal, eBay, Mozilla, NVIDIA gibi
# 92 kurum) veri setinde HEM yatirimci HEM de yatirim alan sirket olarak geciyor
# (kurumsal risk sermayesi / corporate VC durumu). Bu iki rolu ayni dugumde
# birlestirmek grafi bipartite olmaktan cikarip tek yonlu olmayan tuhaf dongulere
# (ornegin A->B->C->A) yol acabiliyor ve networkx'in bipartite fonksiyonlari bunu
# reddediyor. Bu yuzden yatirimci-rolu ve sirket-rolu ayri dugumler olarak
# modelleniyor (ID'lerin basina INV::/CO:: on eki eklenerek). Bu, literatürde
# affiliation aglari icin standart bir yaklasimdir ve rapor icinde metodolojik
# bir tercih olarak tartisiliyor.
def inv_id(p):
    return f"INV::{p}"

def co_id(p):
    return f"CO::{p}"

G = nx.Graph()

companies = df[["company_permalink", "company_name", "company_category_code",
                 "company_country_code", "company_region"]].drop_duplicates("company_permalink")
investors = df[["investor_permalink", "investor_name", "investor_category_code",
                 "investor_country_code", "investor_region"]].drop_duplicates("investor_permalink")

for _, row in companies.iterrows():
    G.add_node(co_id(row["company_permalink"]), bipartite=1, node_type="company",
               permalink=row["company_permalink"], name=row["company_name"],
               category=row["company_category_code"],
               country=row["company_country_code"], region=row["company_region"])

for _, row in investors.iterrows():
    G.add_node(inv_id(row["investor_permalink"]), bipartite=0, node_type="investor",
               permalink=row["investor_permalink"], name=row["investor_name"],
               category=row["investor_category_code"],
               country=row["investor_country_code"], region=row["investor_region"])

# Iki rolde de gorulen tuzel kisilikleri say (rapor icin ilginc bir bulgu)
dual_role = set(df["company_permalink"].dropna()) & set(df["investor_permalink"].dropna())
print(f"Hem yatirimci hem sirket rolunde gorulen tuzel kisilik sayisi: {len(dual_role)}")

# Kenarlar: yatirimci -> sirket. Ayni ikili birden fazla turda yatirim yapmis
# olabilir (farkli fonlama turlari), bu yuzden agirlik = toplam yatirim tutari
# (bilinmiyorsa = yatirim sayisi).
edge_weights = {}
for _, row in df.iterrows():
    key = (inv_id(row["investor_permalink"]), co_id(row["company_permalink"]))
    amt = row["raised_amount_usd"] if pd.notna(row["raised_amount_usd"]) else 0
    if key in edge_weights:
        edge_weights[key]["weight"] += amt
        edge_weights[key]["count"] += 1
    else:
        edge_weights[key] = {"weight": amt, "count": 1}

for (inv, comp), attrs in edge_weights.items():
    G.add_edge(inv, comp, weight=attrs["weight"], n_rounds=attrs["count"])

investor_nodes = {n for n, d in G.nodes(data=True) if d["bipartite"] == 0}
company_nodes = set(G) - investor_nodes

print("\n=== AG TIPI ===")
print("Yonsuz (undirected), agirlikli (weighted) bipartite affiliation agi")
print("Dugum turleri: Yatirimci (bipartite=0), Sirket (bipartite=1)")

print("\n=== ORDER & SIZE ===")
print(f"Toplam dugum sayisi (order): {G.number_of_nodes()}")
print(f"  - Yatirimci dugumu: {len(investor_nodes)}")
print(f"  - Sirket dugumu:    {len(company_nodes)}")
print(f"Toplam kenar sayisi (size): {G.number_of_edges()}")

print("\n=== YOGUNLUK (density) ===")
# Bipartite yogunluk = |E| / (n0 * n1)
dens = bipartite.density(G, investor_nodes)
print(f"Bipartite density: {dens:.6f}")

print("\n=== DERECE DAGILIMI ===")
inv_degs = [d for n, d in G.degree(investor_nodes)]
comp_degs = [d for n, d in G.degree(company_nodes)]
print(f"Yatirimci basina ort. sirket sayisi: {sum(inv_degs)/len(inv_degs):.2f} (max={max(inv_degs)})")
print(f"Sirket basina ort. yatirimci sayisi: {sum(comp_degs)/len(comp_degs):.2f} (max={max(comp_degs)})")

print("\n=== KUMELENME KATSAYISI (bipartite clustering) ===")
# Standart clustering bipartite graflarda ucgen olmadigi icin 0'dir;
# bunun yerine Latapy ve ark. (2008) bipartite clustering (4-cycle tabanli) kullanilir.
clust = bipartite.clustering(G, investor_nodes)
avg_clust = sum(clust.values()) / len(clust) if clust else 0
print(f"Ortalama bipartite clustering (yatirimci kumesi): {avg_clust:.4f}")

print("\n=== BAGLI BILESEN DAGILIMI (components) ===")
components = list(nx.connected_components(G))
comp_sizes = sorted((len(c) for c in components), reverse=True)
print(f"Bilesen sayisi: {len(components)}")
print(f"En buyuk bilesen boyutu: {comp_sizes[0]} ({comp_sizes[0]/G.number_of_nodes()*100:.1f}% dugumler)")
print(f"Bilesen boyut dagilimi (ilk 10): {comp_sizes[:10]}")

# --- 3. Tek-modlu izdusum (opsiyonel genisletme, discussion icin) ---
print("\n=== TEK-MODLU IZDUSUM: Yatirimci ortak-yatirim agi ===")
G_investors = bipartite.weighted_projected_graph(G, investor_nodes)
print(f"Yatirimci-yatirimci ag: {G_investors.number_of_nodes()} dugum, {G_investors.number_of_edges()} kenar")
if G_investors.number_of_edges() > 0:
    print(f"Ortalama standart clustering: {nx.average_clustering(G_investors):.4f}")

nx.write_gml(G, "full_bipartite_graph.gml")
print("\nGraf 'full_bipartite_graph.gml' olarak kaydedildi.")

# --- 4. Gorsellestirmeler ---
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

inv_deg_counts = Counter(inv_degs)
xs, ys = zip(*sorted(inv_deg_counts.items()))
axes[0].scatter(xs, ys, s=14, color="#2c6fbb")
axes[0].set_xscale("log"); axes[0].set_yscale("log")
axes[0].set_xlabel("Derece (yatirim yapilan sirket sayisi)")
axes[0].set_ylabel("Yatirimci sayisi")
axes[0].set_title("Yatirimci derece dagilimi (log-log)")

comp_deg_counts = Counter(comp_degs)
xs2, ys2 = zip(*sorted(comp_deg_counts.items()))
axes[1].scatter(xs2, ys2, s=14, color="#c0392b")
axes[1].set_xscale("log"); axes[1].set_yscale("log")
axes[1].set_xlabel("Derece (yatirimci sayisi)")
axes[1].set_ylabel("Sirket sayisi")
axes[1].set_title("Sirket derece dagilimi (log-log)")

plt.tight_layout()
plt.savefig("degree_distribution.png", dpi=150)
plt.close()

plt.figure(figsize=(6, 4.2))
plt.bar(range(1, min(21, len(comp_sizes) + 1)), comp_sizes[:20], color="#2c6fbb")
plt.xlabel("Bilesen sirasi (buyukten kucuge)")
plt.ylabel("Bilesen boyutu (dugum sayisi)")
plt.title("En buyuk 20 bagli bilesenin boyutu")
plt.yscale("log")
plt.tight_layout()
plt.savefig("component_sizes.png", dpi=150)
plt.close()

print("Gorseller kaydedildi: degree_distribution.png, component_sizes.png")

# --- 5. Ozet istatistikleri JSON olarak kaydet (rapor icin) ---
summary = {
    "n_records": int(len(df)),
    "n_companies": int(df["company_permalink"].nunique()),
    "n_investors": int(df["investor_permalink"].nunique()),
    "n_dual_role_entities": int(len(dual_role)),
    "graph_type": "undirected, weighted, bipartite affiliation network",
    "order_total": int(G.number_of_nodes()),
    "order_investors": int(len(investor_nodes)),
    "order_companies": int(len(company_nodes)),
    "size": int(G.number_of_edges()),
    "bipartite_density": dens,
    "avg_degree_investor": sum(inv_degs) / len(inv_degs),
    "max_degree_investor": max(inv_degs),
    "avg_degree_company": sum(comp_degs) / len(comp_degs),
    "max_degree_company": max(comp_degs),
    "avg_bipartite_clustering_investors": avg_clust,
    "n_components": len(components),
    "giant_component_size": comp_sizes[0],
    "giant_component_fraction": comp_sizes[0] / G.number_of_nodes(),
    "component_size_top10": comp_sizes[:10],
    "projection_investor_investor_nodes": G_investors.number_of_nodes(),
    "projection_investor_investor_edges": G_investors.number_of_edges(),
    "projection_investor_investor_avg_clustering": nx.average_clustering(G_investors) if G_investors.number_of_edges() > 0 else 0,
}
with open("summary_stats.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print("Ozet istatistikler 'summary_stats.json' dosyasina kaydedildi.")
