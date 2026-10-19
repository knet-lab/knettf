<template>
  <div v-pre lang="en">
    <h1>Deploying Changes</h1>
    <div class="meta">Always: edit and commit in the development directory <code>~/github/NetSentinel</code>, push to GitHub, then run <code>scripts/deploy.sh</code> there (your account must be in the <code>netsentinel</code> group). The script pulls GitHub <code>main</code> into <code>/srv/netsentinel/prod</code>, builds and restarts.</div>

    <section id="code">
      <h2>Frontend and backend code</h2>
      <div class="task"><h4><span class="n">1</span>Test and commit</h4>
        <div class="do"><div><pre class="on-dev"><code>cd ~/github/NetSentinel
git status
git add -A
git commit -m "what changed"</code></pre></div></div>
        <div class="why"><div>Only committed code reaches production, so every release maps to one commit you can find or revert.</div></div>
        <div class="res"><div>Only your changes are committed (never <code>dist/</code>, <code>.venv/</code>, <code>node_modules/</code>, <code>db.sqlite3</code>, <code>.env</code>).</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>Deploy</h4>
        <div class="do"><div><pre class="on-both"><code>cd ~/github/NetSentinel
scripts/deploy.sh -frontend     # frontend only
scripts/deploy.sh -backend      # backend only
scripts/deploy.sh -all          # both</code></pre></div></div>
        <div class="why"><div>Frontend: install exact dependencies, build, restart. Backend: install dependencies, <code>manage.py check</code>, collect static files, migrate the <code>default</code> database, restart, wait for HTTP 200.</div></div>
        <div class="res"><div><code>✓ netsentinel active, HTTP 200</code>. Press Ctrl+F5 in the browser. A failed build leaves the old site running — fix the reported file and line.</div></div>
      </div>
      <div class="note">A backend restart drops all WebSocket connections (they reconnect) and loses flows still waiting in the queue. Kafka reading resumes where it left off.</div>
    </section>

    <section id="db">
      <h2>Database model changes</h2>
      <div class="task"><h4><span class="n">1</span>Back up first</h4>
        <div class="do"><div><pre class="on-prod"><code>sqlite3 /srv/netsentinel/prod/backend/db.sqlite3 ".backup '/srv/netsentinel/backups/db_backup_$(date +%Y%m%d_%H%M%S).sqlite3'"
docker exec pg pg_dump -U vigil -Fc vigil > ~/vigil_$(date +%F).dump</code></pre></div></div>
        <div class="why"><div>A migration that fails halfway can leave tables half-changed.</div></div>
        <div class="res"><div>Backup files exist and are not empty.</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>Create and inspect the migration</h4>
        <div class="do"><div><pre class="on-dev"><code>cd ~/github/NetSentinel/backend
../.venv/bin/python manage.py makemigrations
../.venv/bin/python manage.py sqlmigrate APP NUMBER</code></pre></div></div>
        <div class="why"><div>Read the SQL before running it, especially column drops or type changes.</div></div>
        <div class="res"><div>Run it on the development databases first, then commit the migration file.</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>Apply in production</h4>
        <div class="do"><div><pre class="on-prod"><code>cd ~/github/NetSentinel && scripts/deploy.sh -backend
cd /srv/netsentinel/prod/backend && ../.venv/bin/python manage.py migrate --database=vigil
sudo systemctl restart netsentinel</code></pre></div></div>
        <div class="why"><div>The <code>vigil</code> database is never migrated automatically: altering its large table locks writes. Do it when no experiment is running.</div></div>
        <div class="res"><div><code>manage.py showmigrations</code> shows all <code>[X]</code>; the site returns 200.</div></div>
      </div>
    </section>

    <section id="other">
      <h2>Other changes</h2>
      <div class="table-wrap"><table>
        <tr><th>Changed</th><th>Do</th></tr>
        <tr><td>Python dependency</td><td><code>cd ~/github/NetSentinel && uv add PACKAGE</code>, commit, <code>scripts/deploy.sh -backend</code></td></tr>
        <tr><td>Frontend dependency</td><td><code>cd ~/github/NetSentinel/frontend && pnpm add PACKAGE</code>, commit <code>package.json</code> and <code>pnpm-lock.yaml</code>, <code>scripts/deploy.sh -frontend</code></td></tr>
        <tr><td>Production <code>.env</code></td><td>Edit <code>/srv/netsentinel/prod/backend/backend/.env</code>, then <code>sudo systemctl restart netsentinel</code></td></tr>
        <tr><td>systemd unit file</td><td><code>sudo systemctl daemon-reload</code>, then restart the service</td></tr>
        <tr><td>Model files</td><td>Copy into <code>/srv/netsentinel/prod/backend/vigil/ml/ads_ml/trained/</code> (keep the old files renamed), restart, check the log for <code>AdsMLModel loaded</code></td></tr>
      </table></div>
    </section>
  </div>
</template>
