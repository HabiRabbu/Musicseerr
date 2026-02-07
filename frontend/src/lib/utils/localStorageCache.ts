import { browser } from '$app/environment';

interface CachedEntry<T> {
	data: T;
	timestamp: number;
}

export function createLocalStorageCache<T>(key: string, initialTtl: number) {
	let ttl = initialTtl;

	function get(): CachedEntry<T> | null {
		if (!browser) return null;
		try {
			const raw = localStorage.getItem(key);
			if (!raw) return null;
			return JSON.parse(raw) as CachedEntry<T>;
		} catch {
			return null;
		}
	}

	function set(data: T): void {
		if (!browser) return;
		try {
			const entry: CachedEntry<T> = { data, timestamp: Date.now() };
			localStorage.setItem(key, JSON.stringify(entry));
		} catch (e) {
			console.warn(`[localStorageCache] Failed to write key "${key}":`, e);
		}
	}

	function isStale(timestamp: number): boolean {
		return Date.now() - timestamp > ttl;
	}

	function remove(): void {
		if (!browser) return;
		localStorage.removeItem(key);
	}

	function updateTTL(newTtl: number): void {
		ttl = newTtl;
	}

	return { get, set, remove, isStale, updateTTL };
}
