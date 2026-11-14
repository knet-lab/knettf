<template>
  <div v-pre lang="en">
    <h1>Accounts, Permissions &amp; GitHub</h1>
    <div class="meta">Do this once, before touching any service. When all seven checks at the end pass, you are ready to take over. In the commands, replace <code>NEWUSER</code> with your own Linux user name.</div>

    <section id="linux">
      <h2>Your own Linux account</h2>
      <div class="danger">Never use the shared <code>cis</code> account. It has every permission, and nothing done with it can be traced to a person.</div>
      <p>There are only two people: the <b>original author</b> (Linux account <code>soar009</code>) and the <b>new owner</b> (you).</p>
      <div class="table-wrap"><table>
        <tr><th>Step</th><th>Who</th><th>What</th></tr>
        <tr><td>1</td><td>New owner</td><td>On your own computer, create a login key; send your user name and the public key to the original author</td></tr>
        <tr><td>2</td><td>Original author</td><td>Create the account, add the key, add the groups</td></tr>
        <tr><td>3</td><td>New owner</td><td>Log in and check the groups</td></tr>
        <tr><td>4</td><td>Original author</td><td>Copy the cluster credentials; invite you to Tailscale if you need outside access</td></tr>
        <tr><td>5</td><td>New owner</td><td>Check cluster access</td></tr>
      </table></div>
      <div class="task"><h4><span class="n">1</span>New owner: create a login key</h4>
        <div class="do"><div>On your own computer; send the whole <code>id_ed25519.pub</code> line and your user name to the original author:<pre><code>ssh-keygen -t ed25519 -C "NEWUSER@cis-Z10PE-D8-WS"</code></pre></div></div>
        <div class="why"><div>The server only accepts SSH keys, not passwords.</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>Original author: create the account</h4>
        <div class="do"><div><pre><code>sudo adduser NEWUSER
sudo usermod -aG sudo,docker,libvirt,netsentinel NEWUSER
sudo install -d -o NEWUSER -g NEWUSER -m 700 /home/NEWUSER/.ssh
echo 'the-public-key-line' | sudo tee -a /home/NEWUSER/.ssh/authorized_keys
sudo chown NEWUSER:NEWUSER /home/NEWUSER/.ssh/authorized_keys
sudo chmod 600 /home/NEWUSER/.ssh/authorized_keys</code></pre></div></div>
        <div class="why"><div><code>sudo</code>: manage services and logs; <code>docker</code>: the database container <code>pg</code>; <code>libvirt</code>: start / stop the lab VMs; <code>netsentinel</code>: write under <code>/srv/netsentinel</code> (releases, model files).</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>New owner: log in and check</h4>
        <div class="do"><div><pre><code>ssh NEWUSER@192.168.0.247
id</code></pre></div></div>
        <div class="res"><div>No password prompt; <code>id</code> lists sudo, docker, libvirt, netsentinel. From outside the lab use the Tailscale address <code>100.117.219.123</code> (step 4).</div></div>
      </div>
      <div class="task"><h4><span class="n">4</span>Original author: cluster credentials and Tailscale</h4>
        <div class="do"><div><pre><code>sudo install -d -o NEWUSER -g NEWUSER -m 700 /home/NEWUSER/.kube
sudo install -o NEWUSER -g NEWUSER -m 600 /home/soar009/.kube/config /home/NEWUSER/.kube/config</code></pre>For outside access, invite the new owner in the Tailscale admin console (Users → Invite users).</div></div>
      </div>
      <div class="task"><h4><span class="n">5</span>New owner: check cluster access</h4>
        <div class="do"><div><pre><code>kubectl get nodes</code></pre></div></div>
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
      <p>Each Linux account on the server maps to one GitHub account and uses its own key and its own commit identity. The original author is Linux <code>soar009</code> = GitHub <code>Wk-P</code>.</p>
      <pre class="uml">flowchart LR
  A["Dev directory<br>task branch feat/…"] -->|"1 PR on GitHub"| B["main"]
  B -->|"2 deploy.sh"| D["Production"]
  classDef dev fill:#f0fff4,stroke:#38a169,color:#1a202c
  classDef gh fill:#f8fafc,stroke:#1a202c,color:#1a202c
  classDef prod fill:#fff5f5,stroke:#e53e3e,color:#1a202c
  class A dev
  class B gh
  class D prod</pre>
      <ol>
        <li><b>PR on GitHub</b>: create a task branch from the latest <code>main</code>, commit, merge the latest <code>main</code> in and run <code>ops/scripts/check.sh</code>, push, open and merge a PR into <code>main</code> on the website (ask another member to approve when there is one), delete the branch.</li>
        <li><b>deploy.sh</b>: <code>/srv/netsentinel/prod/ops/scripts/deploy.sh -frontend | -backend | -all</code> pulls <code>main</code> into <code>/srv/netsentinel/prod</code> with the runner's own GitHub key, builds and restarts.</li>
      </ol>
      <p>The lab (<code>lab/</code>, formerly knetsentinel) is in the same repository and goes through the same PR; after merging, run <code>bash /srv/netsentinel/lab/sync-to-srv.sh</code> to update <code>/srv/netsentinel/lab</code> (see Deploying Changes). Review happens only on the PR. So, in order: your GitHub key → clone → commit identity → test commit.</p>
      <div class="task"><h4><span class="n">1</span>Join knet-lab and give the server your GitHub key</h4>
        <div class="do"><div>Any Owner invites your GitHub username at <code>https://github.com/orgs/knet-lab/people</code>; accept at <code>https://github.com/orgs/knet-lab/invitation</code>. Then, logged in as yourself on the server:<pre><code>ssh-keygen -t ed25519 -N "" -C "your-github-email" -f /home/NEWUSER/.ssh/github_ssh_key
