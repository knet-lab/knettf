<template>
  <div v-pre lang="en">
        <h1>Web Guide</h1>
    <div class="meta">How to use the NetSentinel website: what to click, why, and what you should see. No server access is needed for anything on this page.</div>

    <section id="login">
      <h2>Sign in</h2>
      <div class="task"><h4><span class="n">1</span>Open the site and sign in</h4>
        <div class="do"><div>Go to <code>https://knettf.com</code>, enter <span class="ui">Username</span> and <span class="ui">Password</span>, press Enter.</div></div>
        <div class="why"><div>Every page requires an account; when you are not signed in, any address sends you to <code>/login</code>.</div></div>
        <div class="res"><div>Standard users land on <code>/kcore</code>, admins on <code>/admin/dashboard</code>. A wrong password shows <code>Invalid username or password</code>.</div></div>
      </div>
      <ul>
        <li><b>Staying signed in</b>: your session renews itself silently for 7 days. After that you are sent back to the login page.</li>
        <li><b>Sign out</b>: <span class="ui">Sign Out</span> at the top right (bottom left in the admin console).</li>
        <li><b>Strange login behaviour</b> (keeps logging out, shows someone else's name): browser DevTools → Application → Local Storage → delete <code>token</code>, <code>refreshToken</code>, <code>user</code>, then sign in again.</li>
      </ul>
    </section>

    <section id="layout">
      <h2>Where things are</h2>
      <div class="table-wrap"><table>
        <tr><th>Menu</th><th>Address</th><th>What it is for</th></tr>
        <tr><td><span class="ui">Kubernetes</span></td><td><code>/kcore</code></td><td>Clusters <b>you</b> registered: browse resources, read Pod logs, edit YAML, restart, delete</td></tr>
        <tr><td><span class="ui">Terraform Scan</span></td><td><code>/autotf</code></td><td>Your Terraform configs: write, scan, apply</td></tr>
        <tr><td><span class="ui">AI Vigil</span></td><td><code>/vigil</code>, <code>/vigil/log</code></td><td>Live attack detection on cluster traffic (everyone sees the same data)</td></tr>
        <tr><td><span class="ui">Help</span></td><td><code>/help</code></td><td>This guide and the project handbooks</td></tr>
        <tr><td>(no menu entry)</td><td><code>/admin</code></td><td>Admin console; type the address. Non-admins are sent back to <code>/kcore</code></td></tr>
      </table></div>
      <div class="learn"><b>Who can touch what</b>: every cluster and Terraform config has an owner. Standard users can only act on their own; admins can act on everyone's. Detection data has no owner and is visible to all signed-in users.</div>
    </section>

    <section id="clusters">
      <h2>Kubernetes clusters</h2>
      <div class="task"><h4><span class="n">1</span>Register a cluster</h4>
        <div class="do"><div><span class="ui">Kubernetes</span> → <span class="ui">Add</span> next to My Clusters → enter a name (unique for you) and paste the whole <b>kubeconfig</b> → <span class="ui">Add Cluster</span>.</div></div>
        <div class="why"><div>The site talks to the cluster with exactly that kubeconfig. It carries full cluster rights, so only get it through a safe channel.</div></div>
        <div class="res"><div>Click the new cluster → <span class="ui">Namespaces</span>. You should see <code>default</code>, <code>kube-system</code>, <code>metallb-system</code>, <code>targets</code>… An error means a wrong kubeconfig or the cluster is powered off.</div></div>
      </div>
      <h3>Tabs</h3>
      <p><span class="ui">Namespaces</span>, <span class="ui">Pods</span>, <span class="ui">Deployments</span>, <span class="ui">Services</span>, <span class="ui">ConfigMaps</span>, <span class="ui">DaemonSets</span>. All but Namespaces need a namespace picked in <span class="ui">Select Namespace</span> first (default <code>default</code>).</p>
      <div class="table-wrap"><table>
        <tr><th>Action</th><th>Where</th><th>What happens</th></tr>
        <tr><td>View YAML</td><td>row → <span class="ui">YAML</span></td><td>Read-only view of the live object</td></tr>
        <tr><td>Edit</td><td>row → <span class="ui">Edit</span> → <span class="ui">Apply</span></td><td>Applied immediately and overrides fields managed by others</td></tr>
        <tr><td>Create</td><td><span class="ui">Apply YAML</span> (top right)</td><td>Several documents separated by <code>---</code> are fine; you get “Applied: N resource(s), M error(s)”</td></tr>
        <tr><td>Pod logs</td><td>Pods → <span class="ui">Logs</span></td><td>Streams live once <b>● Connected</b> shows; closing the window disconnects</td></tr>
        <tr><td>Restart</td><td>Deployments / DaemonSets row</td><td><b>Normal (Rolling)</b> replaces Pods one by one with no downtime — prefer this. <b>Force</b> deletes all Pods at once and causes an outage</td></tr>
        <tr><td>Delete</td><td>row → <span class="ui">Delete</span> → <b>Confirm Delete</b></td><td>A deleted Pod is usually recreated; deleting a Deployment, Service or Namespace is permanent</td></tr>
      </table></div>
      <div class="danger"><b>Never delete</b> <code>kafka-controller</code> or any Namespace, and never force-restart anything in <code>kube-system</code> or <code>metallb-system</code>. <code>kafka-controller</code> is not recreated once deleted, and detection stops until Kafka is rebuilt.</div>
      <p><b>After the cluster is rebuilt</b>, the old kubeconfig stops working and every tab errors. Delete the cluster entry (this only removes the website record) and add it again with the new kubeconfig.</p>
    </section>

    <section id="tf">
      <h2>Terraform scan &amp; apply</h2>
      <div class="task"><h4><span class="n">1</span>Create a config</h4>
        <div class="do"><div><span class="ui">Terraform Scan</span> → <span class="ui">New</span>. Either <span class="ui">Upload File</span> (a local <code>.tf</code>) or <span class="ui">Write Online</span> (paste HCL).</div></div>
        <div class="why"><div>The site keeps one file per config and scans that file.</div></div>
        <div class="res"><div>The config appears under My Configs. Names must be unique for you.</div></div>
      </div>
      <div class="task"><h4><span class="n">2</span>Scan it</h4>
        <div class="do"><div><span class="ui">Full Scan</span> runs every enabled tool; <span class="ui">Manual Scan</span> lets you pick tools. Wait — do not refresh.</div></div>
        <div class="why"><div>Five tools look for different problems: <code>terraform_validate</code> (syntax), <code>tflint</code> (best practice), <code>checkov</code> (compliance), <code>tfsec</code> (security misconfig), <code>trivy</code> (misconfig + CVEs). The scan runs while the request is open, from a few seconds to about a minute.</div></div>
        <div class="res"><div><b>Scan Report</b> shows HIGH / MEDIUM / LOW counts and a section per tool. <span class="ui">View Report</span> opens it as HTML, <span class="ui">Download PDF</span> saves a PDF. <code>tool not found</code> for one tool means it is not installed on the server; the other tools' results still count.</div></div>
      </div>
      <div class="task"><h4><span class="n">3</span>Apply it</h4>
        <div class="do"><div>Click <span class="ui">Apply</span>. If it is grey, hover to see why: <i>Run a scan first</i> / <i>Scan must be complete</i> / <i>Fix all HIGH severity issues first</i>.</div></div>
        <div class="why"><div>Apply is only allowed after a finished scan with zero HIGH findings. Editing the content clears the “scanned” flag, so you must scan again after every edit.</div></div>
        <div class="res"><div>The page shows Last apply success / failure and the full output.</div></div>
      </div>
      <div class="danger">Apply <b>really creates resources</b>, and no Terraform state is kept: applying twice creates everything twice, and nothing can be destroyed from the website.</div>
    </section>

    <section id="vigil">
      <h2>AI Vigil</h2>
      <p>A machine-learning model watches traffic inside the lab cluster and flags flows that look like attacks. The dashboard <code>/vigil</code> refreshes every <b>30 seconds</b>, the log <code>/vigil/log</code> every <b>15 seconds</b>; <span class="ui">Refresh now</span> reloads immediately.</p>
      <div class="table-wrap"><table>
        <tr><th>Area</th><th>Meaning</th></tr>
        <tr><td>Detection model</td><td>Should show <code>ads_ml_ocsvm</code>. “No models registered” means the model failed to load — tell the operator</td></tr>
        <tr><td>Total Inspected / Attacks Detected / Normal Flows / Attack Rate</td><td>All-time totals over the whole database, not since the page opened</td></tr>
        <tr><td>Attack Type Breakdown</td><td>Count per attack type</td></tr>
        <tr><td>Recent Attack Events</td><td>Latest 30 attacks; <span class="ui">View log →</span> opens the full log</td></tr>
        <tr><td><span class="ui">Attacks only</span></td><td>Hide normal flows in the log</td></tr>
      </table></div>
      <h3>Reading a record</h3>
      <p>In <code>/vigil/log</code>, filter by verdict, attack type and time range; click a row for details.</p>
      <div class="table-wrap"><table>
        <tr><th>Field</th><th>How to read it</th></tr>
        <tr><td>Verdict</td><td>Attack or normal</td></tr>
        <tr><td>Confidence</td><td>0–1, how closely the flow matches the named attack type. <b>Always 0 for normal flows</b> — it is not “confidence that it is normal”</td></tr>
        <tr><td>Attack Type</td><td>Closest known attack (e.g. <code>Dos-TCP SYN flood</code>, <code>Slowloris</code>); <code>Unknown_Attack</code> when nothing is similar enough</td></tr>
        <tr><td>Cilium action</td><td><code>ignore</code> / <code>alert</code> / <code>rate_limit</code> / <code>drop</code>. <b>A suggestion only</b> — nothing is actually blocked</td></tr>
        <tr><td>Ground Truth</td><td>Label from the test traffic: source .20–.29 = attack, .50–.64 = normal, otherwise empty</td></tr>
        <tr><td>Flow Features</td><td>The 35 numbers the model saw (duration, packet counts, SYN ratio, timing…)</td></tr>
      </table></div>
      <p>Sources <code>192.168.100.20–29</code> and <code>.170–.184</code> are normally the lab's own simulated attacks and are expected.</p>
    </section>

    <section id="admin">
      <h2>Admin console</h2>
      <div class="table-wrap"><table>
        <tr><th>Menu</th><th>You can</th><th>Note</th></tr>
        <tr><td><span class="ui">Users</span></td><td>Create, delete</td><td>The <span class="ui">Admin</span> switch in New User <b>has no effect</b>; ask the operator to grant admin. Deleting a user also deletes all their clusters and Terraform configs. Never delete <code>vigil-bridge</code> (the detection service account)</td></tr>
        <tr><td><span class="ui">Clusters</span></td><td>View everyone's, delete</td><td>Only the owner can browse a cluster from the Kubernetes page</td></tr>
        <tr><td><span class="ui">TF Configs</span></td><td>View everyone's, delete</td><td></td></tr>
        <tr><td><span class="ui">TF Tools</span></td><td>Create, edit, enable / disable, delete</td><td>Prefer disabling to deleting; standard users only see enabled tools</td></tr>
      </table></div>
      <p>Password changes, disabling an account and granting admin are done on the server by the operator.</p>
    </section>

  </div>
</template>
