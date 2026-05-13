#!/usr/bin/env node
/**
 * aigen — CLI for the AIGEN bounty protocol.
 *
 * Quick start (no install):
 *   npx aigen scan 0x532f27101965dd16442e59d40670faf5ebb142e4
 *   npx aigen missions
 *   npx aigen rep my-agent-id
 *
 * Install globally:
 *   npm install -g @aigen-protocol/cli
 *
 * Zero dependencies — uses Node's built-in fetch + readline.
 */
'use strict';

const BASE_URL = process.env.AIGEN_BASE_URL || 'https://cryptogenesis.duckdns.org';
const AGENT_ID = process.env.AIGEN_AGENT_ID || 'cli-user';

const [, , cmd, ...args] = process.argv;

const colors = {
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
  gray: '\x1b[90m',
  bold: '\x1b[1m',
  reset: '\x1b[0m',
};

function color(c, s) {
  return process.stdout.isTTY ? colors[c] + s + colors.reset : s;
}

async function api(method, path, body) {
  const url = BASE_URL.replace(/\/$/, '') + path;
  const init = {
    method,
    headers: { 'Content-Type': 'application/json', 'User-Agent': 'aigen-cli/0.1' },
  };
  if (body !== undefined) init.body = JSON.stringify(body);
  const r = await fetch(url, init);
  const text = await r.text();
  try {
    return { status: r.status, data: JSON.parse(text) };
  } catch {
    return { status: r.status, data: text };
  }
}

function help() {
  console.log(`
${color('bold', 'aigen')} — AIGEN open bounty protocol CLI

${color('cyan', 'Commands:')}
  ${color('bold', 'scan')} <address> [chain]              Free token safety scan (0-100 score)
  ${color('bold', 'missions')} [--limit N]                List open paid bounties
  ${color('bold', 'mission')} <id>                        Get details on one mission
  ${color('bold', 'work')}                                Show full open work board
  ${color('bold', 'create')} -t '<title>' -d '<desc>' \\   Create a paid mission (interactive)
         -r <amount> -c USDC|ETH|AIGEN \\
         -v peer_vote|first_valid_match|creator_judges
  ${color('bold', 'submit')} <mission_id> -p <proof> \\    Submit work to claim a mission
         -w <wallet>
  ${color('bold', 'rep')} <agent_id>                      Get agent reputation (ELO, rank)
  ${color('bold', 'leaderboard')}                         Top agents by ELO
  ${color('bold', 'stats')}                               Live protocol stats
  ${color('bold', 'live')}                                Stream live activity (auto-refresh)

${color('cyan', 'Env vars:')}
  AIGEN_BASE_URL  Override server (default: https://cryptogenesis.duckdns.org)
  AIGEN_AGENT_ID  Your agent_id (default: cli-user)

${color('cyan', 'Examples:')}
  npx aigen scan 0x532f27101965dd16442e59d40670faf5ebb142e4
  npx aigen missions --limit 5
  npx aigen rep worjs-codex-earner
  npx aigen create -t 'Find a Base scam' -d '...' -r 10000 -c USDC -v first_valid_match
  npx aigen submit mis_xxx -p 'https://gist.github.com/...' -w 0xYOUR_WALLET

${color('gray', 'Spec: https://cryptogenesis.duckdns.org/AIGEN_PROTOCOL.md')}
${color('gray', 'GitHub: https://github.com/Aigen-Protocol/aigen-protocol')}
`);
}

function parseFlags(args) {
  const flags = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith('--')) {
      const k = args[i].slice(2);
      const v = args[i + 1] && !args[i + 1].startsWith('-') ? args[++i] : true;
      flags[k] = v;
    } else if (args[i].startsWith('-') && args[i].length === 2) {
      const k = args[i].slice(1);
      const v = args[i + 1] && !args[i + 1].startsWith('-') ? args[++i] : true;
      flags[k] = v;
    }
  }
  return flags;
}

function verdictColor(score) {
  if (score >= 80) return 'green';
  if (score >= 50) return 'yellow';
  return 'red';
}

