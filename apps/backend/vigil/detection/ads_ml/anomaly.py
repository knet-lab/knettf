import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

REVIEW_THRESHOLD       = 0.10
TOP_K                  = 5
COSINE_NORMAL_THRESH   = 0.95
COSINE_ANOMALY_THRESH  = 0.90


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def ad(X_pca: np.ndarray, ocsvm, X_train: np.ndarray) -> np.ndarray:
    svm_pred   = ocsvm.predict(X_pca)
    prediction = np.where(svm_pred == -1, 1, 0)

    dec_score    = ocsvm.decision_function(X_pca)
    normal_score = _sigmoid(dec_score)
    anomaly_score = _sigmoid(-dec_score)
    score_gap    = np.abs(normal_score - anomaly_score)
    review_flag  = np.where(score_gap < REVIEW_THRESHOLD, 1, 0)

    for idx in np.where(review_flag == 1)[0]:
        sample  = X_pca[idx].reshape(1, -1)
        sim     = cosine_similarity(sample, X_train)[0]
        avg_sim = np.mean(np.sort(sim)[-TOP_K:])

        if avg_sim >= COSINE_NORMAL_THRESH:
            prediction[idx] = 0
        elif avg_sim <= COSINE_ANOMALY_THRESH:
            prediction[idx] = 1

    return prediction
