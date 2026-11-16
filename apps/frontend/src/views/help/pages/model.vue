<template>
  <div v-pre>
    <h1>更换检测模型</h1>
    <div class="meta">手上有一个训练好的模型（例如 <code>.joblib</code>），怎么放进项目、在线上启用、出问题怎么回滚。<br>
      <b>全部通过 Git 完成</b>：模型代码和模型文件都在仓库里，合并到 <code>main</code> 后自动部署会同步并重启后端。不需要登录服务器放文件、改 <code>.env</code> 或手动重启。
      写模型的接口细节见 <code>model-kit/README.md</code>，后端怎么调用模型见 <a href="/help/detect">4 检测链路与模型</a>。</div>

    <section id="rules">
      <h2>规则</h2>
      <div class="table-wrap"><table>
        <tr><th>什么</th><th>放在哪</th><th>说明</th></tr>
        <tr><td>模型目录</td><td><code>apps/backend/vigil/detection/&lt;模型名&gt;/</code></td><td>每个模型一个目录，目录名 = 模型名（小写英文和下划线）</td></tr>
        <tr><td>推理代码</td><td><code>&lt;模型名&gt;/model.py</code> + <code>__init__.py</code></td><td>一个继承 <code>BaseDetectionModel</code> 的类</td></tr>
        <tr><td>训练好的模型文件</td><td><code>&lt;模型名&gt;/files/</code></td><td>随代码进 Git（<code>.gitignore</code> 只对这里放行 <code>.joblib</code> / <code>.pkl</code>）</td></tr>
        <tr><td>启用哪些模型</td><td><code>apps/backend/backend/settings.py</code> 的 <code>VIGIL_MODELS</code> 默认值</td><td>走 PR 修改。线上 <code>.env</code> <b>不要</b>写 <code>VIGIL_MODELS</code>，否则会覆盖这里</td></tr>
        <tr><td>训练代码、训练数据</td><td><b>不进 Git</b></td><td>训练由模型方在自己的环境里做（例如本地的 <code>experiments/</code>，已被本地排除）。项目里只放成品</td></tr>
      </table></div>
      <div class="note">只有一个 <code>.joblib</code> 文件不够：平台不知道该给它什么特征、按什么顺序、做什么预处理、输出怎么换算成“是不是攻击”。这些写在 <code>model.py</code> 里。所以先判断是下面哪种情况。</div>
    </section>

    <section id="io">
      <h2>输入与输出</h2>
      <p>平台启动时调用一次 <code>模型类()</code>（<b>不传参数</b>，模型自己从 <code>files/</code> 加载），之后每来一条流调用一次 <code>predict(flow)</code>（当前逐条调用）。</p>
      <div class="table-wrap"><table>
        <tr><th></th><th>类型</th><th>要点</th></tr>
        <tr><td>输入</td><td><code>DetectionInput</code></td><td>一条流的 35 个特征，按属性取：<code>flow.syn_count</code>。<code>flow_duration</code>、<code>iat_*</code> 单位是<b>微秒</b>；<code>protocol</code> 是 <code>"TCP"</code> / <code>"UDP"</code> / <code>"ICMPv4"</code> / <code>"ICMPv6"</code> 文字；<b>没有字节数 / 包长特征</b>；<code>label</code> 推理时为空，不能用</td></tr>
        <tr><td>输出</td><td><code>DetectionResult</code></td><td><code>model_name</code>（= <code>name</code>）、<code>is_attack</code>（Python <code>bool</code>）、<code>confidence</code>（0~1 的 Python <code>float</code>）、<code>attack_type</code>（正常为 <code>None</code>）、<code>raw_output</code>（能转 JSON 的 dict）、<code>explanation</code></td></tr>
      </table></div>
      <p>环境：Python 3.12、scikit-learn <b>1.7.2</b>、numpy 2.4、pandas 3.0、joblib 1.5，没有 torch。用别的 scikit-learn 版本保存的 joblib 可能加载失败。</p>
    </section>

    <section id="update">
      <h2>情况一：同一个模型的新版本（只换模型文件）</h2>
      <p>算法、特征、预处理都没变，只是重新训练了。以 <code>lof_baseline</code> 为例。</p>
      <div class="task"><h4><span class="n">1</span>从最新 main 开分支</h4>
        <div class="do"><div><pre class="on-dev"><code>cd <span class="vn">/home/NEWUSER/github/knettf</span>
