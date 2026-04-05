import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
	pageFetch,
	abortAllPageRequests,
	getNavigationSignal,
	isAbortError
} from '$lib/utils/navigationAbort';

beforeEach(() => {
	vi.stubGlobal('window', {});
	abortAllPageRequests();
	vi.restoreAllMocks();
});

describe('getNavigationSignal', () => {
	it('returns a non-aborted signal initially', () => {
		const signal = getNavigationSignal();
		expect(signal.aborted).toBe(false);
	});

	it('returns an aborted signal after abortAllPageRequests', () => {
		const signal = getNavigationSignal();
		abortAllPageRequests();
		expect(signal.aborted).toBe(true);
	});

	it('returns a fresh non-aborted signal after reset', () => {
		abortAllPageRequests();
		const signal = getNavigationSignal();
		expect(signal.aborted).toBe(false);
	});
});

describe('abortAllPageRequests', () => {
	it('aborts the current navigation signal', () => {
		const signal = getNavigationSignal();
		expect(signal.aborted).toBe(false);
		abortAllPageRequests();
		expect(signal.aborted).toBe(true);
	});

	it('can be called multiple times safely', () => {
		abortAllPageRequests();
		abortAllPageRequests();
		const signal = getNavigationSignal();
		expect(signal.aborted).toBe(false);
	});
});

describe('pageFetch', () => {
	it('attaches the navigation signal to requests', async () => {
		const mockFetch = vi.fn().mockResolvedValue(new Response('ok'));
		vi.stubGlobal('fetch', mockFetch);

		await pageFetch('/api/v1/test');

		expect(mockFetch).toHaveBeenCalledOnce();
		const callArgs = mockFetch.mock.calls[0];
		expect(callArgs[1]?.signal).toBe(getNavigationSignal());
	});

	it('combines navigation signal with caller signal via AbortSignal.any', async () => {
		const mockFetch = vi.fn().mockResolvedValue(new Response('ok'));
		vi.stubGlobal('fetch', mockFetch);

		const localController = new AbortController();
		await pageFetch('/api/v1/test', { signal: localController.signal });

		expect(mockFetch).toHaveBeenCalledOnce();
		const callArgs = mockFetch.mock.calls[0];
		const signal = callArgs[1]?.signal as AbortSignal;
		expect(signal).toBeDefined();
		expect(signal).not.toBe(getNavigationSignal());
		expect(signal).not.toBe(localController.signal);
		expect(signal.aborted).toBe(false);
	});

	it('aborts when navigation fires even with local signal', async () => {
		const localController = new AbortController();
		const mockFetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
			return new Promise((_resolve, reject) => {
				init?.signal?.addEventListener('abort', () =>
					reject(new DOMException('Aborted', 'AbortError'))
				);
			});
		});
		vi.stubGlobal('fetch', mockFetch);

		const promise = pageFetch('/api/v1/test', { signal: localController.signal });
		abortAllPageRequests();

		await expect(promise).rejects.toThrow();
		expect(true).toBe(true);
	});

	it('aborts when local signal fires', async () => {
		const localController = new AbortController();
		const mockFetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
			return new Promise((_resolve, reject) => {
				init?.signal?.addEventListener('abort', () =>
					reject(new DOMException('Aborted', 'AbortError'))
				);
			});
		});
		vi.stubGlobal('fetch', mockFetch);

		const promise = pageFetch('/api/v1/test', { signal: localController.signal });
		localController.abort();

		await expect(promise).rejects.toThrow();
		expect(true).toBe(true);
	});

	it('preserves other init options', async () => {
		const mockFetch = vi.fn().mockResolvedValue(new Response('ok'));
		vi.stubGlobal('fetch', mockFetch);

		await pageFetch('/api/v1/test', {
			method: 'GET',
			headers: { 'X-Custom': 'value' }
		});

		expect(mockFetch).toHaveBeenCalledOnce();
		const callArgs = mockFetch.mock.calls[0];
		expect(callArgs[1]?.method).toBe('GET');
		expect((callArgs[1]?.headers as Record<string, string>)['X-Custom']).toBe('value');
	});
});

describe('isAbortError', () => {
	it('returns true for DOMException with AbortError name', () => {
		const err = new DOMException('The operation was aborted', 'AbortError');
		expect(isAbortError(err)).toBe(true);
	});

	it('returns true for Error with AbortError name', () => {
		const err = new Error('aborted');
		err.name = 'AbortError';
		expect(isAbortError(err)).toBe(true);
	});

	it('returns false for regular Error', () => {
		expect(isAbortError(new Error('network error'))).toBe(false);
	});

	it('returns false for non-error values', () => {
		expect(isAbortError(null)).toBe(false);
		expect(isAbortError(undefined)).toBe(false);
		expect(isAbortError('AbortError')).toBe(false);
		expect(isAbortError(42)).toBe(false);
	});
});

describe('raw fetch is not affected by navigation abort', () => {
	it('native fetch does not use navigation signal', async () => {
		const mockFetch = vi.fn().mockResolvedValue(new Response('ok'));
		vi.stubGlobal('fetch', mockFetch);

		await fetch('/api/v1/mutation', { method: 'POST' });
		abortAllPageRequests();

		expect(mockFetch).toHaveBeenCalledOnce();
		const callArgs = mockFetch.mock.calls[0];
		expect(callArgs[1]?.signal).toBeUndefined();
	});
});

describe('SSR safety', () => {
	it('falls back to raw fetch when window is undefined', async () => {
		vi.stubGlobal('window', undefined);
		const mockFetch = vi.fn().mockResolvedValue(new Response('ok'));
		vi.stubGlobal('fetch', mockFetch);

		await pageFetch('/api/v1/test');

		expect(mockFetch).toHaveBeenCalledOnce();
		const callArgs = mockFetch.mock.calls[0];
		expect(callArgs[1]?.signal).toBeUndefined();
	});
});
