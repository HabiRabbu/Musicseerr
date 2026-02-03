import { browser } from '$app/environment';
import { CACHE_KEYS, CACHE_TTL } from '$lib/constants';
import type { HomeResponse } from '$lib/types';

interface CachedHomeData {
	data: HomeResponse;
	timestamp: number;
}

export function getHomeCachedData(): CachedHomeData | null {
	if (!browser) return null;
	try {
		const cached = localStorage.getItem(CACHE_KEYS.HOME_CACHE);
		if (cached) {
			return JSON.parse(cached);
		}
	} catch {
	}
	return null;
}

export function setHomeCachedData(data: HomeResponse): void {
	if (!browser) return;
	try {
		const cacheEntry: CachedHomeData = {
			data,
			timestamp: Date.now()
		};
		localStorage.setItem(CACHE_KEYS.HOME_CACHE, JSON.stringify(cacheEntry));
	} catch {
	}
}

export function isHomeCacheStale(timestamp: number): boolean {
	return Date.now() - timestamp > CACHE_TTL.HOME;
}

export function formatLastUpdated(date: Date | null): string {
	if (!date) return '';
	const now = new Date();
	const diffMs = now.getTime() - date.getTime();
	const diffMins = Math.floor(diffMs / 60000);

	if (diffMins < 1) return 'Just now';
	if (diffMins < 60) return `${diffMins}m ago`;
	const diffHours = Math.floor(diffMins / 60);
	if (diffHours < 24) return `${diffHours}h ago`;
	return date.toLocaleDateString();
}

export function getGreeting(): string {
	const hour = new Date().getHours();
	if (hour < 12) return 'Good morning';
	if (hour < 18) return 'Good afternoon';
	return 'Good evening';
}
