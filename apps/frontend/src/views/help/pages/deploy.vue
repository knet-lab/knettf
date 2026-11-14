<template>
  <div v-pre>
        <h1>改动上线</h1>
    <div class="meta">改了代码或配置之后，怎么让它在线上生效、会影响谁、怎么确认成功。<br>
      流程固定为：在开发目录 <code class="vn">/home/NEWUSER/github/knettf</code> 从最新 <code>main</code> 建<b>任务分支</b> → 提交 → 把最新 <code>main</code> 合进任务分支并本地检查 → push → 在 GitHub 网页开 PR 合入 <code>main</code> → 删除任务分支 → 在服务器运行 <code>ops/scripts/deploy.sh</code>，把线上目录 <code class="vp">/srv/netsentinel/prod</code> 更新到 <code>main</code> 并构建、重启。两个目录的分工见 <a href="/help/index#envs">开发与生产</a>。</div>

    <section id="branches">
      <h2>分支规则</h2>
      <div class="table-wrap"><table>
        <tr><th>分支</th><th>怎么改</th><th>作用</th></tr>
        <tr><td><code>main</code></td><td><b>只通过 GitHub 网页 PR 合入</b>，不直接 push、不 force push。本地 <code>main</code> 只用来 <code>git pull</code>，不在上面 commit 或 merge</td><td>唯一的长期分支，GitHub 默认分支；线上运行的就是它</td></tr>
        <tr><td>任务分支（<code>feat/…</code>、<code>fix/…</code>、<code>docs/…</code>）</td><td>本人随便 commit / push</td><td>一件事一个分支，从最新 <code>main</code> 建；PR 合并后删除（远端 + 本地）</td></tr>
      </table></div>
      <div class="note">仓库是免费组织的私有仓库，GitHub 的分支保护（Rulesets）<b>不生效</b>，以上规则靠大家遵守。<b>任何时候都不要用 <code>git push -f</code></b>。动手前先 <code>git status</code>，确认第一行不是 <code>On branch main</code>。</div>
    </section>

    <section id="before">
      <h2>日常流程</h2>
      <div class="task"><h4><span class="n">1</span>从最新 main 建任务分支</h4>
        <div class="do"><div><pre class="on-dev"><code>cd <span class="vn">/home/NEWUSER/github/knettf</span>
git switch main && git pull origin main
git switch -c feat/简短说明</code></pre></div></div>
        <div class="why"><div>从最新的 <code>main</code> 出发，后面的冲突最少。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>在任务分支上改代码、提交</h4>
        <div class="do"><div><pre class="on-dev"><code>git status && git diff
git add -A && git commit -m "模块：说明"</code></pre>开发时可在开发环境（<code>runserver 8090</code> + <code>pnpm dev</code>）里试。</div></div>
        <div class="res"><div>只有你这次的改动。<code>dist/</code>、<code>.venv/</code>、<code>node_modules/</code>、<code>*.sqlite3</code>、<code>.env</code>、数据文件不会被提交（已在 <code>.gitignore</code> 里）。</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>把最新 main 合进任务分支，本地检查</h4>
        <div class="do"><div><pre class="on-dev"><code>git switch main && git pull origin main
git switch feat/简短说明 && git merge main      # 有冲突就在这里解决，再 git add + git commit
ops/scripts/check.sh                            # 或只查改到的部分：check.sh backend / frontend / lab / detector</code></pre></div></div>
        <div class="why"><div>别人刚合进 <code>main</code> 的改动先在你的分支里合并、测试，冲突和报错都留在任务分支上解决，不会带进 <code>main</code>。</div></div>
        <div class="res"><div><code>check.sh</code> 最后输出 <code>✓ 全部通过</code>。</div></div>
      </div>
      <div class="task"><h4><span class="n">4</span>push，在 GitHub 网页开 PR 合入 main</h4>
        <div class="do"><div><pre class="on-dev"><code>git push -u origin feat/简短说明</code></pre>打开 GitHub 上的 knet-lab/knettf，点黄色提示条 <b>Compare &amp; pull request</b>（或 Pull requests → New）。确认方向是 <b>base: main ← compare: feat/简短说明</b>，页面显示 <b>Able to merge</b>，点 <b>Create pull request</b>；有其他成员时在 Reviewers 里选人审查（Files changed → Review changes → Approve）。然后点 <b>Merge pull request</b>，再点 <b>Delete branch</b> 删除远端任务分支。</div></div>
        <div class="why"><div>进入 <code>main</code> 的每个改动都有 PR 记录，能查到是谁、为什么改的。</div></div>
        <div class="res"><div>PR 显示 <code>merged … into main</code>。</div></div>
      </div>
      <div class="task"><h4><span class="n">5</span>同步本地、删除任务分支</h4>
        <div class="do"><div><pre class="on-dev"><code>git switch main && git pull origin main
