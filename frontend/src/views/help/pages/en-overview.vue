<template>
  <div v-pre lang="en">
    <h1>System Overview</h1>
    <div class="meta">What NetSentinel is made of, where everything lives, and how data flows from the lab cluster to the website.</div>

    <section id="what">
      <h2>What it does</h2>
      <p>NetSentinel captures network traffic inside a self-built Kubernetes lab cluster, uses a machine-learning model to flag attacks, and shows the results on <code>https://knettf.com</code>. The site can also manage clusters and scan Terraform configs for security problems.</p>
      <div class="table-wrap"><table>
        <tr><th>Project</th><th>What it is</th><th>Directory on the server</th></tr>
        <tr><td><b>NetSentinel</b></td><td>The platform: Django backend (apps <code>kcore</code>, <code>autotf</code>, <code>vigil</code>), Vue 3 frontend, OCSVM detection model</td><td>Development: <code>~/github/NetSentinel</code><br>Production: <code>/srv/netsentinel/prod</code></td></tr>
        <tr><td><b>knetsentinel</b></td><td>The lab: scripts that build 5 KVM VMs, install Kubernetes, Cilium/Hubble, Kafka and Vector, and send normal / attack traffic</td><td><code>/srv/netsentinel/knetsentinel</code></td></tr>
      </table></div>
    </section>

    <section id="flow">
      <h2>How a packet reaches the website</h2>
      <div class="steps">
        <div class="step"><div class="step-title">Traffic is sent</div><p>Scripts in <code>/srv/netsentinel/knetsentinel/traffic/</code> send packets from spoofed source IPs: <code>192.168.100.20–29</code> (attack) and <code>.50–.64</code> (normal).</p></div>
        <div class="step"><div class="step-title">Cilium and Hubble see it</div><p>Cilium (eBPF) on each node observes the packet; Hubble turns it into a JSON flow event.</p></div>
        <div class="step"><div class="step-title">Vector writes it to Kafka</div><p>A Vector pod on every node writes events to the Kafka topic <code>ebpf-net-logs</code>. Kafka's external addresses are <code>192.168.100.200–203:9094</code>.</p></div>
        <div class="step"><div class="step-title">The backend detects</div><p>The <b>bridge</b> thread in the backend reads Kafka, groups packets into flows, computes 35 features; the <b>drainer</b> thread runs the model and inserts results into the PostgreSQL table <code>vigil_detectionrecord</code> (one partition per day).</p></div>
        <div class="step"><div class="step-title">The page shows it</div><p><code>/vigil</code> refreshes every 30 seconds, <code>/vigil/log</code> every 15 seconds.</p></div>
      </div>
    </section>

    <section id="where">
      <h2>Where things live</h2>
      <div class="table-wrap"><table>
        <tr><th>Thing</th><th>Location</th></tr>
        <tr><td>Backend service</td><td>systemd system unit <code>netsentinel</code> (uvicorn on port 8080, runs as account <code>netsentinel</code>), file <code>/etc/systemd/system/netsentinel.service</code></td></tr>
        <tr><td>Public tunnel</td><td>systemd system unit <code>cloudflared-knettf</code> (runs as <code>netsentinel</code>), config <code>/etc/cloudflared/knettf/config.yml</code></td></tr>
        <tr><td>Users, clusters, Terraform data</td><td>SQLite <code>/srv/netsentinel/prod/backend/db.sqlite3</code></td></tr>
        <tr><td>Detection records</td><td>PostgreSQL in Docker container <code>pg</code>, database <code>vigil</code> (development uses <code>vigil_dev</code>)</td></tr>
        <tr><td>Secrets</td><td><code>/srv/netsentinel/prod/backend/backend/.env</code> (not in Git)</td></tr>
        <tr><td>Model files</td><td><code>/srv/netsentinel/prod/backend/vigil/ml/ads_ml/trained/</code></td></tr>
        <tr><td>Daily partition job</td><td><code>/etc/cron.d/netsentinel</code>, runs <code>rotate_partitions</code> as <code>netsentinel</code> at midnight</td></tr>
        <tr><td>Lab VMs</td><td>libvirt <code>k8s-master</code> (<code>192.168.100.10</code>), <code>k8s-node1–4</code> (<code>.11–.14</code>); disks in <code>/home/vm-images/</code></td></tr>
      </table></div>
      <div class="note">Other projects run on this server too (my-code services, pnu-notice and emotion-talk containers, ports 3306 / 8000 / 8081 / 8099). They are not NetSentinel — do not stop or delete them.</div>
    </section>

    <section id="envs">
      <h2>Development vs. production</h2>
      <div class="env-cards">
        <div class="env-card dev"><h4>Development · ~/github/NetSentinel</h4><ul><li>Edit and commit code here</li><li>Run with <code>runserver 8090</code> + <code>pnpm dev</code></li><li>Uses database <code>vigil_dev</code></li></ul></div>
        <div class="env-card prod"><h4>Production · /srv/netsentinel/prod</h4><ul><li>What knettf.com serves</li><li>Owned by account <code>netsentinel</code>; updated only by <code>scripts/deploy.sh</code> from GitHub <code>prod</code></li><li>Never edit or commit here</li></ul></div>
      </div>
    </section>
  </div>
</template>
