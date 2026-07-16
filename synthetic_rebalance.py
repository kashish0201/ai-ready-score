"""
Synthetic minority-class rebalancing for AI-Ready Score.

Drop-in module. Main function:

    rebalanced_df, report = rebalance_with_synthetic(df, target_col)

Works on ANY tabular dataframe and ANY categorical target column.
Generates synthetic minority-class rows with SDV to reach a healthy
class ratio, then you can re-run your quality checks to see the score improve.
"""

import numpy as np
import pandas as pd

from sdv.metadata import Metadata
from sdv.single_table import GaussianCopulaSynthesizer


def rebalance_with_synthetic(df, target_col, target_ratio=1.5, verbose=False):
    """
    Rebalance an imbalanced dataset by generating synthetic minority rows.

    Parameters
    ----------
    df : pd.DataFrame
        The full dataset.
    target_col : str
        Name of the target/label column to balance.
    target_ratio : float
        Desired majority:minority ratio after rebalancing (e.g. 1.5 means the
        majority class is at most 1.5x the minority class). Must be >= 1.
    verbose : bool
        If True, print progress.

    Returns
    -------
    rebalanced_df : pd.DataFrame
        Original data + synthetic minority rows (shuffled).
    report : dict
        What happened: counts, ratios, how many rows were generated.
    """

    # --- Guard clauses: fail gracefully on bad input --------------------
    if target_col is None or target_col not in df.columns:
        return df.copy(), {"status": "skipped",
                           "reason": "no valid target column provided"}

    if target_ratio < 1:
        target_ratio = 1.0

    counts = df[target_col].value_counts(dropna=False)

    if len(counts) < 2:
        return df.copy(), {"status": "skipped",
                           "reason": "target has fewer than 2 classes"}

    # --- Identify majority and minority classes -------------------------
    majority_class = counts.index[0]
    minority_class = counts.index[-1]
    majority_count = int(counts.iloc[0])
    minority_count = int(counts.iloc[-1])

    current_ratio = majority_count / minority_count

    # If already balanced enough, do nothing.
    if current_ratio <= target_ratio:
        return df.copy(), {
            "status": "skipped",
            "reason": "already balanced",
            "current_ratio": round(current_ratio, 2),
        }

    # --- Decide how many synthetic rows to generate ---------------------
    # We want: majority_count / (minority_count + N) == target_ratio
    # Solve for N:
    desired_minority = int(np.ceil(majority_count / target_ratio))
    n_to_generate = desired_minority - minority_count

    if n_to_generate <= 0:
        return df.copy(), {"status": "skipped", "reason": "nothing to generate"}

    # --- Train SDV on the minority class only ---------------------------
    minority_df = df[df[target_col] == minority_class].copy()

    # SDV needs at least a couple of rows to learn anything.
    if len(minority_df) < 2:
        return df.copy(), {
            "status": "failed",
            "reason": "not enough minority samples to learn from (need >= 2)",
            "minority_count": minority_count,
        }

    if verbose:
        print(f"Minority class '{minority_class}': {minority_count} rows")
        print(f"Generating {n_to_generate} synthetic rows...")

    # SDV models features, so we let it learn the whole minority row
    # (target column included; we re-stamp the label afterward to be safe).
    metadata = Metadata.detect_from_dataframe(minority_df)

    synthesizer = GaussianCopulaSynthesizer(metadata)
    synthesizer.fit(minority_df)

    synthetic = synthesizer.sample(num_rows=n_to_generate)

    # Force the label so every synthetic row is unambiguously the minority class.
    synthetic[target_col] = minority_class

    # --- Combine, shuffle, and build the report -------------------------
    rebalanced_df = pd.concat([df, synthetic], ignore_index=True)
    rebalanced_df = rebalanced_df.sample(frac=1, random_state=42).reset_index(drop=True)

    new_counts = rebalanced_df[target_col].value_counts(dropna=False)
    new_ratio = new_counts.iloc[0] / new_counts.iloc[-1]

    report = {
        "status": "success",
        "target_column": target_col,
        "minority_class": str(minority_class),
        "majority_class": str(majority_class),
        "rows_before": int(len(df)),
        "rows_after": int(len(rebalanced_df)),
        "synthetic_rows_added": int(n_to_generate),
        "ratio_before": round(current_ratio, 2),
        "ratio_after": round(float(new_ratio), 2),
        "target_ratio": target_ratio,
    }

    return rebalanced_df, report