git switch main &amp;&amp; git pull origin main
git switch -c model/lof-baseline-日期</code></pre></div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>覆盖模型文件（文件名不变）</h4>
        <div class="do"><div><pre class="on-dev"><code>cp /你的路径/lof.joblib apps/backend/vigil/detection/lof_baseline/files/lof.joblib</code></pre></div></div>
        <div class="why"><div><code>model.py</code> 按固定文件名加载。文件名变了就要改 <code>model.py</code>，属于情况二。</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>检查接口</h4>
        <div class="do"><div><pre class="on-dev"><code>cd apps/backend &amp;&amp; ../../.venv/bin/python manage.py check_model</code></pre></div></div>
        <div class="why"><div>真的加载一遍模型文件并调用 <code>predict</code>，检查返回的字段和类型。文件损坏、scikit-learn 版本不对会在这里报错。</div></div>
        <div class="res"><div><code>✓ vigil.detection.lof_baseline.LofBaselineModel（name=lof_baseline_v1）</code></div></div>
      </div>
      <div class="task"><h4><span class="n">4</span>在正常数据上试跑，看误报率和速度</h4>
        <div class="do"><div><pre class="on-dev"><code>cd ../../model-kit
../.venv/bin/python try_my_model.py --model ../apps/backend/vigil/detection/lof_baseline/model.py:LofBaselineModel</code></pre></div></div>
        <div class="why"><div><code>check_model</code> 只查接口，不查效果。特征单位或预处理和训练时不一致时，接口检查照样通过，但结果全错，只有在数据上跑才看得出来。</div></div>
        <div class="res"><div>“判为攻击”比例就是误报率（2026-11-17 上线的版本为 3.4%）；每条耗时应在毫秒级。明显变差就不要上线。</div></div>
      </div>
      <div class="task"><h4><span class="n">5</span>提交、开 PR</h4>
        <div class="do"><div><pre class="on-dev"><code>cd ..
git add apps/backend/vigil/detection/lof_baseline/files/
git commit -m "lof_baseline：更新模型文件（训练数据 …，误报率 …）"
git push -u origin HEAD</code></pre>在 GitHub 网页开 PR 到 <code>main</code>，描述里写训练数据和第 4 步的结果。</div></div>
      </div>
      <div class="task"><h4><span class="n">6</span>等 CI 通过后合并</h4>
        <div class="do"><div><pre class="on-dev"><code>gh pr checks --watch
gh pr merge --merge</code></pre></div></div>
        <div class="why"><div>CI 的 <code>test_models</code> 会加载 <code>VIGIL_MODELS</code> 里的每个模型并检查接口，不通过不能合并，也不会部署。</div></div>
      </div>
      <div class="task"><h4><span class="n">7</span>等自动部署（2～5 分钟）</h4>
        <div class="do"><div><pre class="on-prod"><code>tail -f <span class="vp">/srv/netsentinel/logs</span>/auto-deploy.log</code></pre></div></div>
        <div class="res"><div>依次出现 <code>==== 部署 … → 新提交</code>、<code>deploy.sh -backend</code>、<code>✓ netsentinel active，HTTP 200</code>。日志里的 <code>⚠ lab 同步失败</code> 与平台无关。</div></div>
      </div>
      <div class="task"><h4><span class="n">8</span>确认线上生效</h4>
        <div class="do"><div><pre class="on-prod"><code>git -C <span class="vp">/srv/netsentinel/prod</span> log --oneline -1
sudo journalctl -u netsentinel --since '-10 min' | grep -i 'not loaded'</code></pre>打开网站 AI Vigil 页面，新检测记录的模型名正确。</div></div>
        <div class="res"><div>线上提交 = 刚合并的提交；没有 <code>not loaded</code>。</div></div>
      </div>
    </section>

    <section id="new">
      <h2>情况二：一个新模型（新算法 / 新特征 / 新预处理）</h2>
      <div class="task"><h4><span class="n">1</span>建模型目录，放入模型文件</h4>
        <div class="do"><div><pre class="on-dev"><code>git switch main &amp;&amp; git pull origin main &amp;&amp; git switch -c model/xgb-v1
D=apps/backend/vigil/detection/xgb_v1
mkdir -p $D/files
cp /你的路径/xgb.joblib $D/files/
cp model-kit/my_model.py $D/model.py
printf 'from .model import XgbModel\n\n__all__ = ["XgbModel"]\n' &gt; $D/__init__.py</code></pre></div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>改写 model.py</h4>
        <div class="do"><div>改模板里标了 <code>TODO</code> 的地方：
          <ul>
            <li>类名改成 <code>XgbModel</code>；<code>name</code> 返回 <code>"xgb_v1"</code>（页面和数据库里的名字，新版本要分开统计就换名字）</li>
            <li><code>__init__</code>：<code>self.clf = joblib.load(self.model_dir / "xgb.joblib")</code></li>
            <li><code>predict</code>：按<b>训练时的特征顺序和预处理</b>从 <code>flow</code> 取特征 → 调模型 → 返回 <code>DetectionResult</code>，<code>is_attack</code> 用 <code>bool(...)</code>、<code>confidence</code> 用 <code>float(...)</code></li>
          </ul></div></div>
        <div class="why"><div>预处理（特征选择、取对数、标准化等）要么已经打包在 joblib 的 Pipeline 里，要么写在 <code>model.py</code> 里，二者必须和训练时一致。</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>启用</h4>
        <div class="do"><div>改 <code>apps/backend/backend/settings.py</code>：<pre class="on-dev"><code>VIGIL_MODELS = env.list("VIGIL_MODELS", default=["vigil.detection.xgb_v1.XgbModel"])
