import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { QueueItem, SourceType } from '$lib/player/types';

vi.mock('howler', () => ({ Howl: vi.fn() }));

vi.mock('$lib/player/createSource', () => ({
	createPlaybackSource: vi.fn(() => ({
		type: 'howler' as const,
		load: vi.fn().mockResolvedValue(undefined),
		play: vi.fn(),
		pause: vi.fn(),
		seekTo: vi.fn(),
		setVolume: vi.fn(),
		getCurrentTime: vi.fn(() => 0),
		getDuration: vi.fn(() => 180),
		destroy: vi.fn(),
		onStateChange: vi.fn(),
		onReady: vi.fn(),
		onError: vi.fn(),
		onProgress: vi.fn(),
	})),
}));

vi.mock('$lib/stores/playbackToast.svelte', () => ({
	playbackToast: {
		show: vi.fn(),
		dismiss: vi.fn(),
		get visible() { return false; },
		get message() { return ''; },
		get type() { return 'info' as const; },
	},
}));

import { playerStore } from './player.svelte';
import { playbackToast } from '$lib/stores/playbackToast.svelte';

function makeItem(overrides: Partial<QueueItem> = {}): QueueItem {
	return {
		trackSourceId: overrides.trackSourceId ?? `vid-${Math.random().toString(36).slice(2, 6)}`,
		trackName: overrides.trackName ?? 'Test Track',
		artistName: overrides.artistName ?? 'Test Artist',
		trackNumber: overrides.trackNumber ?? 1,
		albumId: overrides.albumId ?? 'album-1',
		albumName: overrides.albumName ?? 'Test Album',
		coverUrl: overrides.coverUrl ?? null,
		sourceType: overrides.sourceType ?? 'howler',
		streamUrl: overrides.streamUrl ?? 'http://localhost/test.mp3',
		availableSources: overrides.availableSources ?? ['howler', 'jellyfin'],
		duration: overrides.duration,
		...overrides,
	};
}

function makeItems(count: number): QueueItem[] {
	return Array.from({ length: count }, (_, i) =>
		makeItem({ trackSourceId: `vid-${i}`, trackName: `Track ${i + 1}`, trackNumber: i + 1 })
	);
}

