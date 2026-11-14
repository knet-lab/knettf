import numpy as np
import pandas as pd


def preprocess_data(data: dict, pipeline) -> np.ndarray:
    df = pd.DataFrame([data])

    encoder        = pipeline["encoder"]
    scaler         = pipeline["scaler"]
    use_pca        = pipeline["use_pca"]
    pca            = pipeline["pca"]
    ebpf_features  = pipeline["ebpf_35_features"]
    encode_cols    = pipeline["encode_columns"]
    numeric_cols   = pipeline["numeric_columns"]
    encoded_cols   = pipeline["encoded_columns"]
    constant_cols  = pipeline["constant_cols"]
    log_features   = pipeline["log_features"]
    clip_ranges    = pipeline["clip_ranges"]
    selected_feats = pipeline["selected_features"]

    for col in ebpf_features:
        if col not in df.columns:
            df[col] = 0
    df = df[ebpf_features]

    encoder_df = df[encode_cols].copy()
    numeric_df = df[numeric_cols].copy()

    for col in encode_cols:
        encoder_df[col] = encoder_df[col].fillna("Unknown").astype(str)
    for col in numeric_cols:
        numeric_df[col] = pd.to_numeric(numeric_df[col], errors="coerce")
    numeric_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    numeric_df.fillna(0, inplace=True)

    encoded_array = encoder.transform(encoder_df)
    encoded_df    = pd.DataFrame(encoded_array, columns=encoded_cols)

    X_df = pd.concat(
        [encoded_df.reset_index(drop=True), numeric_df.reset_index(drop=True)], axis=1
    )
    X_df = X_df.drop(columns=constant_cols, errors="ignore")

    for col in log_features:
        if col in X_df.columns:
            X_df[col] = np.log1p(X_df[col].clip(lower=0))

    for col, bounds in clip_ranges.items():
        if col in X_df.columns:
            X_df[col] = X_df[col].clip(bounds["lower"], bounds["upper"])

    X_df    = X_df.reindex(columns=selected_feats, fill_value=0)
    X_scaled = scaler.transform(X_df)

    if use_pca and pca is not None:
        return pca.transform(X_scaled)
    return X_scaled
