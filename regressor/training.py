#!/usr/bin/env python3
"""Training di un regressore lineare, un modello per inquinante, dati in scala originale.

Per ogni inquinante (pm25, no2, ozone, hap):
  - GroupKFold a 5 fold, raggruppato per nazione, con ordine delle nazioni mescolato (seed fisso):
    le nazioni del fold di test non compaiono mai nel training;
  - feature: Exposure Mean; target: Burden Mean (nessuna trasformazione logaritmica);
  - metriche per fold sulla scala originale: MAE, RMSE, R^2.

Tutti i risultati vengono raccolti in un unico CSV.

Richiede scikit-learn >= 1.6 (GroupKFold con shuffle).

Uso:
  python train_linear.py --data-dir output_preprocessing --out results_linear.csv
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

POLLUTANTS = ["pm25", "no2", "ozone", "hap"]
FEATURE = "Exposure Mean"
TARGET = "Burden Mean"
GROUP = "Country"  # serve solo per costruire i fold, non entra nel modello
METRICS = ["MAE", "RMSE", "R2"]

def make_splitter(n_splits: int, seed: int) -> GroupKFold:
    try:
        return GroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    except TypeError as e:  # scikit-learn < 1.6
        raise SystemExit("Serve scikit-learn >= 1.6 (GroupKFold con shuffle). Aggiorna con: pip install -U scikit-learn") from e


def run_pollutant(name: str, df: pd.DataFrame, n_splits: int, seed: int) -> list[dict]:
    # i fold si costruiscono prima, usando Country; poi si tengono solo feature e target
    groups = df[GROUP].to_numpy()
    X = df[[FEATURE]].to_numpy()
    y = df[TARGET].to_numpy()

    rows = []
    for fold, (tr, te) in enumerate(make_splitter(n_splits, seed).split(X, y, groups), start=1):
        assert not set(groups[tr]) & set(groups[te]), f"{name} fold {fold}: nazioni sia in train sia in test"

        model = LinearRegression().fit(X[tr], y[tr])
        pred = model.predict(X[te])
        rows.append({
            "pollutant": name, "fold": str(fold),
            "n_train": len(tr), "n_test": len(te),
            "n_countries_test": len(set(groups[te])),
            "MAE": mean_absolute_error(y[te], pred),
            "RMSE": float(np.sqrt(mean_squared_error(y[te], pred))),
            "R2": r2_score(y[te], pred),
            "coef": float(model.coef_[0]), "intercept": float(model.intercept_),
            "n_pred_negative": int((pred < 0).sum()),
        })
    return rows

def main(data_dir: Path, out: Path, n_splits: int, seed: int) -> None:
    all_rows = []
    for p in POLLUTANTS:
        df = pd.read_csv(data_dir / f"{p}.csv", usecols=[GROUP, FEATURE, TARGET])
        rows = run_pollutant(p, df, n_splits, seed)
        all_rows += rows

        # riga di sintesi: media e deviazione standard sui fold
        r = pd.DataFrame(rows)
        for label, fn in (("mean", r[METRICS + ["coef", "intercept"]].mean), ("std", r[METRICS + ["coef", "intercept"]].std)):
            all_rows.append({"pollutant": p, "fold": label, **fn().to_dict()})

    res = pd.DataFrame(all_rows)
    res.insert(0, "model", "linear_regression")
    out.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out, index=False)

    summ = res[res.fold.isin(["mean", "std"])].pivot(index="pollutant", columns="fold", values=METRICS)
    print(f"Risultati salvati in: {out.resolve()}\n")
    for p in POLLUTANTS:
        s = res[(res.pollutant == p) & res.fold.isin(["mean", "std"])].set_index("fold")
        print(f"{p:6s}  " + "  ".join(f"{m}: {s.loc['mean', m]:.3f} (+/-{s.loc['std', m]:.3f})" for m in METRICS))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("output_preprocessing"), help="cartella con pm25.csv, no2.csv, ozone.csv, hap.csv")
    ap.add_argument("--out", type=Path, default=Path("results_linear.csv"), help="CSV con tutti i risultati")
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    main(a.data_dir, a.out, a.n_splits, a.seed)
