<template>
  <div v-pre lang="en">
    <h1>Troubleshooting &amp; Logs</h1>
    <div class="meta">Find which layer is broken first, from the outside in, then look up the symptom.</div>

    <section id="order">
      <h2>Where to start</h2>
      <div class="table-wrap"><table>
        <tr><th>You see</th><th>Check</th><th>Then</th></tr>
        <tr><td>knettf.com does not open</td><td><code>curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/</code></td><td>Not 200 → backend: <code>sudo journalctl -u netsentinel -n 100</code>. 200 → tunnel: <code>sudo systemctl status cloudflared-knettf</code></td></tr>
        <tr><td>One feature fails</td><td>Browser F12 → Network → failed <code>/api/</code> request</td><td>401 sign in again; 403 not the owner; 404 wrong URL; 500 read the backend log</td></tr>
        <tr><td>No new detections</td><td>Health check step 5 (Kafka)</td><td>No data → cluster side (Vector, hubble-relay). Data → backend log for <code>bridge error</code> / <code>drainer failed</code></td></tr>
      </table></div>
      <div class="learn">Nine times out of ten, "no new detections" means the bridge thread exited. Restarting the backend fixes it.</div>
    </section>

    <section id="symptoms">
      <h2>Symptoms</h2>
      <div class="table-wrap"><table>
        <tr><th>Symptom</th><th>Cause → fix</th></tr>
        <tr><td>White page / 404 for <code>/assets/*.js</code></td><td>Not built or not restarted → <code>/srv/netsentinel/prod/ops/scripts/deploy.sh -frontend</code> (redeploys current prod)</td></tr>
        <tr><td>Logged out right after sign-in</td><td>Session expired (7 days) → sign in again, clear the site's local storage</td></tr>
        <tr><td><code>bridge error</code> in the log</td><td>Kafka unreachable → fix Kafka, then <code>sudo systemctl restart netsentinel</code></td></tr>
        <tr><td><code>drainer failed</code> + <code>no partition of relation</code></td><td>Missing day partition → <code>cd /srv/netsentinel/prod/apps/backend && ../.venv/bin/python manage.py rotate_partitions --database vigil</code></td></tr>
        <tr><td>Detection model empty</td><td>Model files missing or wrong scikit-learn version (must be 1.7.2)</td></tr>
        <tr><td>Kafka has no data</td><td><code>kubectl -n kube-system logs -l app=vector --tail=50</code>; hubble-relay port must be 4245</td></tr>
        <tr><td>Node NotReady</td><td><code>ssh k8s@192.168.100.11 'systemctl status kubelet containerd'</code> (use the node's address)</td></tr>
        <tr><td>Kubernetes page all errors</td><td>Cluster rebuilt, old kubeconfig invalid → delete and re-add the cluster on the website</td></tr>
        <tr><td>Terraform Apply greyed out</td><td>Not scanned, scan unfinished, or HIGH findings → fix and scan again</td></tr>
      </table></div>
    </section>

    <section id="logs">
      <h2>Logs</h2>
      <div class="table-wrap"><table>
        <tr><th>Source</th><th>Command</th></tr>
        <tr><td>Backend (bridge, drainer, model)</td><td><code>sudo journalctl -u netsentinel -f</code></td></tr>
        <tr><td>Tunnel</td><td><code>sudo journalctl -u cloudflared-knettf -f</code></td></tr>
        <tr><td>Partition job</td><td><code>/srv/netsentinel/logs/rotate_partitions.log</code></td></tr>
        <tr><td>PostgreSQL</td><td><code>docker logs --tail 100 pg</code></td></tr>
        <tr><td>Vector / Kafka</td><td><code>kubectl -n kube-system logs -l app=vector --tail=50</code>, <code>kubectl logs kafka-broker-0</code></td></tr>
      </table></div>
    </section>

    <section id="dont">
      <h2>Never do this</h2>
      <div class="table-wrap"><table>
        <tr><th>Don't</th><th>Because</th></tr>
        <tr><td>Delete the <code>kafka-controller</code> pod or any namespace</td><td>It is not recreated; Kafka must be rebuilt</td></tr>
        <tr><td>Edit, commit or <code>git pull</code> inside <code>/srv/netsentinel/prod</code></td><td><code>deploy.sh</code> refuses to deploy over local changes; production is only updated by <code>deploy.sh</code> from GitHub <code>main</code></td></tr>
        <tr><td>Run <code>manage.py runserver</code> in production</td><td>Starts a second bridge that steals Kafka traffic</td></tr>
        <tr><td><code>docker stop pg</code></td><td>A manually stopped container does not start after reboot</td></tr>
        <tr><td>Run cluster scripts with <code>sudo bash</code></td><td>The kubeconfig is written to root's home</td></tr>
        <tr><td><code>users_clear</code> / <code>autotf_clear</code> on production</td><td>Deletes all users and Terraform data</td></tr>
        <tr><td>Apply a Terraform config you don't understand</td><td>Creates real resources and cannot be undone from the site</td></tr>
      </table></div>
    </section>
  </div>
</template>
