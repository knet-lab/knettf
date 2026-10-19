<template>
  <div v-pre lang="en">
    <h1>Deploying Changes</h1>
    <div class="meta">Always: edit and commit on your personal branch in <code>~/github/NetSentinel</code>, push, open a PR into <code>merge-dev</code> and have the other person review it. After the merge run <code>/srv/netsentinel/release.sh -frontend</code> (or <code>-backend</code> / <code>-all</code>): it fast-forwards <code>prod</code> to <code>merge-dev</code> and runs <code>scripts/deploy.sh</code>, which pulls GitHub <code>prod</code> into <code>/srv/netsentinel/prod</code>, builds and restarts. Your account must be in the <code>netsentinel</code> group.</div>

    <section id="branches">
      <h2>Branches and collaboration</h2>
      <pre><code>personal branch ── PR (reviewed by the other person) ──▶ merge-dev ──fast-forward──▶ prod ──deploy.sh──▶ /srv/netsentinel/prod</code></pre>
      <div class="table-wrap"><table>
        <tr><th>Branch</th><th>Who changes it, how</th><th>Purpose</th></tr>
        <tr><td>Personal (<code>soar009</code>, …)</td><td>Owner commits and pushes freely</td><td>Your own workspace, named after your Linux user</td></tr>
        <tr><td><code>merge-dev</code></td><td>Only through reviewed PRs, never a direct push</td><td>Integration branch and GitHub default branch</td></tr>
        <tr><td><code>prod</code></td><td>Only <code>git push origin origin/merge-dev:prod</code> — no commits, no PRs, no force push</td><td>The version running in production</td></tr>
      </table></div>
      <div class="note">Branch protection (Rulesets) is not enforced on this free private repository, so these rules are kept by agreement. Never use <code>git push -f</code>; without it, a non-fast-forward push to prod is rejected. Review happens once, on the PR into merge-dev (Reviewers → Files changed → Review changes → Approve). Check the PR says <b>into merge-dev</b>. Ignore GitHub's “Compare &amp; pull request” banner for prod. To publish after a PR is merged, run <code>/srv/netsentinel/release.sh -frontend</code> (or <code>-backend</code> / <code>-all</code>; no argument = fast-forward only): it lists the commits, asks for <code>y</code>, fast-forwards prod and runs <code>deploy.sh</code>. The script lives only on the server and is git-ignored. To roll back,<code>git revert</code> on your branch and go through the same flow.</div>
      <div class="note">knetsentinel follows the same flow: work on your personal branch in <code>/home/USER/github/knetsentinel</code> → PR into <code>merge-dev</code> → fast-forward <code>master</code> and update the run directory: <code>git -C /srv/netsentinel/knetsentinel push origin origin/merge-dev:master</code>, then <code>git -C /srv/netsentinel/knetsentinel pull --ff-only origin master</code>. Never edit code in <code>/srv/netsentinel/knetsentinel</code>; its data (<code>dataset/</code>, <code>logs/</code>, <code>*.csv</code>) is not in Git.</div>
    </section>

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
docker exec pg pg_dump -U vigil -Fc vigil > /srv/netsentinel/backups/vigil_$(date +%F).dump</code></pre></div></div>
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
