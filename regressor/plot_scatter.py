#!/usr/bin/env python3
"""
Scatter plot con asse x = Exposure Mean (feature),
asse y = Burden Mean (target) su un sottoinsieme casuale dei punti.

Legge i CSV prodotti da preprocess_dataset.py (uno per inquinante) e disegna
un pannello per inquinante. 
Le unita' di misura dell'esposizione sono diverse per ogni inquinante,
pertanto non si possono sovrapporre sullo stesso asse x.

Uso:
  python plot_scatter.py --data-dir output_preprocessing --n 6000 --log-target --seed 42 --out ./images/scatter_originale.png
"""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")  # nessuna finestra: salva direttamente su file
import matplotlib.pyplot as plt
import pandas as pd

POLLUTANTS = [("pm25", "PM2.5"), ("no2", "NO₂"), ("ozone", "Ozono"), ("hap", "HAP (inquinamento domestico)")]
POINT_COLOR = "#2B6CB0"
INK, INK_SOFT, GRID = "#1F2937", "#6B7280", "#E5E7EB"

def main(data_dir: Path, n: int, seed: int, out: Path, log_target: bool) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), dpi=150)
    fig.patch.set_facecolor("white")

    for ax, (key, title) in zip(axes.ravel(), POLLUTANTS):
        df = pd.read_csv(data_dir / f"{key}.csv")
        sub = df.sample(n=min(n, len(df)), random_state=seed)  # sottoinsieme casuale riproducibile
        unit = df["Units"].iloc[0]

        ax.scatter(sub["Exposure Mean"], sub["Burden Mean"],
                   s=14, color=POINT_COLOR, alpha=0.45, linewidths=0)
        if log_target:
            ax.set_yscale("log")
        ax.set_title(f"{title}  (n = {len(sub)} di {len(df)})", loc="left", fontsize=11, color=INK)
        ax.set_xlabel(f"Exposure Mean ({unit})", fontsize=9, color=INK_SOFT)
        ax.set_ylabel("Burden Mean (DALY)", fontsize=9, color=INK_SOFT)
        ax.set_facecolor("white")
        ax.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(colors=INK_SOFT, labelsize=8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)

    scala = "target in scala logaritmica" if log_target else "scala originale"
    fig.suptitle(f"Esposizione vs burden, {scala} (sottoinsieme casuale)",
                 x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out)
    print(f"Grafico salvato in: {out.resolve()}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("output_preprocessing"), help="cartella per prendere i datasets")
    ap.add_argument("--n", type=int, default=6000, help="punti casuali per inquinante")
    ap.add_argument("--seed", type=int, default=42, help="seed del campionamento")
    ap.add_argument("--out", type=Path, default=Path("./images/scatter_originale.png"), help="file immagine di output")
    ap.add_argument("--log-target", action="store_true", help="mostra il burden in scala logaritmica")
    a = ap.parse_args()
    main(a.data_dir, a.n, a.seed, a.out, a.log_target)
