#!/usr/bin/env python3
"""
Pre-processing del dataset air quality + health.
L'output è un dataset per ogni inquinante, debitamente processato.

Passi:
  1. rimozione delle colonne-refuso dei salvataggi multipli ("Unnamed: ...");
  2. rimozione delle righe WORLD (aggregato mondiale);
  3. rimozione delle righe con Cause_Name diversa da "All causes";
  4. rimozione delle righe con esposizione NO2 negativa;
  5. controlli di integrita';
  6. un CSV per ciascun inquinante + manifest.json.

Uso:
  python preprocessing.py --src dataset/per_nation_air_quality_health_dataset.csv --outdir output_preprocessing
"""
import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

KEEP_CAUSE = "All causes"
WORLD_ISO3 = "WORLD"
KEY = ["Country", "Year"]

def main(src: Path, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(src)
    steps = [{"passo": "righe in input", "righe": len(df)}]

    # Drop delle colonne refuso
    junk = [c for c in df.columns if c.startswith("Unnamed")]
    df = df.drop(columns=junk)

    # Rimozione aggregati mondiali
    n0 = len(df)
    df = df[df["ISO3"] != WORLD_ISO3]
    steps.append({"passo": "rimosse righe WORLD", "righe_rimosse": n0 - len(df), "righe": len(df)})

    # Rimozione delle righe con cause diverse da "All causes"
    n0 = len(df)
    df = df[df["Cause_Name"] == KEEP_CAUSE]
    steps.append({"passo": f"tenuto solo Cause_Name == '{KEEP_CAUSE}'",
                  "righe_rimosse": n0 - len(df), "righe": len(df)})

    # Rimozione esposizioni NO2 negative
    neg = (df["Pollutant"] == "no2") & (df["Exposure Mean"] < 0)
    dropped_no2 = df.loc[neg, ["Country", "Year"]]
    df = df[~neg].reset_index(drop=True)
    steps.append({"passo": "rimosse righe NO2 con esposizione negativa",
                  "righe_rimosse": int(neg.sum()), "righe": len(df)})

    # Recap controlli di integrita'
    checks = {}

    # Funzione per controlli di integrita'
    def check(name: str, condition: bool) -> None:
        checks[name] = bool(condition)
        assert condition, f"Controllo fallito: {name}"

    check("nessun NaN nelle colonne rimaste", df.isna().sum().sum() == 0)
    check("nessuna riga WORLD", (df["ISO3"] != WORLD_ISO3).all())
    check("solo 'All causes'", (df["Cause_Name"] == KEEP_CAUSE).all())
    check("esposizione >= 0 per tutti gli inquinanti", (df["Exposure Mean"] >= 0).all())
    check("burden > 0", (df["Burden Mean"] > 0).all())
    check("anni compresi tra 1990 e 2020", df["Year"].between(1990, 2020).all())
    check("Country <-> ISO3 in corrispondenza 1:1",
          df.groupby("Country")["ISO3"].nunique().max() == 1
          and df.groupby("ISO3")["Country"].nunique().max() == 1)
    check("nessun duplicato (inquinante, paese, anno)",
          not df.duplicated(["Pollutant"] + KEY).any())
    for col in ["Units", "Measure", "Metric"]:
        check(f"{col} univoca per inquinante", df.groupby("Pollutant")[col].nunique().max() == 1)

    # Creazione di un CSV per inquinante
    pollutants = sorted(df["Pollutant"].unique())
    manifest_pollutants = {}
    for p in pollutants:
        d = df[df["Pollutant"] == p].sort_values(KEY).reset_index(drop=True)
        fname = f"{p}.csv"
        d.to_csv(outdir / fname, index=False)
        manifest_pollutants[p] = {
            "file": fname,
            "righe": len(d),
            "paesi": int(d["Country"].nunique()),
            "anni": [int(d["Year"].min()), int(d["Year"].max())],
            "unita_esposizione": d["Units"].iloc[0],
            "esposizione_min_max": [float(d["Exposure Mean"].min()), float(d["Exposure Mean"].max())],
            "burden_min_max": [float(d["Burden Mean"].min()), float(d["Burden Mean"].max())],
        }
    check("somma righe dei file == righe del dataset pulito",
          sum(v["righe"] for v in manifest_pollutants.values()) == len(df))

    # Dettagli
    per_country = dropped_no2.groupby("Country")["Year"].agg(["count", "min", "max"])
    all_countries = set(df["Country"])
    no2_left = set(df.loc[df["Pollutant"] == "no2", "Country"])
    manifest = {
        "creato_il": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ambiente": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "input": {"file": src.name},
        "colonne_refuso_rimosse": junk,
        "colonne_output": list(df.columns),
        "passi": steps,
        "controlli_integrita": checks,
        "inquinanti": manifest_pollutants,
        "no2_esposizione_negativa": {
            "righe_rimosse": int(neg.sum()),
            "paesi_coinvolti": {c: {"righe": int(r["count"]), "primo_anno": int(r["min"]), "ultimo_anno": int(r["max"])}
                                for c, r in per_country.iterrows()},
            "paesi_completamente_assenti_da_no2": sorted(all_countries - no2_left),
        },
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    print(f"OK. File scritti in: {outdir.resolve()}")
    for s in steps:
        print(f"  {s['passo']}: {s['righe']} righe" + (f" (-{s['righe_rimosse']})" if "righe_rimosse" in s else ""))
    for p, v in manifest_pollutants.items():
        print(f"  {v['file']:<10} {v['righe']:>5} righe, {v['paesi']} paesi, unita': {v['unita_esposizione']}")
    print(f"  controlli superati: {sum(checks.values())}/{len(checks)}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, required=True, help="CSV originale")
    ap.add_argument("--outdir", type=Path, default=Path("output_preprocessing"), help="cartella di output")
    a = ap.parse_args()
    main(a.src, a.outdir)
