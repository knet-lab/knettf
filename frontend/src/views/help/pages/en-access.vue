<template>
  <div v-pre lang="en">
    <h1>Accounts, Permissions &amp; GitHub</h1>
    <div class="meta">Do this once, before touching any service. When all seven checks at the end pass, you are ready to take over. In the commands, replace <code>NEWUSER</code> with your own Linux user name.</div>

    <section id="linux">
      <h2>Your own Linux account</h2>
      <div class="danger">Never use the shared <code>cis</code> account. It has every permission, and nothing done with it can be traced to a person.</div>
      <div class="task"><h4><span class="n">1</span>Request the account</h4>
        <div class="do"><div>Send the lab head your user name, your SSH public key, and which groups you need and why. Create the key on your own computer:<pre><code>ssh-keygen -t ed25519 -C "NEWUSER@cis-Z10PE-D8-WS"
cat /home/NEWUSER/.ssh/id_ed25519.pub</code></pre></div></div>
        <div class="why"><div>The server only accepts SSH keys, not passwords. The approval should be written (email or chat) and kept.</div></div>
        <div class="res"><div>Written approval.</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>An existing admin creates it</h4>
        <div class="do"><div><pre><code>sudo adduser NEWUSER
sudo usermod -aG sudo,docker,libvirt NEWUSER
sudo install -d -o NEWUSER -g NEWUSER -m 700 /home/NEWUSER/.ssh
echo 'ssh-ed25519 AAAA... NEWUSER@cis-Z10PE-D8-WS' | sudo tee -a /home/NEWUSER/.ssh/authorized_keys
sudo chown NEWUSER:NEWUSER /home/NEWUSER/.ssh/authorized_keys
sudo chmod 600 /home/NEWUSER/.ssh/authorized_keys</code></pre></div></div>
        <div class="why"><div>Add only the approved groups. <code>sudo</code> = full admin; <code>docker</code> = manage the database container; <code>libvirt</code> = start / stop the lab VMs.</div></div>
        <div class="res"><div><code>ssh NEWUSER@192.168.0.247</code> logs in without a password prompt. From outside the lab, use Tailscale address <code>100.117.219.123</code> (ask the original author to invite you to the tailnet).</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>Get cluster access</h4>
        <div class="do"><div><pre><code>sudo install -d -o NEWUSER -g NEWUSER -m 700 /home/NEWUSER/.kube
sudo install -o NEWUSER -g NEWUSER -m 600 /home/soar009/.kube/config /home/NEWUSER/.kube/config
kubectl get nodes</code></pre></div></div>
        <div class="why"><div><code>kubectl</code> reads this file to reach the lab cluster.</div></div>
        <div class="res"><div>Five nodes, all <code>Ready</code>.</div></div>
      </div>
    </section>

    <section id="services">
      <h2>Running the services</h2>
      <p>The backend and tunnel are system services running as the account <code>netsentinel</code>; the daily job is <code>/etc/cron.d/netsentinel</code>. Manage them from your own account with sudo:</p>
      <pre><code>sudo systemctl status netsentinel cloudflared-knettf
sudo systemctl restart netsentinel
sudo journalctl -u netsentinel -f</code></pre>
      <div class="note">Never <code>git commit</code> while switched to <code>soar009</code>: it would be recorded under the original author's GitHub account Wk-P.</div>
    </section>

    <section id="github">
      <h2>GitHub access</h2>
      <p>Each Linux account on the server maps to one GitHub account and uses its own key and its own commit identity. The Linux user name is also your personal branch name. The original author is Linux <code>soar009</code> = GitHub <code>Wk-P</code>.</p>
      <pre class="uml">flowchart LR
  A["Dev directory<br>branch NEWUSER"] -->|"1 PR + review"| B["merge-dev"]
  B -->|"2 release.sh"| C["prod"]
  C -->|"3 deploy.sh"| D["Production"]
  classDef dev fill:#f0fff4,stroke:#38a169,color:#1a202c
  classDef gh fill:#f8fafc,stroke:#1a202c,color:#1a202c
  classDef prod fill:#fff5f5,stroke:#e53e3e,color:#1a202c
  class A dev
  class B,C gh
  class D prod</pre>
      <ol>
        <li><b>PR + review</b>: commit and push on branch <code>NEWUSER</code> in <code>/home/NEWUSER/github/NetSentinel</code>, open a PR into <code>merge-dev</code>; the other person reviews and approves, then it is merged.</li>
        <li><b>release.sh</b>: <code>/srv/netsentinel/release.sh -frontend | -backend | -all</code> fast-forwards <code>prod</code> to <code>merge-dev</code>.</li>
        <li><b>deploy.sh</b>: <code>git pull</code> in <code>/srv/netsentinel/prod</code> with the runner's own GitHub key, build, restart.</li>
      </ol>
      <p>knetsentinel is the same up to merge-dev; then <code>master</code> is fast-forwarded and <code>/srv/netsentinel/knetsentinel</code> pulled (see Deploying Changes). Review happens only on the PR. So, in order: your GitHub key → clone and create your branch → commit identity → test commit.</p>
      <div class="task"><h4><span class="n">1</span>Join knet-lab and give the server your GitHub key</h4>
        <div class="do"><div>Any Owner invites your GitHub username at <code>https://github.com/orgs/knet-lab/people</code>; accept at <code>https://github.com/orgs/knet-lab/invitation</code>. Then, logged in as yourself on the server:<pre><code>ssh-keygen -t ed25519 -N "" -C "your-github-email" -f /home/NEWUSER/.ssh/github_ssh_key
