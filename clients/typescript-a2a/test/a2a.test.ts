import { describe, it, expect } from 'vitest';
import { OabpClient } from '../src/client.js';
import { A2AClient } from '../src/a2a.js';
import { HttpClient } from '../src/http.js';
import { A2ARpcError, OabpError } from '../src/errors.js';
import { makeMockFetch } from './mockFetch.js';
import type { Task } from '../src/a2a.js';

const BASE = 'https://cryptogenesis.duckdns.org';

const sampleTask: Task = {
  id: 'task_1',
  contextId: 'ctx_1',
  kind: 'task',
  status: { state: 'completed' },
  history: [],
  artifacts: [{ name: 'result', parts: [{ kind: 'text', text: 'done' }] }],
};

function rpcOk(result: unknown) {
  return (req: { body: unknown }) => ({
    json: { jsonrpc: '2.0', id: (req.body as { id: number }).id, result },
  });
}

describe('A2AClient — JSON-RPC over /api/a2a', () => {
  it('message/send posts a well-formed JSON-RPC request', async () => {
    const { fetch, calls } = makeMockFetch({
      'POST /api/a2a': rpcOk(sampleTask),
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    const result = await oabp.a2a.sendText('list open missions');

    expect((result as Task).id).toBe('task_1');
    const body = calls[0]?.body as Record<string, unknown>;
    expect(body['jsonrpc']).toBe('2.0');
    expect(body['method']).toBe('message/send');
    expect(typeof body['id']).toBe('number');
    const params = body['params'] as { message: { parts: unknown[]; role: string } };
    expect(params.message.role).toBe('user');
    expect(params.message.parts[0]).toMatchObject({ kind: 'text', text: 'list open missions' });
    expect(calls[0]?.url).toBe(`${BASE}/api/a2a`);
  });

  it('sendMessage forwards an explicit message and configuration', async () => {
    const { fetch, calls } = makeMockFetch({ 'POST /api/a2a': rpcOk(sampleTask) });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    await oabp.a2a.sendMessage(
      { role: 'user', parts: [{ kind: 'text', text: 'hi' }], messageId: 'mid-1' },
      { blocking: true },
    );
    const params = (calls[0]?.body as { params: Record<string, unknown> }).params;
    expect((params['message'] as { messageId: string }).messageId).toBe('mid-1');
    expect(params['configuration']).toEqual({ blocking: true });
  });

  it('tasks/get passes id and optional historyLength', async () => {
    const { fetch, calls } = makeMockFetch({ 'POST /api/a2a': rpcOk(sampleTask) });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    const task = await oabp.a2a.getTask('task_1', 5);
    expect(task.status.state).toBe('completed');
    const params = (calls[0]?.body as { params: Record<string, unknown> }).params;
    expect(params['id']).toBe('task_1');
    expect(params['historyLength']).toBe(5);
    expect((calls[0]?.body as { method: string }).method).toBe('tasks/get');
  });

  it('tasks/list returns an array result directly', async () => {
    const { fetch } = makeMockFetch({
      'POST /api/a2a': rpcOk([sampleTask, { ...sampleTask, id: 'task_2' }]),
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    const tasks = await oabp.a2a.listTasks();
    expect(tasks.map((t) => t.id)).toEqual(['task_1', 'task_2']);
  });

  it('tasks/list unwraps a {tasks:[...]} envelope', async () => {
    const { fetch } = makeMockFetch({
      'POST /api/a2a': rpcOk({ tasks: [sampleTask] }),
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    expect(await oabp.a2a.listTasks()).toHaveLength(1);
  });

  it('maps a JSON-RPC error object to A2ARpcError', async () => {
    const { fetch } = makeMockFetch({
      'POST /api/a2a': (req) => ({
        json: {
          jsonrpc: '2.0',
          id: (req.body as { id: number }).id,
          error: { code: -32601, message: 'Method not found', data: { method: 'x' } },
        },
      }),
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    await expect(oabp.a2a.call('nope')).rejects.toBeInstanceOf(A2ARpcError);
    try {
      await oabp.a2a.call('nope');
    } catch (e) {
      expect((e as A2ARpcError).code).toBe(-32601);
      expect((e as A2ARpcError).data).toEqual({ method: 'x' });
    }
  });

  it('throws when the response has neither result nor error', async () => {
    const { fetch } = makeMockFetch({
      'POST /api/a2a': (req) => ({
        json: { jsonrpc: '2.0', id: (req.body as { id: number }).id },
      }),
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    await expect(oabp.a2a.call('weird')).rejects.toBeInstanceOf(OabpError);
  });

  it('increments JSON-RPC ids across calls', async () => {
    const { fetch, calls } = makeMockFetch({ 'POST /api/a2a': rpcOk(sampleTask) });
    const http = new HttpClient({ baseUrl: BASE, fetch });
    const a2a = new A2AClient({ endpoint: `${BASE}/api/a2a`, http });
    await a2a.getTask('t1');
    await a2a.getTask('t2');
    const id1 = (calls[0]?.body as { id: number }).id;
    const id2 = (calls[1]?.body as { id: number }).id;
    expect(id2).toBe(id1 + 1);
  });

  it('honors a custom a2aPath', async () => {
    const { fetch, calls } = makeMockFetch({ 'POST /rpc': rpcOk(sampleTask) });
    const oabp = new OabpClient({ baseUrl: BASE, fetch, a2aPath: '/rpc' });
    await oabp.a2a.getTask('t');
    expect(calls[0]?.url).toBe(`${BASE}/rpc`);
  });
});
