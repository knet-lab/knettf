<template>
  <div v-pre>
        <h1>改动上线</h1>
    <div class="meta">改了代码或配置之后，怎么让它在线上生效、会影响谁、怎么确认成功。<br>
      最常见的前端、后端改动用 <code>scripts/deploy.sh</code> 一条命令完成；其他改动按后面几节逐项做。</div>

    <section id="before">
      <h2>上线前</h2>
      <div class="task"><h4><span class="n">1</span>确认工作区干净、改动是你想要的</h4>
        <div class="do"><div><pre><code>cd $N && git status && git diff</code></pre></div></div>
        <div class="why"><div>线上目录就是 Git 仓库本身。混进别人没提交的改动，或者带着调试代码上线，出了问题很难分清是哪次改动引起的。</div></div>
        <div class="res"><div>只有你这次的改动。<code>dist/</code>、<code>.venv/</code>、<code>node_modules/</code>、<code>db.sqlite3</code>、<code>.env</code> 不提交。</div></div>
      </div>
      <div class="note"><span class="tag tag-k">K</span> knetsentinel 的脚本大多<b>不在 Git 里</b>，改之前先手动备份：<code>cp 03-deploy-5nodes.sh 03-deploy-5nodes.sh.bak_$(date +%F)</code>。</div>
    </section>

    <section id="script">
      <h2>前端 / 后端代码：用部署脚本</h2>

      <div class="task"><h4><span class="n">1</span>改了前端代码，或 public 下的手册</h4>
        <div class="do"><div><pre><code>cd $N && scripts/deploy.sh -frontend</code></pre>脚本执行 <code>pnpm install --frozen-lockfile</code> 和 <code>pnpm build</code>。</div></div>
        <div class="why"><div>浏览器拿到的是 <code>frontend/dist/</code> 里构建好的文件，不是 <code>src/</code> 源码，不构建改动就不会出现。<code>--frozen-lockfile</code> 保证依赖版本和 <code>pnpm-lock.yaml</code> 一致。后端每次请求都从磁盘读 dist，所以<b>不用重启服务</b>，在线用户不受影响。</div></div>
        <div class="res"><div>最后输出 <code>✓ 前端已构建到 frontend/dist</code>。浏览器按 <span class="kbd">Ctrl</span>+<span class="kbd">F5</span> 强制刷新即可看到。<br><span class="bad">构建失败</span>：多半是 TypeScript 类型错误，按报错的文件和行号修改。线上不受影响，旧的 dist 还在。</div></div>
      </div>

      <div class="task"><h4><span class="n">2</span>改了后端 Python 代码</h4>
        <div class="do"><div><pre><code>cd $N && scripts/deploy.sh -backend</code></pre>脚本依次：安装依赖 → <code>manage.py check</code> → <code>migrate</code>（default 库）→ 重启 <code>netsentinel</code> → 最多等 20 秒，确认 8080 返回 200。</div></div>
        <div class="why"><div>Python 代码在进程启动时加载，不重启就还是旧代码。先 <code>check</code> 是为了在重启<b>之前</b>发现语法和配置错误，免得把服务重启成起不来的状态。vigil 库（PostgreSQL）<b>不会</b>自动 migrate：大表 ALTER 可能锁表很久，脚本只提示，由你确认后手动执行。</div></div>
        <div class="res"><div>最后输出 <code>✓ netsentinel active，HTTP 200</code>。<br>副作用：所有 WebSocket 断开（页面和入口 B 检测器会自动重连）；<code>flow_queue</code> 里还没处理的批次丢失；bridge 从 Kafka 已提交的 offset 继续，不重复也不漏。<br><span class="bad">20 秒内没有 200</span>：脚本会打印最后 30 行日志并以失败退出，按其中的 Traceback 修好再跑一次。<br><span class="bad">提示 vigil 有未应用的迁移</span>：看下面“数据库结构”一节。</div></div>
      </div>

      <div class="task"><h4><span class="n">3</span>前后端都改了</h4>
        <div class="do"><div><pre><code>cd $N && scripts/deploy.sh -all</code></pre></div></div>
        <div class="why"><div>先后端再前端：新页面可能要调新接口，后端先就位，新页面一出来就能用。</div></div>
        <div class="res"><div>依次看到上面两步的 ✓，最后是 <code>==&gt; 完成</code>。</div></div>
      </div>
    </section>

    <section id="models">
      <h2>数据库结构（models.py）</h2>
      <div class="task"><h4><span class="n">1</span>先备份</h4>
        <div class="do"><div><pre><code>sqlite3 $N/backend/db.sqlite3 ".backup '$N/backend/db_backup_$(date +%Y%m%d_%H%M%S).sqlite3'"
