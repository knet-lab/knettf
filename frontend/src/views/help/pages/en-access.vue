<template>
  <div v-pre lang="en">
    <h1>Accounts, Permissions &amp; GitHub</h1>
    <div class="meta">Do this once, before touching any service. When all seven checks at the end pass, you are ready to take over. In the commands, replace <code>NEWUSER</code> with your own Linux user name.</div>

    <section id="linux">
      <h2>Your own Linux account</h2>
      <div class="danger">Never use the shared <code>cis</code> account. It has every permission, and nothing done with it can be traced to a person.</div>
      <div class="task"><h4><span class="n">1</span>Request the account</h4>
        <div class="do"><div>Send the lab head your user name, your SSH public key, and which groups you need and why. Create the key on your own computer:<pre><code>ssh-keygen -t ed25519 -C "NEWUSER@cis-Z10PE-D8-WS"
cat ~/.ssh/id_ed25519.pub</code></pre></div></div>
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
      <div class="note">Never <code>git commit</code> while switched to <code>soar009</code>: the commit would be recorded under the original author's name.</div>
    </section>

    <section id="github">
      <h2>GitHub access</h2>
      <div class="task"><h4><span class="n">1</span>Join the knet-lab organization</h4>
        <div class="do"><div>Any Owner of <code>knet-lab</code> opens <code>https://github.com/orgs/knet-lab/people</code> → <span class="ui">Invite member</span> and enters your GitHub username. You accept at <code>https://github.com/orgs/knet-lab/invitation</code>.</div></div>
        <div class="why"><div>Both repositories (<code>knet-lab/NetSentinel</code> and <code>knet-lab/knetsentinel</code>) belong to the lab organization, so one invitation covers both. Keep at least two Owners so access never depends on one person.</div></div>
        <div class="res"><div>You can see both repositories at <code>https://github.com/knet-lab</code>.</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>Give the server your GitHub key</h4>
        <div class="do"><div>Logged in as yourself on the server:<pre><code>ssh-keygen -t ed25519 -C "your-github-email"
cat ~/.ssh/id_ed25519.pub
ssh -T git@github.com</code></pre>Add the printed key in GitHub → Settings → SSH and GPG keys → New SSH key, then run the last line.</div></div>
        <div class="why"><div>This key is for GitHub only; it is different from the key you use to log in to the server. Generate it under your own account and add it to your own GitHub account. Never copy <code>/home/soar009/.ssh/github_ssh_key</code>: that is the original author's personal key and is removed in step 4.</div></div>
        <div class="res"><div><code>Hi your-name!</code>. If it says <code>Hi Wk-P!</code>, you are using the original author's key.</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>Set your commit identity</h4>
        <div class="do"><div><pre><code>git config --global user.name  "Your Name"
git config --global user.email "your-verified-github-email"</code></pre>Also remove the original author's identity that is stored inside both repositories (run once):<pre><code>sudo -iu soar009
git config --global user.name  Wk-P
git config --global user.email weekend2000119@gmail.com
git -C ~/github/NetSentinel config --local --unset user.name
git -C ~/github/NetSentinel config --local --unset user.email
git -C ~/knetsentinel config --local --unset user.name
git -C ~/knetsentinel config --local --unset user.email
exit</code></pre></div></div>
        <div class="why"><div>A repository-level identity overrides yours, so every commit would otherwise show <code>Wk-P</code>.</div></div>
        <div class="res"><div>A test commit and push shows you as the author on GitHub.</div></div>
      </div>
      <div class="task"><h4><span class="n">4</span>Fully replace the original author's key on soar009 (mandatory)</h4>
        <div class="do"><div><div class="danger">Do not skip this or do half of it. Handover is complete only when Wk-P's key is deleted <b>both on the server and on GitHub</b>.</div>
