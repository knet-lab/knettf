"""
ads_ml：OCSVM 异常检测 + 余弦复核 + 零样本攻击分类。

代码在这里（进 Git）；模型文件只在服务器上，由 settings.VIGIL_ADS_ML_CONFIG 指向：
  /srv/netsentinel/models/ads_ml/current/config.yaml
    trained/ebpf_ocsvm_pipeline.joblib                  预处理 + OCSVM
    trained/multi_attack_semantic_prototypes_kmeans.joblib  攻击原型
    trained/step_10_final_train_data.csv                余弦复核用的参考样本
"""

from .model import AdsMLModel

__all__ = ["AdsMLModel"]
