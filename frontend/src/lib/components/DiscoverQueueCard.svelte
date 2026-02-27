<script lang="ts">
	import { Music, Play, Loader2, RefreshCw } from 'lucide-svelte';
	import { getQueueCachedData, subscribeQueueCacheChanges } from '$lib/utils/discoverQueueCache';
	import type { MusicSource } from '$lib/stores/musicSource';
	import {
		discoverQueueStatusStore,
		type QueueBuildStatus,
	} from '$lib/stores/discoverQueueStatus';

	let { onLaunch, source }: { onLaunch: () => void; source: MusicSource } = $props();

	let hasCachedQueue = $state(false);
	let bgStatus = $state<QueueBuildStatus>('unknown');

	function recheckCachedQueue() {
		const cached = getQueueCachedData(source);
		hasCachedQueue = (cached?.data?.items?.length ?? 0) > 0;
	}

	$effect(() => {
		source;
		recheckCachedQueue();
	});

	$effect(() => {
		const unsubStatus = discoverQueueStatusStore.subscribe((s) => {
			bgStatus = s.status;
			recheckCachedQueue();
		});
		return unsubStatus;
	});

	$effect(() => {
		const unsubscribeCache = subscribeQueueCacheChanges((changedSource) => {
			if (!changedSource || changedSource === source) {
				recheckCachedQueue();
			}
		});
		return unsubscribeCache;
	});

	let isBuilding = $derived(bgStatus === 'building');
	let isReady = $derived(bgStatus === 'ready' && !hasCachedQueue);
	let isError = $derived(bgStatus === 'error');

	function handleRetry() {
		discoverQueueStatusStore.triggerGenerate(true, source);
	}
</script>

<div
	class="card card-border bg-gradient-to-br from-primary/10 via-secondary/8 to-accent/6 w-full shadow-sm"
>
	<div class="card-body items-center gap-5 py-12 text-center">
		<div class="text-primary opacity-70">
			{#if isBuilding && !hasCachedQueue}
				<Loader2 class="h-10 w-10 animate-spin" strokeWidth={1.5} />
			{:else}
				<Music class="h-10 w-10" strokeWidth={1.5} />
			{/if}
		</div>
		<div class="flex flex-col gap-1">
			<h3 class="text-xl font-bold text-base-content">Discover Queue</h3>
			{#if hasCachedQueue}
				<p class="text-sm text-base-content/60">You have a queue in progress</p>
			{:else if isBuilding}
				<p class="text-sm text-base-content/60">Building your personalised queue…</p>
			{:else if isError}
				<p class="text-sm text-error/80">Something went wrong building your queue</p>
			{:else if isReady}
				<p class="text-sm text-success/80">Your queue is ready!</p>
			{:else}
				<p class="text-sm text-base-content/60">Find new music tailored to your taste</p>
			{/if}
		</div>
		<div class="flex gap-2">
			{#if hasCachedQueue}
				<button class="btn btn-primary btn-lg" onclick={onLaunch}>
					<Play class="h-5 w-5" strokeWidth={2} />
					Resume Discover Queue
				</button>
			{:else if isBuilding}
				<button class="btn btn-primary btn-lg btn-disabled" disabled>
					<Loader2 class="h-5 w-5 animate-spin" strokeWidth={2} />
					Building…
				</button>
			{:else if isError}
				<button class="btn btn-error btn-outline btn-lg" onclick={handleRetry}>
					<RefreshCw class="h-5 w-5" strokeWidth={2} />
					Retry
				</button>
				<button class="btn btn-primary btn-lg" onclick={onLaunch}>
					<Play class="h-5 w-5" strokeWidth={2} />
					Launch Anyway
				</button>
			{:else}
				<button class="btn btn-primary btn-lg" onclick={onLaunch}>
					<Play class="h-5 w-5" strokeWidth={2} />
					Launch Discover Queue
				</button>
			{/if}
		</div>
	</div>
</div>
