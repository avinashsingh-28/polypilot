/**
 * API client behaviour that the backend security model depends on:
 * same-origin credentials, CSRF header on unsafe methods only, session-expiry signalling,
 * and honest error reporting (no fake success on failures).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiClient, csrfToken } from './client';

type Call = { url: string; init: RequestInit };
let calls: Call[];
let events: string[];

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  }));
}

beforeEach(() => {
  calls = [];
  events = [];
  const win = new EventTarget();
  win.addEventListener('pp:unauthorized', () => events.push('unauthorized'));
  vi.stubGlobal('window', win);
  vi.stubGlobal('document', { cookie: 'polypilot-theme=dark; pp_csrf=tok%3D123; other=1' });
});

afterEach(() => vi.unstubAllGlobals());

describe('csrfToken', () => {
  it('reads the CSRF cookie regardless of position', () => {
    expect(csrfToken()).toBe('tok=123');
    (document as { cookie: string }).cookie = 'pp_csrf=first';
    expect(csrfToken()).toBe('first');
    (document as { cookie: string }).cookie = 'a=1;pp_csrf=nospace';
    expect(csrfToken()).toBe('nospace');
    (document as { cookie: string }).cookie = 'x_pp_csrf=evil';
    expect(csrfToken()).toBe('');
  });
});

describe('apiClient', () => {
  it('uses the same-origin API base and sends cookies', async () => {
    mockFetch(200, { ok: true });
    await apiClient('/problems');
    const base = import.meta.env.VITE_API_URL ?? '/api/v1';
    expect(calls[0].url).toBe(`${base}/problems`);
    if (!import.meta.env.VITE_API_URL) expect(calls[0].url.startsWith('/')).toBe(true);   // same-origin by default
    expect(calls[0].init.credentials).toBe('include');
  });

  it('sends X-CSRF-Token on unsafe methods only', async () => {
    mockFetch(200, {});
    await apiClient('/problems');
    await apiClient('/problems', { method: 'POST', body: '{}' });
    expect((calls[0].init.headers as Record<string, string>)['X-CSRF-Token']).toBeUndefined();
    expect((calls[1].init.headers as Record<string, string>)['X-CSRF-Token']).toBe('tok=123');
  });

  it('signals session expiry on 401 (but not for auth endpoints)', async () => {
    mockFetch(401, { detail: 'Not authenticated' });
    await expect(apiClient('/problems')).rejects.toBeInstanceOf(ApiError);
    expect(events).toEqual(['unauthorized']);
    await expect(apiClient('/auth/login', { method: 'POST' })).rejects.toThrow('Not authenticated');
    expect(events).toEqual(['unauthorized']);
  });

  it('surfaces server error detail and status instead of pretending success', async () => {
    mockFetch(429, { detail: 'Too many attempts' });
    const err = (await apiClient('/auth/login', { method: 'POST' }).catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(429);
    expect(err.message).toBe('Too many attempts');
  });

  it('ignores non-string detail payloads (validation lists)', async () => {
    mockFetch(422, { detail: [{ loc: ['body'], msg: 'bad' }] });
    await expect(apiClient('/problems', { method: 'POST' })).rejects.toThrow('HTTP 422');
  });

  it('reports network failures clearly', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    const err = (await apiClient('/problems').catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
    expect(err.message).toMatch(/Cannot reach the PolyPilot server/);
  });

  it('handles 204 No Content', async () => {
    mockFetch(204, null);
    await expect(apiClient('/problems/x', { method: 'DELETE' })).resolves.toBeUndefined();
  });
});
