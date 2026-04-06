import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { API } from '$lib/constants';
import { musicSourceStore, type MusicSource } from '$lib/stores/musicSource';
import { getCacheTTLs } from '$lib/stores/cacheTtl';
import { api, ApiError } from '$lib/api/client';

export type QueueBuildStatus = 'idle' | 'building' | 'ready' | 'error' | 'unknown';

interface DiscoverQueueStatusState {
	status: QueueBuildStatus;
	source: string;
	queueId?: string;
	itemCount?: number;
	error?: string;
	lastChecked: number;
}

type QueueStatusPayload = {
	status: QueueBuildStatus;
	source: string;
	queue_id?: string;
	item_count?: number;
	error?: string;
};

const INITIAL: DiscoverQueueStatusState = {
	status: 'unknown',
	source: 'listenbrainz',
	lastChecked: 0
};

function createDiscoverQueueStatusStore() {
	const { subscribe, set, update } = writable<DiscoverQueueStatusState>({ ...INITIAL });

	let pollTimer: ReturnType<typeof setInterval> | null = null;
	let isPolling = false;

	function getPollingInterval(): number {
		return getCacheTTLs().discoverQueuePollingInterval;
	}

	function isAutoGenerateEnabled(): boolean {
		return getCacheTTLs().discoverQueueAutoGenerate;
	}

	function applyStatusData(data: QueueStatusPayload): void {
		set({
			status: data.status,
			source: data.source,
			queueId: data.queue_id,
			itemCount: data.item_count,
			error: data.error,
			lastChecked: Date.now()
		});
	}

	function resolveSource(source?: MusicSource): MusicSource {
		return source ?? musicSourceStore.getPageSource('discover');
	}

	async function fetchStatus(source?: MusicSource): Promise<QueueStatusPayload | null> {
		if (!browser) return null;
		try {
			const activeSource = resolveSource(source);
			const data = await api.global.get<QueueStatusPayload>(API.discoverQueueStatus(activeSource));
			applyStatusData(data);
			return data;
		} catch {
			return null;
		}
	}

	async function triggerGenerate(force = false, source?: MusicSource): Promise<void> {
		if (!browser) return;
		try {
			const activeSource = resolveSource(source);
			update((s) => ({ ...s, status: 'building', source: activeSource }));
			const data = await api.global.post<QueueStatusPayload>(API.discoverQueueGenerate(), {
				source: activeSource,
				force
			});
			applyStatusData(data);
			if (data.status === 'building') {
				startPolling(activeSource);
			}
		} catch (e) {
			if (e instanceof ApiError) {
				update((s) => ({
					...s,
					status: 'error',
					error: `Server responded with ${e.status}`
				}));
			} else {
				update((s) => ({ ...s, status: 'error', error: 'Failed to trigger generation' }));
			}
		}
	}

	function startPolling(source?: MusicSource): void {
		if (pollTimer || !browser) return;
		isPolling = true;
		const interval = getPollingInterval();
		pollTimer = setInterval(async () => {
			const result = await fetchStatus(source);
			if (result && result.status !== 'building') {
				stopPolling();
			}
		}, interval);
	}

	function stopPolling(): void {
		if (pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
		isPolling = false;
	}

	async function init(source?: MusicSource): Promise<void> {
		if (!browser) return;
		const activeSource = resolveSource(source);
		const result = await fetchStatus(activeSource);
		if (!result) return;

		if (result.status === 'building') {
			startPolling(activeSource);
		} else if (result.status === 'idle' && isAutoGenerateEnabled()) {
			await triggerGenerate(false, activeSource);
		}
	}

	function reset(): void {
		stopPolling();
		set({ ...INITIAL });
	}

	function markConsumed(): void {
		update((s) => ({ ...s, status: 'idle', queueId: undefined, itemCount: undefined }));
	}

	return {
		subscribe,
		fetchStatus,
		triggerGenerate,
		startPolling,
		stopPolling,
		init,
		reset,
		markConsumed,
		get isPolling() {
			return isPolling;
		}
	};
}

export const discoverQueueStatusStore = createDiscoverQueueStatusStore();
