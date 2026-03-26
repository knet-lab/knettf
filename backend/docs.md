# 开发文档

## 后端App

| App    | Description          |
| ------ | -------------------- |
| kcore  | k8s 管理服务         |
| autotf | tf 自动化检测        |
| vigil  | 基于AI的异常流量监测 |

### kcore

#### model

KubeCluster

- **Meta class: unique_togather**

  只能指定一个 user 和 (cluster) name 对应到cluster 对象
  不能同一个用户有两个一样名字的 cluster