printf 'Host github.com\n    HostName github.com\n    User git\n    IdentityFile /home/NEWUSER/.ssh/github_ssh_key\n    IdentitiesOnly yes\n' &gt;&gt; /home/NEWUSER/.ssh/config
chmod 600 /home/NEWUSER/.ssh/config
cat /home/NEWUSER/.ssh/github_ssh_key.pub
ssh -T git@github.com</code></pre>The key gets its own name instead of the default <code>id_ed25519</code> and is used only for github.com. Add the printed key in GitHub → Settings → SSH and GPG keys → New SSH key, then run the last line.</div></div>
        <div class="why"><div>This key is for GitHub only, not for logging in to the server. Never borrow someone else's key.</div></div>
        <div class="res"><div><code>Hi your-name!</code>.</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>Clone into your development directory</h4>
        <div class="do"><div><pre><code>mkdir -p /home/NEWUSER/github
git clone git@github.com:knet-lab/knettf.git /home/NEWUSER/github/knettf</code></pre></div></div>
        <div class="why"><div>Code is only edited here, never in <code>/srv/netsentinel/prod</code> or <code>/srv/netsentinel/lab</code>. The <code>netsentinel</code> group (log in again afterwards) lets you deploy into <code>/srv</code>. There is no long-lived personal branch: create a task branch from <code>main</code> for each piece of work (see Deploying Changes).</div></div>
        <div class="res"><div>Repository cloned.</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>Set your commit identity</h4>
        <div class="do"><div><pre><code>git -C /home/NEWUSER/github/knettf  config user.name  "your-github-username"
git -C /home/NEWUSER/github/knettf  config user.email "your-verified-github-email"
git -C /home/NEWUSER/github/knettf  config --local --get-regexp user</code></pre></div></div>
        <div class="why"><div>The identity is set in your own development repository only, so it affects nothing else in your account. Never set one in the shared directories under <code>/srv/netsentinel</code>: they are run directories, never committed in.</div></div>
        <div class="res"><div>The last two commands print your name and email. A test commit pushed on a temporary branch shows you as the author on GitHub.</div></div>
      </div>
      <div class="task"><h4><span class="n">4</span>Check that you can deploy (pull into production)</h4>
        <div class="do"><div><p><code>deploy.sh</code> runs <code>git pull</code> in <code>/srv/netsentinel/prod</code> with the key of <b>whoever runs it</b> (you: <code>/home/NEWUSER/.ssh/github_ssh_key</code>). Check it:</p>
<pre><code>git -C /srv/netsentinel/prod fetch origin</code></pre></div></div>
        <div class="why"><div><code>Permission denied (publickey)</code> → step 1. <code>insufficient permission</code> / <code>dubious ownership</code> → not yet in group <code>netsentinel</code> or not logged in again.</div></div>
        <div class="res"><div>The fetch succeeds without errors.</div></div>
      </div>
    </section>

    <section id="ready">
      <h2>Ready check</h2>
      <div class="table-wrap"><table>
        <tr><th>#</th><th>Run</th><th>Expect</th></tr>
        <tr><td>1</td><td><code>ssh NEWUSER@192.168.0.247</code></td><td>Logs in with your key, no password</td></tr>
        <tr><td>2</td><td><code>id</code></td><td>sudo, docker, libvirt, netsentinel</td></tr>
        <tr><td>3</td><td><code>sudo systemctl is-active netsentinel cloudflared-knettf</code></td><td><code>active</code></td></tr>
        <tr><td>4</td><td><code>kubectl get nodes</code></td><td>5 nodes <code>Ready</code></td></tr>
        <tr><td>5</td><td><code>ssh -T git@github.com</code></td><td><code>Hi your-name!</code></td></tr>
        <tr><td>6</td><td>Commit and push a test branch</td><td>GitHub shows you as the author</td></tr>
        <tr><td>7</td><td><code>git -C /srv/netsentinel/prod fetch origin</code> as yourself</td><td>Succeeds</td></tr>
      </table></div>
    </section>
  </div>
</template>