git branch -d feat/简短说明
git fetch --prune                               # 清掉已在网页上删除的远端分支</code></pre></div></div>
      </div>
      <div class="task"><h4><span class="n">6</span>上线：部署 main</h4>
        <div class="do"><div><pre class="on-prod"><code>/srv/netsentinel/prod/ops/scripts/deploy.sh -frontend    # 或 -backend / -all</code></pre>脚本在 <code class="vp">/srv/netsentinel/prod</code> 里用运行者自己的 GitHub 密钥 <code>git pull --ff-only origin main</code>，然后构建 / 迁移，重启 <code>netsentinel</code>，确认 HTTP 200。运行者必须在 <code>netsentinel</code> 组里；线上目录有本地改动或不在 <code>main</code> 分支时脚本拒绝部署。注意：<code>deploy.sh</code> 在 pull 之前就开始运行，执行的是线上目录里旧的那份；如果这次改了 <code>deploy.sh</code> 本身，新版本从下一次部署才生效。</div></div>
        <div class="why"><div>合并进 <code>main</code> 不会自动上线，什么时候部署由人决定。线上当前版本：<code>git -C /srv/netsentinel/prod log --oneline -1</code>。</div></div>
      </div>
      <div class="task"><h4><span class="n">7</span>常见情况</h4>
        <div class="do"><div><div class="table-wrap"><table>
          <tr><th>情况</th><th>做法</th></tr>
          <tr><td>PR 冲突（This branch has conflicts）</td><td>回到第 3 步：在任务分支上 <code>git merge main</code>，解决冲突、检查后 push，PR 自动变为可合并</td></tr>
          <tr><td>PR 的 base 选错了</td><td>合并前：PR 标题旁 Edit，把 base 改成 <code>main</code></td></tr>
          <tr><td>不小心在本地 main 上 commit 了</td><td>还没 push：<code>git switch -c feat/补救</code> 把提交带到新分支，再 <code>git switch main && git reset --hard origin/main</code></td></tr>
          <tr><td>上线后出问题要回退</td><td>新建任务分支 <code>git revert &lt;提交&gt;</code> → PR → 部署。不要在线上目录里改代码</td></tr>
          <tr><td>新成员加入</td><td>owner 在 GitHub 邀请进 knet-lab；Linux 账户见 <a href="/help/prepare">接手准备</a>；克隆后直接按第 1 步建任务分支</td></tr>
        </table></div></div></div>
        <div class="res"><div><code>git branch -a</code> 只看到 <code>main</code> 和正在进行的任务分支。</div></div>
      </div>
      <div class="note"><span class="tag tag-k">K</span> 实验环境 <code>lab/</code> 在同一个仓库，走同样的 PR 流程。合并到 <code>main</code> 后，在自己的开发目录里同步到运行目录：<pre><code>cd /home/NEWUSER/github/knettf &amp;&amp; git switch main &amp;&amp; git pull --ff-only
