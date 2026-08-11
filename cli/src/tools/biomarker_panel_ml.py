"""ML helpers for biomarker.panel_select: feature importance and CV-AUC."""

import numpy as np


def _compute_importances(method: str, X, y_binary, y_lfc, n_sensitive: int, n_resistant: int):
    """Compute per-feature importance scores for the requested method."""
    if method == "mutual_info":
        from sklearn.feature_selection import mutual_info_classif
        return mutual_info_classif(X, y_binary, random_state=42)

    if method == "lasso":
        from sklearn.linear_model import LassoCV
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        lasso = LassoCV(cv=min(5, n_sensitive, n_resistant), random_state=42, max_iter=5000)
        lasso.fit(X_scaled, y_lfc)  # Use continuous LFC for lasso
        return np.abs(lasso.coef_)

    from sklearn.ensemble import RandomForestClassifier
    rf = RandomForestClassifier(
        n_estimators=100, max_depth=5, random_state=42, class_weight="balanced",
    )
    rf.fit(X, y_binary)
    return rf.feature_importances_


def _cross_val_auc(X, y_binary, feature_names, biomarkers, n_sensitive: int, n_resistant: int):
    """Cross-validated ROC-AUC using the top selected biomarker features."""
    if not biomarkers:
        return None
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score

    top_gene_idx = [feature_names.index(b["gene"]) for b in biomarkers if b["gene"] in feature_names]
    if not top_gene_idx:
        return None
    cv_folds = min(5, n_sensitive, n_resistant)
    if cv_folds < 2:
        return None
    X_top = X[:, top_gene_idx]
    clf = RandomForestClassifier(n_estimators=50, max_depth=3, random_state=42, class_weight="balanced")
    try:
        scores = cross_val_score(clf, X_top, y_binary, cv=cv_folds, scoring="roc_auc")
        return round(float(scores.mean()), 4)
    except ValueError:
        return None
