"""
CarDealersPro — egyptian_cars.csv ingestion CLI.

A single, self-contained tool to turn the raw Kaggle dataset
(`egyptian_cars.csv`) into the ML-ready parquet that the price model trains on.

Usage (from the project root):

    python -m tools.ingest inspect
    python -m tools.ingest features
    python -m tools.ingest features --csv some.csv
    python -m tools.ingest sync

Output parquet schema (matches data_pipeline.load_from_parquet):
    - features          : list[float]  (7-dim, order = FEATURE_COLUMNS)
    - price_prediction  : float        (target price in EGP)
    - damage_score      : float        (0.0 placeholder until the damage model exists)

Artifacts (in ai_models/ai_artifacts/):
    - price_scaler.pt   : StandardScalerBundle (pure PyTorch, torch.save format)
    - price_encoders.pt : dict of sklearn LabelEncoders (torch.save/pickle format)

Why LabelEncoder and not a PyTorch alternative:
    - Categorical string -> integer mapping is a *data preprocessing* step,
      not a model component. sklearn's LabelEncoder is the industry standard,
      fully deterministic, and produces pickle-safe objects. A torch-native
      re-implementation would add ~40 lines of code for zero benefit.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import torch
from sklearn.preprocessing import LabelEncoder

from app.services.ml.data_pipeline import StandardScalerBundle

# --------------------------------------------------------------------------- #
# Constants (mirrored from app/services/ml/config.py — keep in sync!)
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FEATURE_COLUMNS = (
    "year",
    "mileage",
    "brand_enc",
    "model_enc",
    "fuel_type_enc",
    "transmission_enc",
    "body_type_enc",
)
TARGET_COLUMN = "price_prediction"
DAMAGE_COLUMN = "damage_score"

OUTPUT_DIR = PROJECT_ROOT / "data" / "optimized"
ARTIFACTS_DIR = PROJECT_ROOT / "ai_models" / "ai_artifacts"
DEFAULT_CSV = PROJECT_ROOT / "egyptian_cars.csv"

CSV_COLUMN_MAP = {
    "brand": "Brand",
    "model": "Model",
    "year": "Year",
    "mileage": "Kilometers",
    "fuel_type": "Fuel Type",
    "transmission": "Transmission Type",
    "body_type": "Body Type",
    "price": "Price_EGP",
}
CATEGORICAL_COLS = ("brand", "model", "fuel_type", "transmission", "body_type")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("CsvIngest")


# --------------------------------------------------------------------------- #
# Cleaning helpers
# --------------------------------------------------------------------------- #
def clean_number(value) -> float:
    """'EGP 140,000' -> 140000.0 (strip currency/commas, keep digits + dot)."""
    if pd.isna(value) or value in (None, ""):
        return 0.0
    cleaned = re.sub(r"[^\d.]", "", str(value))
    return float(cleaned) if cleaned else 0.0


def load_clean_cars(csv_path: Path) -> pd.DataFrame:
    """Read the raw CSV and return a normalized DataFrame keyed by feature names."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    logger.info("Loaded %d rows from %s", len(df), csv_path)

    clean = pd.DataFrame()
    for feature, raw_col in CSV_COLUMN_MAP.items():
        if raw_col not in df.columns:
            raise KeyError(
                f"Expected column {raw_col!r} in {csv_path.name}, "
                f"got {list(df.columns)}"
            )
        clean[feature] = df[raw_col]

    clean["price"] = clean["price"].apply(clean_number)
    clean["year"] = pd.to_numeric(clean["year"], errors="coerce").fillna(0).astype(int)
    clean["mileage"] = (
        pd.to_numeric(clean["mileage"], errors="coerce").fillna(0).astype(float)
    )
    for c in CATEGORICAL_COLS:
        clean[c] = clean[c].fillna("unknown").astype(str).str.strip().str.lower()

    clean = clean[clean["price"] > 0].reset_index(drop=True)
    logger.info("After cleaning: %d usable rows", len(clean))
    return clean


