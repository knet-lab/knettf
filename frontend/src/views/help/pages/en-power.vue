<template>
  <div v-pre lang="en">
    <h1>Shutdown, Startup &amp; Backup</h1>
    <div class="meta">Follow this page before the host shuts down, after it starts, and before any rebuild.</div>

    <section id="auto">
      <h2>What starts by itself</h2>
      <div class="table-wrap"><table>
        <tr><th>Component</th><th>Starts automatically?</th></tr>
        <tr><td>Backend <code>netsentinel</code>, tunnel <code>cloudflared-knettf</code></td><td>Yes — but the backend starts before the cluster, so it must be restarted afterwards</td></tr>
        <tr><td>PostgreSQL container <code>pg</code></td><td>Yes, unless someone ran <code>docker stop pg</code></td></tr>
        <tr><td>5 lab VMs</td><td><b>No</b></td></tr>
        <tr><td>iptables rules for VM internet access</td><td><b>No</b></td></tr>
      </table></div>
    </section>

    <section id="shutdown">
      <h2>Planned shutdown</h2>
      <div class="task"><h4><span class="n">1</span>Stop experiment scripts and remove spoofed IPs</h4>
        <div class="do"><div>Press Ctrl+C in every experiment terminal, then:<pre><code>cd /srv/netsentinel/knetsentinel && sudo .venv/bin/python3 traffic/handle_addr.py --action delete
ip -4 addr show virbr-k8s | grep inet</code></pre></div></div>
        <div class="why"><div>Leftover spoofed addresses mix up the labels of the next experiment.</div></div>
        <div class="res"><div>Only <code>192.168.100.1/24</code> remains.</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>Shut down workers, then the master, then the host</h4>
        <div class="do"><div><pre><code>for v in k8s-node1 k8s-node2 k8s-node3 k8s-node4; do virsh -c qemu:///system shutdown $v; done
virsh -c qemu:///system list --all
virsh -c qemu:///system shutdown k8s-master
sudo reboot</code></pre></div></div>
        <div class="why"><div>A clean shutdown lets etcd and Kafka finish writing. Wait until all workers show <code>shut off</code> before stopping the master.</div></div>
        <div class="res"><div>All VMs shut off within 1–2 minutes. Do not run <code>docker stop pg</code>.</div></div>
      </div>
    </section>

    <section id="startup">
      <h2>Startup after a reboot</h2>
      <div class="task"><h4><span class="n">1</span>Restore VM internet access</h4>
        <div class="do"><div><pre><code>sudo iptables -t nat -C POSTROUTING -s 192.168.100.0/24 ! -d 192.168.100.0/24 -o enp6s0 -j MASQUERADE 2>/dev/null || sudo iptables -t nat -A POSTROUTING -s 192.168.100.0/24 ! -d 192.168.100.0/24 -o enp6s0 -j MASQUERADE
sudo iptables -C FORWARD -s 192.168.100.0/24 -j ACCEPT 2>/dev/null || sudo iptables -A FORWARD -s 192.168.100.0/24 -j ACCEPT
sudo iptables -C FORWARD -d 192.168.100.0/24 -j ACCEPT 2>/dev/null || sudo iptables -A FORWARD -d 192.168.100.0/24 -j ACCEPT</code></pre></div></div>
        <div class="why"><div>These rules are lost on reboot. Safe to run more than once.</div></div>
        <div class="res"><div>No errors.</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>Start the master, then the workers</h4>
        <div class="do"><div><pre><code>virsh -c qemu:///system start k8s-master
until kubectl get --raw=/readyz >/dev/null 2>&1; do sleep 5; done; echo apiserver ready
for v in k8s-node1 k8s-node2 k8s-node3 k8s-node4; do virsh -c qemu:///system start $v; done
kubectl wait --for=condition=Ready node --all --timeout=600s</code></pre></div></div>
        <div class="why"><div>Workers register with the master, so the master must be ready first.</div></div>
        <div class="res"><div><code>apiserver ready</code>, then 5 lines <code>condition met</code>.</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>Wait for Kafka and Vector</h4>
        <div class="do"><div><pre><code>kubectl get pod kafka-controller
kubectl rollout status sts/kafka-broker --timeout=600s
kubectl -n kube-system rollout status ds/vector --timeout=300s
kubectl get svc -A | grep LoadBalancer</code></pre></div></div>
        <div class="why"><div>The backend reaches Kafka at fixed addresses <code>192.168.100.200–203</code>.</div></div>
        <div class="res"><div>Everything rolled out; <code>kafka-0…3-external</code> are <code>.200–.203</code>.</div></div>
      </div>
      <div class="task"><h4><span class="n">4</span>Restart the backend (easy to forget)</h4>
        <div class="do"><div><pre><code>sudo systemctl restart netsentinel
sudo journalctl -u netsentinel --since '-1 min' | grep -E 'AdsMLModel|bridge|drainer'</code></pre></div></div>
        <div class="why"><div>The bridge thread gave up when Kafka was not there at boot and does not reconnect.</div></div>
        <div class="res"><div><code>AdsMLModel loaded</code>, <code>bridge starting</code>, no <code>bridge error</code>. New records appear in <code>/vigil/log</code>.</div></div>
      </div>
    </section>

    <section id="backup">
      <h2>Backup</h2>
      <div class="table-wrap"><table>
        <tr><th>What</th><th>Command</th></tr>
        <tr><td>Users / clusters / Terraform</td><td><code>sqlite3 /srv/netsentinel/prod/backend/db.sqlite3 ".backup '/srv/netsentinel/backups/db_backup_$(date +%F).sqlite3'"</code></td></tr>
        <tr><td>Detection records</td><td><code>docker exec pg pg_dump -U vigil -Fc vigil > /srv/netsentinel/backups/vigil_$(date +%F).dump</code></td></tr>
        <tr><td>Secrets</td><td><code>cp /srv/netsentinel/prod/backend/backend/.env ~/netsentinel_env_$(date +%F)</code></td></tr>
        <tr><td>Lab scripts</td><td><code>tar czf /srv/netsentinel/backups/knetsentinel_$(date +%F).tgz -C /srv/netsentinel --exclude='knetsentinel/.venv' knetsentinel</code></td></tr>
        <tr><td>Daily job</td><td><code>/etc/cron.d/netsentinel</code> (source <code>deploy/cron.netsentinel</code> in the repo)</td></tr>
      </table></div>
      <div class="danger">Rebuilding Kafka or the whole cluster deletes data and takes up to two hours. Back up first and follow the Chinese handbook page 开关机 · 重建 · 备份 step by step.</div>
    </section>
  </div>
</template>
