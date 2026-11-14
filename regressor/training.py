#!/usr/bin/env python3
"""
GAM a una feature (spline penalizzata, P-spline) con vincolo di monotonia opzionale.

Modello, un'istanza per inquinante:   ln(1 + Burden Mean) = f(Exposure Mean)
f e' una spline cubica in base B: f(x) = sum_k theta_k * B_k(x).
vincolo opzionale di monotonia crescente: theta_1 <= theta_2 <= ... <= theta_K.

Validazione: GroupKFold a 5 fold per nazione (ordine mescolato, seed fisso).
Il parametro di smoothness lambda viene scelto, dentro ogni fold di training, con una seconda
GroupKFold per nazione (nested CV), scegliendo il lambda con errore quadratico minimo in scala log.

Metriche per fold: R2 e MAE in scala log; R2, MAE e RMSE in scala originale.
Grafici: dati reali vs curve predette (varianti a confronto), scala originale e scala log.

Uso:
  python training.py --data-dir output_preprocessing --out results_gam.csv --plot-dir plots_gam
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import SplineTransformer

POLLUTANTS = [("pm25", "PM2.5"), ("no2", "NO₂"), ("ozone", "Ozono"), ("hap", "HAP (inquinamento domestico)")]
FEATURE, TARGET, GROUP = "Exposure Mean", "Burden Mean", "Country"
TARGET_LOG = "ln1p_burden"
METRICS = ["R2_log", "MAE_log", "R2_orig", "MAE_orig", "RMSE_orig"]
VARIANTS = {"free": False, "monotone": True}
VARIANT_LABEL = {"free": "GAM senza vincoli", "monotone": "GAM monotona crescente"}
VARIANT_COLOR = {"free": "#2B6CB0", "monotone": "#C2410C"}

POINT_COLOR = "#9CA3AF"
INK, INK_SOFT, GRID = "#1F2937", "#6B7280", "#E5E7EB"

class PSpline:
    """Spline penalizzata (P-spline): minimi quadrati penalizzati, con monotonia opzionale."""

    def __init__(self, n_basis: int = 12, lam: float = 1.0, monotone: bool = False):
        self.n_basis, self.lam, self.monotone = n_basis, lam, monotone

    def fit(self, X: np.ndarray, y: np.ndarray) -> "PSpline":
        x = X[:, 0]
        # nodi ai quantili dell'esposizione (piu' fitti dove ci sono piu' dati), duplicati eliminati
        knots = np.unique(np.quantile(x, np.linspace(0, 1, self.n_basis - 2)))
        self.st_ = SplineTransformer(degree=3, knots=knots.reshape(-1, 1),
                                     extrapolation="constant", include_bias=True).fit(X)
        B = self.st_.transform(X)
        K = B.shape[1]
        D2 = np.diff(np.eye(K), n=2, axis=0)
        sqrt_lam = np.sqrt(self.lam)

        if not self.monotone:
            # soluzione in forma chiusa
            A = B.T @ B + self.lam * (D2.T @ D2) + 1e-10 * np.eye(K)
            self.theta_ = np.linalg.solve(A, B.T @ y)
        else:
            T = np.tril(np.ones((K, K)))
            A = np.vstack([B @ T, sqrt_lam * (D2 @ T)])
            b = np.concatenate([y, np.zeros(D2.shape[0])])
            lower = np.r_[-np.inf, np.zeros(K - 1)]
            sol = lsq_linear(A, b, bounds=(lower, np.full(K, np.inf)), method="bvls")
            self.theta_ = T @ sol.x
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.st_.transform(X) @ self.theta_

def make_splitter(n_splits: int, seed: int) -> GroupKFold:
    try:
        return GroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    except TypeError as e:  # scikit-learn < 1.6
        raise SystemExit("Serve scikit-learn >= 1.6 (GroupKFold con shuffle). Aggiorna con: pip install -U scikit-learn") from e

def to_original(y_log):
    """Riporta in scala originale: e^(y_log) - 1."""
    return np.expm1(y_log)

def select_lambda(X, y, groups, monotone, n_basis, lambdas, n_splits, seed) -> float:
    """CV interna per nazione: sceglie lam con MSE minimo in scala log."""
    inner = make_splitter(n_splits, seed)
    scores = np.zeros(len(lambdas))
    for tr, te in inner.split(X, y, groups):
        for i, lam in enumerate(lambdas):
            m = PSpline(n_basis, lam, monotone).fit(X[tr], y[tr])
            scores[i] += mean_squared_error(y[te], m.predict(X[te]))
    return float(lambdas[int(np.argmin(scores))])

def run_pollutant(name, df, variant, n_splits, seed, n_basis, lambdas):
    monotone = VARIANTS[variant]
    groups = df[GROUP].to_numpy()
    X = df[[FEATURE]].to_numpy()
    y_orig, y_log = df[TARGET].to_numpy(), df[TARGET_LOG].to_numpy()
    grid = np.linspace(X.min(), X.max(), 400).reshape(-1, 1)

    rows = []
    for fold, (tr, te) in enumerate(make_splitter(n_splits, seed).split(X, y_log, groups), start=1):
        assert not set(groups[tr]) & set(groups[te]), f"{name} fold {fold}: nazioni sia in train sia in test"

        lam = select_lambda(X[tr], y_log[tr], groups[tr], monotone, n_basis, lambdas, n_splits, seed)
        model = PSpline(n_basis, lam, monotone).fit(X[tr], y_log[tr])
        pred_log = model.predict(X[te])
        pred_orig = to_original(pred_log)
        curve = model.predict(grid)

        rows.append({
            "pollutant": name, "variant": variant, "fold": str(fold),
            "n_train": len(tr), "n_test": len(te), "n_countries_test": len(set(groups[te])),
            "R2_log": r2_score(y_log[te], pred_log),
            "MAE_log": mean_absolute_error(y_log[te], pred_log),
            "R2_orig": r2_score(y_orig[te], pred_orig),
            "MAE_orig": mean_absolute_error(y_orig[te], pred_orig),
            "RMSE_orig": float(np.sqrt(mean_squared_error(y_orig[te], pred_orig))),
            "lambda": lam,
            "max_decrease_log": float(max(0.0, -np.diff(curve).min())),  # 0 = curva mai decrescente
            "n_pred_negative_orig": int((pred_orig < 0).sum()),
        })
    return rows

def plot_curves(data: dict, scale: str, out: Path, variants: list) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), dpi=150)
    for ax, (key, title) in zip(axes.ravel(), POLLUTANTS):
        df, models = data[key]
        x = df[FEATURE].to_numpy()
        grid = np.linspace(x.min(), x.max(), 400).reshape(-1, 1)
        y_real = df[TARGET].to_numpy() if scale == "orig" else df[TARGET_LOG].to_numpy()
        ax.scatter(x, y_real, s=8, color=POINT_COLOR, alpha=0.35, linewidths=0, label="dati reali")
        curves = []
        for v in variants:
            p = models[v].predict(grid)
            c = to_original(p) if scale == "orig" else p
            curves.append(c)
            ax.plot(grid, c, color=VARIANT_COLOR[v], linewidth=2.2, label=VARIANT_LABEL[v] + " (modello su tutti i dati)")
        ymax = float(y_real.max()); ymin = float(min(y_real.min(), *(c.min() for c in curves), 0))
        ax.set_ylim(ymin - 0.03 * ymax, 1.05 * ymax)
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
    fig.suptitle(f"GAM (spline penalizzata): dati reali vs curva predetta, {label}", x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out); plt.close(fig)

def main(a) -> None:
    lambdas = np.array([float(v) for v in a.lambdas.split(",")])
    variants = a.variants
    all_rows, plot_data = [], {}
    for p, _ in POLLUTANTS:
        df = pd.read_csv(a.data_dir / f"{p}.csv")
        df[TARGET_LOG] = np.log1p(df[TARGET])
        sub = df[[GROUP, FEATURE, TARGET, TARGET_LOG] + (["Units"] if "Units" in df else [])]

        models = {}
        for v in variants:
            rows = run_pollutant(p, sub, v, a.n_splits, a.seed, a.n_basis, lambdas)
            all_rows += rows
            r = pd.DataFrame(rows)
            cols = METRICS + ["lambda", "max_decrease_log"]
            all_rows.append({"pollutant": p, "variant": v, "fold": "mean", **r[cols].mean().to_dict()})
            all_rows.append({"pollutant": p, "variant": v, "fold": "std", **r[cols].std().to_dict()})
            # modello su tutti i dati, solo per il grafico (lam = mediana dei lam scelti nei fold)
            lam_full = float(np.median(r["lambda"]))
            models[v] = PSpline(a.n_basis, lam_full, VARIANTS[v]).fit(sub[[FEATURE]].to_numpy(), sub[TARGET_LOG].to_numpy())
        plot_data[p] = (sub, models)

    res = pd.DataFrame(all_rows)
    res.insert(0, "model", f"gam_pspline_{a.n_basis}basis_ln1p_target")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(a.out, index=False)
    plot_curves(plot_data, "orig", a.plot_dir / "curves_original_scale.png", variants)
    plot_curves(plot_data, "log", a.plot_dir / "curves_log_scale.png", variants)

    print(f"Risultati salvati in: {a.out.resolve()}")
    print(f"Grafici salvati in:   {a.plot_dir.resolve()}\n")
    for p, _ in POLLUTANTS:
        for v in variants:
            s = res[(res.pollutant == p) & (res.variant == v) & res.fold.isin(["mean", "std"])].set_index("fold")
            print(f"{p:6s} {v:9s} " + "  ".join(f"{m}: {s.loc['mean', m]:.3f} (+/-{s.loc['std', m]:.3f})" for m in METRICS))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("output_preprocessing"))
    ap.add_argument("--out", type=Path, default=Path("results_gam.csv"))
    ap.add_argument("--plot-dir", type=Path, default=Path("plots_gam"))
    ap.add_argument("--variants", nargs="+", choices=list(VARIANTS), default=["free", "monotone"])
    ap.add_argument("--n-basis", type=int, default=12, help="numero di funzioni di base della spline")
    ap.add_argument("--lambdas", default="0.01,0.1,1,10,100,1000,10000,100000", help="griglia del parametro di lisciamento")
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    main(ap.parse_args())
