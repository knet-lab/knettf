import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

SEEN_SIM_THRESHOLD = 0.50


def zero_shot_learning(
    X_pca: np.ndarray,
    prediction: np.ndarray,
    semantic_prototypes: dict,
) -> tuple[list, list, list]:
    zsl_seen_status, zsl_preds, zsl_sims = [], [], []

    for idx in range(len(X_pca)):
        if prediction[idx] != 1:
            zsl_seen_status.append("Normal")
            zsl_preds.append("Normal")
            zsl_sims.append(0.0)
            continue

        sample     = X_pca[idx].reshape(1, -1)
        best_name  = "Unknown_Attack"
        best_score = -1.0

        for attack_name, info in semantic_prototypes.items():
            for proto in info["prototypes"]:
                score = float(cosine_similarity(sample, proto["vector"].reshape(1, -1))[0][0])
                if score > best_score:
                    best_score, best_name = score, attack_name

        if best_score >= SEEN_SIM_THRESHOLD:
            zsl_seen_status.append("Seen_Attack")
            zsl_preds.append(best_name)
        else:
            zsl_seen_status.append("Unknown_Attack")
            zsl_preds.append("Unknown_Attack")
        zsl_sims.append(best_score)

    return zsl_seen_status, zsl_preds, zsl_sims
