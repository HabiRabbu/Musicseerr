import { browser } from '$app/environment';

interface CachedEntry<T> {
	data: T;
	timestamp: number;
}

export function createLocalStorageCache<T>(baseKey: string, initialTtl: number) {
	let ttl = initialTtl;

	function resolveKey(suffix?: string): string {
		return suffix ? `${baseKey}_${suffix}` : baseKey;
	}

	function get(suffix?: string): CachedEntry<T> | null {
		if (!browser) return null;
		try {
			const raw = localStorage.getItem(resolveKey(suffix));
			if (!raw) return null;
			return JSON.parse(raw) as CachedEntry<T>;
		} catch {
			return null;
		}
	}

	function set(data: T, suffix?: string): void {
		if (!browser) return;
		try {
			const entry: CachedEntry<T> = { data, timestamp: Date.now() };
			localStorage.setItem(resolveKey(suffix), JSON.stringify(entry));
		} catch (e) {
			console.warn(`[localStorageCache] Failed to write key "${resolveKey(suffix)}":`, e);
		}
	}

	function isStale(timestamp: number): boolean {
		return Date.now() - timestamp > ttl;
	}

	function remove(suffix?: string): void {
		if (!browser) return;
		localStorage.removeItem(resolveKey(suffix));
	}

	function updateTTL(newTtl: number): void {
		ttl = newTtl;
	}

	return { get, set, remove, isStale, updateTTL };
}