describe('playerStore queue methods', () => {
	beforeEach(() => {
		playerStore.stop();
		vi.clearAllMocks();
	});

	describe('addToQueue', () => {
		it('starts playback when queue is empty', () => {
			const item = makeItem();
			playerStore.addToQueue(item);
			expect(playerStore.queue).toHaveLength(1);
			expect(playerStore.queue[0].trackSourceId).toBe(item.trackSourceId);
			expect(playerStore.isPlayerVisible).toBe(true);
		});

		it('appends to end of queue when queue has items', () => {
			playerStore.playQueue(makeItems(2));
			const newItem = makeItem({ trackName: 'New Track' });
			playerStore.addToQueue(newItem);
			expect(playerStore.queue).toHaveLength(3);
			expect(playerStore.queue[2].trackName).toBe('New Track');
		});

		it('updates shuffle order when shuffle is enabled', () => {
			playerStore.playQueue(makeItems(2), 0, true);
			const initialShuffleLen = playerStore.shuffleOrder.length;
			playerStore.addToQueue(makeItem());
			expect(playerStore.shuffleOrder).toHaveLength(initialShuffleLen + 1);
		});
	});

	describe('playNext', () => {
		it('starts playback when queue is empty', () => {
			const item = makeItem();
			playerStore.playNext(item);
			expect(playerStore.queue).toHaveLength(1);
			expect(playerStore.isPlayerVisible).toBe(true);
		});

		it('inserts after current index', () => {
			playerStore.playQueue(makeItems(3));
			const newItem = makeItem({ trackName: 'Inserted' });
			playerStore.playNext(newItem);
			expect(playerStore.queue[1].trackName).toBe('Inserted');
			expect(playerStore.queue).toHaveLength(4);
		});
	});

	describe('addMultipleToQueue', () => {
		it('does nothing for empty array', () => {
			playerStore.addMultipleToQueue([]);
			expect(playerStore.queue).toHaveLength(0);
		});

		it('starts playback when queue is empty', () => {
			const items = makeItems(3);
			playerStore.addMultipleToQueue(items);
			expect(playerStore.queue).toHaveLength(3);
			expect(playerStore.isPlayerVisible).toBe(true);
		});

		it('appends all items to existing queue', () => {
			playerStore.playQueue(makeItems(2));
			playerStore.addMultipleToQueue(makeItems(3));
			expect(playerStore.queue).toHaveLength(5);
		});
	});

	describe('playMultipleNext', () => {
		it('does nothing for empty array', () => {
			playerStore.playMultipleNext([]);
			expect(playerStore.queue).toHaveLength(0);
		});

		it('starts playback when queue is empty', () => {
			const items = makeItems(2);
			playerStore.playMultipleNext(items);
			expect(playerStore.queue).toHaveLength(2);
			expect(playerStore.isPlayerVisible).toBe(true);
		});

		it('inserts all items after current index', () => {
			playerStore.playQueue(makeItems(3));
			const newItems = makeItems(2).map((item, i) => ({ ...item, trackName: `Inserted ${i}` }));
			playerStore.playMultipleNext(newItems);
			expect(playerStore.queue).toHaveLength(5);
			expect(playerStore.queue[1].trackName).toBe('Inserted 0');
			expect(playerStore.queue[2].trackName).toBe('Inserted 1');
		});
	});

	describe('removeFromQueue', () => {
		it('ignores out-of-bounds index', () => {
			playerStore.playQueue(makeItems(2));
			playerStore.removeFromQueue(-1);
			expect(playerStore.queue).toHaveLength(2);
			playerStore.removeFromQueue(10);
			expect(playerStore.queue).toHaveLength(2);
		});

		it('stops playback when removing only item', () => {
			playerStore.addToQueue(makeItem());
			playerStore.removeFromQueue(0);
			expect(playerStore.queue).toHaveLength(0);
			expect(playerStore.isPlayerVisible).toBe(false);
		});

		it('decrements currentIndex when removing item before current', () => {
			playerStore.playQueue(makeItems(3), 2);
			const prevIndex = playerStore.currentIndex;
			playerStore.removeFromQueue(0);
			expect(playerStore.currentIndex).toBe(prevIndex - 1);
			expect(playerStore.queue).toHaveLength(2);
		});

		it('updates shuffle order after removal', () => {
			playerStore.playQueue(makeItems(4), 0, true);
			const initialLen = playerStore.shuffleOrder.length;
			playerStore.removeFromQueue(3);
			expect(playerStore.shuffleOrder).toHaveLength(initialLen - 1);
		});
	});

	describe('reorderQueue', () => {
		it('does nothing for same index', () => {
			playerStore.playQueue(makeItems(3));
			const before = [...playerStore.queue];
			playerStore.reorderQueue(0, 0);
			expect(playerStore.queue.map((i) => i.trackSourceId)).toEqual(before.map((i) => i.trackSourceId));
		});

		it('does nothing for out-of-bounds indices', () => {
			playerStore.playQueue(makeItems(3));
			const before = [...playerStore.queue];
			playerStore.reorderQueue(-1, 2);
			expect(playerStore.queue.map((i) => i.trackSourceId)).toEqual(before.map((i) => i.trackSourceId));
		});

		it('moves an item forward', () => {
			playerStore.playQueue(makeItems(4));
			const moved = playerStore.queue[0].trackSourceId;
			playerStore.reorderQueue(0, 2);
			expect(playerStore.queue[2].trackSourceId).toBe(moved);
		});

		it('moves an item backward', () => {
			playerStore.playQueue(makeItems(4));
			const moved = playerStore.queue[3].trackSourceId;
			playerStore.reorderQueue(3, 1);
			expect(playerStore.queue[1].trackSourceId).toBe(moved);
		});

		it('tracks currentIndex when current item is moved', () => {
			playerStore.playQueue(makeItems(4));
			expect(playerStore.currentIndex).toBe(0);
			playerStore.reorderQueue(0, 3);
			expect(playerStore.currentIndex).toBe(3);
		});

		it('adjusts currentIndex when item moves across it', () => {
			playerStore.playQueue(makeItems(5), 2);
			expect(playerStore.currentIndex).toBe(2);
			playerStore.reorderQueue(0, 4);
			expect(playerStore.currentIndex).toBe(1);
		});

		it('updates shuffle order after reorder', () => {
			playerStore.playQueue(makeItems(4), 0, true);
			const initialOrder = [...playerStore.shuffleOrder];
			playerStore.reorderQueue(0, 3);
			expect(playerStore.shuffleOrder).toHaveLength(initialOrder.length);
		});
	});

	describe('clearQueue', () => {
		it('keeps current track and removes all upcoming tracks', () => {
			playerStore.playQueue(makeItems(3), 1);
			playerStore.clearQueue();
			expect(playerStore.queue).toHaveLength(1);
			expect(playerStore.queue[0].trackSourceId).toBe('vid-1');
			expect(playerStore.isPlayerVisible).toBe(true);
			expect(playerStore.currentIndex).toBe(0);
			expect(playerStore.upcomingQueueLength).toBe(0);
		});
	});

	describe('upcomingQueueLength', () => {
		it('counts tracks after current index for normal queue', () => {
			playerStore.playQueue(makeItems(3), 0);
			expect(playerStore.upcomingQueueLength).toBe(2);
		});

		it('counts remaining tracks in shuffle order', () => {
			playerStore.playQueue(makeItems(4), 0, true);
			playerStore.jumpToTrack(2);
			const expectedRemaining = Math.max(0, playerStore.shuffleOrder.length - playerStore.shuffleOrder.indexOf(playerStore.currentIndex) - 1);
			expect(playerStore.upcomingQueueLength).toBe(expectedRemaining);
		});
	});

	describe('changeTrackSource', () => {
		it('ignores out-of-bounds index', () => {
			playerStore.playQueue(makeItems(3));
			const before = playerStore.queue[0].sourceType;
			playerStore.changeTrackSource(-1, 'jellyfin');
			expect(playerStore.queue[0].sourceType).toBe(before);
		});

		it('is a no-op on current track with toast', () => {
			playerStore.playQueue(makeItems(3));
			const currentIdx = playerStore.currentIndex;
			const beforeSource = playerStore.queue[currentIdx].sourceType;
			playerStore.changeTrackSource(currentIdx, 'jellyfin');
			expect(playerStore.queue[currentIdx].sourceType).toBe(beforeSource);
			expect(playbackToast.show).toHaveBeenCalled();
		});

		it('updates source on non-current item', () => {
			playerStore.playQueue(makeItems(3));
			playerStore.changeTrackSource(2, 'jellyfin');
			expect(playerStore.queue[2].sourceType).toBe('jellyfin');
		});

		it('updates streamUrl for target source', () => {
			playerStore.playQueue(makeItems(3));
			playerStore.changeTrackSource(1, 'jellyfin');
			expect(playerStore.queue[1].streamUrl).toBe('/api/stream/jellyfin/vid-1?format=aac&bitrate=128000');
		});
	});

	describe('playQueue', () => {
		it('does nothing for empty array', () => {
			playerStore.playQueue([]);
			expect(playerStore.queue).toHaveLength(0);
		});

		it('sets queue and starts playback at specified index', () => {
			const items = makeItems(5);
			playerStore.playQueue(items, 2);
			expect(playerStore.queue).toHaveLength(5);
			expect(playerStore.currentIndex).toBe(2);
			expect(playerStore.isPlayerVisible).toBe(true);
		});

		it('creates shuffle order when shuffle enabled', () => {
			playerStore.playQueue(makeItems(5), 0, true);
			expect(playerStore.shuffleEnabled).toBe(true);
			expect(playerStore.shuffleOrder).toHaveLength(5);
		});

		it('does not create shuffle order when disabled', () => {
			playerStore.playQueue(makeItems(5), 0, false);
			expect(playerStore.shuffleEnabled).toBe(false);
		});
	});

	describe('toggleShuffle', () => {
		it('enables shuffle and creates order', () => {
			playerStore.playQueue(makeItems(4));
			playerStore.toggleShuffle();
			expect(playerStore.shuffleEnabled).toBe(true);
			expect(playerStore.shuffleOrder).toHaveLength(4);
			expect(playerStore.shuffleOrder[0]).toBe(playerStore.currentIndex);
		});

		it('disables shuffle and clears order', () => {
			playerStore.playQueue(makeItems(4), 0, true);
			playerStore.toggleShuffle();
			expect(playerStore.shuffleEnabled).toBe(false);
			expect(playerStore.shuffleOrder).toHaveLength(0);
		});
	});

	describe('jumpToTrack', () => {
		it('loads the track at the specified index', () => {
			playerStore.playQueue(makeItems(3));
			playerStore.jumpToTrack(2);
			expect(playerStore.currentIndex).toBe(2);
		});

		it('ignores out-of-bounds index', () => {
			playerStore.playQueue(makeItems(3));
			const before = playerStore.currentIndex;
			playerStore.jumpToTrack(10);
			expect(playerStore.currentIndex).toBe(before);
		});
	});
});
