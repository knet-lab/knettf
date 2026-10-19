<template>
  <div v-pre>
        <h1>账号与令牌</h1>
    <div class="meta">网页上只能新建和删除用户（管理后台 Users），其余操作都要用命令行。<br>
      下面的命令都在后端目录里执行：<code class="vp">cd ~/netsentinel-prod/backend</code></div>

    <section id="users">
      <h2>用户</h2>
      <div class="table-wrap"><table>
        <tr><th>要做什么</th><th>命令</th><th>为什么 / 结果</th></tr>
        <tr><td>改密码</td><td><code>../.venv/bin/python manage.py changepassword &lt;用户名&gt;</code></td><td>默认账号 admin / alice / bob 的密码写在 <code>users_init.py</code> 里，等于是公开的，接手后第一时间改掉</td></tr>
        <tr><td>新建超级管理员</td><td><code>../.venv/bin/python manage.py createsuperuser</code></td><td>网页上新建时的 Admin 开关不生效（序列化器会把 <code>is_staff</code> 丢掉）</td></tr>
        <tr><td>设 / 取消管理员</td><td><code>../.venv/bin/python manage.py shell -c "from kcore.models import User;u=User.objects.get(username='alice');u.is_staff=True;u.save()"</code></td><td>下次登录生效；管理员登录后进入 <code>/admin/dashboard</code></td></tr>
        <tr><td>停用账号（不删）</td><td>同上，改成 <code>u.is_active=False</code></td><td>比删除安全：删除会级联删掉他名下所有集群和 Terraform 配置。已经签发的 access token 在过期前（最多 2 小时）仍然有效</td></tr>
        <tr><td>列出所有用户</td><td><code>sqlite3 db.sqlite3 "select id,username,email,is_staff,is_active,last_login from kcore_user;"</code></td><td>注册接口对公网开放，定期看有没有陌生账号</td></tr>
      </table></div>
    </section>

    <section id="token">
      <h2>服务令牌 VIGIL_BRIDGE_TOKEN</h2>
      <p>它是 <code>vigil-bridge</code> 用户的 10 年期 JWT，有两个用途：调用所有需要登录的 REST 接口；入口 B 检测器推送结果时的共享密钥。</p>
      <div class="task"><h4><span class="n">1</span>重新生成</h4>
        <div class="do"><div><pre class="on-prod"><code>../.venv/bin/python manage.py generate_bridge_token --write-env
systemctl --user restart netsentinel</code></pre></div></div>
        <div class="why"><div>token 写进 <code>backend/backend/.env</code>，后端只在启动时读一次，所以要重启。</div></div>
        <div class="res"><div><code>.env</code> 里的值变了，服务 active。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>同步给入口 B（部署了才需要）</h4>
        <div class="do"><div><pre class="on-prod"><code>kubectl -n netsentinel create secret generic detector-secret \
  --from-literal=django-token="$(grep ^VIGIL_BRIDGE_TOKEN= <span class="vp">~/netsentinel-prod</span>/backend/backend/.env | cut -d= -f2-)" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n netsentinel rollout restart deploy/netsentinel-detector</code></pre></div></div>
        <div class="why"><div>后端拿 Secret 里的值和自己的 token 做字符串全等比较，两边对不上，WebSocket 就会以 4401 拒绝连接。</div></div>
        <div class="res"><div>检测器日志出现 <code>connected to Django</code>。</div></div>
      </div>
      <div class="danger"><b>泄露之后光重新生成是不够的</b>：JWT 是无状态的，旧 token 只要签名对、没过期就一直有效。要真正作废，只能停用 <code>vigil-bridge</code> 账号后重建，或者改 <code>SECRET_KEY</code>（所有人都要重新登录）。<br>
        不要删除 <code>vigil-bridge</code> 账号（除非马上重建），不要把 token、kubeconfig、<code>.env</code> 发到群聊或截图里。</div>
    </section>
  </div>
</template>
