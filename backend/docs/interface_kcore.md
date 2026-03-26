# kcore API 接口文档

Base URL: `/api/kcore`

## 响应格式

```json
// 成功
{ "status": "success", "code": 0, "message": "Success", "data": {...} }

// 错误
{ "status": "error", "code": 1, "message": "...", "data": null }
```

---

## User

### GET /users/
获取所有用户列表

**Response 200**
```json
{
  "status": "success",
  "code": 0,
  "message": "Success",
  "data": [
    { "id": 1, "username": "admin", "email": "admin@example.com" }
  ]
}
```

---

### POST /users/
创建用户

**Request Body**
```json
{ "username": "admin", "email": "admin@example.com", "password": "123456" }
```

**Response 201**
```json
{
  "status": "success",
  "code": 0,
  "message": "Success",
  "data": { "id": 1, "username": "admin", "email": "admin@example.com" }
}
```

---

### GET /users/`{id}`/
获取用户详情

**Response 200**
```json
{
  "status": "success",
  "code": 0,
  "message": "Success",
  "data": { "id": 1, "username": "admin", "email": "admin@example.com" }
}
```

---

### PUT /users/`{id}`/
更新用户（字段均为可选）

**Request Body**
```json
{ "username": "new_name", "email": "new@example.com" }
```

**Response 200**
```json
{
  "status": "success",
  "code": 0,
  "message": "Success",
  "data": { "id": 1, "username": "new_name", "email": "new@example.com" }
}
```

---

### DELETE /users/`{id}`/
删除用户

**Response 200**
```json
{ "status": "success", "code": 0, "message": "Success", "data": { "message": "User deleted" } }
```

---

## KubeCluster

### GET /users/`{user_id}`/clusters/
获取某用户的所有集群

**Response 200**
```json
{
  "status": "success",
  "code": 0,
  "message": "Success",
  "data": [
    {
      "id": 1,
      "name": "my-cluster",
      "owner": { "id": 1, "username": "admin", "email": "admin@example.com" },
      "kubeconfig": "...",
      "is_active": true,
      "last_synced_at": "2024-01-01T00:00:00Z",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

### POST /users/`{user_id}`/clusters/
创建集群

**Request Body**
```json
{ "name": "my-cluster", "kubeconfig": "apiVersion: v1 ..." }
```

**Response 201**
```json
{
  "status": "success",
  "code": 0,
  "message": "Success",
  "data": {
    "id": 1,
    "name": "my-cluster",
    "owner": { "id": 1, "username": "admin", "email": "admin@example.com" },
    "kubeconfig": "...",
    "is_active": true,
    "last_synced_at": null,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

---

### GET /clusters/`{id}`/
获取集群详情

**Response 200** — 同上结构

---

### PUT /clusters/`{id}`/
更新集群（字段均为可选）

**Request Body**
```json
{ "name": "new-name", "kubeconfig": "..." }
```

**Response 200** — 同上结构

---

### DELETE /clusters/`{id}`/
删除集群

**Response 200**
```json
{ "status": "success", "code": 0, "message": "Success", "data": { "message": "Cluster deleted" } }
```

---

## K8s Resources

### GET /clusters/`{cluster_id}`/resources/`{resource_type}`/
列出资源

`resource_type` 可选值：`namespaces` | `pods` | `deployments` | `services` | `configmaps` | `daemonsets`

- `namespaces`：不需要 namespace 参数
- 其他资源：需要 query 参数 `?namespace=<namespace>`

**Query Params**
| 参数 | 必填 | 说明 |
|------|------|------|
| namespace | 否（namespaces 除外必填） | 目标命名空间 |

**Response 200**
```json
{
  "status": "success",
  "code": 0,
  "message": "Success",
  "data": { "resources": [ {...}, {...} ] }
}
```

---

### POST /clusters/`{cluster_id}`/resources/`{resource_type}`/
创建资源

**namespaces**
```json
{ "name": "my-namespace" }
```

**deployments / services / daemonsets**
```json
{
  "namespace": "default",
  // 标准 k8s manifest 字段
}
```

**configmaps**
```json
{
  "namespace": "default",
  "name": "my-config",
  "data": { "key": "value" }
}
```

**Response 201**
```json
{
  "status": "success",
  "code": 0,
  "message": "Success",
  "data": { "resource": {...} }
}
```

---

### PUT /clusters/`{cluster_id}`/resources/`{resource_type}`/
更新资源（不支持 namespaces、pods）

**Request Body**
```json
{
  "namespace": "default",
  "name": "my-deployment",
  // 标准 k8s manifest 字段
}
```

**configmaps 需额外传 data**
```json
{
  "namespace": "default",
  "name": "my-config",
  "data": { "key": "new-value" }
}
```

**Response 200**
```json
{
  "status": "success",
  "code": 0,
  "message": "Success",
  "data": { "resource": {...} }
}
```

---

### DELETE /clusters/`{cluster_id}`/resources/`{resource_type}`/
删除资源

**namespaces**
```json
{ "name": "my-namespace" }
```

**其他资源**
```json
{ "namespace": "default", "name": "my-deployment" }
```

**Response 200**
```json
{
  "status": "success",
  "code": 0,
  "message": "Success",
  "data": { "message": "Deployment deleted" }
}
```

---

## 错误响应

| HTTP 状态码 | code | 场景 |
|-------------|------|------|
| 400 | 1 | 参数缺失 / 校验失败 |
| 404 | 1 | 资源不存在 |
| 500 | 2 | 服务器内部错误 |
