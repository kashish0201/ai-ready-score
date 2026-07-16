"""Streamlit-free quality checks and scoring for AI-Ready Score."""

import numpy as np
import pandas as pd


def check_missing_values(df):
    issues = []

    for column in df.columns:
        missing_count = df[column].isna().sum()
        missing_pct = float(missing_count / len(df) * 100)

        if missing_pct == 0:
            continue

        if missing_pct > 20:
            severity = "high"
        elif missing_pct > 5:
            severity = "medium"
        else:
            severity = "low"

        issue = {
            "check": "missing_values",
            "column": column,
            "severity": severity,
            "metric": "missing_pct",
            "value": missing_pct,
            "explanation": f"Column '{column}' has {missing_pct:.2f}% missing values.",
            "recommendation": "Consider imputing this column or checking why values are missing."
        }

        issues.append(issue)

    return issues


def check_duplicate_rows(df):
    issues = []

    duplicate_count = df.duplicated().sum()
    duplicate_pct = float(duplicate_count / len(df) * 100)

    if duplicate_pct == 0:
        return issues

    if duplicate_pct > 10:
        severity = "high"
    elif duplicate_pct > 2:
        severity = "medium"
    else:
        severity = "low"

    issue = {
        "check": "duplicate_rows",
        "column": "dataset",
        "severity": severity,
        "metric": "duplicate_pct",
        "value": duplicate_pct,
        "explanation": f"The dataset has {duplicate_pct:.2f}% duplicate rows.",
        "recommendation": "Consider removing duplicate rows before training an AI model."
    }

    issues.append(issue)

    return issues


def check_constant_columns(df):
    issues = []

    for column in df.columns:
        unique_count = df[column].nunique(dropna=False)

        if unique_count > 1:
            continue

        issue = {
            "check": "constant_column",
            "column": column,
            "severity": "high",
            "metric": "unique_count",
            "value": int(unique_count),
            "explanation": f"Column '{column}' has only one unique value, so it does not add useful information for modeling.",
            "recommendation": "Consider dropping this column before training an AI model."
        }

        issues.append(issue)

    return issues


def check_near_constant_columns(df, threshold=0.95):
    issues = []

    for column in df.columns:
        unique_count = df[column].nunique(dropna=False)

        if unique_count <= 1:
            continue

        value_counts = df[column].value_counts(dropna=False)
        top_count = value_counts.iloc[0]
        dominant_ratio = float(top_count / len(df))

        if dominant_ratio < threshold:
            continue

        if dominant_ratio >= 0.99:
            severity = "high"
        else:
            severity = "medium"

        issue = {
            "check": "near_constant_column",
            "column": column,
            "severity": severity,
            "metric": "dominant_value_ratio",
            "value": dominant_ratio,
            "explanation": f"Column '{column}' is dominated by one value in {dominant_ratio * 100:.2f}% of rows.",
            "recommendation": "Consider removing this column if it does not provide useful signal for modeling."
        }

        issues.append(issue)

    return issues


def check_high_cardinality_columns(df, threshold=0.5):
    issues = []

    for column in df.columns:
        if df[column].dtype not in ["object", "category"]:
            continue

        unique_count = df[column].nunique(dropna=False)
        unique_ratio = float(unique_count / len(df))

        if unique_ratio < threshold:
            continue

        if unique_ratio > 0.9:
            severity = "high"
        else:
            severity = "medium"

        issue = {
            "check": "high_cardinality",
            "column": column,
            "severity": severity,
            "metric": "unique_ratio",
            "value": unique_ratio,
            "explanation": f"Column '{column}' has {unique_count} unique values, which is {unique_ratio * 100:.2f}% of the dataset.",
            "recommendation": "Check whether this column is an ID-like column. If yes, consider dropping it before modeling."
        }

        issues.append(issue)

    return issues


def check_class_imbalance(df, target_col):
    issues = []

    if target_col is None:
        return issues

    if target_col not in df.columns:
        return issues

    value_counts = df[target_col].value_counts(dropna=False)

    if len(value_counts) < 2:
        return issues

    majority_count = value_counts.iloc[0]
    minority_count = value_counts.iloc[-1]

    if minority_count == 0:
        imbalance_ratio = float("inf")
    else:
        imbalance_ratio = float(majority_count / minority_count)

    if imbalance_ratio < 2:
        return issues

    if imbalance_ratio >= 10:
        severity = "high"
    elif imbalance_ratio >= 5:
        severity = "medium"
    else:
        severity = "low"

    issue = {
        "check": "class_imbalance",
        "column": target_col,
        "severity": severity,
        "metric": "imbalance_ratio",
        "value": imbalance_ratio,
        "explanation": f"Target column '{target_col}' is imbalanced. The majority class is {imbalance_ratio:.2f} times larger than the minority class.",
        "recommendation": "Consider resampling, class weights, SMOTE, or collecting more minority-class examples."
    }

    issues.append(issue)

    return issues


def check_numeric_outliers(df):
    issues = []

    numeric_columns = df.select_dtypes(include=np.number).columns

    for column in numeric_columns:
        series = df[column].dropna()

        if len(series) == 0:
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            continue

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outlier_count = ((series < lower_bound) | (series > upper_bound)).sum()
        outlier_pct = float(outlier_count / len(series) * 100)

        if outlier_pct == 0:
            continue

        if outlier_pct > 10:
            severity = "high"
        elif outlier_pct > 3:
            severity = "medium"
        else:
            severity = "low"

        issue = {
            "check": "numeric_outliers",
            "column": column,
            "severity": severity,
            "metric": "outlier_pct",
            "value": outlier_pct,
            "explanation": f"Column '{column}' has {outlier_pct:.2f}% potential outliers based on the IQR method.",
            "recommendation": "Review these values. Consider capping, transforming, removing, or investigating them depending on the business context."
        }

        issues.append(issue)

    return issues


