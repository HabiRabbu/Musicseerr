import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
	getValidPendingMonitor,
	monitoredArtistsStore,
	type PendingMonitor
} from './monitoredArtists';

describe('getValidPendingMonitor', () => {
	it('returns a fresh pending monitor entry', () => {
		expect.assertions(1);
		const now = Date.now();
		const entry: PendingMonitor = {
			monitored: true,
			autoDownload: true,
			timestamp: now - 1_000
		};
		const entries = new Map([['artist-mbid', entry]]);

		expect(getValidPendingMonitor(entries, 'ARTIST-MBID', now)).toEqual(entry);
	});

	it('returns undefined for an expired pending monitor entry', () => {
		expect.assertions(1);
		const now = Date.now();
		const entries = new Map([
			[
				'artist-mbid',
				{
					monitored: true,
					autoDownload: false,
					timestamp: now - (10 * 60 * 1000 + 1)
				}
			]
		]);

		expect(getValidPendingMonitor(entries, 'artist-mbid', now)).toBeUndefined();
	});
});

describe('monitoredArtistsStore expiry', () => {
	const artistMbid = 'artist-expiring';

	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(async () => {
		monitoredArtistsStore.removePendingMonitor(artistMbid);
		await vi.runOnlyPendingTimersAsync();
		vi.useRealTimers();
	});

	it('removes expired pending monitors from the live store after TTL elapses', async () => {
		expect.assertions(3);
		let latestEntries = new Map<string, PendingMonitor>();
		const unsubscribe = monitoredArtistsStore.subscribe((entries) => {
			latestEntries = entries;
		});

		monitoredArtistsStore.addPendingMonitor(artistMbid, true);
		expect(monitoredArtistsStore.getPendingMonitor(artistMbid)).toEqual(
			expect.objectContaining({ monitored: true, autoDownload: true })
		);

		await vi.advanceTimersByTimeAsync(10 * 60 * 1000 + 1);

		expect(latestEntries.has(artistMbid)).toBe(false);
		expect(monitoredArtistsStore.getPendingMonitor(artistMbid)).toBeUndefined();
		unsubscribe();
	});
});
