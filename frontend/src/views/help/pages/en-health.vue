<template>
  <div v-pre lang="en">
    <h1>Daily Health Check</h1>
    <div class="meta">Once a day, about 5 minutes. Run the steps in order — if one fails, the later ones are meaningless. Until the services are migrated, first run <code>sudo -iu soar009</code>.</div>

    <section id="cli">
      <h2>On the server</h2>
      <div class="task"><h4><span class="n">1</span>Services and port</h4>
        <div class="do"><div><pre class="on-prod"><code>sudo systemctl is-active netsentinel cloudflared-knettf
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/</code></pre></div></div>
        <div class="why"><div><code>netsentinel</code> is the backend and website; <code>cloudflared-knettf</code> publishes it as knettf.com.</div></div>
        <div class="res"><div>Two lines <code>active</code>, then <code>200</code>. <span class="bad">If not</span>: <code>sudo journalctl -u netsentinel -n 50</code>.</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>Model loaded, bridge reading Kafka</h4>
        <div class="do"><div><pre><code>sudo journalctl -u netsentinel --since today | grep -E 'AdsMLModel (loaded|not loaded)' | tail -1
sudo journalctl -u netsentinel --since '-10 min' | grep -E 'vigil.bridge|bridge error' | tail -3</code></pre></div></div>
        <div class="why"><div>The service can be running while detection has stopped: if the bridge thread loses Kafka it exits and <b>never reconnects</b>.</div></div>
        <div class="res"><div><code>AdsMLModel loaded</code>; recent <code>queue: … flows → … attack(s)</code> lines; no <code>bridge error</code>. <span class="bad">bridge error</span>: check step 5, then <code>sudo systemctl restart netsentinel</code>.</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>Database writing, tomorrow's partition exists</h4>
        <div class="do"><div><pre><code>docker exec pg psql -U vigil vigil -Atc "select max(created_at) from vigil_detectionrecord;"
docker exec pg psql -U vigil vigil -Atc "select to_regclass('vigil_detectionrecord_'||to_char(now()+interval '1 day','YYYY_MM_DD'));"
tail -1 /srv/netsentinel/logs/rotate_partitions.log</code></pre></div></div>
        <div class="why"><div>Records are stored in one partition per day. If tomorrow's is missing, every write fails after midnight.</div></div>
        <div class="res"><div>A recent time; a table name (not empty); <code>rotate_partitions done</code>. <span class="bad">Empty second line</span>: <code>cd /srv/netsentinel/prod/backend && ../.venv/bin/python manage.py rotate_partitions --database vigil</code>, then check <code>crontab -l</code>.</div></div>
      </div>
      <div class="task"><h4><span class="n">4</span>Cluster</h4>
        <div class="do"><div><pre><code>virsh -c qemu:///system list --all
kubectl get nodes
kubectl get pods -A | grep -vE 'Running|Completed'</code></pre></div></div>
        <div class="why"><div>The traffic comes from the 5-VM cluster. VMs do not start by themselves after a host reboot.</div></div>
        <div class="res"><div>5 VMs running, 5 nodes Ready, last command prints only the header. <span class="bad">VMs shut off</span>: follow <a href="/help/en-power#startup">Startup</a>.</div></div>
      </div>
      <div class="task"><h4><span class="n">5</span>New data in Kafka</h4>
        <div class="do"><div><pre><code>kubectl exec kafka-broker-0 -- /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka-svc.default.svc.cluster.local:9092 --topic ebpf-net-logs --max-messages 2 --timeout-ms 15000</code></pre></div></div>
        <div class="why"><div>Tells you whether a data problem is on the cluster side or the backend side.</div></div>
        <div class="res"><div>Two JSON lines. Timeout: the cluster side (Vector / Hubble) is broken.</div></div>
      </div>
      <div class="task"><h4><span class="n">6</span>Disk space</h4>
        <div class="do"><div><pre><code>df -h / /home /home/docker-data</code></pre></div></div>
        <div class="why"><div>The database, Kafka and VM disks all live here; a full disk breaks everything at once.</div></div>
        <div class="res"><div>Below 85%. Above: clear <code>/tmp</code>, old logs and CSVs under <code>/srv/netsentinel/prod/backend/vigil/ml/ads_ml/results/</code>.</div></div>
      </div>
    </section>

    <section id="web">
      <h2>On the website</h2>
      <div class="table-wrap"><table>
        <tr><th>Look at</th><th>Normal</th><th>If not</th></tr>
        <tr><td>Sign in at knettf.com</td><td>Works</td><td>Step 1 fine but site down → tunnel: <code>sudo systemctl status cloudflared-knettf</code></td></tr>
        <tr><td>AI Vigil → Detection model</td><td><code>ads_ml_ocsvm</code></td><td>Model failed to load</td></tr>
        <tr><td>Newest log entry</td><td>Minutes old while experiments run</td><td>Restart the backend</td></tr>
        <tr><td>Admin → Users</td><td>You know everyone</td><td>Anyone can register; delete strangers and report</td></tr>
        <tr><td>Admin → TF Tools</td><td>All 5 enabled</td><td>Find out why before re-enabling</td></tr>
      </table></div>
    </section>
  </div>
</template>
