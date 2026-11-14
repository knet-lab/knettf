# 开发文档

## 后端App

| App                                                    | Description          |
| ------------------------------------------------------ | -------------------- |
| **<p style="color: rgb(0, 200, 255, 1)">kcore</p>**    | k8s 管理服务         |
| **<p style="color: rgb(251, 128, 255, 1)">autotf</p>** | tf 自动化检测        |
| **<p style="color: rgb(250, 70, 70, 1)">vigil</p>**    | 基于AI的异常流量监测 |

### kcore

#### model

KubeCluster

- **Meta class: unique_togather**

  只能指定一个 user 和 (cluster) name 对应到cluster 对象。
  不能同一个用户有两个一样名字的 cluster。

## 具体代码结构

**结构设计**

- service -> serializers -> views

**实际代码结构**

- service -> views(serializers)

- <p style="color: rgba(255, 50, 50, 1)"><strong>在 serializers 工序中只做 validte 校验，不使用 create, update, save, delete</strong></p>

## 响应格式

统一使用 `ResponseMixin`，所有响应都走这里。

<p style="color: rgb(100, 210, 100, 1)">200:  { "status": "success", "code": 0, "message": "Success", "data": {...} }</p>
<p style="color: rgb(100, 210, 100, 1)">201:  { "status": "success", "code": 0, "message": "Created", "data": {...} }</p>
<p style="color: rgb(255, 160, 50, 1)">400/401/403/404:  { "status": "error", "code": 1, "message": "...", "data": null }</p>
<p style="color: rgb(255, 100, 100, 1)">500:  { "status": "error", "code": 2, "message": "Internal Server Error", "data": null }</p>

- <p style="color: rgb(100, 210, 100, 1)"><strong>成功响应的 data 嵌套在 <code>data</code> 键里，支持 dict 和 list。</strong></p>

## 异常处理

service 层统一抛异常，不返回 `None`。

- <p style="color: rgb(255, 100, 100, 1)">找不到资源 → <code>raise NotFound('...')</code></p>
- <p style="color: rgb(255, 100, 100, 1)">serializer 校验失败 → <code>serializer.is_valid(raise_exception=True)</code></p>

<p style="color: rgb(100, 210, 100, 1)">所有异常由 <code>common/exceptions.py</code> 里的 exception handler 统一捕获，转成上面的响应格式返回。views 里不需要写 <code>try/except</code>，也不需要手动判断 <code>if not user</code>。</p>

注册在 `settings.py`：

```python
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'common.exceptions.exception_handler',
}
```

## k8s 资源操作

<p style="color: rgb(100, 210, 100, 1)">通过 <code>common/kclient.py</code> 的 <code>KubeClient</code> 连接集群，<code>KubeResourceService</code> 包一层统一调用。</p>

**调用链**

<p style="color: rgb(100, 210, 100, 1)"><code>KubeCluster.kubeconfig → KubeClient → KubeResourceService → views</code></p>

**支持的资源**

| 资源 | 操作 |
|------|------|
| Namespace | list, create, delete |
| Pod | list, get, delete |
| Deployment | list, get, create, update, delete |
| Service | list, get, create, delete |
| ConfigMap | list, get, create, update, delete |

- <p style="color: rgb(255, 160, 50, 1)"><strong>注意：Pod 不支持直接 create，应通过 Deployment 管理。</strong></p>
- <p style="color: rgb(255, 100, 100, 1)">每次操作都会新建一个 <code>KubeClient</code> 实例，后续如有性能需求可考虑连接复用。</p>
