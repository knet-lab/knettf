# 项目规则（给开发者和 AI 助手）

NetSentinel 检测平台 + Kubernetes eBPF 流量实验环境。总体说明见 [README.md](README.md)，交接与迁移见 [docs/HANDOVER.md](docs/HANDOVER.md)。

## 必须遵守

1. **不要写死环境相关的值。** 项目会交接，域名、Cloudflare 账号、Linux 用户、部署目录、GitHub 仓库都会更换。新代码和文档里不要出现具体的域名、个人账户名、`/home/<用户>`、`/srv/netsentinel` 之类的路径；用配置或环境变量，并在 `docs/HANDOVER.md` 第 2 节登记。
2. **一台机器同时是开发、线上和实验集群。**
   - `manage.py` 默认连**线上数据库**：只读查询可以，写入或删除前先确认并备份。
   - 开发环境运行后端必须设 `VIGIL_KAFKA_GROUP_ID=vigil-bridge-dev`。
   - 不要占用 8080 端口（线上服务）。
   - 重 CPU 任务会扰动采集到的时间特征。
3. **检测模型归模型方所有。** 不要修改 `apps/backend/vigil/detection/`（模型代码）和 `DetectionInput` / `DetectionResult` 接口。数据接入（`vigil/ingest/`）可以改，但送给模型的 35 个特征的名称、单位和含义必须保持不变。
4. **改了接口要同步副本。** `model-kit/base.py` 是 `vigil/detection/base.py` 的副本，由测试 `test_model_kit` 检查是否一致。
5. **实验环境出问题时整体重建**（`lab/cluster/00 → 04`），不要在集群里局部打补丁。03、04 是幂等的。
6. **通过 PR 上线。** 分支 → PR → CI（`ops/scripts/check.sh`）→ 合并 main → 自动部署。lab 的改动合并后只会同步文件，需要重跑 03/04 才会在集群里生效。

## 关键约定

- 流的定义：双向五元组；RST 立即结束，双方 FIN 后收下挥手最后的 ACK 再结束（参照 Zeek），空闲 60 秒、活跃 120 秒超时；`flow_duration` 和 `iat_*` 的单位是**微秒**（与 CICFlowMeter、训练数据一致）。实现见 `apps/backend/vigil/ingest/flows.py`。
- 实验环境内部网段：VM `192.168.100.0/24`，MetalLB `.200-.250`，Pod `10.0.0.0/8`，仿真客户端区 `172.30.0.0/16`。