printf 'Host github.com\n    HostName github.com\n    User git\n    IdentityFile /home/NEWUSER/.ssh/github_ssh_key\n    IdentitiesOnly yes\n' &gt;&gt; /home/NEWUSER/.ssh/config
chmod 600 /home/NEWUSER/.ssh/config
cat /home/NEWUSER/.ssh/github_ssh_key.pub
ssh -T git@github.com</code></pre>The key gets its own name instead of the default <code>id_ed25519</code> and is used only for github.com. Add the printed key in GitHub → Settings → SSH and GPG keys → New SSH key, then run the last line.</div></div>
        <div class="why"><div>This key is for GitHub only, not for logging in to the server. Never borrow someone else's key.</div></div>
        <div class="res"><div><code>Hi your-name!</code>.</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>Clone into your development directory and create your branch</h4>
        <div class="do"><div><pre><code>sudo usermod -aG netsentinel NEWUSER
mkdir -p /home/NEWUSER/github
git clone git@github.com:knet-lab/NetSentinel.git /home/NEWUSER/github/NetSentinel
git clone git@github.com:knet-lab/knetsentinel.git /home/NEWUSER/github/knetsentinel
git -C /home/NEWUSER/github/NetSentinel switch -c NEWUSER origin/merge-dev
git -C /home/NEWUSER/github/NetSentinel push -u origin NEWUSER
git -C /home/NEWUSER/github/knetsentinel switch -c NEWUSER origin/merge-dev
git -C /home/NEWUSER/github/knetsentinel push -u origin NEWUSER</code></pre></div></div>
        <div class="why"><div>Code is only edited here, never in <code>/srv/netsentinel/prod</code> or <code>/srv/netsentinel/knetsentinel</code>. The <code>netsentinel</code> group (log in again afterwards) lets you release into <code>/srv</code>.</div></div>
        <div class="res"><div>Both repositories cloned; your branch exists on GitHub.</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>Set your commit identity</h4>
        <div class="do"><div><pre><code>git -C /home/NEWUSER/github/NetSentinel  config user.name  "your-github-username"
git -C /home/NEWUSER/github/NetSentinel  config user.email "your-verified-github-email"
git -C /home/NEWUSER/github/knetsentinel config user.name  "your-github-username"
git -C /home/NEWUSER/github/knetsentinel config user.email "your-verified-github-email"
git -C /home/NEWUSER/github/NetSentinel  config --local --get-regexp user
git -C /home/NEWUSER/github/knetsentinel config --local --get-regexp user</code></pre></div></div>
        <div class="why"><div>The identity is set in your own two development repositories only, so it affects nothing else in your account. Never set one in the shared directories under <code>/srv/netsentinel</code>: they are only pulled, never committed in.</div></div>
        <div class="res"><div>The last two commands print your name and email. A test commit pushed on a temporary branch shows you as the author on GitHub.</div></div>
      </div>
      <div class="task"><h4><span class="n">4</span>Check that you can release (pull in the production directory)</h4>
        <div class="do"><div><p><code>release.sh</code> → <code>deploy.sh</code> runs <code>git pull</code> in <code>/srv/netsentinel/prod</code> with the GitHub key of <b>whoever runs it</b>: you use <code>/home/NEWUSER/.ssh/github_ssh_key</code> from step 1.</p>
<pre><code>git -C /srv/netsentinel/prod fetch origin     # as NEWUSER</code></pre></div></div>
        <div class="why"><div><code>Permission denied (publickey)</code> → step 1. <code>insufficient permission</code> / <code>dubious ownership</code> → not yet in group <code>netsentinel</code> or not logged in again.</div></div>
        <div class="res"><div>The fetch succeeds.</div></div>
      </div>
    </section>

    <section id="ready">
      <h2>Ready check</h2>
      <div class="table-wrap"><table>
        <tr><th>#</th><th>Run</th><th>Expect</th></tr>
        <tr><td>1</td><td><code>ssh NEWUSER@192.168.0.247</code></td><td>Logs in with your key, no password</td></tr>
        <tr><td>2</td><td><code>id</code></td><td>Exactly the approved groups</td></tr>
        <tr><td>3</td><td><code>sudo systemctl is-active netsentinel cloudflared-knettf</code></td><td><code>active</code></td></tr>
        <tr><td>4</td><td><code>kubectl get nodes</code></td><td>5 nodes <code>Ready</code></td></tr>
        <tr><td>5</td><td><code>ssh -T git@github.com</code></td><td><code>Hi your-name!</code></td></tr>
        <tr><td>6</td><td>Commit and push a test branch in both repositories</td><td>GitHub shows you as the author</td></tr>
        <tr><td>7</td><td><code>git -C /srv/netsentinel/prod fetch origin</code> as yourself</td><td>Succeeds</td></tr>
      </table></div>
    </section>
  </div>
</template>
