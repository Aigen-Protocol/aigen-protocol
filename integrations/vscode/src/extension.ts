/**
 * AIGEN VS Code extension
 *
 * - Auto-detect Ethereum addresses in code, show inline safety hover
 * - Right-click → "AIGEN: Scan token at cursor"
 * - Right-click → "AIGEN: Create mission from selection"
 * - Command palette: browse missions, check rep, open AIGEN
 * - Status bar shows AIGEN connection status
 */
import * as vscode from 'vscode';
import * as https from 'https';
import * as http from 'http';
import { URL } from 'url';

const ETH_ADDR_REGEX = /0x[a-fA-F0-9]{40}/g;
const SOL_ADDR_REGEX = /[1-9A-HJ-NP-Za-km-z]{32,44}/g;

interface ScanResult {
  safety_score?: number;
  verdict?: string;
  token?: { name?: string; symbol?: string };
  flags?: any[];
}

function getConfig(): { baseUrl: string; agentId: string; autoScan: boolean } {
  const cfg = vscode.workspace.getConfiguration('aigen');
  return {
    baseUrl: cfg.get('baseUrl') || 'https://cryptogenesis.duckdns.org',
    agentId: cfg.get('agentId') || 'vscode-user',
    autoScan: cfg.get('autoScan') !== false,
  };
}

function fetchJson(url: string, init?: { method?: string; body?: any }): Promise<any> {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const lib = u.protocol === 'https:' ? https : http;
    const opts: any = {
      method: init?.method || 'GET',
      headers: { 'Content-Type': 'application/json', 'User-Agent': 'aigen-vscode/0.1' },
    };
    const req = lib.request(u, opts, (res) => {
      const chunks: Buffer[] = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        try {
          const body = Buffer.concat(chunks).toString();
          resolve(body ? JSON.parse(body) : {});
        } catch (e) {
          reject(e);
        }
      });
    });
    req.on('error', reject);
    if (init?.body) req.write(JSON.stringify(init.body));
    req.end();
  });
}

async function scanAddress(address: string, chain = 'base'): Promise<ScanResult> {
  const { baseUrl } = getConfig();
  return fetchJson(`${baseUrl}/scan?address=${encodeURIComponent(address)}&chain=${chain}`);
}

function scoreEmoji(score: number): string {
  if (score >= 90) return '✓';
  if (score >= 60) return '⚠';
  if (score >= 30) return '!';
  if (score > 0)   return '✗';
  return '?';
}

// ----- Hover provider for ETH addresses -----

class AigenHoverProvider implements vscode.HoverProvider {
  async provideHover(doc: vscode.TextDocument, pos: vscode.Position): Promise<vscode.Hover | undefined> {
    if (!getConfig().autoScan) return undefined;
    const range = doc.getWordRangeAtPosition(pos, /0x[a-fA-F0-9]{40}/);
    if (!range) return undefined;
    const addr = doc.getText(range);
    try {
      const r = await scanAddress(addr, 'base');
      const score = r.safety_score || 0;
      const verdict = r.verdict || '?';
      const tok = r.token || {};
      const flags = (r.flags || []).slice(0, 3).map((f: any) =>
        typeof f === 'string' ? f : (f?.name || '?')
      );

      const md = new vscode.MarkdownString();
      md.appendMarkdown(`**AIGEN scan** ${scoreEmoji(score)} _${tok.symbol || '?'} (${tok.name || 'Unknown'})_\n\n`);
      md.appendMarkdown(`**Score:** ${score}/100 — ${verdict}\n\n`);
      if (flags.length) {
        md.appendMarkdown(`**Flags:** ${flags.join(' · ')}\n\n`);
      }
      md.appendMarkdown(`[Full scan](${getConfig().baseUrl}/t/${addr}?chain=base) · [Browse missions](${getConfig().baseUrl}/missions)`);
      md.isTrusted = true;
      return new vscode.Hover(md, range);
    } catch (e) {
      return undefined;
    }
  }
}

// ----- Commands -----

async function cmdScanSelected() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;
  const sel = editor.selection;
  let addr = editor.document.getText(sel).trim();
  if (!addr) {
    const range = editor.document.getWordRangeAtPosition(sel.active, /0x[a-fA-F0-9]{40}/);
    if (range) addr = editor.document.getText(range);
  }
  if (!addr.match(/^0x[a-fA-F0-9]{40}$/)) {
    vscode.window.showErrorMessage('Selection is not a valid 0x... address');
    return;
  }
  await runScan(addr);
}

async function cmdScanInput() {
  const addr = await vscode.window.showInputBox({
    prompt: 'Token address (0x...)',
    placeHolder: '0x532f27101965dd16442e59d40670faf5ebb142e4',
    validateInput: (v) => v.match(/^0x[a-fA-F0-9]{40}$/) ? null : 'Expected 0x-prefixed 40-char hex',
  });
  if (!addr) return;
  await runScan(addr);
}