<p><b>Now:</b> the server account <code>soar009</code> and the GitHub account <code>Wk-P</code> belong to the same person, the original author. <code>soar009</code> reaches GitHub with Wk-P's personal private key <code>/home/soar009/.ssh/github_ssh_key</code> (<code>sudo -iu soar009 ssh -T git@github.com</code> prints <code>Hi Wk-P!</code>), and every deployment pull depends on it. The services keep running as <code>soar009</code> after the author leaves, so the key would stay on the server.</p>
<p><b>Risks if you leave it:</b></p>
<ul>
<li><b>Impersonation:</b> anyone with sudo can use the key to push, delete branches or change the repositories as Wk-P. GitHub records the original author's name, so nobody can tell who really did it.</li>
<li><b>Too much access:</b> it unlocks Wk-P's whole GitHub account, not just these two repositories, including personal repositories unrelated to the lab.</li>
<li><b>Deployment can break without warning:</b> if the author ever removes this key or closes the account, <code>git pull</code> as <code>soar009</code> fails and <code>scripts/deploy.sh</code> can no longer fetch code.</li>
</ul>
<p><b>Replacement:</b> one read-only deploy key per repository (GitHub does not allow the same deploy key on two repositories). A deploy key belongs to the repository, not to a person; it can only pull that one repository.</p>
<p><b>Order:</b> install and test the new keys first, then remove the old one. Reversing the order breaks deployment in between.</p>
<p><b>4.1 Create the deploy keys</b></p><pre><code>sudo -iu soar009
ssh-keygen -t ed25519 -N "" -C "soar009 deploy NetSentinel"  -f /home/soar009/.ssh/deploy_netsentinel
ssh-keygen -t ed25519 -N "" -C "soar009 deploy knetsentinel" -f /home/soar009/.ssh/deploy_knetsentinel
cat /home/soar009/.ssh/deploy_netsentinel.pub
cat /home/soar009/.ssh/deploy_knetsentinel.pub</code></pre>A knet-lab Owner adds each printed key at <code>https://github.com/knet-lab/NetSentinel/settings/keys</code> and <code>https://github.com/knet-lab/knetsentinel/settings/keys</code> → <span class="ui">Add deploy key</span>, leaving <span class="ui">Allow write access</span> unchecked.
<p><b>4.2 Switch SSH config and remotes</b></p>Delete the whole <code>Host github.com</code> block (the one with <code>IdentityFile ~/.ssh/github_ssh_key</code>) from <code>/home/soar009/.ssh/config</code> and put this in its place:<pre><code>Host github-netsentinel
    HostName github.com
    User git
    IdentityFile /home/soar009/.ssh/deploy_netsentinel
    IdentitiesOnly yes

Host github-knetsentinel
    HostName github.com
    User git
    IdentityFile /home/soar009/.ssh/deploy_knetsentinel
    IdentitiesOnly yes</code></pre>Then, still as <code>soar009</code>:<pre><code>git -C /home/soar009/github/NetSentinel remote set-url origin git@github-netsentinel:knet-lab/NetSentinel.git
git -C /home/soar009/knetsentinel        remote set-url origin git@github-knetsentinel:knet-lab/knetsentinel.git
git -C /home/soar009/github/NetSentinel fetch origin
git -C /home/soar009/knetsentinel        fetch origin
exit</code></pre>If either fetch fails, stop and fix it before 4.3.
<p><b>4.3 Remove Wk-P's key on both sides</b></p><ol>
<li>Server: <code>sudo rm /home/soar009/.ssh/github_ssh_key</code></li>
<li>GitHub: ask Wk-P to delete the matching key under GitHub → Settings → SSH and GPG keys. Deleting the file alone is not enough: if anyone copied the private key earlier, the copy still works until the GitHub side is removed.</li>
</ol>
<p><b>4.4 Confirm the replacement</b></p><pre><code>sudo grep -rn github_ssh_key /home/soar009/.ssh/
sudo -iu soar009 ssh -T git@github.com
sudo -iu soar009 git -C /home/soar009/github/NetSentinel pull --ff-only
sudo -iu soar009 git -C /home/soar009/github/NetSentinel push --dry-run</code></pre></div></div>
        <div class="why"><div>Deployment must not depend on a person who has left, and no one's personal key should stay on a shared server.</div></div>
        <div class="res"><div>grep prints nothing; <code>ssh -T</code> says <code>Permission denied</code> (never <code>Hi Wk-P!</code>); pull succeeds; push is rejected.</div></div>
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
        <tr><td>7</td><td><code>sudo -iu soar009 ssh -T git@github.com</code></td><td><code>Permission denied</code>, not <code>Hi Wk-P!</code>; pull as <code>soar009</code> still works</td></tr>
      </table></div>
    </section>
  </div>
</template>
