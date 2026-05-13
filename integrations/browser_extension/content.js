/* AIGEN content script — detects 0x... addresses on any webpage and inserts
 * inline safety badges. Click → modal with full scan + flags + link.
 *
 * Smart sites it understands well:
 *   etherscan.io, basescan.org, optimistic.etherscan.io, arbiscan.io,
 *   polygonscan.com, bscscan.com, solscan.io, dexscreener.com,
 *   geckoterminal.com, defillama.com, coingecko.com
 */
(function () {
  'use strict';

  if (window.__aigenInjected) return;
  window.__aigenInjected = true;

  const BASE = 'https://cryptogenesis.duckdns.org';
  const ETH_REGEX = /0x[a-fA-F0-9]{40}/g;
  // Solana: base58 32-44 chars (we'll only auto-scan on solscan/jup pages to avoid false positives)
  const SOL_REGEX = /[1-9A-HJ-NP-Za-km-z]{32,44}/g;
  const HOST = location.hostname.toLowerCase();
  const IS_SOLANA_SITE = /solscan\.io|jup\.ag|magiceden\.io/.test(HOST);
  const cache = new Map(); // address → {score, verdict, ...}

  // Detect chain hint from URL/host
  function chainHint() {
    if (HOST.includes('basescan')) return 'base';
    if (HOST.includes('optimistic.etherscan')) return 'optimism';
    if (HOST.includes('arbiscan')) return 'arbitrum';
    if (HOST.includes('polygonscan')) return 'polygon';
    if (HOST.includes('bscscan')) return 'bsc';
    if (HOST.includes('etherscan.io')) return 'ethereum';
    return 'base';
  }

  function scoreColor(s) {
    if (s >= 90) return '#22c55e';
    if (s >= 60) return '#eab308';
    if (s >= 30) return '#f97316';
    if (s > 0)   return '#ef4444';
    return '#888';
  }

  function badgeHtml(score, verdict) {
    return `<span class="aigen-badge" style="background:${scoreColor(score)}">AIGEN ${score}</span>`;
  }

  async function scanQuiet(addr, chain) {
    const key = `${chain}:${addr}`;
    if (cache.has(key)) return cache.get(key);
    try {
      const r = await fetch(`${BASE}/scan?address=${addr}&chain=${chain}`);
      const d = await r.json();
      cache.set(key, d);
      return d;
    } catch (e) {
      return null;
    }
  }

  async function scanSolanaQuiet(addr) {
    const key = `solana:${addr}`;
    if (cache.has(key)) return cache.get(key);
    try {
      const r = await fetch(`${BASE}/scan/solana?address=${addr}`);
      const d = await r.json();
      cache.set(key, d);
      return d;
    } catch (e) {
      return null;
    }
  }

  // Show a modal popup with full scan
  function showModal(addr, chain, scan) {
    const tok = scan.token || {};
    const flags = (scan.flags || []).slice(0, 5).map(f =>
      typeof f === 'string' ? f : (f.name || '?')
    );
    const score = scan.safety_score || 0;
    const color = scoreColor(score);

    const bg = document.createElement('div');
    bg.className = 'aigen-modal-bg';
    bg.innerHTML = `
      <div class="aigen-modal">
        <button class="aigen-modal-close">×</button>
        <div class="aigen-brand">AIGEN SAFETY SCAN</div>
        <div class="aigen-token">${(tok.symbol || '?').replace(/</g,'&lt;')}<span style="color:#888;font-size:0.7em;font-weight:400;margin-left:8px">on ${chain.toUpperCase()}</span></div>
        <div class="aigen-name">${(tok.name || 'Unknown').replace(/</g,'&lt;')}</div>
        <div class="aigen-addr">${addr}</div>
        <div class="aigen-score-row">
          <div class="aigen-score-circle" style="background:${color}">${score}</div>
          <div class="aigen-verdict">
            <div style="color:${color};font-weight:700">${scan.verdict || '?'}</div>
            <div style="color:#888;font-size:12px;margin-top:4px">${flags.length} flags</div>
          </div>
        </div>
        ${flags.length ? '<div class="aigen-flags-label">FLAGS</div>' + flags.map(f => `<div class="aigen-flag-item">• ${f.replace(/</g,'&lt;')}</div>`).join('') : ''}
        <div class="aigen-cta-row">
          <a class="aigen-cta" href="${BASE}/t/${addr}?chain=${chain}" target="_blank">Full scan →</a>
          <a class="aigen-cta-alt" href="${BASE}/missions" target="_blank">Browse missions</a>
        </div>
      </div>
    `;
    document.body.appendChild(bg);
    bg.querySelector('.aigen-modal-close').addEventListener('click', () => bg.remove());
    bg.addEventListener('click', e => { if (e.target === bg) bg.remove(); });
  }

  // Walk text nodes and inject badges next to addresses
  function injectBadges() {
    const chain = chainHint();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        if (n.parentElement?.closest('script,style,noscript,textarea,input,.aigen-modal')) return NodeFilter.FILTER_REJECT;
        if (n.parentElement?.classList.contains('aigen-injected')) return NodeFilter.FILTER_REJECT;
        return ETH_REGEX.test(n.textContent) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });

    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);

    nodes.forEach(node => {
      const text = node.textContent;
      const matches = [...text.matchAll(ETH_REGEX)];
      if (!matches.length) return;

      const frag = document.createDocumentFragment();
      let last = 0;
      matches.forEach(m => {
        const addr = m[0].toLowerCase();
        if (m.index > last) frag.appendChild(document.createTextNode(text.substring(last, m.index)));
        const wrap = document.createElement('span');
        wrap.className = 'aigen-injected';
        wrap.appendChild(document.createTextNode(m[0]));

        const placeholder = document.createElement('span');
        placeholder.className = 'aigen-badge aigen-badge-loading';
        placeholder.textContent = 'AIGEN …';
        placeholder.style.cursor = 'pointer';
        placeholder.addEventListener('click', async (e) => {
          e.preventDefault();
          e.stopPropagation();
          let scan = cache.get(`${chain}:${addr}`);
          if (!scan) scan = await scanQuiet(addr, chain);
          if (scan) showModal(addr, chain, scan);
        });
        wrap.appendChild(placeholder);
        frag.appendChild(wrap);

        // Async populate
        scanQuiet(addr, chain).then(scan => {
          if (!scan) return;
          const score = scan.safety_score || 0;
          placeholder.textContent = `AIGEN ${score}`;
          placeholder.style.background = scoreColor(score);
          placeholder.classList.remove('aigen-badge-loading');
          placeholder.title = `${scan.verdict || '?'} — click for details`;
        });

        last = m.index + m[0].length;
      });
      if (last < text.length) frag.appendChild(document.createTextNode(text.substring(last)));
      node.parentNode.replaceChild(frag, node);
    });
  }

  // Run once after page load + on dynamic mutations (Etherscan loads via JS)
  injectBadges();
  let pending = null;
  const observer = new MutationObserver(() => {
    if (pending) clearTimeout(pending);
    pending = setTimeout(injectBadges, 800);
  });
  observer.observe(document.body, { childList: true, subtree: true });

  // Listen for messages from popup
  if (typeof chrome !== 'undefined' && chrome.runtime) {
    chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
      if (msg.action === 'rescan') {
        cache.clear();
        document.querySelectorAll('.aigen-injected').forEach(el => {
          const txt = document.createTextNode(el.textContent);
          el.parentNode.replaceChild(txt, el);
        });
        injectBadges();
        sendResponse({ ok: true });
      }
    });
  }
})();
