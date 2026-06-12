"""
Adapter for ads_ml OCSVM + Zero-Shot Learning model.

Wraps the pipeline in vigil/ml/ads_ml/Trained/ without touching the original
utils (which load config.yaml at import time with relative paths).
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import joblib

from .base import BaseDetectionModel, DetectionInput, DetectionResult

logger = logging.getLogger("vigil.ads_ml")

_ADS_ML_DIR = Path(__file__).resolve().parent.parent / "ads_ml" / "Trained"

SEEN_SIM_THRESHOLD   = 0.50
REVIEW_THRESHOLD     = 0.10
TOP_K                = 5
COSINE_NORMAL_THRESH = 0.95
COSINE_ANOMALY_THRESH = 0.90


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class AdsMLModel(BaseDetectionModel):
    """
    OCSVM anomaly detector + k-means Zero-Shot attack classifier.

    Pipeline stages (mirrors ads_ml/utils/):
      1. preprocess  — encode + scale + PCA  (all stored in the joblib pipeline)
      2. detect      — OCSVM predict + cosine similarity review
      3. zero_shot   — map anomaly vector to known attack prototype
    """

    def __init__(self):
        pipeline_path   = _ADS_ML_DIR / "ebpf_ocsvm_pipeline.joblib"
        prototypes_path = _ADS_ML_DIR / "multi_attack_semantic_prototypes_kmeans.joblib"
        train_data_path = _ADS_ML_DIR / "step_10_final_train_data.csv"

        self._pipeline   = joblib.load(pipeline_path)
        self._prototypes = joblib.load(prototypes_path)
        self._X_train    = pd.read_csv(train_data_path).values

        # unpack pipeline components
        self._encoder         = self._pipeline["encoder"]
        self._scaler          = self._pipeline["scaler"]
        self._pca             = self._pipeline.get("pca")
        self._use_pca         = self._pipeline.get("use_pca", False)
        self._ocsvm           = self._pipeline["detector"]
        self._ebpf_features   = self._pipeline["ebpf_35_features"]
        self._encode_cols     = self._pipeline["encode_columns"]
        self._numeric_cols    = self._pipeline["numeric_columns"]
        self._encoded_cols    = self._pipeline["encoded_columns"]
        self._constant_cols   = self._pipeline.get("constant_cols", [])
        self._log_features    = self._pipeline.get("log_features", [])
        self._clip_ranges     = self._pipeline.get("clip_ranges", {})
        self._selected_feats  = self._pipeline["selected_features"]

        logger.info("AdsMLModel loaded from %s", _ADS_ML_DIR)

    @property
    def name(self) -> str:
        return "ads_ml_ocsvm"

    # ── preprocessing (mirrors data_preprocessing.py) ─────────────────────────
    def _preprocess(self, df: pd.DataFrame) -> np.ndarray:
        for col in self._ebpf_features:
            if col not in df.columns:
                df[col] = 0
        df = df[self._ebpf_features].copy()

        encoder_df = df[self._encode_cols].copy()
        numeric_df = df[self._numeric_cols].copy()

        for col in self._encode_cols:
            encoder_df[col] = encoder_df[col].fillna("Unknown").astype(str)
        for col in self._numeric_cols:
            numeric_df[col] = pd.to_numeric(numeric_df[col], errors="coerce")
        numeric_df.replace([np.inf, -np.inf], np.nan, inplace=True)
        numeric_df.fillna(0, inplace=True)

        encoded_array = self._encoder.transform(encoder_df)
        encoded_df    = pd.DataFrame(encoded_array, columns=self._encoded_cols)

        X_df = pd.concat([encoded_df.reset_index(drop=True), numeric_df.reset_index(drop=True)], axis=1)
        X_df = X_df.drop(columns=self._constant_cols, errors="ignore")

        for col in self._log_features:
            if col in X_df.columns:
                X_df[col] = np.log1p(X_df[col].clip(lower=0))

        for col, bounds in self._clip_ranges.items():
            if col in X_df.columns:
                X_df[col] = X_df[col].clip(bounds["lower"], bounds["upper"])

        X_df    = X_df.reindex(columns=self._selected_feats, fill_value=0)
        X_scaled = self._scaler.transform(X_df)

        if self._use_pca and self._pca is not None:
            return self._pca.transform(X_scaled)
        return X_scaled

    # ── detection (mirrors anomaly_detection.py) ───────────────────────────────
    def _detect(self, X_pca: np.ndarray):
        svm_pred   = self._ocsvm.predict(X_pca)
        prediction = np.where(svm_pred == -1, 1, 0)

        dec_score    = self._ocsvm.decision_function(X_pca)
        normal_score = _sigmoid(dec_score)
        anomaly_score = _sigmoid(-dec_score)
        score_gap    = np.abs(normal_score - anomaly_score)
        review_flag  = np.where(score_gap < REVIEW_THRESHOLD, 1, 0)

        from sklearn.metrics.pairwise import cosine_similarity
        for idx in np.where(review_flag == 1)[0]:
            sample = X_pca[idx].reshape(1, -1)
            sim    = cosine_similarity(sample, self._X_train)[0]
            avg_sim = np.mean(np.sort(sim)[-TOP_K:])
            if avg_sim >= COSINE_NORMAL_THRESH:
                prediction[idx] = 0
            elif avg_sim <= COSINE_ANOMALY_THRESH:
                prediction[idx] = 1

        return prediction, anomaly_score

    # ── zero-shot (mirrors zero_shot_learning.py) ──────────────────────────────
    def _zero_shot(self, X_pca: np.ndarray, prediction: np.ndarray):
        from sklearn.metrics.pairwise import cosine_similarity
        attack_types, similarities = [], []

        for idx in range(len(X_pca)):
            if prediction[idx] != 1:
                attack_types.append(None)
                similarities.append(0.0)
                continue

            sample = X_pca[idx].reshape(1, -1)
            best_name, best_score = None, -1.0

            for attack_name, info in self._prototypes.items():
                for proto in info["prototypes"]:
                    score = float(cosine_similarity(sample, proto["vector"].reshape(1, -1))[0][0])
                    if score > best_score:
                        best_score, best_name = score, attack_name

            if best_score >= SEEN_SIM_THRESHOLD:
                attack_types.append(best_name)
            else:
                attack_types.append("unknown_attack")
            similarities.append(best_score)

        return attack_types, similarities

    # ── BaseDetectionModel interface ───────────────────────────────────────────
    def predict(self, flow: DetectionInput) -> DetectionResult:
        results = self.predict_batch([flow])
        return results[0]

    def predict_batch(self, flows: list[DetectionInput]) -> list[DetectionResult]:
        from dataclasses import asdict
        rows = []
        for f in flows:
            d = asdict(f)
            d.pop("extra", None)
            rows.append(d)

        df    = pd.DataFrame(rows)
        X_pca = self._preprocess(df)

        prediction, anomaly_score = self._detect(X_pca)
        attack_types, similarities = self._zero_shot(X_pca, prediction)

        results = []
        for i, flow in enumerate(flows):
            is_attack   = bool(prediction[i] == 1)
            confidence  = float(anomaly_score[i])
            attack_type = attack_types[i] if is_attack else None

            results.append(DetectionResult(
                model_name  = self.name,
                is_attack   = is_attack,
                confidence  = round(confidence, 4),
                attack_type = attack_type,
                explanation = f"OCSVM anomaly_score={confidence:.3f}" + (
                    f", zsl_sim={similarities[i]:.3f}" if is_attack else ""
                ),
                raw_output  = {
                    "anomaly_score":  confidence,
                    "zsl_similarity": similarities[i],
                    "zsl_attack":     attack_type,
                },
            ))
        return results
