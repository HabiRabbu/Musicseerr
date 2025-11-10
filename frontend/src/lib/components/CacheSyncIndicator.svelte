<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	type SyncStatus = {
		is_syncing: boolean;
		phase: string | null;
		total_items: number;
		processed_items: number;
		progress_percent: number;
		current_item: string | null;
	};

	let status: SyncStatus = {
		is_syncing: false,
		phase: null,
		total_items: 0,
		processed_items: 0,
		progress_percent: 0,
		current_item: null
	};

	let interval: ReturnType<typeof setInterval> | null = null;
	let pollInterval = 5000; // Start with 5 second polling

	async function checkStatus() {
		try {
			const res = await fetch('/api/cache/sync/status');
			if (res.ok) {
				const newStatus = await res.json();
				const wasSync = status.is_syncing;
				status = newStatus;
				
				if (interval) {
					clearInterval(interval);
					interval = null;
				}
				
				if (newStatus.is_syncing) {
					pollInterval = 2000;
					interval = setInterval(checkStatus, pollInterval);
				} else {
					if (!wasSync && pollInterval < 30000) {
						pollInterval = Math.min(pollInterval * 1.5, 30000);
					}
					interval = setInterval(checkStatus, pollInterval);
				}
			}
		} catch (error) {
			console.error('Failed to check sync status:', error);
		}
	}

	onMount(() => {
		checkStatus();
	});

	onDestroy(() => {
		if (interval) {
			clearInterval(interval);
			interval = null;
		}
	});

	$: phaseLabel = status.phase === 'artists' ? 'Artist Images' : status.phase === 'albums' ? 'Album Data' : status.phase === 'warming' ? 'Warming Cache' : 'Library';
</script>

{#if status.is_syncing}
	<div class="fixed top-20 right-4 z-40 animate-fade-in">
		<div class="alert alert-info shadow-lg max-w-md">
			<div class="flex-1">
				<svg class="w-6 h-6 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
				</svg>
				<div class="ml-3 flex-1 min-w-0">
					<h3 class="font-bold">Refreshing {phaseLabel}...</h3>
					<div class="text-sm opacity-70">
						{status.processed_items} / {status.total_items} items ({status.progress_percent}%)
					</div>
					{#if status.current_item}
						<div class="text-xs mt-1 truncate max-w-xs opacity-60">
							{status.current_item}
						</div>
					{/if}
					<progress class="progress progress-primary w-full mt-2" value={status.progress_percent} max="100"></progress>
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
