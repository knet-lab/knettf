#!/bin/bash
# 把 ads_ml 代码和模型同步到 detector/ 再构建镜像
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADS_ML_SRC="$SCRIPT_DIR/../apps/backend/vigil/ml/ads_ml"

echo "syncing ads_ml..."
rsync -a --delete \
    --exclude "__pycache__" \
    --exclude "results/" \
    --exclude "*.pyc" \
    "$ADS_ML_SRC/" "$SCRIPT_DIR/ads_ml/"

# 模型文件以线上当前版本为准（与入口 A 用同一份）；没有版本目录时沿用 ads_ml/ 里的
MODEL_DIR="${ADS_ML_MODEL_DIR:-/srv/netsentinel/models/ads_ml/current}"
if [ -f "$MODEL_DIR/config.yaml" ]; then
    echo "using model $(readlink -f "$MODEL_DIR")"
    rsync -a --delete "$MODEL_DIR/trained/" "$SCRIPT_DIR/ads_ml/trained/"
    cp "$MODEL_DIR/config.yaml" "$SCRIPT_DIR/ads_ml/config.yaml"
fi

echo "building image..."
docker build -t soar009/netsentinel-detector:latest "$SCRIPT_DIR"

echo "pushing to Docker Hub..."
docker push soar009/netsentinel-detector:latest
echo "done: soar009/netsentinel-detector:latest"