# 与现有模型并行对比（页面上分别显示，每条流每个模型各一条记录）：
# default=["vigil.detection.lof_baseline.LofBaselineModel", "vigil.detection.xgb_v1.XgbModel"]</code></pre></div></div>
      </div>
      <div class="task"><h4><span class="n">4</span>检查、上线</h4>
        <div class="do"><div>同情况一的第 3～8 步（<code>try_my_model.py</code> 的路径换成 <code>../apps/backend/vigil/detection/xgb_v1/model.py:XgbModel</code>），提交时加上 <code>settings.py</code>：<pre class="on-dev"><code>git add apps/backend/vigil/detection/xgb_v1 apps/backend/backend/settings.py</code></pre></div></div>
      </div>
    </section>

    <section id="rollback">
      <h2>回滚与停用</h2>
      <div class="table-wrap"><table>
        <tr><th>要做什么</th><th>怎么做</th></tr>
        <tr><td>回滚到上一个模型 / 上一版文件</td><td>在 GitHub 上对那个 PR 点 <b>Revert</b> → 合并 revert PR → 自动部署</td></tr>
        <tr><td>停用某个模型</td><td>从 <code>settings.py</code> 的 <code>VIGIL_MODELS</code> 里删掉 → PR</td></tr>
        <tr><td>紧急情况（来不及走 PR）</td><td>在线上 <code class="vp">/srv/netsentinel/prod</code><code>/apps/backend/backend/.env</code> 临时写 <code>VIGIL_MODELS=…</code> → <code>sudo systemctl restart netsentinel</code>。<b>事后必须</b>走 PR 改好并删掉这一行，否则以后 PR 里的启用设置都不生效</td></tr>
      </table></div>
      <div class="note">某个模型加载失败（构造函数报错）只会让它没有检测结果，日志出现 <code>model … not loaded: 原因</code>，平台其他部分照常运行。</div>
    </section>

    <section id="perf">
      <h2>资源消耗：为什么换成 LOF</h2>
      <p>2026-11-17 把 <code>ads_ml_ocsvm</code> 换成 <code>lof_baseline_v1</code>，同一台机器实测：</p>
      <div class="table-wrap"><table>
        <tr><th></th><th>ads_ml_ocsvm</th><th>lof_baseline_v1</th></tr>
        <tr><td>单条流推理（逐条调用，单线程）</td><td><b>154 ms</b></td><td><b>1.9 ms</b>（约 80 倍）</td></tr>
        <tr><td>单核每秒能处理的流</td><td>约 6～7 条</td><td>500 条以上</td></tr>
        <tr><td>后端服务平均 CPU</td><td>约 86%（运行 11.5 小时用掉 9 小时 52 分 CPU）</td><td>约 42%（含 Kafka、切流、写库；重启后 30 秒采样）</td></tr>
        <tr><td>后端内存</td><td>峰值 276 MB</td><td>约 270 MB</td></tr>
        <tr><td>模型文件</td><td>11 MB</td><td>7 MB</td></tr>
      </table></div>
      <ul>
        <li><b>内存不随流量增长</b>：模型文件只在启动时加载一次，每条流推理完即释放。服务内存上限 3 GB（systemd <code>MemoryMax</code>），没有 OOM 风险。</li>
        <li><b>没有额外 IO</b>：推理不读写文件；写库量与模型无关（每条流每个模型一条记录）。</li>
        <li>推理慢的模型会让流在队列里积压，后端 CPU 长期占满还会扰动实验集群采到的时间特征。<b>上线新模型前务必看第 4 步的“每条耗时”</b>，建议不超过几毫秒。</li>
        <li>启用多个模型时，耗时和写库量按模型个数叠加。</li>
      </ul>
      <p>自己测某个模型的速度：</p>
<pre class="on-dev"><code>cd apps/backend
OMP_NUM_THREADS=1 ../../.venv/bin/python manage.py shell -c "
import csv, time
from vigil.detection.base import flow_from_dict
from vigil.detection.lof_baseline import LofBaselineModel as M
rows = [flow_from_dict({k: v for k, v in r.items() if k != 'kind'})
        for r, _ in zip(csv.DictReader(open('../../model-kit/data/normal_baseline_sample.csv')), range(300))]
m = M(); t = time.perf_counter(); [m.predict(f) for f in rows]
print(m.name, round((time.perf_counter() - t) / len(rows) * 1000, 3), 'ms/条')"</code></pre>
    </section>
  </div>
</template>