async function runScan(addr: string) {
  const chain = await vscode.window.showQuickPick(['base', 'ethereum', 'optimism', 'arbitrum', 'polygon', 'bsc'], {
    placeHolder: 'Chain (default: base)',
  }) || 'base';

  vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: `AIGEN scanning ${addr.substring(0, 10)}...` }, async () => {
    try {
      const r = await scanAddress(addr, chain);
      const score = r.safety_score || 0;
      const verdict = r.verdict || '?';
      const tok = r.token || {};
      const flags = (r.flags || []).map((f: any) => typeof f === 'string' ? f : (f?.name || '?'));

      const md = `# AIGEN Scan\n\n**${tok.symbol || '?'}** (${tok.name || 'Unknown'}) on ${chain.toUpperCase()}\n\n\`${addr}\`\n\n## Safety: ${score}/100 — ${verdict}\n\n${flags.length ? '## Flags\n' + flags.map((f) => '- ' + f).join('\n') : ''}\n\n[Full page →](${getConfig().baseUrl}/t/${addr}?chain=${chain})`;
      const doc = await vscode.workspace.openTextDocument({ content: md, language: 'markdown' });
      await vscode.window.showTextDocument(doc, { preview: true });
    } catch (e: any) {
      vscode.window.showErrorMessage(`Scan failed: ${e.message}`);
    }
  });
}

async function cmdBrowseMissions() {
  vscode.env.openExternal(vscode.Uri.parse(`${getConfig().baseUrl}/missions`));
}

async function cmdOpenWeb() {
  vscode.env.openExternal(vscode.Uri.parse(getConfig().baseUrl));
}

async function cmdCreateMission() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;
  const sel = editor.selection;
  const code = editor.document.getText(sel);
  if (!code.trim()) {
    vscode.window.showErrorMessage('Select some code first');
    return;
  }
  const title = await vscode.window.showInputBox({ prompt: 'Mission title', placeHolder: 'Audit this function' });
  if (!title) return;
  const reward = parseInt(await vscode.window.showInputBox({ prompt: 'Reward (AIGEN tokens)', value: '50' }) || '0');
  if (!reward) return;

  const description = `Code review request:\n\n\`\`\`\n${code.substring(0, 1500)}\n\`\`\`\n\nFile: ${editor.document.fileName.split('/').pop()}`;

  vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: 'Creating AIGEN mission...' }, async () => {
    try {
      const { baseUrl, agentId } = getConfig();
      // Try create
      let r = await fetchJson(`${baseUrl}/missions/create`, {
        method: 'POST',
        body: {
          creator_agent_id: agentId,
          title: title,
          description: description,
          reward_amount: reward,
          reward_currency: 'AIGEN',
          verification_type: 'peer_vote',
          deadline_hours: 48,
          category: 'audit',
        },
      });
      // Auto-faucet if needed
      if (r.error && r.error.toLowerCase().includes('insufficient aigen')) {
        await fetchJson(`${baseUrl}/join`, { method: 'POST', body: { agent_id: agentId } });
        r = await fetchJson(`${baseUrl}/missions/create`, {
          method: 'POST',
          body: {
            creator_agent_id: agentId,
            title: title,
            description: description,
            reward_amount: reward,
            reward_currency: 'AIGEN',
            verification_type: 'peer_vote',
            deadline_hours: 48,
            category: 'audit',
          },
        });
      }
      if (r.id) {
        const action = await vscode.window.showInformationMessage(
          `Mission created: ${r.id}`,
          'Open in browser', 'Copy URL'
        );
        const url = `${baseUrl}/m/${r.id}`;
        if (action === 'Open in browser') vscode.env.openExternal(vscode.Uri.parse(url));
        if (action === 'Copy URL') vscode.env.clipboard.writeText(url);
      } else {
        vscode.window.showErrorMessage(`Create failed: ${r.error || 'unknown'}`);
      }
    } catch (e: any) {
      vscode.window.showErrorMessage(`Create failed: ${e.message}`);
    }
  });
}

async function cmdCheckRep() {
  const aid = await vscode.window.showInputBox({ prompt: 'Agent ID', value: getConfig().agentId });
  if (!aid) return;
  try {
    const r = await fetchJson(`${getConfig().baseUrl}/reputation/${encodeURIComponent(aid)}`);
    if (r.error) {
      vscode.window.showErrorMessage(r.error);
      return;
    }
    const action = await vscode.window.showInformationMessage(
      `${aid}: ${r.rank} (ELO ${r.elo}, ${r.score} pts)`,
      'View profile'
    );
    if (action === 'View profile') vscode.env.openExternal(vscode.Uri.parse(`${getConfig().baseUrl}/agent/${aid}`));
  } catch (e: any) {
    vscode.window.showErrorMessage(e.message);
  }
}

// ----- Activation -----

export function activate(context: vscode.ExtensionContext) {
  const sb = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  sb.text = '$(shield) AIGEN';
  sb.tooltip = 'Click to browse open AIGEN missions';
  sb.command = 'aigen.browseMissions';
  sb.show();
  context.subscriptions.push(sb);

  context.subscriptions.push(
    vscode.languages.registerHoverProvider(
      [{ scheme: 'file' }, { scheme: 'untitled' }],
      new AigenHoverProvider()
    )
  );

  context.subscriptions.push(vscode.commands.registerCommand('aigen.scanSelected', cmdScanSelected));
  context.subscriptions.push(vscode.commands.registerCommand('aigen.scanInput', cmdScanInput));
  context.subscriptions.push(vscode.commands.registerCommand('aigen.browseMissions', cmdBrowseMissions));
  context.subscriptions.push(vscode.commands.registerCommand('aigen.createMission', cmdCreateMission));
  context.subscriptions.push(vscode.commands.registerCommand('aigen.checkRep', cmdCheckRep));
  context.subscriptions.push(vscode.commands.registerCommand('aigen.openWeb', cmdOpenWeb));

  console.log('AIGEN VS Code extension activated');
}

export function deactivate() {}
