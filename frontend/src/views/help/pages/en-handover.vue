<template>
  <div v-pre lang="en">
    <h1>Handover</h1>
    <div class="meta">Do this whenever an owner leaves. Production runs as the system account <code>netsentinel</code> and does not depend on any personal account, so the handover is about <b>external accounts and secrets</b>: the GitHub organization, Cloudflare, Tailscale, the site admin and the production <code>.env</code>. Make sure the people who stay control all of them, then lock the leaving account.</div>

    <section id="offboard">
      <h2>Checklist</h2>
      <ol>
        <li>The new owner has passed the <a href="/help/en-access#ready">ready check</a>.</li>
        <li>GitHub: keep at least two Owners in knet-lab; confirm the others are Owners before removing the leaving person.</li>
        <li>Cloudflare: knettf.com and its tunnel are in the original author's Cloudflare account; add the people who stay as members (Manage Account → Members).</li>
        <li>Tailscale: the tailnet belongs to the original author; invite the people who stay, or switch to their own tailnet.</li>
        <li>Hand over in person: site admin account, <code>/srv/netsentinel/prod/backend/backend/.env</code> (SECRET_KEY, VIGIL_BRIDGE_TOKEN), PostgreSQL password (user vigil, currently the default in <code>settings.py</code>).</li>
        <li>Lock the leaving account. NetSentinel production is not under any personal account, so this does not affect it. The my-code services and tunnel do run under soar009: locking soar009 (or disabling linger) stops them too, so check with whoever owns my-code first.
          <pre><code>sudo usermod -L USERNAME              # password only; for key login also remove /home/USERNAME/.ssh/authorized_keys
sudo gpasswd -d USERNAME sudo</code></pre></li>
      </ol>
    </section>
  </div>
</template>
