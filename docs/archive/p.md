# 问题报告

## 问题：模型资源重复加载

### 位置

`backend/vigil/ml/ads_ml/main.py` 第 44 行

```python
def main(...):
    ...
    pipeline, prototypes, X_train, report_path = _load_resources()  # ← 每次都加载
```

### 原因

`_load_resources()` 被写死在 `main()` 函数体内，每次调用 `main()` 都会从磁盘重新读取：

- `joblib.load(pipeline)` — OCSVM 模型
- `joblib.load(prototypes)` — 原型文件
- `pd.read_csv(train_data)` — 训练数据

`AdsMLModel.__init__` 虽然预热调用了一次 `_load_resources()`，但无法阻止 `main()` 内部的重复加载。

### 影响

`simulate_4.py` 每批送入 200 条 flow，每条 flow 经由 `detect_batch` → `detect_flow` → `AdsMLModel.predict` → `main()` 各触发一次磁盘加载，**N 条 flow 加载 N 次**，性能严重浪费。

### 责任归属

- **simulate_4.py**：无错，调用链路正常
- **ads_ml_model.py**：无错，返回值解释正确（`prediction[0]==1` → `is_attack`）
- **ads_ml/main.py**：设计问题，资源加载应提到调用方或做模块级缓存

### 结论

检测结果**正确**，仅存在性能问题。根本原因是 `ads_ml/main.py` 的 `main()` 函数未将资源加载与推理逻辑分离。

---

## 问题：推理阶段依赖训练集（过拟合风险）

### 位置

`backend/vigil/ml/ads_ml/utils/anomaly_detection.py`

### 原因

`ad()` 函数在 OCSVM 判断置信度不足时（`score_gap < 0.10`），会把输入样本与整个训练集做 cosine 相似度比对来辅助决策：

```python
sim     = cosine_similarity(sample, X_train)[0]
avg_sim = np.mean(np.sort(sim)[-TOP_K:])
```

这导致：
1. 推理时必须加载完整训练集（`step_10_final_train_data.csv`），增加内存和启动开销
2. 边界样本的判断结果强行向训练集靠拢，**等同于推理时看答案，导致过拟合**

### 修复

删除 cosine 兜底逻辑，`ad()` 直接返回 OCSVM 预测结果；`_load_resources()` 不再加载训练集 CSV。

---

## 分表方案：DetectionRecord 按天分区

### 方案

PostgreSQL 原生声明式分区，`PARTITION BY RANGE (created_at)`，每天一张子表，保留 90 天滚动窗口。

### 文件

| 文件 | 说明 |
|---|---|
| `vigil/models.py` | 加 `managed = False`，DDL 不由 Django 自动生成 |
| `vigil/migrations/0002_detection_record_partitioned.py` | 手写 SQL：建分区主表、索引、初始 91 个子分区（过去 89 天 + 今天 + 明天） |
| `vigil/management/commands/rotate_partitions.py` | 每日运行：建明天分区 + DROP 90 天前分区 |

### 分区命名规则

```
vigil_detectionrecord_YYYY_MM_DD
```

### 每日维护

```bash
python manage.py rotate_partitions --database vigil
```

建议通过 cron 或 systemd timer 在每天 00:00 自动执行。

### 前置条件

需先将 `vigil` 数据库从 SQLite 切换到 PostgreSQL（SQLite 不支持分区表）。
