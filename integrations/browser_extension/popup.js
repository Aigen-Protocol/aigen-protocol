const BASE = 'https://cryptogenesis.duckdns.org';

document.getElementById('scanBtn').addEventListener('click', async () => {
  const addr = document.getElementById('addr').value.trim();
  const r = document.getElementById('result');
  r.style.display = 'block';
  r.className = '';
  if (addr.match(/^0x[a-fA-F0-9]{40}$/)) {
    r.textContent = 'Scanning...';
    try {
      const resp = await fetch(`${BASE}/scan?address=${addr}&chain=base`);
      const d = await resp.json();
      const score = d.safety_score || 0;
      r.className = score >= 60 ? 'r-ok' : 'r-err';
      const tok = d.token || {};
      r.innerHTML = `<b>${tok.symbol || '?'}</b> (${tok.name || 'Unknown'})<br>Score: <b>${score}/100</b> — ${d.verdict || '?'}<br><a href="${BASE}/t/${addr}?chain=base" target="_blank" style="color:#5fe8a3">Full scan →</a>`;
    } catch (e) {
      r.className = 'r-err';
      r.textContent = 'Failed: ' + e.message;
    }
  } else if (addr.match(/^[1-9A-HJ-NP-Za-km-z]{32,44}$/)) {
    r.textContent = 'Scanning Solana...';
    try {
      const resp = await fetch(`${BASE}/scan/solana?address=${addr}`);
      const d = await resp.json();
      const score = d.safety_score || 0;
      r.className = score >= 60 ? 'r-ok' : 'r-err';
      r.innerHTML = `<b>${d.token?.symbol || '?'}</b><br>Score: <b>${score}/100</b> — ${d.verdict || '?'}<br>Mint auth: ${d.mint_authority?.substring(0,8) || 'None'}`;
    } catch (e) {
      r.className = 'r-err';
      r.textContent = 'Failed: ' + e.message;
    }
  } else {
    r.className = 'r-err';
    r.textContent = 'Invalid address — expected 0x... (40 hex) or Solana base58';
  }
});

document.getElementById('rescanBtn').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) {
    chrome.tabs.sendMessage(tab.id, { action: 'rescan' });
    window.close();
  }
});

document.getElementById('missionsBtn').addEventListener('click', () => {
  chrome.tabs.create({ url: BASE + '/missions' });
});

document.getElementById('meBtn').addEventListener('click', () => {
  chrome.tabs.create({ url: BASE + '/me' });
});

document.getElementById('addr').addEventListener('keypress', (e) => {
  if (e.key === 'Enter') document.getElementById('scanBtn').click();
});