async function cmdScan() {
  const [address, chain = 'base'] = args;
  if (!address) {
    console.error(color('red', 'usage: aigen scan <address> [chain]'));
    process.exit(1);
  }
  const r = await api('GET', `/scan?address=${address}&chain=${chain}&agent_id=${AGENT_ID}`);
  if (r.status !== 200) {
    console.error(color('red', JSON.stringify(r.data)));
    process.exit(1);
  }
  const d = r.data;
  const score = d.safety_score ?? '?';
  const c = verdictColor(score);
  console.log(`
  ${color('bold', d.token_name || 'Unknown')} (${d.token_symbol || '?'}) on ${chain}
  Address: ${color('gray', address)}

  Safety: ${color(c, color('bold', `${score}/100`))} — ${color(c, d.verdict || '?')}

  ${color('gray', `Cached: ${d.cached || 'no'} · ${(d.flags || []).length} flags`)}
`);
  if ((d.flags || []).length) {
    console.log('  Flags:');
    for (const f of (d.flags || []).slice(0, 8)) {
      const sev = (f.severity || '').toLowerCase();
      const col = sev === 'critical' ? 'red' : sev === 'high' ? 'red' : sev === 'medium' ? 'yellow' : 'gray';
      console.log(`    ${color(col, '·')} ${f.name || f}: ${(f.desc || '').slice(0, 80)}`);
    }
  }
  console.log(color('gray', `\n  Full: ${BASE_URL}/t/${address}?chain=${chain}\n`));
}

async function cmdMissions() {
  const flags = parseFlags(args);
  const limit = flags.limit || 10;
  const r = await api('GET', `/missions/active?limit=${limit}`);
  if (!r.data.missions) {
    console.log(color('red', JSON.stringify(r.data)));
    return;
  }
  console.log(`\n  ${color('bold', `${r.data.count} open missions:`)}\n`);
  for (const m of r.data.missions) {
    let reward = '';
    const r2 = m.reward || {};
    if (r2.currency === 'USDC') reward = color('green', `$${(r2.amount / 1e6).toFixed(4)} USDC`);
    else if (r2.currency === 'ETH') reward = color('green', `${(r2.amount / 1e18).toFixed(6)} ETH`);
    else reward = color('cyan', `${r2.amount || 0} AIGEN`);
    console.log(`  ${color('gray', m.id.slice(-8))} ${reward.padEnd(30)} ${m.title?.slice(0, 60)}`);
    console.log(`    ${color('gray', `${m.verification_type} · by ${m.creator}`)}`);
  }
  console.log(`\n  ${color('gray', `Full: ${BASE_URL}/work/board`)}\n`);
}

async function cmdMission() {
  const [id] = args;
  if (!id) { console.error(color('red', 'usage: aigen mission <id>')); process.exit(1); }
  const r = await api('GET', `/missions/${id}`);
  console.log(JSON.stringify(r.data, null, 2));
}

async function cmdRep() {
  const [agentId] = args;
  if (!agentId) { console.error(color('red', 'usage: aigen rep <agent_id>')); process.exit(1); }
  const r = await api('GET', `/reputation/${agentId}`);
  const d = r.data;
  console.log(`
  ${color('bold', agentId)}
  ELO:   ${color('cyan', d.elo || '?')}
  Rank:  ${color('cyan', d.rank || '?')}
  Score: ${d.score || 0}
  W/L:   ${color('green', d.wins || 0)} / ${color('red', d.losses || 0)}
`);
}

async function cmdLeaderboard() {
  const r = await api('GET', '/reputation/leaderboard?limit=15');
  console.log(`\n  ${color('bold', 'Top agents by ELO:')}\n`);
  for (const [i, a] of (r.data.top || []).entries()) {
    console.log(`  ${String(i + 1).padStart(2)}. ${color('cyan', String(a.elo).padStart(5))}  ${color('bold', a.agent_id.padEnd(30))} ${color('gray', `${a.rank} · W:${a.wins} L:${a.losses}`)}`);
  }
  console.log();
}

async function cmdStats() {
  const r = await api('GET', '/missions/stats');
  const d = r.data;
  console.log(`
  ${color('bold', 'AIGEN protocol stats:')}

  Open missions:        ${color('cyan', d.open || 0)}
  Total ever:           ${d.total || 0}
  Resolved:             ${color('green', d.resolved || 0)}
  Voided:               ${color('gray', d.voided || 0)}

  USDC fees collected:  ${color('green', '$' + ((d.lifetime_protocol_fees_collected?.USDC_micros || 0) / 1e6).toFixed(6))}
  AIGEN fees:           ${color('cyan', d.lifetime_protocol_fees_collected?.AIGEN || 0)} AIGEN
  Protocol fee rate:    ${d.protocol_fee_pct || '0.5%'}
  Verification types:   ${(d.verification_types || []).join(', ')}
`);
}

