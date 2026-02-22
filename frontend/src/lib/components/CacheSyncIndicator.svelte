<script lang="ts">
	import { Loader2, TriangleAlert, Check } from 'lucide-svelte';
	import { onMount, onDestroy } from 'svelte';

	type SyncStatus = {
		is_syncing: boolean;
		phase: string | null;
		total_items: number;
		processed_items: number;
		progress_percent: number;
		current_item: string | null;
		error_message: string | null;
		total_artists: number;
		processed_artists: number;
		total_albums: number;
		processed_albums: number;
	};

	let status: SyncStatus = $state({
		is_syncing: false,
		phase: null,
		total_items: 0,
		processed_items: 0,
		progress_percent: 0,
		current_item: null,
		error_message: null,
		total_artists: 0,
		processed_artists: 0,
		total_albums: 0,
		processed_albums: 0
	});

	let eventSource: EventSource | null = null;
	let pollInterval: ReturnType<typeof setInterval> | null = null;
	let showIndicator = $state(false);
	let hideTimeout: ReturnType<typeof setTimeout> | null = null;
	let connectionMode: 'sse' | 'polling' = $state('sse');
	let reconnectAttempts = 0;
	const MAX_RECONNECT_ATTEMPTS = 5;

	function connectSSE() {
		if (eventSource) {
			eventSource.close();
		}

		eventSource = new EventSource('/api/cache/sync/stream');

		eventSource.onopen = () => {
			connectionMode = 'sse';
			reconnectAttempts = 0;
			if (pollInterval) {
				clearInterval(pollInterval);
				pollInterval = null;
			}
		};

		eventSource.onmessage = (event) => {
			try {
				const data = JSON.parse(event.data);
				status = data;
				handleStatusUpdate(data);
			} catch {
			}
		};

		eventSource.onerror = () => {
			eventSource?.close();
			eventSource = null;
			reconnectAttempts++;

			if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
				const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
				setTimeout(connectSSE, delay);
			} else {
				connectionMode = 'polling';
				startPolling();
			}
		};
	}

	function handleStatusUpdate(newStatus: SyncStatus) {
		if (newStatus.is_syncing) {
			if (hideTimeout) {
				clearTimeout(hideTimeout);
				hideTimeout = null;
			}
			showIndicator = true;
		} else if (newStatus.error_message) {
			showIndicator = true;
			if (!hideTimeout) {
				hideTimeout = setTimeout(() => {
					showIndicator = false;
					hideTimeout = null;
				}, 5000);
			}
		} else if (showIndicator && !hideTimeout) {
			hideTimeout = setTimeout(() => {
				showIndicator = false;
				hideTimeout = null;
			}, 3000);
		}
	}

	async function checkStatus() {
		try {
			const res = await fetch('/api/cache/sync/status');
			if (res.ok) {
				const newStatus = await res.json();
				status = newStatus;
				handleStatusUpdate(newStatus);
			}
		} catch {
		}
	}

	function startPolling() {
		if (pollInterval) {
			clearInterval(pollInterval);
		}
		checkStatus();
		pollInterval = setInterval(checkStatus, status.is_syncing ? 1500 : 5000);
	}

	function handleSyncTriggered() {
		checkStatus();
	}

	onMount(() => {
		connectSSE();
		window.addEventListener('library-sync-triggered', handleSyncTriggered);
	});

	onDestroy(() => {
		eventSource?.close();
		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
		if (hideTimeout) {
			clearTimeout(hideTimeout);
			hideTimeout = null;
		}
		window.removeEventListener('library-sync-triggered', handleSyncTriggered);
	});

	let phaseLabel = $derived(
		status.phase === 'artists'
			? 'Artist Images'
			: status.phase === 'albums'
				? 'Album Data'
				: status.phase === 'warming'
					? 'Warming Cache'
					: 'Library'
	);

	let alertClass = $derived(
		status.error_message ? 'alert-error' : status.is_syncing ? 'alert-info' : 'alert-success'
	);

	let headerText = $derived(
		status.error_message
			? 'Sync Failed'
			: status.is_syncing
				? `Refreshing ${phaseLabel}...`
				: 'Sync Complete!'
	);
</script>

{#if showIndicator}
	<div class="fixed top-20 right-4 z-40 animate-fade-in">
		<div class="alert shadow-lg max-w-md {alertClass}">
			<div class="flex-1">
				{#if status.is_syncing}
					<Loader2 class="w-6 h-6 animate-spin shrink-0" />
				{:else if status.error_message}
					<TriangleAlert class="w-6 h-6 shrink-0" />
				{:else}
					<Check class="w-6 h-6 shrink-0" />
				{/if}
				<div class="ml-3 flex-1 min-w-0">
					<h3 class="font-bold">{headerText}</h3>
					{#if status.error_message}
						<div class="text-sm opacity-70 truncate max-w-xs">
							{status.error_message}
						</div>
					{:else}
						<div class="text-sm opacity-70">
							{status.processed_items} / {status.total_items} items ({status.progress_percent}%)
						</div>
						{#if status.current_item}
							<div class="text-xs mt-1 truncate max-w-xs opacity-60">
								{status.current_item}
							</div>
						{/if}
						<progress
							class="progress w-full mt-2"
							class:progress-primary={status.is_syncing}
							class:progress-success={!status.is_syncing}
							value={status.progress_percent}
							max="100"
						></progress>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}

<style>
	@keyframes fade-in {
		from {
			opacity: 0;
			transform: translateY(-10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
	.animate-fade-in {
		animation: fade-in 0.3s ease-out;
	}
</style>