# --------------------------------------------------------------------------- #
# Feature engineering (pure PyTorch scaling, sklearn only for label encoding)
# --------------------------------------------------------------------------- #
def encode_features(df: pd.DataFrame):
    """
    Returns:
        X_scaled : np.ndarray (N, 7) float32 — standardized features.
        encoders : dict[str, LabelEncoder]    — for inference-time re-use.
        bundle   : StandardScalerBundle       — for inference-time re-use.
    """
    encoders = {c: LabelEncoder().fit(df[c]) for c in CATEGORICAL_COLS}
    encoded = pd.DataFrame(
        {f"{c}_enc": encoders[c].transform(df[c]) for c in CATEGORICAL_COLS}
    )

    numeric = pd.DataFrame(
        {
            "year": df["year"].astype(float),
            "mileage": df["mileage"].astype(float),
        }
    )

    # Column order MUST equal FEATURE_COLUMNS.
    X = (
        pd.concat([numeric, encoded], axis=1)[list(FEATURE_COLUMNS)]
        .values.astype(np.float32)
    )
    X_t = torch.from_numpy(X)

    # Fit the scaler on the training data. target_scaler=None because we
    # deliberately keep the target in raw EGP (better loss scaling for Huber).
    bundle = StandardScalerBundle.fit(X_t)
    X_scaled = bundle.transform_features(X_t).numpy().astype(np.float32)
    return X_scaled, encoders, bundle


def write_parquet(X_scaled: np.ndarray, prices: pd.Series, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final = pd.DataFrame(
        {
            "features": X_scaled.tolist(),
            TARGET_COLUMN: prices.astype(float).values,
            DAMAGE_COLUMN: np.zeros(len(prices)),
        }
    )
    pq.write_table(pa.Table.from_pandas(final), out_path)
    logger.info("Parquet written: %s (%d rows)", out_path, len(final))


def save_artifacts(encoders, bundle: StandardScalerBundle, artifacts_dir: Path) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    # torch.save uses pickle under the hood — safe for LabelEncoder objects.
    torch.save(encoders, artifacts_dir / "price_encoders.pt")
    # bundle.save() writes a self-describing dict with format_version + state_dicts.
    bundle.save(artifacts_dir / "price_scaler.pt")
    logger.info("Encoders + scaler bundle saved to %s", artifacts_dir)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_inspect(args) -> None:
    df = load_clean_cars(Path(args.csv))
    print("\n=== egyptian_cars.csv summary ===")
    print(f"Usable rows      : {len(df)}")
    print(f"Columns          : {list(df.columns)}")
    print(f"Price range      : {df['price'].min():,.0f} -> {df['price'].max():,.0f} EGP")
    print(f"Price mean       : {df['price'].mean():,.0f} EGP")
    print(f"Unique brands    : {df['brand'].nunique()}")
    print(f"Unique models    : {df['model'].nunique()}")
    print(f"Fuel types       : {sorted(df['fuel_type'].unique())}")
    print(f"Transmissions    : {sorted(df['transmission'].unique())}")
    print(f"Body types       : {sorted(df['body_type'].unique())}")
    print(f"Year range       : {df['year'].min()} -> {df['year'].max()}")
    print("\nMissing values (after clean):")
    print(df.isnull().sum().to_string())
    print("\nSample rows:")
    print(df.head(8).to_string())
    print()


def cmd_features(args) -> None:
    df = load_clean_cars(Path(args.csv))
    X, encoders, bundle = encode_features(df)
    write_parquet(X, df["price"], Path(args.out))
    save_artifacts(encoders, bundle, Path(args.artifacts))
    print(
        f"\nDone. feature_dim={X.shape[1]} (must equal {len(FEATURE_COLUMNS)}), "
        f"samples={X.shape[0]}"
    )
    print(f"Parquet   : {args.out}")
    print(f"Artifacts : {args.artifacts}\n")


def cmd_sync(args) -> None:
    """Push data/optimized/*.parquet into car_features table (needs .env + DB)."""
    import asyncio

    try:
        from core.data_sync import sync_parquet_to_db
    except Exception as exc:  # noqa: BLE001
        logger.error("DB sync requires DATABASE_URL + project deps: %s", exc)
        sys.exit(1)
    asyncio.run(sync_parquet_to_db())
    logger.info("Sync complete.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Use egyptian_cars.csv anytime.")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("inspect", help="Show a cleaned summary of the CSV.")
    pi.add_argument("--csv", default=str(DEFAULT_CSV), help="Path to the CSV file.")
    pi.set_defaults(func=cmd_inspect)

    pf = sub.add_parser("features", help="CSV -> ML-ready parquet + artifacts.")
    pf.add_argument("--csv", default=str(DEFAULT_CSV), help="Path to the CSV file.")
    pf.add_argument(
        "--out",
        default=str(OUTPUT_DIR / "car_features.parquet"),
        help="Parquet output path.",
    )
    pf.add_argument(
        "--artifacts", default=str(ARTIFACTS_DIR), help="Dir for encoders/scaler."
    )
    pf.set_defaults(func=cmd_features)

    ps = sub.add_parser("sync", help="Push parquet into car_features table (needs DB).")
    ps.set_defaults(func=cmd_sync)

    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)