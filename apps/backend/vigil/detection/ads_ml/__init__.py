"""
ads_ml：OCSVM 异常检测 + 余弦复核 + 零样本攻击分类。

代码和模型文件都在这个目录（进 Git），模型文件在 files/ 下，由 settings.VIGIL_ADS_ML_CONFIG 指向：
  files/config.yaml
    trained/ebpf_ocsvm_pipeline.joblib                  预处理 + OCSVM
    trained/multi_attack_semantic_prototypes_kmeans.joblib  攻击原型
    trained/step_10_final_train_data.csv                余弦复核用的参考样本
"""

from .model import AdsMLModel

__all__ = ["AdsMLModel"]
