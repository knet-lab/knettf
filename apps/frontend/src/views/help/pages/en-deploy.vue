<template>
  <div v-pre lang="en">
    <h1>Deploying Changes</h1>
    <div class="meta">Always: in <code>/home/NEWUSER/github/knettf</code> create a task branch from the latest <code>main</code>, commit, merge the latest <code>main</code> into it and run <code>ops/scripts/check.sh</code>, push, then open and merge a PR into <code>main</code> on the GitHub website and delete the branch. To go live run <code>/srv/netsentinel/prod/ops/scripts/deploy.sh -frontend</code> (or <code>-backend</code> / <code>-all</code>): it pulls <code>main</code> into <code>/srv/netsentinel/prod</code>, builds and restarts. Your account must be in the <code>netsentinel</code> group.</div>

    <section id="branches">
      <h2>Branches</h2>
      <pre class="uml">flowchart LR
  A["Task branch feat/…"] -->|"PR on GitHub"| B["main"]
  B -->|"deploy.sh"| D["/srv/netsentinel/prod"]</pre>
      <div class="table-wrap"><table>
        <tr><th>Branch</th><th>Who changes it, how</th><th>Purpose</th></tr>
        <tr><td><code>main</code></td><td>Only through PRs merged on the GitHub website; never a direct or force push. Your local <code>main</code> is only ever pulled, never committed or merged into</td><td>The only long-lived branch; GitHub default branch; what production runs</td></tr>
        <tr><td>Task branches (<code>feat/…</code>, <code>fix/…</code>, <code>docs/…</code>)</td><td>Owner commits and pushes freely</td><td>One per task, created from the latest <code>main</code>, deleted (remote and local) after the PR is merged</td></tr>
      </table></div>
      <div class="note">The repository is public and <code>main</code> is protected by a GitHub Ruleset: changes must go through a PR; direct push, force push and deletion are blocked. Never use <code>git push -f</code>. Run <code>git status</code> before working and make sure it does not say <code>On branch main</code>. If a PR has conflicts, merge <code>main</code> into your task branch, resolve, re-run <code>check.sh</code> and push. To roll back, create a task branch, <code>git revert</code> the commit, PR, deploy.</div>
      <div class="note">The lab (<code>lab/</code>) lives in the same repository and follows the same PR flow. After merging into <code>main</code>, run <code>bash /srv/netsentinel/lab/sync-to-srv.sh -n</code> (preview) and <code>bash /srv/netsentinel/lab/sync-to-srv.sh</code>. The run directory is a sparse Git checkout of <code>lab/</code> (<code>/srv/netsentinel/lab-repo</code>); the script fast-forwards it to GitHub <code>main</code> and refuses if tracked files were edited there. Ignored data (<code>*.csv</code>, <code>logs/</code>, <code>.env</code>, <code>.venv</code>) is never touched. Never edit code in <code>/srv/netsentinel/lab</code>.</div>
    </section>

    <section id="code">
      <h2>Frontend and backend code</h2>
      <div class="task"><h4><span class="n">1</span>Test and commit</h4>
        <div class="do"><div><pre class="on-dev"><code>cd /home/NEWUSER/github/knettf
git status
git add -A
git commit -m "what changed"</code></pre></div></div>
        <div class="why"><div>Only committed code reaches production, so every release maps to one commit you can find or revert.</div></div>
        <div class="res"><div>Only your changes are committed (never <code>dist/</code>, <code>.venv/</code>, <code>node_modules/</code>, <code>db.sqlite3</code>, <code>.env</code>).</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>Push, PR, release</h4>
        <div class="do"><div><pre class="on-prod"><code># after the PR into main is merged
