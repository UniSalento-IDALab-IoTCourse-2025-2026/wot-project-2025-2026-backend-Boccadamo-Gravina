#!/usr/bin/env python3
"""
Clustering dei paesi in base a quanto la loro relazione esposizione -> burden somiglia a quella dell'Italia.

Per ogni inquinante, con numero di cluster fisso (default 3), abbiamo:
  1. curva di riferimento globale f(x): GAM monotono (spline penalizzata) su tutti i paesi,
     target ln(1 + Burden Mean);
  2. finestra di esposizione italiana: [min, max] dell'esposizione dell'Italia;
  3. profilo di ogni paese, calcolato SOLO sulle sue righe dentro la finestra, dai residui r = y_log - f(x):
       - offset : media dei residui (e^offset = burden del paese rispetto a quello "tipico", a pari esposizione);
       - slope  : pendenza dei residui lungo la finestra;
       - spread : dispersione dei residui attorno al proprio trend;
     i paesi con meno di --min-rows righe dentro la finestra sono "non confrontabili" e restano fuori dal clustering;
  4. profili standardizzati in modo robusto (mediana / MAD) e pesati; distanza di ogni paese dall'Italia;
  5. clustering gerarchico (Ward) con k cluster: paesi nello stesso cluster dell'Italia = "simili", gli altri = "distanti".

Uso:
  python clustering.py --data-dir output_preprocessing --out-dir clustering_data --summary-dir clustering_data/riepilogo_clustering
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # per importare training.py

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
from training import PSpline  # spline penalizzata con monotonia opzionale

POLLUTANTS = [("pm25", "PM2.5"), ("no2", "NO₂"), ("ozone", "Ozono"), ("hap", "HAP (inquinamento domestico)")]
DEFAULT_LAM = {"pm25": 300.0, "no2": 30.0, "ozone": 30.0, "hap": 3.0}
FEATURES = ["offset", "slope", "spread"]
WEIGHTS = np.array([1.0, 0.5, 0.5])   # l'offset (livello) pesa di piu': e' la differenza principale tra paesi
SLOPE_FLOOR = 0.02                    # varianza minima (in unita' di finestra) per il shrinkage della pendenza
REF = "Italy"

COLORS = {"Italia": "#C2410C", "simili": "#2B6CB0", "distanti": "#9CA3AF", "non confrontabili": "#D1D5DB"}
INK, INK_SOFT, GRID = "#1F2937", "#6B7280", "#E5E7EB"

def style(ax):
    ax.grid(True, color=GRID, linewidth=0.8); ax.set_axisbelow(True)
    ax.tick_params(colors=INK_SOFT, labelsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)

def build_profiles(d: pd.DataFrame, lo: float, hi: float, min_rows: int) -> pd.DataFrame:
    # Costruzione dei profili nella finestra italiana
    center, width = (lo + hi) / 2, max(hi - lo, 1e-9)
    w = d[(d["x"] >= lo) & (d["x"] <= hi)]
    rows = []
    for country, g in w.groupby("Country"):
        if len(g) < min_rows:
            continue
        r = g["res"].to_numpy()
        t = (g["x"].to_numpy() - center) / width          # esposizione in unita' di finestra
        tc = t - t.mean()
        offset = r.mean()
        slope = (tc * (r - offset)).sum() / ((tc ** 2).sum() + SLOPE_FLOOR * len(g))   # pendenza, ristretta rispetto alla finestra
        spread = np.std(r - offset - slope * tc)
        rows.append({"Country": country, "n_rows_window": len(g), "offset": offset, "slope": slope, "spread": spread})
    return pd.DataFrame(rows).set_index("Country")

def robust_z(M: pd.DataFrame) -> pd.DataFrame:
    med = M.median()
    mad = (M - med).abs().median()
    return (M - med) / mad

# Questa funzione non la usiamo perché k è fissato a 3 attualmente
# def choose_k(Z: np.ndarray, k_min: int, k_max: int) -> int:
#     best_k, best_s = k_min, -1.0
#     for k in range(k_min, min(k_max, len(Z) - 1) + 1):
#         s = silhouette_score(Z, AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(Z))
#         if s > best_s:
#             best_k, best_s = k, s
#     return best_k

def not_comparable_table(key: str, d: pd.DataFrame, res: pd.DataFrame, lo: float, hi: float, min_rows: int) -> pd.DataFrame:
    # Paesi non confrontabili: meno di min_rows righe nella finestra italiana, oppure esposizione sempre sotto o sopra la finestra
    in_win = d[(d["x"] >= lo) & (d["x"] <= hi)].groupby("Country").size()
    rng = d.groupby("Country")["x"].agg(["min", "max"])
    nc = res[res["group"] == "non confrontabili"].index
    t = pd.DataFrame(index=nc)
    t["n_rows_in_window"] = in_win.reindex(nc).fillna(0).astype(int)
    t["exposure_min"], t["exposure_max"] = rng.loc[nc, "min"], rng.loc[nc, "max"]

    def reason(c):
        n, mn, mx = t.loc[c, "n_rows_in_window"], t.loc[c, "exposure_min"], t.loc[c, "exposure_max"]
        if mx < lo:
            return "esposizione sempre sotto la finestra italiana"
        if mn > hi:
            return "esposizione sempre sopra la finestra italiana"
        return f"troppo poche righe nella finestra (meno di {min_rows})"
    t["motivo"] = [reason(c) for c in t.index]
    t.insert(0, "pollutant", key)
    t.insert(1, "window_min", lo)
    t.insert(2, "window_max", hi)
    t.index.name = "Country"
    return t.reset_index().sort_values(["motivo", "Country"])

def analyse(key: str, title: str, a, out_dir: Path):

    # Leggo i dati dell'inquinante
    d = pd.read_csv(a.data_dir / f"{key}.csv")
    d["x"] = d["Exposure Mean"]
    y = np.log1p(d["Burden Mean"]).to_numpy()
    lam = a.lam if a.lam is not None else DEFAULT_LAM[key]

    # Fitting della curva globale (spline penalizzata)
    model = PSpline(12, lam, monotone=False).fit(d[["x"]].to_numpy(), y)
    d["y"] = y
    d["res"] = y - model.predict(d[["x"]].to_numpy())   # Calcolo dei residui rispetto alla curva globale

    # Definisco la finestra italiana
    it = d[d["Country"] == REF]
    if it.empty:
        raise SystemExit(f"'{REF}' non presente in {key}.csv")
    w_ita = it["x"].max() - it["x"].min()
    lo = max(0.0, it["x"].min() - a.margin * w_ita)
    hi = it["x"].max() + a.margin * w_ita

    # Costruisco i profili dei paesi nella finestra italiana e calcolo le distanze dall'Italia
    prof = build_profiles(d, lo, hi, a.min_rows)
    all_countries = sorted(d["Country"].unique())
    Z = robust_z(prof[FEATURES]) * WEIGHTS
    dist = np.sqrt(((Z - Z.loc[REF]) ** 2).sum(axis=1))

    # Fisso il numero di cluster
    k = a.n_clusters # if a.n_clusters > 0 else choose_k(Z.to_numpy(), a.k_min, a.k_max)

    # Eseguo il clustering
    # Con il Ward linkage fondo i cluster in modo da minimizzare la dispersione interna al cluster
    labels = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(Z.to_numpy())
    sil = float(silhouette_score(Z.to_numpy(), labels))

    # Aggiorno il dataframe dei profili con i risultati del clustering
    prof["cluster"] = labels
    prof["distance_to_italy"] = dist
    prof["rank"] = prof["distance_to_italy"].rank(method="min").astype(int) - 1   # Italia = 0
    ita_cluster = prof.loc[REF, "cluster"]
    prof["group"] = np.where(prof["cluster"] == ita_cluster, "simili", "distanti")
    prof.loc[REF, "group"] = "Italia"
    prof["burden_factor_vs_global"] = np.exp(prof["offset"])

    res = pd.DataFrame(index=all_countries).join(prof)
    res["group"] = res["group"].fillna("non confrontabili") # I paesi fuori dalla window italiana sono "non confrontabili"
    res.insert(0, "pollutant", key)
    res.index.name = "Country"

    # Genero i grafici per dataset 
    plot(key, title, d, res, model, lo, hi, k, out_dir / f"cluster_{key}.png")

    # Tabelle di sintesi
    noncomp = not_comparable_table(key, d, res, lo, hi, a.min_rows)
    similar = prof[prof["group"] == "simili"].sort_values("distance_to_italy")
    distant = prof[prof["group"] == "distanti"]
    summary = {
        "inquinante": key, "unita_esposizione": d["Units"].iloc[0] if "Units" in d else "",
        "finestra_italiana_min": round(lo, 4), "finestra_italiana_max": round(hi, 4),
        "n_paesi_totali": len(all_countries), "n_confrontabili": len(prof),
        "n_non_confrontabili": len(noncomp),
        "quota_non_confrontabili": round(len(noncomp) / len(all_countries), 3),
        "n_cluster": k, "silhouette": round(sil, 3),
        "n_simili_all_italia": int(len(similar) - 0),
        "n_distanti": len(distant),
        "offset_italia": round(float(prof.loc[REF, "offset"]), 3),
        "fattore_burden_italia_vs_globale": round(float(np.exp(prof.loc[REF, "offset"])), 3),
        "distanza_media_simili": round(float(similar["distance_to_italy"].mean()), 3) if len(similar) else np.nan,
        "distanza_media_distanti": round(float(distant["distance_to_italy"].mean()), 3) if len(distant) else np.nan,
        "10_paesi_piu_vicini": "; ".join(prof.drop(index=REF).sort_values("distance_to_italy").index[:10]),
        "paesi_non_confrontabili": "; ".join(noncomp["Country"]),
    }
    cl = prof.groupby("cluster").agg(n_paesi=("offset", "size"), offset_medio=("offset", "mean"),
                                     pendenza_media=("slope", "mean"), dispersione_media=("spread", "mean"),
                                     distanza_media_da_italia=("distance_to_italy", "mean"))
    cl["fattore_burden_medio_vs_globale"] = np.exp(cl["offset_medio"])
    cl["contiene_italia"] = cl.index == ita_cluster
    cl["esempi_piu_vicini_all_italia"] = [
        "; ".join(g.sort_values("distance_to_italy").index[:6]) for _, g in prof.groupby("cluster")]
    cl.insert(0, "inquinante", key)
    cl = cl.reset_index().round(3)

    print(f"{key:6s} finestra italiana [{lo:.3g}, {hi:.3g}] | confrontabili: {len(prof)}/{len(all_countries)} | "
          f"non confrontabili: {len(noncomp)} | k={k} (silhouette {sil:.2f}) | "
          f"simili all'Italia: {int((res.group == 'simili').sum())} | distanti: {int((res.group == 'distanti').sum())} | "
          f"offset Italia {prof.loc[REF, 'offset']:+.2f} (x{np.exp(prof.loc[REF, 'offset']):.2f})")
    summary["n_simili_all_italia"] = int((res.group == "simili").sum())   # esclusa l'Italia stessa
    return res.reset_index(), summary, cl, noncomp


def plot(key, title, d, res, model, lo, hi, k, out):
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.4), dpi=150, gridspec_kw={"width_ratios": [1.25, 1.0, 0.9]})
    grp = res["group"]

    # Pannello 1: dati dentro la finestra italiana, colorati per gruppo
    ax = axes[0]
    pad = 0.15 * (hi - lo)
    win = d[(d["x"] >= lo - pad) & (d["x"] <= hi + pad)].copy()
    win["group"] = win["Country"].map(grp)
    for g in ["non confrontabili", "distanti", "simili"]:
        s = win[win["group"] == g]
        ax.scatter(s["x"], s["y"], s=9, color=COLORS[g], alpha=0.45 if g != "simili" else 0.6, linewidths=0,
                   label=f"{g} ({int((grp == g).sum())} paesi)")
    ita = d[d["Country"] == REF].sort_values("x")
    ax.plot(ita["x"], ita["y"], color=COLORS["Italia"], linewidth=0, marker="o", markersize=4.5,
            markeredgecolor="white", markeredgewidth=0.5, label="Italia", zorder=5)
    grid = np.linspace(lo - pad, hi + pad, 200).reshape(-1, 1)
    ax.plot(grid, model.predict(grid), color=INK, linestyle="--", linewidth=1.4, label="curva globale (tutti i paesi)", zorder=4)
    ax.axvspan(lo, hi, color="#FDE68A", alpha=0.25, linewidth=0)
    ax.set_xlim(lo - pad, hi + pad)
    ax.set_xlabel(f"Exposure Mean ({d['Units'].iloc[0]})" if "Units" in d else "Exposure Mean", fontsize=9, color=INK_SOFT)
    ax.set_ylabel("ln(1 + Burden Mean)", fontsize=9, color=INK_SOFT)
    ax.set_title("Relazione esposizione-burden nella finestra italiana", loc="left", fontsize=10.5, color=INK)
    ax.legend(fontsize=7.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, markerscale=1.6)
    style(ax)

    # Pannello 2: profile space per i paesi confrontabili
    ax = axes[1]
    comp = res.dropna(subset=["offset"])

    # Nel for escludiamo i non confrontabili
    for g in ["distanti", "simili"]:
        s = comp[comp["group"] == g]
        ax.scatter(s["offset"], s["slope"], s=26, color=COLORS[g], alpha=0.8, linewidths=0, label=g)
    ri = comp.loc[REF]
    ax.scatter([ri["offset"]], [ri["slope"]], s=190, marker="*", color=COLORS["Italia"], edgecolors="white", linewidths=0.8, zorder=5, label="Italia")
    ax.axvline(0, color=GRID, linewidth=1); ax.axhline(0, color=GRID, linewidth=1)
    ax.set_xlabel("offset = livello del burden rispetto alla curva globale (log)", fontsize=9, color=INK_SOFT)
    ax.set_ylabel("pendenza dei residui nella finestra", fontsize=9, color=INK_SOFT)
    ax.set_title(f"Profili dei paesi ({len(comp)} confrontabili, {k} cluster)", loc="left", fontsize=10.5, color=INK)
    ax.legend(fontsize=7.5, frameon=False, loc="best"); style(ax)

    # Pannello 3: i paesi piu' vicini e i piu' lontani dall'Italia nel profile space
    # La distanza e' calcolata come distanza euclidea pesata tra i profili standardizzati
    ax = axes[2]
    srt = comp.drop(index=REF).sort_values("distance_to_italy")
    sel = pd.concat([srt.head(12), srt.tail(6)])
    ypos = np.arange(len(sel))[::-1]
    ax.barh(ypos, sel["distance_to_italy"], color=[COLORS[g] for g in sel["group"]], height=0.72)
    ax.set_yticks(ypos); ax.set_yticklabels(sel.index, fontsize=7.5, color=INK)
    ax.axhline(len(sel) - 12 - 0.5, color=GRID, linewidth=1)
    ax.set_xlabel("distanza dall'Italia (profilo standardizzato)", fontsize=9, color=INK_SOFT)
    ax.set_title("12 paesi piu' simili e 6 piu' distanti", loc="left", fontsize=10.5, color=INK)
    style(ax); ax.grid(False, axis="y")

    fig.suptitle(f"{title}: paesi simili e distanti dall'Italia (zona gialla = intervallo di esposizione italiano)",
                 x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)

def main(a) -> None:
    a.out_dir.mkdir(parents=True, exist_ok=True)
    a.summary_dir.mkdir(parents=True, exist_ok=True)
    results = [analyse(k, t, a, a.out_dir) for k, t in POLLUTANTS]

    pd.concat([r[0] for r in results], ignore_index=True).to_csv(a.out_dir / "country_similarity.csv", index=False)
    pd.DataFrame([r[1] for r in results]).to_csv(a.summary_dir / "riepilogo_per_inquinante.csv", index=False)
    pd.concat([r[2] for r in results], ignore_index=True).to_csv(a.summary_dir / "riepilogo_per_cluster.csv", index=False)
    pd.concat([r[3] for r in results], ignore_index=True).to_csv(a.summary_dir / "paesi_non_confrontabili.csv", index=False)
    print(f"\nGrafici e CSV completo in: {a.out_dir.resolve()}")
    print(f"Riepiloghi in:             {a.summary_dir.resolve()}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("output_preprocessing"))
    ap.add_argument("--out-dir", type=Path, default=Path("clustering"))
    ap.add_argument("--summary-dir", type=Path, default=Path("riepilogo_clustering"), help="cartella dei CSV di sintesi")
    ap.add_argument("--margin", type=float, default=0.2, help="margine della finestra, come frazione dell'ampiezza dell'esposizione italiana")
    ap.add_argument("--min-rows", type=int, default=8, help="righe minime dentro la finestra per essere confrontabile")
    ap.add_argument("--n-clusters", type=int, default=3, help="numero di cluster, uguale per tutti gli inquinanti (0 = scelta automatica con la silhouette)")
    ap.add_argument("--k-min", type=int, default=3, help="solo con --n-clusters 0")
    ap.add_argument("--k-max", type=int, default=8, help="solo con --n-clusters 0")
    ap.add_argument("--lam", type=float, default=None, help="penalita' della curva globale (default: valore per inquinante)")
    main(ap.parse_args())