docker exec pg pg_dump -U vigil -Fc vigil &gt; ~/vigil_$(date +%F).dump     # 改 vigil 表时</code></pre></div></div>
        <div class="why"><div>迁移中途失败可能让表处于改了一半的状态，有备份才能退回去。</div></div>
        <div class="res"><div>生成备份文件，大小不为 0。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>生成迁移并检查 SQL</h4>
        <div class="do"><div><pre><code>cd $N/backend
../.venv/bin/python manage.py makemigrations
../.venv/bin/python manage.py sqlmigrate &lt;app&gt; &lt;编号&gt;</code></pre></div></div>
        <div class="why"><div>执行之前先看清楚会跑什么 SQL，尤其是删列、改类型这类不可逆的操作。vigil 的 <code>DetectionRecord</code> 是 <code>managed=False</code>，改字段<b>不会</b>生成迁移，要手写 <code>RunSQL</code>（<code>ALTER TABLE vigil_detectionrecord ...</code> 会自动作用于所有分区）。</div></div>
        <div class="res"><div>新的迁移文件出现在 <code>&lt;app&gt;/migrations/</code>，SQL 符合预期。</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>执行并重启</h4>
        <div class="do"><div><pre><code>cd $N && scripts/deploy.sh -backend                          # default 库会自动 migrate
cd $N/backend && ../.venv/bin/python manage.py migrate --database=vigil   # 只在改了 vigil 时
systemctl --user restart netsentinel</code></pre></div></div>
        <div class="why"><div>vigil 是大表，ALTER 期间会锁表、阻塞写入，所以单独执行，并挑没有实验的时候做。</div></div>
        <div class="res"><div><code>showmigrations</code> 全部是 <code>[X]</code>，服务返回 200。</div></div>
      </div>
    </section>

    <section id="deps">
      <h2>依赖</h2>
      <div class="task"><h4><span class="n">1</span>Python 依赖</h4>
        <div class="do"><div>把包加进 <code>backend/requirements.txt</code>，然后：<pre><code>cd $N && scripts/deploy.sh -backend</code></pre>整个 <code>.venv</code> 要重建时先停服务：<pre><code>systemctl --user stop netsentinel
cd $N && rm -rf .venv && python3.12 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
systemctl --user start netsentinel</code></pre></div></div>
        <div class="why"><div>服务配置了 <code>Restart=always</code>：<code>.venv</code> 不完整时它每 3 秒重启失败一次，日志会被刷满，所以重建前要先停。</div></div>
        <div class="res"><div>服务 active，返回 200。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>前端依赖</h4>
        <div class="do"><div><pre><code>cd $N/frontend && pnpm add &lt;包&gt;
cd $N && scripts/deploy.sh -frontend</code></pre></div></div>
        <div class="why"><div><code>pnpm add</code> 会同时修改 <code>package.json</code> 和 <code>pnpm-lock.yaml</code>，两个文件都要提交，否则下一个人用 frozen-lockfile 安装时会报错。</div></div>
        <div class="res"><div>构建成功，<code>git status</code> 里能看到两个文件都有改动。</div></div>
      </div>
    </section>

    <section id="model">
      <h2>检测模型文件（ads_ml）</h2>
      <div class="task"><h4><span class="n">1</span>替换文件</h4>
        <div class="do"><div>新的 joblib / CSV 放到 <code>$N/backend/vigil/ml/ads_ml/trained/</code>；文件名变了就同步改 <code>config.yaml</code>。旧文件先改名留着。</div></div>
        <div class="why"><div>新模型不好用时，换回旧文件、重启就能回滚。</div></div>
        <div class="res"><div>文件就位。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>离线自测</h4>
        <div class="do"><div><pre><code>cd $N/backend && ../.venv/bin/python -c "
