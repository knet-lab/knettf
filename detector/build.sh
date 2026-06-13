#!/bin/bash
# 把 ads_ml 代码和模型同步到 detector/ 再构建镜像
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADS_ML_SRC="$SCRIPT_DIR/../backend/vigil/ml/ads_ml"

echo "syncing ads_ml..."
rsync -a --delete \
    --exclude "__pycache__" \
    --exclude "results/" \
    --exclude "*.pyc" \
    "$ADS_ML_SRC/" "$SCRIPT_DIR/ads_ml/"

echo "building image..."
docker build -t soar009/netsentinel-detector:latest "$SCRIPT_DIR"

echo "pushing to Docker Hub..."
docker push soar009/netsentinel-detector:latest
echo "done: soar009/netsentinel-detector:latest"