bash lab/sync-to-srv.sh -n     # 先看会改哪些文件
bash lab/sync-to-srv.sh</code></pre>只同步 Git 里的文件，运行目录里的数据（<code>dataset/*.csv</code>、<code>logs/</code>、<code>.env</code>、<code>.venv</code>）不会被覆盖或删除。不要直接在 <code>/srv/netsentinel/lab</code> 里改代码。</div>
    </section>

    <section id="script">
      <h2>前端 / 后端代码：用发布脚本</h2>
      <p>下面每一步都在 PR 合并到 <code>main</code> 之后，在服务器上运行。<code class="vp">/srv/netsentinel/prod</code><code>/ops/scripts/deploy.sh</code> 先把线上目录 <code>git pull --ff-only</code> 到 GitHub 上最新的 <code>main</code>，再按参数构建、重启；<code>main</code> 没有新提交时就是按当前版本重新构建。</p>

      <div class="task"><h4><span class="n">1</span>改了前端代码（含 <code>src/views/help/pages/</code> 下的手册）</h4>
        <div class="do"><div><pre class="on-prod"><code>/srv/netsentinel/prod/ops/scripts/deploy.sh -frontend      # PR 合并到 main 之后</code></pre>脚本在 <code class="vp">/srv/netsentinel/prod</code> 里 <code>git pull</code> → <code>pnpm install --frozen-lockfile</code> → <code>pnpm build</code> → 重启 <code>netsentinel</code>。</div></div>
        <div class="why"><div>浏览器拿到的是 <code>apps/frontend/dist/</code> 里构建好的文件，不是 <code>src/</code> 源码，不构建改动就不会出现。<code>--frozen-lockfile</code> 保证依赖版本和 <code>pnpm-lock.yaml</code> 一致。线上 <code>DEBUG=False</code>，WhiteNoise 只在进程启动时扫描一次 dist，新构建的文件（文件名带新哈希）要<b>重启后</b>才能被访问，所以脚本最后会重启服务，副作用同下面后端那一步。</div></div>
        <div class="res"><div>最后输出 <code>✓ netsentinel active，HTTP 200</code>。浏览器按 <span class="kbd">Ctrl</span>+<span class="kbd">F5</span> 强制刷新即可看到。<br><span class="bad">构建失败</span>：多半是 TypeScript 类型错误，按报错的文件和行号修改。线上不受影响，旧的 dist 还在。</div></div>
      </div>

      <div class="task"><h4><span class="n">2</span>改了后端 Python 代码</h4>
        <div class="do"><div><pre class="on-prod"><code>/srv/netsentinel/prod/ops/scripts/deploy.sh -backend      # PR 合并到 main 之后</code></pre>脚本依次：<code>git pull</code> → <code>uv sync --frozen</code> → <code>manage.py check</code> → <code>collectstatic</code> → <code>migrate</code>（default 库）→ 重启 <code>netsentinel</code> → 最多等 20 秒，确认 8080 返回 200。</div></div>
        <div class="why"><div>Python 代码在进程启动时加载，不重启就还是旧代码。先 <code>check</code> 是为了在重启<b>之前</b>发现语法和配置错误，免得把服务重启成起不来的状态。vigil 库（PostgreSQL）<b>不会</b>自动 migrate：大表 ALTER 可能锁表很久，脚本只提示，由你确认后手动执行。</div></div>
        <div class="res"><div>最后输出 <code>✓ netsentinel active，HTTP 200</code>。<br>副作用：所有 WebSocket 断开（页面和入口 B 检测器会自动重连）；<code>flow_queue</code> 里还没处理的批次丢失；bridge 从 Kafka 已提交的 offset 继续，不重复也不漏。<br><span class="bad">20 秒内没有 200</span>：脚本会打印最后 30 行日志并以失败退出，按其中的 Traceback 修好再跑一次。<br><span class="bad">提示 vigil 有未应用的迁移</span>：看下面“数据库结构”一节。</div></div>
      </div>

      <div class="task"><h4><span class="n">3</span>前后端都改了</h4>
        <div class="do"><div><pre class="on-prod"><code>/srv/netsentinel/prod/ops/scripts/deploy.sh -all      # PR 合并到 main 之后</code></pre></div></div>
        <div class="why"><div>先后端再前端，最后只重启一次。</div></div>
        <div class="res"><div>依次看到上面两步的 ✓，最后是 <code>==&gt; 完成</code>。</div></div>
      </div>
    </section>

    <section id="models">
      <h2>数据库结构（models.py）</h2>
      <div class="task"><h4><span class="n">1</span>先备份</h4>
        <div class="do"><div><pre class="on-prod"><code>sqlite3 <span class="vp">/srv/netsentinel/prod</span>/apps/backend/db.sqlite3 ".backup '/srv/netsentinel/backups/db_backup_$(date +%Y%m%d_%H%M%S).sqlite3'"
docker exec pg pg_dump -U vigil -Fc vigil &gt; /srv/netsentinel/backups/vigil_$(date +%F).dump     # 改 vigil 表时</code></pre></div></div>
        <div class="why"><div>迁移中途失败可能让表处于改了一半的状态，有备份才能退回去。</div></div>
        <div class="res"><div>生成备份文件，大小不为 0。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>在开发目录生成迁移并检查 SQL</h4>
        <div class="do"><div><pre class="on-dev"><code>cd <span class="vn">/home/NEWUSER/github/knettf</span>/apps/backend
../../.venv/bin/python manage.py makemigrations
../../.venv/bin/python manage.py sqlmigrate &lt;app&gt; &lt;编号&gt;</code></pre></div></div>
        <div class="why"><div>执行之前先看清楚会跑什么 SQL，尤其是删列、改类型这类不可逆的操作。vigil 的 <code>DetectionRecord</code> 是 <code>managed=False</code>，改字段只会生成<b>不执行 SQL</b> 的状态迁移（<code>sqlmigrate</code> 显示 <code>(no-op)</code>），真正改表要在同一个迁移里手写 <code>RunSQL</code>（<code>ALTER TABLE vigil_detectionrecord ...</code> 会自动作用于所有分区）。</div></div>
        <div class="res"><div>新的迁移文件出现在 <code>&lt;app&gt;/migrations/</code>，SQL 符合预期。先在开发库执行（<code>migrate</code>、<code>migrate --database=vigil</code>，开发的 vigil 库是 <code>vigil_dev</code>）确认没问题，再提交迁移文件。</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>执行并重启</h4>
        <div class="do"><div><pre class="on-both"><code>/srv/netsentinel/prod/ops/scripts/deploy.sh -backend      # PR 合并后；default 库会自动 migrate
cd <span class="vp">/srv/netsentinel/prod</span>/apps/backend && ../../.venv/bin/python manage.py migrate --database=vigil   # 只在改了 vigil 时
sudo systemctl restart netsentinel</code></pre></div></div>
        <div class="why"><div>vigil 是大表，ALTER 期间会锁表、阻塞写入，所以单独执行，并挑没有实验的时候做。</div></div>
        <div class="res"><div><code>showmigrations</code> 全部是 <code>[X]</code>，服务返回 200。</div></div>
      </div>
    </section>

    <section id="deps">
      <h2>依赖</h2>
      <div class="task"><h4><span class="n">1</span>Python 依赖</h4>
        <div class="do"><div>在开发目录 <code>uv add 包名</code> 并提交，然后：<pre class="on-prod"><code>/srv/netsentinel/prod/ops/scripts/deploy.sh -backend      # PR 合并到 main 之后</code></pre>整个 <code>.venv</code> 要重建时先停服务：<pre class="on-prod"><code>sudo systemctl stop netsentinel
cd <span class="vp">/srv/netsentinel/prod</span> && rm -rf .venv && uv sync --frozen
sudo systemctl start netsentinel</code></pre></div></div>
        <div class="why"><div>服务配置了 <code>Restart=always</code>：<code>.venv</code> 不完整时它每 3 秒重启失败一次，日志会被刷满，所以重建前要先停。</div></div>
        <div class="res"><div>服务 active，返回 200。</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>前端依赖</h4>
        <div class="do"><div><pre class="on-both"><code>cd <span class="vn">/home/NEWUSER/github/knettf</span>/apps/frontend && pnpm add &lt;包&gt;     # 提交、push、PR 合并后：
/srv/netsentinel/prod/ops/scripts/deploy.sh -frontend</code></pre></div></div>
        <div class="why"><div><code>pnpm add</code> 会同时修改 <code>package.json</code> 和 <code>pnpm-lock.yaml</code>，两个文件都要提交，否则下一个人用 frozen-lockfile 安装时会报错。</div></div>
        <div class="res"><div>构建成功，<code>git status</code> 里能看到两个文件都有改动。</div></div>
      </div>
    </section>

    <section id="model">
      <h2>检测模型文件（ads_ml）</h2>
      <p>模型文件不在 Git 里，也不随 <code>deploy.sh</code> 发布：线上按版本放在 <code class="vp">/srv/netsentinel/models/ads_ml/current</code> 指向的目录，由 <code>.env</code> 的 <code>VIGIL_ADS_ML_CONFIG</code> 指定。换版本 = 新建版本目录 → <code>manage.py check_model --config …</code> → 改 <code>current</code> 软链接 → 重启；回滚把软链接指回旧版本再重启。完整步骤和流程图见 <a href="/help/detect#newmodel">4.11 替换模型与新增模型</a>。</p>
      <p>新增一个模型类（代码）照常走 PR 和 <code>deploy.sh -backend</code>，上线后在 <code>.env</code> 的 <code>VIGIL_MODELS</code> 里启用。</p>
    </section>

    <section id="other">
      <h2>其他改动对照表</h2>
      <div class="table-wrap"><table>
        <tr><th>改了什么</th><th>怎么做</th><th>为什么 / 结果</th></tr>
        <tr><td>线上 <code class="vp">/srv/netsentinel/prod/apps/backend/backend/.env</code></td><td>直接编辑（不进 Git）→ <code>sudo systemctl restart netsentinel</code></td><td>环境变量只在进程启动时读一次；重启后用 <a href="/help/health">健康检查</a> 第 1 步确认</td></tr>
        <tr><td>systemd unit 文件</td><td><code>sudo systemctl daemon-reload</code> → restart</td><td>不 reload 的话 systemd 还在用旧定义；<code>systemctl cat netsentinel</code> 可确认</td></tr>
        <tr><td>cloudflared 配置</td><td><code>sudo systemctl restart cloudflared-knettf</code></td><td>公网会中断几秒</td></tr>
        <tr><td>Kafka 地址变了</td><td>改 <code>vigil/bridge.py</code> 的 <code>KAFKA_BOOTSTRAP</code>（入口 B 改 ConfigMap）→ PR → <code>deploy.sh -backend</code></td><td>地址是写死在代码里的；成功后日志有 <code>bridge starting</code> 且没有 <code>bridge error</code></td></tr>
        <tr><td>Vector 配置</td><td><code>kubectl apply -f /srv/netsentinel/lab/manifests/vector-5nodes.yaml</code> → <code>kubectl -n kube-system rollout restart ds/vector</code></td><td>重启期间的 Hubble 事件丢失，不会补发</td></tr>
        <tr><td>单个 Kafka broker</td><td><code>kubectl delete pod kafka-broker-N</code>，等它 Running 了再处理下一个</td><td>min.insync.replicas=2，同时停两个以上会导致写入失败；数据在 PVC 上，不会丢</td></tr>
        <tr><td>Kafka controller</td><td><b>不要删</b></td><td>它是裸 Pod + emptyDir，删了不会重建，元数据丢失，只能 <a href="/help/power#rebuild-kafka">重建 Kafka</a></td></tr>
        <tr><td>hubble-relay / Cilium</td><td><code>kubectl -n kube-system rollout restart deploy/hubble-relay</code>（或 <code>ds/cilium</code>）</td><td>Vector 5 秒后自动重连；重启 Cilium 网络会短暂抖动</td></tr>
        <tr><td>单台 VM</td><td><code>kubectl drain k8s-nodeN --ignore-daemonsets --delete-emptydir-data</code> → <code>virsh reboot</code> → <code>kubectl uncordon k8s-nodeN</code></td><td>先 drain 让 Pod 正常迁走；该节点上的 broker 会等节点回来（PVC 绑定在节点上）</td></tr>
        <tr><td>PostgreSQL</td><td><code>docker restart pg</code></td><td>重启期间写库失败，那一批记录丢弃，之后自动恢复</td></tr>
      </table></div>
    </section>
  </div>
</template>