import django,os;os.environ['DJANGO_SETTINGS_MODULE']='backend.settings';django.setup()
from vigil.ml.models import registry;print(registry.list_models())"</code></pre></div></div>
        <div class="why"><div>模型加载失败时，后端照样能启动，只是不出检测结果。上线前先单独加载一次，确认能用。</div></div>
        <div class="res"><div>输出 <code>['ads_ml_ocsvm']</code>。空列表说明加载失败，常见原因是 scikit-learn 版本和训练时不一致（当前固定 1.7.2）。</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>生效</h4>
        <div class="do"><div><pre><code>systemctl --user restart netsentinel                      # 入口 A
<span class="c"># 入口 B（已部署时）</span>
cd $N/detector && bash build.sh
kubectl -n netsentinel rollout restart deploy/netsentinel-detector</code></pre></div></div>
        <div class="why"><div>模型在进程启动时加载一次。入口 B 的模型打包在镜像里，要重新 build 镜像。</div></div>
        <div class="res"><div>日志出现 <code>AdsMLModel loaded</code>；发一次测试流量（<a href="/help/power#verify">端到端验证</a>）能看到新记录。</div></div>
      </div>
    </section>

    <section id="other">
      <h2>其他改动对照表</h2>
      <div class="table-wrap"><table>
        <tr><th>改了什么</th><th>怎么做</th><th>为什么 / 结果</th></tr>
        <tr><td><code>backend/backend/.env</code></td><td><code>systemctl --user restart netsentinel</code></td><td>环境变量只在进程启动时读一次；重启后用 <a href="/help/health">健康检查</a> 第 1 步确认</td></tr>
        <tr><td>systemd unit 文件</td><td><code>systemctl --user daemon-reload</code> → restart</td><td>不 reload 的话 systemd 还在用旧定义；<code>systemctl --user cat netsentinel</code> 可确认</td></tr>
        <tr><td>cloudflared 配置</td><td><code>systemctl --user restart cloudflared-knettf</code></td><td>公网会中断几秒</td></tr>
        <tr><td>Kafka 地址变了</td><td>改 <code>vigil/bridge.py</code> 的 <code>KAFKA_BOOTSTRAP</code>（入口 B 改 ConfigMap）→ <code>deploy.sh -backend</code></td><td>地址是写死在代码里的；成功后日志有 <code>bridge starting</code> 且没有 <code>bridge error</code></td></tr>
        <tr><td>Vector 配置</td><td><code>kubectl apply -f $K/cilium-vector/vector-5nodes.yaml</code> → <code>kubectl -n kube-system rollout restart ds/vector</code></td><td>重启期间的 Hubble 事件丢失，不会补发</td></tr>
        <tr><td>单个 Kafka broker</td><td><code>kubectl delete pod kafka-broker-N</code>，等它 Running 了再处理下一个</td><td>min.insync.replicas=2，同时停两个以上会导致写入失败；数据在 PVC 上，不会丢</td></tr>
        <tr><td>Kafka controller</td><td><b>不要删</b></td><td>它是裸 Pod + emptyDir，删了不会重建，元数据丢失，只能 <a href="/help/power#rebuild-kafka">重建 Kafka</a></td></tr>
        <tr><td>hubble-relay / Cilium</td><td><code>kubectl -n kube-system rollout restart deploy/hubble-relay</code>（或 <code>ds/cilium</code>）</td><td>Vector 5 秒后自动重连；重启 Cilium 网络会短暂抖动</td></tr>
        <tr><td>单台 VM</td><td><code>kubectl drain k8s-nodeN --ignore-daemonsets --delete-emptydir-data</code> → <code>virsh reboot</code> → <code>kubectl uncordon k8s-nodeN</code></td><td>先 drain 让 Pod 正常迁走；该节点上的 broker 会等节点回来（PVC 绑定在节点上）</td></tr>
        <tr><td>PostgreSQL</td><td><code>docker restart pg</code></td><td>重启期间写库失败，那一批记录丢弃，之后自动恢复</td></tr>
      </table></div>
    </section>
  </div>
</template>