def check_high_correlation(df, threshold=0.9):
    issues = []

    numeric_df = df.select_dtypes(include=np.number)

    if numeric_df.shape[1] < 2:
        return issues

    corr_matrix = numeric_df.corr().abs()
    columns = corr_matrix.columns

    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):
            col1 = columns[i]
            col2 = columns[j]

            corr_value = corr_matrix.loc[col1, col2]

            if pd.isna(corr_value):
                continue

            if corr_value < threshold:
                continue

            issue = {
                "check": "high_correlation",
                "column": f"{col1}, {col2}",
                "severity": "medium",
                "metric": "correlation",
                "value": float(corr_value),
                "explanation": f"Columns '{col1}' and '{col2}' are highly correlated with a correlation of {corr_value:.2f}.",
                "recommendation": "Consider removing one of these columns if they provide duplicate information."
            }

            issues.append(issue)

    return issues


def check_mixed_casing(df):
    issues = []

    object_columns = df.select_dtypes(include=["object", "category"]).columns

    for column in object_columns:
        series = df[column].dropna().astype(str)

        if len(series) == 0:
            continue

        original_unique = series.nunique()
        lowercase_unique = series.str.lower().nunique()

        if lowercase_unique < original_unique:
            issue = {
                "check": "mixed_casing",
                "column": column,
                "severity": "low",
                "metric": "case_variants",
                "value": int(original_unique - lowercase_unique),
                "explanation": f"Column '{column}' appears to contain inconsistent casing, such as uppercase/lowercase variants of the same category.",
                "recommendation": "Standardize casing using lowercase, uppercase, or title case before modeling."
            }

            issues.append(issue)

    return issues


def run_quality_checks(df, target_col=None):
    all_issues = []

    all_issues.extend(check_missing_values(df))
    all_issues.extend(check_duplicate_rows(df))
    all_issues.extend(check_constant_columns(df))
    all_issues.extend(check_near_constant_columns(df))
    all_issues.extend(check_high_cardinality_columns(df))
    all_issues.extend(check_class_imbalance(df, target_col))
    all_issues.extend(check_numeric_outliers(df))
    all_issues.extend(check_high_correlation(df))
    all_issues.extend(check_mixed_casing(df))

    issues_df = pd.DataFrame(all_issues)

    if len(issues_df) == 0:
        return pd.DataFrame(columns=[
            "check",
            "column",
            "severity",
            "metric",
            "value",
            "explanation",
            "recommendation"
        ])

    severity_order = {
        "high": 3,
        "medium": 2,
        "low": 1
    }

    issues_df["severity_rank"] = issues_df["severity"].map(severity_order)
    issues_df = issues_df.sort_values(
        by="severity_rank",
        ascending=False
    ).drop(columns=["severity_rank"])

    return issues_df


# -----------------------------
# Phase 3: Scoring Engine
# -----------------------------

def compute_ai_ready_score(issues_df):
    penalties = {
        "low": 2,
        "medium": 5,
        "high": 10
    }

    score = 100

    if issues_df is None or len(issues_df) == 0:
        return {
            "score": 100,
            "grade": "Excellent",
            "total_issues": 0,
            "high_issues": 0,
            "medium_issues": 0,
            "low_issues": 0,
            "summary": "No major data quality issues were detected. The dataset appears highly ready for AI/ML training."
        }

    for _, row in issues_df.iterrows():
        severity = row["severity"]
        score = score - penalties.get(severity, 0)

    score = max(score, 0)

    high_count = int((issues_df["severity"] == "high").sum())
    medium_count = int((issues_df["severity"] == "medium").sum())
    low_count = int((issues_df["severity"] == "low").sum())

    if score >= 90:
        grade = "Excellent"
        summary = "The dataset looks highly ready for AI/ML training. Only minor or no issues were detected."
    elif score >= 75:
        grade = "Good"
        summary = "The dataset is mostly ready for AI/ML training, but some issues should be reviewed before modeling."
    elif score >= 50:
        grade = "Fair"
        summary = "The dataset has several quality issues. It may be usable, but cleaning is recommended before model training."
    else:
        grade = "Poor"
        summary = "The dataset has serious quality issues. It is not recommended for AI/ML training without significant cleaning."

    return {
        "score": int(score),
        "grade": grade,
        "total_issues": int(len(issues_df)),
        "high_issues": high_count,
        "medium_issues": medium_count,
        "low_issues": low_count,
        "summary": summary
    }


# -----------------------------
# UI Helper Functions
# -----------------------------

def get_dataset_overview(df):
    total_cells = df.shape[0] * df.shape[1]
    missing_cells = df.isna().sum().sum()

    if total_cells == 0:
        missing_pct = 0
    else:
        missing_pct = float(missing_cells / total_cells * 100)

    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    object_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime"]).columns.tolist()

    return {
        "rows": df.shape[0],
        "columns": df.shape[1],
        "missing_pct": missing_pct,
        "numeric_columns": len(numeric_cols),
        "categorical_columns": len(object_cols),
        "datetime_columns": len(datetime_cols)
    }
