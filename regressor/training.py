#!/usr/bin/env python3
"""Regressione lineare con target ln(1 + Burden Mean), un modello per inquinante.

Per ogni inquinante (pm25, no2, ozone, hap):
  - si crea la colonna ln1p_burden = ln(1 + Burden Mean);
  - feature: Exposure Mean (scala originale); target di training: ln1p_burden;
  - GroupKFold a 5 fold per nazione (ordine mescolato, seed fisso): nel test solo nazioni mai viste;
  - le predizioni vengono riportate in scala originale con  y = exp(y_log) - 1;
  - metriche per fold: R2 e MAE in scala log; R2, MAE e RMSE in scala originale;
  - grafici: dati reali vs curva predetta, in scala originale e in scala log.

Richiede scikit-learn >= 1.6 e matplotlib.

Uso:
  python train_linear_log.py --data-dir output_preprocessing --out results_linear_log.csv --plot-dir plots_linear_log
  (opzionale) --save-datasets DIR  salva copie dei CSV con la colonna ln1p_burden aggiunta
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

POLLUTANTS = [("pm25", "PM2.5"), ("no2", "NO₂"), ("ozone", "Ozono"), ("hap", "HAP (inquinamento domestico)")]
FEATURE, TARGET, GROUP = "Exposure Mean", "Burden Mean", "Country"
TARGET_LOG = "ln1p_burden"
METRICS = ["R2_log", "MAE_log", "R2_orig", "MAE_orig", "RMSE_orig"]

POINT_COLOR, CURVE_COLOR, FOLD_COLOR = "#9CA3AF", "#C2410C", "#2B6CB0"
INK, INK_SOFT, GRID = "#1F2937", "#6B7280", "#E5E7EB"

def make_splitter(n_splits: int, seed: int) -> GroupKFold:
    try:
        return GroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    except TypeError as e:  # scikit-learn < 1.6
        raise SystemExit("Serve scikit-learn >= 1.6 (GroupKFold con shuffle). Aggiorna con: pip install -U scikit-learn") from e

def to_original(y_log):
    """Riporta in scala originale: e^(y_log) - 1."""
    return np.expm1(y_log)

def run_pollutant(name: str, df: pd.DataFrame, n_splits: int, seed: int):
    groups = df[GROUP].to_numpy()
    X = df[[FEATURE]].to_numpy()
    y_orig = df[TARGET].to_numpy()
    y_log = df[TARGET_LOG].to_numpy()

    rows, fold_models = [], []
    for fold, (tr, te) in enumerate(make_splitter(n_splits, seed).split(X, y_log, groups), start=1):
        assert not set(groups[tr]) & set(groups[te]), f"{name} fold {fold}: nazioni sia in train sia in test"

        model = LinearRegression().fit(X[tr], y_log[tr])      # training sul target in log
        pred_log = model.predict(X[te])
        pred_orig = to_original(pred_log)                     # riconversione: e^y - 1
        fold_models.append(model)

        rows.append({
            "pollutant": name, "fold": str(fold),
            "n_train": len(tr), "n_test": len(te), "n_countries_test": len(set(groups[te])),
            "R2_log": r2_score(y_log[te], pred_log),
            "MAE_log": mean_absolute_error(y_log[te], pred_log),
            "R2_orig": r2_score(y_orig[te], pred_orig),
            "MAE_orig": mean_absolute_error(y_orig[te], pred_orig),
            "RMSE_orig": float(np.sqrt(mean_squared_error(y_orig[te], pred_orig))),
            "coef_log": float(model.coef_[0]), "intercept_log": float(model.intercept_),
            "n_pred_negative_orig": int((pred_orig < 0).sum()),
        })
    return rows, fold_models

def plot_curves(data: dict, scale: str, out: Path) -> None:
    """scale = 'orig' (DALY) oppure 'log' (ln(1+DALY)). Punti reali + curva predetta."""
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), dpi=150)
    for ax, (key, title) in zip(axes.ravel(), POLLUTANTS):
        df, fold_models, full_model = data[key]
        x = df[FEATURE].to_numpy()
        grid = np.linspace(x.min(), x.max(), 300).reshape(-1, 1)
        y_real = df[TARGET].to_numpy() if scale == "orig" else df[TARGET_LOG].to_numpy()

        def curve(m):
            p = m.predict(grid)
            return to_original(p) if scale == "orig" else p

        ax.scatter(x, y_real, s=8, color=POINT_COLOR, alpha=0.35, linewidths=0, label="dati reali")
        for i, m in enumerate(fold_models):
            ax.plot(grid, curve(m), color=FOLD_COLOR, alpha=0.5, linewidth=0.9,
                    label="curva dei 5 modelli di fold" if i == 0 else None)
        c_full = curve(full_model)
        ax.plot(grid, c_full, color=CURVE_COLOR, linewidth=2.2, label="curva predetta (modello su tutti i dati)")

        ymax, ymin = float(y_real.max()), float(min(y_real.min(), c_full.min(), 0))
        ax.set_ylim(ymin - 0.03 * ymax, 1.05 * ymax)  # una curva esponenziale puo' uscire dal grafico: la tagliamo
        unit = df["Units"].iloc[0] if "Units" in df.columns else ""
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.set_xlabel(f"Exposure Mean ({unit})" if unit else "Exposure Mean", fontsize=9, color=INK_SOFT)
        ax.set_ylabel("Burden Mean (DALY)" if scale == "orig" else "ln(1 + Burden Mean)", fontsize=9, color=INK_SOFT)
        ax.grid(True, color=GRID, linewidth=0.8); ax.set_axisbelow(True)
        ax.tick_params(colors=INK_SOFT, labelsize=8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(GRID)
        ax.legend(fontsize=7, frameon=False, loc="upper left")

    label = "scala originale (DALY)" if scale == "orig" else "scala logaritmica, ln(1 + DALY)"
    fig.suptitle(f"Dati reali vs curva predetta, {label}", x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out); plt.close(fig)

def main(data_dir: Path, out: Path, plot_dir: Path, n_splits: int, seed: int, save_datasets: Path | None) -> None:
    all_rows, plot_data = [], {}
    for p, _ in POLLUTANTS:
        df = pd.read_csv(data_dir / f"{p}.csv")
        df[TARGET_LOG] = np.log1p(df[TARGET])                  # colonna ln(1 + burden_mean)
        if save_datasets is not None:
            save_datasets.mkdir(parents=True, exist_ok=True)
            df.to_csv(save_datasets / f"{p}.csv", index=False)

        rows, fold_models = run_pollutant(p, df[[GROUP, FEATURE, TARGET, TARGET_LOG] + (["Units"] if "Units" in df else [])], n_splits, seed)
        all_rows += rows

        r = pd.DataFrame(rows)
        cols = METRICS + ["coef_log", "intercept_log"]
        all_rows.append({"pollutant": p, "fold": "mean", **r[cols].mean().to_dict()})
        all_rows.append({"pollutant": p, "fold": "std", **r[cols].std().to_dict()})

        full_model = LinearRegression().fit(df[[FEATURE]].to_numpy(), df[TARGET_LOG].to_numpy())
        plot_data[p] = (df, fold_models, full_model)

    res = pd.DataFrame(all_rows)
    res.insert(0, "model", "linear_regression_ln1p_target")
    out.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out, index=False)

    plot_curves(plot_data, "orig", plot_dir / "curves_original_scale.png")
    plot_curves(plot_data, "log", plot_dir / "curves_log_scale.png")

    print(f"Risultati salvati in: {out.resolve()}")
    print(f"Grafici salvati in:   {plot_dir.resolve()}\n")
    for p, _ in POLLUTANTS:
        s = res[(res.pollutant == p) & res.fold.isin(["mean", "std"])].set_index("fold")
        print(f"{p:6s} " + "  ".join(f"{m}: {s.loc['mean', m]:.3f} (+/-{s.loc['std', m]:.3f})" for m in METRICS))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("output_preprocessing"))
    ap.add_argument("--out", type=Path, default=Path("results_linear_log.csv"))
    ap.add_argument("--plot-dir", type=Path, default=Path("plots_linear_log"))
    ap.add_argument("--save-datasets", type=Path, default=None, help="cartella dove salvare i CSV con la colonna ln1p_burden")
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    main(a.data_dir, a.out, a.plot_dir, a.n_splits, a.seed, a.save_datasets)
