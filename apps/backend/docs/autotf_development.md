# autotf 开发文档

> Terraform 配置安全检测与管理模块
>
> 所属项目：NetSentinel · Phase 2

---

## 目录

- [模块概述](#模块概述)
- [后端接口](#后端接口)
- [前端接口调用](#前端接口调用)
- [鉴权说明](#鉴权说明)
- [Management Commands](#management-commands)
- [待开发](#待开发)

---

## 模块概述

`autotf` 负责 Terraform 配置文件的托管与安全检测，核心流程：

**上传 / 编写配置 → 自动触发全量扫描 → 生成检测报告 → 通过后方可 apply**

扫描工具当前仅使用 `terraform validate`，二进制路径由 `settings.TF_BIN` 提供。

---

## 后端接口

所有接口前缀：`/api/autotf/`

鉴权方式：`Authorization: Bearer <access_token>`（HTML / PDF 接口除外，见[鉴权说明](#鉴权说明)）

### 配置管理

| Method   | Endpoint                                       | 说明                                             |
| -------- | ---------------------------------------------- | ------------------------------------------------ |
| `GET`    | `/api/autotf/users/<user_pk>/tf-configs/`      | 当前用户配置列表（含报告摘要）                   |
| `POST`   | `/api/autotf/users/<user_pk>/tf-configs/`      | 上传 `.tf` 文件（multipart）；创建后自动全量扫描 |
| `POST`   | `/api/autotf/users/<user_pk>/tf-configs/text/` | 在线编写配置（JSON body）；创建后自动全量扫描    |
| `GET`    | `/api/autotf/tf-configs/<config_pk>/`          | 配置详情                                         |
| `PUT`    | `/api/autotf/tf-configs/<config_pk>/`          | 更新配置（文件或文本）；更新后自动全量扫描       |
| `DELETE` | `/api/autotf/tf-configs/<config_pk>/`          | 删除配置（级联删除报告）                         |
| `GET`    | `/api/autotf/tf-configs/<config_pk>/content/`  | 查看配置文件原始内容                             |

#### POST `/users/<user_pk>/tf-configs/` — 上传文件

```
Content-Type: multipart/form-data

name: string        # 配置备注名（同一用户下唯一）
file: .tf 文件
```

#### POST `/users/<user_pk>/tf-configs/text/` — 在线编写

```json
{
  "name": "my-config",
  "content": "resource \"null_resource\" \"example\" {}"
}
```

#### PUT `/tf-configs/<config_pk>/` — 更新

```
# 更新文件（multipart）
file: .tf 文件

# 更新文本（JSON）
{ "content": "..." }

# 仅改名（JSON）
{ "name": "new-name" }
```

---

### 扫描工具

| Method | Endpoint                | 说明               |
| ------ | ----------------------- | ------------------ |
| `GET`  | `/api/autotf/tf-tools/` | 所有已启用工具列表 |

响应示例：

```json
{
  "status": "success",
  "data": [{ "id": 1, "name": "terraform_validate", "version": "1.14.7" }]
}
```

---

### 扫描

| Method | Endpoint                                          | 说明                           |
| ------ | ------------------------------------------------- | ------------------------------ |
| `POST` | `/api/autotf/tf-configs/<config_pk>/scan/`        | 全量扫描（使用所有已启用工具） |
| `POST` | `/api/autotf/tf-configs/<config_pk>/scan/manual/` | 手动扫描（指定工具子集）       |

#### POST `/scan/manual/` body

```json
{ "tool_ids": [1] }
```

扫描响应（两者相同）：

```json
{
  "status": "success",
  "data": {
    "id": 1,
    "status": "done",
    "tools": [{ "id": 1, "name": "terraform_validate", "version": "1.14.7" }],
    "result": {
      "summary": { "high": 0, "medium": 0, "low": 0 },
      "tools": {
        "terraform_validate": { "items": [] }
      }
    },
    "scanned_at": "2026-03-27T10:00:00Z"
  }
}
```

---

### 检测报告

| Method   | Endpoint                                          | 鉴权      | 说明                                  |
| -------- | ------------------------------------------------- | --------- | ------------------------------------- |
| `GET`    | `/api/autotf/tf-configs/<config_pk>/report/`      | Bearer    | 报告 JSON（含完整 findings）          |
| `DELETE` | `/api/autotf/tf-configs/<config_pk>/report/`      | Bearer    | 删除报告；自动重置 `is_scanned=False` |
| `GET`    | `/api/autotf/tf-configs/<config_pk>/report/html/` | `?token=` | 网页版报告（新标签页打开）            |
| `GET`    | `/api/autotf/tf-configs/<config_pk>/report/pdf/`  | `?token=` | PDF 下载（实时生成，不落盘）          |

---

### Apply（预留）

| Method | Endpoint                                    | 说明                                     |
| ------ | ------------------------------------------- | ---------------------------------------- |
| `POST` | `/api/autotf/tf-configs/<config_pk>/apply/` | **未实现** — 待与 K8s Cluster 联动后开发 |

`is_scanned=False` 时返回 `403`。

---

## 前端接口调用

测试页面：`http://localhost:5173/autotf`

文件：`frontend/src/views/AutoTFView.vue`

| 节               | 操作                                        | 对应后端接口                                                   |
| ---------------- | ------------------------------------------- | -------------------------------------------------------------- |
| 1. Login         | 获取 JWT token                              | `POST /api/auth/token/`                                        |
| 2. Tools         | 查看可用工具及 ID                           | `GET /api/autotf/tf-tools/`                                    |
| 3. Configs       | 列表 / 上传文件 / 在线编写                  | `GET` `POST` `/users/:id/tf-configs/`                          |
| 4. Config Detail | 详情 / 查看内容 / 更新 / 删除               | `GET` `PUT` `DELETE` `/tf-configs/:id/`                        |
| 5. Scan          | 全量扫描 / 手动扫描（填 tool ids）          | `POST /tf-configs/:id/scan/` `.../scan/manual/`                |
| 6. Report        | JSON 报告 / 删除 / HTML 新标签页 / PDF 下载 | `GET` `DELETE` `/report/` `.../report/html/` `.../report/pdf/` |

> HTML 报告链接和 PDF 下载链接由 `computed` 自动拼接当前 `configId` 和 `token`，无需手动填写。

---

## 鉴权说明

所有 REST API 接口使用 `Authorization: Bearer <access_token>` Header 鉴权。

**HTML / PDF 报告接口**为浏览器直接导航（`<a target="_blank">`），无法设置 Header，改用 Query Param：

```
GET /api/autotf/tf-configs/<pk>/report/html/?token=<access_token>
GET /api/autotf/tf-configs/<pk>/report/pdf/?token=<access_token>
```

后端通过 `rest_framework_simplejwt.tokens.AccessToken` 校验 token，owner 检查与其他接口一致。

---

## Management Commands

在 `backend/` 目录下执行。

### `autotf_init` — 初始化

首次部署或清库后执行。

```bash
python manage.py autotf_init
```

执行内容：

1. 创建 `backend/terraform/` 目录（Django FileField 上传目录）
2. 调用 `settings.TF_BIN version -json` 读取版本号
3. upsert `TerraformTool(name='terraform_validate')`

输出示例：

```
Directory ready: /path/to/backend/terraform
Created tool: terraform_validate v1.14.7
```

---

### `autotf_clear` — 清库

清空所有 autotf 数据，**开发环境重置用**。

```bash
python manage.py autotf_clear
```

执行内容：

1. 删除所有 `ScanReport`
2. 删除所有 `TerraformConfig`
3. 删除所有 `TerraformTool`
4. 删除 `backend/terraform/` 目录及其中所有上传文件

输出示例：

```
Deleted directory: /path/to/backend/terraform
Cleared: 3 reports, 3 configs, 1 tools
```

---

### 典型开发流程

```bash
# 1. 清库（可选，重置环境）
python manage.py autotf_clear

# 2. 初始化
python manage.py autotf_init

# 3. 启动后端
python manage.py runserver

# 4. 启动前端（frontend/ 目录下）
npm run dev
```

---

## 待开发

| 功能                | 说明                                                                 |
| ------------------- | -------------------------------------------------------------------- |
| Apply 实现          | 需与 K8s Cluster 配置联动，接口预留于 `POST /tf-configs/<pk>/apply/` |
| `TF_BIN` 环境变量化 | 当前写死在 `settings.py`，生产环境改为从 env 读取                    |