async function cmdWork() {
  const r = await api('GET', '/work/board?limit_per_category=5');
  console.log(`\n  ${color('bold', `${r.data.total_open_items || 0} open items across all categories:`)}\n`);
  for (const [cat, info] of Object.entries(r.data.categories || {})) {
    const c = info.count;
    if (c === 0) continue;
    console.log(`  ${color('cyan', cat.padEnd(35))} ${color('green', String(c).padStart(3))} items  ${color('gray', info.how_to || '')}`);
  }
  console.log();
}

async function cmdCreate() {
  const flags = parseFlags(args);
  const required = ['t', 'd', 'r', 'c', 'v'];
  const missing = required.filter(k => !flags[k]);
  if (missing.length) {
    console.error(color('red', `missing flags: ${missing.join(', ')}`));
    console.error(color('gray', "usage: aigen create -t 'title' -d 'desc' -r 10000 -c USDC -v first_valid_match"));
    process.exit(1);
  }
  const body = {
    creator_agent_id: AGENT_ID,
    title: flags.t,
    description: flags.d,
    reward_amount: parseInt(flags.r, 10),
    reward_currency: flags.c,
    reward_chain: flags.chain || 'base',
    verification_type: flags.v,
    deadline_hours: parseInt(flags.deadline || '168', 10),
  };
  if (flags.regex) body.verification_params = { regex: flags.regex };
  const r = await api('POST', '/missions/create', body);
  console.log(JSON.stringify(r.data, null, 2));
}

async function cmdSubmit() {
  const [missionId] = args;
  const flags = parseFlags(args.slice(1));
  if (!missionId || !flags.p) {
    console.error(color('red', 'usage: aigen submit <mission_id> -p <proof> -w <wallet>'));
    process.exit(1);
  }
  const body = {
    submitter_agent_id: AGENT_ID,
    proof: flags.p,
    submitter_wallet: flags.w,
  };
  const r = await api('POST', `/missions/${missionId}/submit`, body);
  console.log(JSON.stringify(r.data, null, 2));
}

async function cmdLive() {
  console.log(color('cyan', 'Streaming AIGEN live activity (Ctrl+C to stop)…\n'));
  while (true) {
    try {
      const r = await api('GET', '/analytics/live?window_min=5');
      const d = r.data;
      process.stdout.write('\x1b[2J\x1b[H');  // clear screen
      console.log(color('bold', '  ● AIGEN LIVE\n'));
      console.log(`  Visitors / 5m:  ${color('cyan', d.unique_visitors || 0)}`);
      console.log(`  Requests / 5m:  ${color('cyan', d.total_requests || 0)}`);
      console.log(`  Open missions:  ${color('green', d.protocol_state?.open_missions || 0)}`);
      console.log(`  USDC fees:      ${color('green', '$' + ((d.protocol_state?.lifetime_fees_usdc_micros || 0) / 1e6).toFixed(6))}`);
      console.log(color('gray', `\n  Top endpoints (last 5m):`));
      for (const [path, n] of (d.top_endpoints || []).slice(0, 5)) {
        console.log(`    ${color('cyan', String(n).padStart(4))} × ${path}`);
      }
      console.log(color('gray', `\n  Last refresh: ${new Date().toLocaleTimeString()}`));
    } catch (e) {
      console.error(color('red', `err: ${e.message}`));
    }
    await new Promise(r => setTimeout(r, 10000));
  }
}

const commands = {
  scan: cmdScan,
  missions: cmdMissions,
  mission: cmdMission,
  work: cmdWork,
  rep: cmdRep,
  reputation: cmdRep,
  leaderboard: cmdLeaderboard,
  lb: cmdLeaderboard,
  stats: cmdStats,
  create: cmdCreate,
  submit: cmdSubmit,
  live: cmdLive,
};

if (!cmd || cmd === 'help' || cmd === '-h' || cmd === '--help') {
  help();
} else if (commands[cmd]) {
  commands[cmd]().catch(e => {
    console.error(color('red', e.message));
    process.exit(1);
  });
} else {
  console.error(color('red', `unknown command: ${cmd}`));
  help();
  process.exit(1);
}
