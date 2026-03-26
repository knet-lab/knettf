# autotf 模块需求文档

> Terraform 配置安全检测与管理模块
>
> 所属项目：NetSentinel · Phase 2

---

## 目录

- [模块概述](#模块概述)
- [数据模型](#数据模型)
- [功能需求](#功能需求)
- [API 接口清单](#api-接口清单)
- [业务规则与约束](#业务规则与约束)
- [代码结构规范](#代码结构规范)

---

## 模块概述

`autotf` 负责 Terraform 配置文件的托管与安全检测，核心流程为：

**上传 / 编写配置 → 自动触发全量扫描 → 生成检测报告 → 通过后方可 apply**

---

## 数据模型

### `TerraformConfig` — Terraform 配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | AutoField PK | 主键 |
| `owner` | ForeignKey → User | 配置归属用户 |
| `name` | CharField(255) | 配置备注名 |
| `file` | FileField | 上传的 `.tf` 文件，存服务器磁盘 |
| `is_scanned` | BooleanField | 是否已完成至少一次扫描，默认 `False` |
| `created_at` | DateTimeField | 创建时间，auto_now_add |
| `updated_at` | DateTimeField | 最后修改时间，auto_now |

> `is_scanned` 为 `False` 时，禁止该配置被 apply。

---

### `TerraformTool` — 可用扫描工具

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | AutoField PK | 主键 |
| `name` | CharField(255) | 工具名称，唯一，如 `tfsec`、`checkov` |
| `version` | CharField(50) | 工具版本，如 `0.58.0` |
| `is_enabled` | BooleanField | 是否对用户开放，默认 `True` |
| `created_at` | DateTimeField | 创建时间，auto_now_add |

> 由**开发者**通过 Django Admin 维护，用户只能从已启用的工具中选择。

---

### `ScanReport` — 检测报告

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | AutoField PK | 主键 |
| `owner` | ForeignKey → User | 报告归属用户 |
| `config` | ForeignKey → TerraformConfig | 对应的配置（非 OneToOne，支持历史覆盖） |
| `tools` | ManyToManyField → TerraformTool | 本次扫描使用的工具集合 |
| `status` | CharField(20) | `pending` / `running` / `done` / `failed` |
| `result` | JSONField | 结构化扫描结果，见下方格式约定 |
| `scanned_at` | DateTimeField | 最后扫描时间，auto_now |

> **当前实现：每份配置只对应一条 ScanReport**，重新扫描时直接覆盖（update or create）。
> 数据库使用 `ForeignKey`（非 `OneToOneField`）保留扩展空间，业务层保证当前只有一条。未来若需要保留历史记录，只需调整 service 层逻辑，model 无需变更。

#### `result` JSON 格式约定

```json
{
  "summary": {
    "high": 3,
    "medium": 5,
    "low": 2
  },
  "tools": {
    "tfsec": {
      "items": [
        {
          "rule_id": "AWS001",
          "severity": "HIGH",
          "description": "S3 bucket has logging disabled",
          "location": "main.tf:12"
        }
      ]
    },
    "checkov": {
      "items": [...]
    }
  }
}
```

---

## 功能需求

### F1 — 配置文件管理

#### F1.1 上传配置文件

- 用户通过 multipart 上传 `.tf` 文件
- 创建 `TerraformConfig` 记录，`is_scanned` 初始为 `False`
- **上传完成后自动触发一次全量扫描**（使用所有已启用工具）
- 同一用户下配置名不可重复

#### F1.2 在线编写配置

- 用户通过纯文本接口提交 `.tf` 内容
- 后端将内容写入文件后保存，流程同上传
- **提交完成后自动触发一次全量扫描**

#### F1.3 修改配置

- 支持更新配置文件内容（上传新文件或在线编辑）
- **更新完成后自动触发一次全量扫描，`is_scanned` 重置为 `False` 直至扫描完成**

#### F1.4 查看配置列表

- 返回当前用户下所有配置
- 每条记录包含：`id`、`name`、`is_scanned`、`created_at`、`updated_at`
- 如果该配置存在 `ScanReport`，附带报告的 `status` 和 `scanned_at`

#### F1.5 查看配置详情

- 返回单份配置的完整信息
- 包含：配置基本信息 + `is_scanned` 状态 + 当前报告的 `status` / `result.summary`（如有）

#### F1.6 删除配置

- 删除配置时级联删除关联的 `ScanReport`（Django `on_delete=CASCADE` 自动处理）

---

### F2 — 扫描工具管理

#### F2.1 获取可用工具列表

- 返回所有 `is_enabled=True` 的 `TerraformTool`
- 供用户在手动触发扫描时选择工具

---

### F3 — 安全扫描

#### F3.1 自动全量扫描（内部触发）

- 触发时机：配置**创建**或**更新**后自动调用
- 使用所有 `is_enabled=True` 的工具
- 流程：
  1. 将 `file` 内容写入临时目录
  2. 依次调用每个工具，解析输出
  3. 合并结果写入 `ScanReport.result`
  4. 更新 `ScanReport.status` 为 `done` / `failed`
  5. 扫描产出结果（`status=done`）后将 `TerraformConfig.is_scanned` 置为 `True`，无论 findings 是否有问题

#### F3.2 用户手动触发扫描

- 用户可选择工具子集（必须是已启用工具的子集）手动触发
- 流程同 F3.1，但工具范围以用户选择为准
- 扫描完成后同样覆盖旧报告

---

### F4 — 检测报告

#### F4.1 查看报告总览

- 返回 `result.summary`：high / medium / low 各工具汇总数量

#### F4.2 查看各工具详细结果

- 返回 `result.tools` 下各工具的 `items` 详情

#### F4.3 下载 PDF 报告

- 用户点击下载时**实时生成** PDF，不存盘
- PDF 内容包含：配置名、扫描时间、使用工具、summary、各工具详细 findings

#### F4.4 删除检测报告

- 用户可以删除某份配置的检测报告
- 删除后，若该配置下**不再有任何 `ScanReport`**，则将 `TerraformConfig.is_scanned` 自动重置为 `False`
- 用户**无权修改** `ScanReport` 的任何字段，报告只能由扫描流程生成

---

### F5 — Apply 保护

- `TerraformConfig.is_scanned` 为 `False` 时，apply 接口返回 `403`，提示"请先完成安全检测"
- Apply 接口为预留占位，Phase 2 仅实现保护逻辑，不实现实际 apply 功能

---

## API 接口清单

### 配置管理

| Method | Endpoint | 说明 |
|--------|----------|------|
| `GET` | `/api/autotf/users/<pk>/configs/` | 当前用户配置列表 |
| `POST` | `/api/autotf/users/<pk>/configs/` | 上传配置文件（multipart） |
| `POST` | `/api/autotf/users/<pk>/configs/text/` | 在线编写配置（纯文本） |
| `GET` | `/api/autotf/configs/<pk>/` | 配置详情 |
| `PUT` | `/api/autotf/configs/<pk>/` | 更新配置（上传新文件或更新文本） |
| `DELETE` | `/api/autotf/configs/<pk>/` | 删除配置 |

### 扫描

| Method | Endpoint | 说明 |
|--------|----------|------|
| `GET` | `/api/autotf/tools/` | 可用工具列表 |
| `POST` | `/api/autotf/configs/<pk>/scan/` | 手动触发扫描（body 指定工具） |

### 报告

| Method | Endpoint | 说明 |
|--------|----------|------|
| `GET` | `/api/autotf/configs/<pk>/report/` | 查看检测报告（总览 + 各工具详情） |
| `DELETE` | `/api/autotf/configs/<pk>/report/` | 删除检测报告（同步重置 `is_scanned` 如无报告） |
| `GET` | `/api/autotf/configs/<pk>/report/pdf/` | 下载 PDF 报告（实时生成） |

### Apply 保护（预留）

| Method | Endpoint | 说明 |
|--------|----------|------|
| `POST` | `/api/autotf/configs/<pk>/apply/` | 触发 apply（未扫描时返回 403） |

---

## 业务规则与约束

| # | 规则 |
|---|------|
| B1 | 配置创建 / 更新后自动触发全量扫描 |
| B2 | 配置更新时 `is_scanned` 重置为 `False`，直至新一轮扫描完成 |
| B3 | 每份配置只保留最后一次扫描记录，覆盖写入 |
| B4 | `is_scanned=False` 时，apply 接口拒绝请求（403） |
| B4.1 | `is_scanned` 只要扫描产出结果（`status=done`）即置为 `True`，不依赖 findings 是否干净 |
| B5 | 用户手动扫描只能选已启用工具的子集 |
| B6 | PDF 实时生成，不落盘 |
| B7 | 用户只能操作自己名下的配置（`check_owner` 每个接口都要校验） |
| B8 | 同一用户下配置名唯一 |
| B9 | 用户**不可修改** `ScanReport`，报告只能由扫描流程写入 |
| B10 | 删除 `ScanReport` 后，若该配置下已无任何报告，自动将 `is_scanned` 重置为 `False` |

---

## 代码结构规范

与 `kcore` 模块完全对齐：

```
autotf/
├── models.py          # TerraformConfig, TerraformTool, ScanReport
├── serializers.py     # 读写分离：XxxResponseSerializer / XxxCreateSerializer / XxxUpdateSerializer
├── views.py           # 全部 APIView + ResponseMixin，不使用 ViewSet
├── services.py        # TerraformConfigService, ScanService（业务逻辑全在这里）
├── urls.py            # 路由，风格对齐 kcore/urls.py
├── admin.py           # TerraformTool 在 admin 维护
├── tests.py           # 接口参数校验 + 权限校验（不能访问他人资源）
└── migrations/
```

### View 层规范

- 每个接口第一行 `check_owner(request, config.owner.pk)`
- View 只做调度，不写业务逻辑
- 统一使用 `ResponseMixin` 的 `success_response` / `error_response`
- 全部 REST，无 WebSocket

### Serializer 命名规范

| 场景 | 命名示例 |
|------|---------|
| 输出（列表） | `TerraformConfigListSerializer` |
| 输出（详情） | `TerraformConfigDetailSerializer` |
| 输入（创建） | `TerraformConfigCreateSerializer` |
| 输入（更新） | `TerraformConfigUpdateSerializer` |