/srv/netsentinel/prod/ops/scripts/deploy.sh -frontend     # frontend only
/srv/netsentinel/prod/ops/scripts/deploy.sh -backend      # backend only
/srv/netsentinel/prod/ops/scripts/deploy.sh -all          # both</code></pre></div></div>
        <div class="why"><div>Frontend: install exact dependencies, build, restart. Backend: install dependencies, <code>manage.py check</code>, collect static files, migrate the <code>default</code> database, restart, wait for HTTP 200.</div></div>
        <div class="res"><div><code>✓ netsentinel active, HTTP 200</code>. Press Ctrl+F5 in the browser. A failed build leaves the old site running — fix the reported file and line.</div></div>
      </div>
      <div class="note">A backend restart drops all WebSocket connections (they reconnect) and loses flows still waiting in the queue. Kafka reading resumes where it left off.</div>
    </section>

    <section id="db">
      <h2>Database model changes</h2>
      <div class="task"><h4><span class="n">1</span>Back up first</h4>
        <div class="do"><div><pre class="on-prod"><code>sqlite3 /srv/netsentinel/prod/apps/backend/db.sqlite3 ".backup '/srv/netsentinel/backups/db_backup_$(date +%Y%m%d_%H%M%S).sqlite3'"
docker exec pg pg_dump -U vigil -Fc vigil > /srv/netsentinel/backups/vigil_$(date +%F).dump</code></pre></div></div>
        <div class="why"><div>A migration that fails halfway can leave tables half-changed.</div></div>
        <div class="res"><div>Backup files exist and are not empty.</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>Create and inspect the migration</h4>
        <div class="do"><div><pre class="on-dev"><code>cd /home/NEWUSER/github/knettf/backend
../.venv/bin/python manage.py makemigrations
../.venv/bin/python manage.py sqlmigrate APP NUMBER</code></pre></div></div>
        <div class="why"><div>Read the SQL before running it, especially column drops or type changes.</div></div>
        <div class="res"><div>Run it on the development databases first, then commit the migration file.</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>Apply in production</h4>
        <div class="do"><div><pre class="on-prod"><code>/srv/netsentinel/prod/ops/scripts/deploy.sh -backend
cd /srv/netsentinel/prod/apps/backend && ../.venv/bin/python manage.py migrate --database=vigil
sudo systemctl restart netsentinel</code></pre></div></div>
        <div class="why"><div>The <code>vigil</code> database is never migrated automatically: altering its large table locks writes. Do it when no experiment is running.</div></div>
        <div class="res"><div><code>manage.py showmigrations</code> shows all <code>[X]</code>; the site returns 200.</div></div>
      </div>
    </section>

    <section id="other">
      <h2>Other changes</h2>
      <div class="table-wrap"><table>
        <tr><th>Changed</th><th>Do</th></tr>
        <tr><td>Python dependency</td><td><code>cd /home/NEWUSER/github/knettf && uv add PACKAGE</code>, commit, PR, then <code>/srv/netsentinel/prod/ops/scripts/deploy.sh -backend</code></td></tr>
        <tr><td>Frontend dependency</td><td><code>cd /home/NEWUSER/github/knettf/frontend && pnpm add PACKAGE</code>, commit <code>package.json</code> and <code>pnpm-lock.yaml</code>, PR, then <code>/srv/netsentinel/prod/ops/scripts/deploy.sh -frontend</code></td></tr>
        <tr><td>Production <code>.env</code></td><td>Edit <code>/srv/netsentinel/prod/apps/backend/backend/.env</code>, then <code>sudo systemctl restart netsentinel</code></td></tr>
        <tr><td>systemd unit file</td><td><code>sudo systemctl daemon-reload</code>, then restart the service</td></tr>
        <tr><td>Model files</td><td>Create a new version directory under <code>/srv/netsentinel/models/ads_ml/</code>, run <code>manage.py check_model --config &lt;dir&gt;/config.yaml</code>, point the <code>current</code> symlink at it, restart. Roll back by pointing <code>current</code> at the old version and restarting.</td></tr>
      </table></div>
    </section>
  </div>
</template>
