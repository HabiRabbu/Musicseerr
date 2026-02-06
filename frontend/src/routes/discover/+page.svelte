<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import HomeSection from '$lib/components/HomeSection.svelte';
	import GenreGrid from '$lib/components/GenreGrid.svelte';
	import DiscoverQueueCard from '$lib/components/DiscoverQueueCard.svelte';
	import DiscoverQueueModal from '$lib/components/DiscoverQueueModal.svelte';
	import ServicePromptCard from '$lib/components/ServicePromptCard.svelte';
	import type { DiscoverResponse } from '$lib/types';
	import {
		getDiscoverCachedData,
		setDiscoverCachedData,
		isDiscoverCacheStale
	} from '$lib/utils/discoverCache';
	import { formatLastUpdated } from '$lib/utils/homeCache';

	let discoverData: DiscoverResponse | null = null;
	let loading = true;
	let refreshing = false;
	let isUpdating = false;
	let error = '';
	let lastUpdated: Date | null = null;
	let abortController: AbortController | null = null;
	let queueModalOpen = false;

	async function loadDiscoverData(forceRefresh = false) {
		const cached = getDiscoverCachedData();
		if (cached && !forceRefresh) {
			const cachedHasContent =
				(cached.data.because_you_listen_to?.length ?? 0) > 0 ||
				cached.data.fresh_releases != null ||
				cached.data.missing_essentials != null ||
				cached.data.globally_trending != null;
			if (cachedHasContent) {
				discoverData = cached.data;
				lastUpdated = new Date(cached.timestamp);
				loading = false;
				refreshInBackground();
				return;
			}
		}

		if (abortController) abortController.abort();
		abortController = new AbortController();

		if (!discoverData) {
			loading = true;
		} else {
			refreshing = true;
		}
		error = '';

		try {
			const response = await fetch('/api/discover', { signal: abortController.signal });
			if (response.ok) {
				const data: DiscoverResponse = await response.json();
				discoverData = data;
				lastUpdated = new Date();
				const dataHasContent =
					(data.because_you_listen_to?.length ?? 0) > 0 ||
					data.fresh_releases != null ||
					data.missing_essentials != null ||
					data.globally_trending != null;
				if (dataHasContent) {
					setDiscoverCachedData(data);
				}
				if (!dataHasContent && data.refreshing) {
					pollForReady();
				}
			} else if (!discoverData) {
				error = 'Failed to load discover data';
			}
		} catch (e) {
			if (e instanceof Error && e.name === 'AbortError') return;
			if (!discoverData) error = 'Failed to load discover data';
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	async function refreshInBackground() {
		if (refreshing) return;
		if (abortController) abortController.abort();
		abortController = new AbortController();
		refreshing = true;
		isUpdating = true;

		try {
			const response = await fetch('/api/discover', { signal: abortController.signal });
			if (response.ok) {
				const data: DiscoverResponse = await response.json();
				discoverData = data;
				lastUpdated = new Date();
				setDiscoverCachedData(data);
			}
		} catch (e) {
			if (e instanceof Error && e.name === 'AbortError') return;
		} finally {
			refreshing = false;
			isUpdating = false;
		}
	}

	async function pollForReady() {
		isUpdating = true;
		for (let i = 0; i < 15; i++) {
			await new Promise((r) => setTimeout(r, 3000));
			try {
				const res = await fetch('/api/discover');
				if (res.ok) {
					const data: DiscoverResponse = await res.json();
					const ready =
						(data.because_you_listen_to?.length ?? 0) > 0 ||
						data.fresh_releases != null ||
						data.missing_essentials != null ||
						data.globally_trending != null;
					if (ready || !data.refreshing) {
						discoverData = data;
						lastUpdated = new Date();
						if (ready) setDiscoverCachedData(data);
						break;
					}
				}
			} catch {
				break;
			}
		}
		isUpdating = false;
	}

	async function handleRefresh() {
		refreshing = true;
		isUpdating = true;
		try {
			await fetch('/api/discover/refresh', { method: 'POST' });
		} catch {}

		const maxPolls = 30;
		for (let i = 0; i < maxPolls; i++) {
			await new Promise((r) => setTimeout(r, 2000));
			try {
				const res = await fetch('/api/discover');
				if (res.ok) {
					const data: DiscoverResponse = await res.json();
					if (!data.refreshing) {
						discoverData = data;
						lastUpdated = new Date();
						setDiscoverCachedData(data);
						break;
					}
				}
			} catch {
				break;
			}
		}
		refreshing = false;
		isUpdating = false;
	}

	function cleanup() {
		if (abortController) {
			abortController.abort();
			abortController = null;
		}
	}

	onMount(() => loadDiscoverData());
	onDestroy(cleanup);
	beforeNavigate(cleanup);

	$: hasContent =
		(discoverData?.because_you_listen_to?.length ?? 0) > 0 ||
		discoverData?.fresh_releases != null ||
		discoverData?.missing_essentials != null ||
		discoverData?.rediscover != null ||
		discoverData?.artists_you_might_like != null ||
		discoverData?.popular_in_your_genres != null ||
		discoverData?.globally_trending != null;
	$: servicePrompts = discoverData?.service_prompts ?? [];
</script>

<svelte:head>
	<title>Discover - Musicseerr</title>
</svelte:head>

<div class="min-h-[calc(100vh-200px)]">
	<div
		class="relative mb-6 overflow-hidden bg-gradient-to-br from-info/30 via-primary/20 to-secondary/10"
	>
		<div class="absolute inset-0 bg-gradient-to-t from-base-100 to-transparent"></div>
		<div class="relative px-4 py-8 sm:px-6 sm:py-12 lg:px-8">
			<div class="flex items-start justify-between">
				<div>
					<h1 class="mb-2 text-3xl font-bold sm:text-4xl lg:text-5xl">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							stroke-linecap="round"
							stroke-linejoin="round"
							class="inline h-8 w-8 sm:h-10 sm:w-10 lg:h-12 lg:w-12 mr-2 align-text-bottom"
						>
							<circle cx="12" cy="12" r="10"></circle>
							<polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon>
						</svg>
						Discover
					</h1>
					<p class="max-w-xl text-sm text-base-content/70 sm:text-base">
						Personalized music recommendations based on your listening habits.
					</p>
				</div>
				<div class="flex items-center gap-2">
					{#if isUpdating}
						<span class="badge badge-ghost badge-sm gap-1">
							<span class="loading loading-spinner loading-xs"></span>
							Updating...
						</span>
					{:else if lastUpdated && !loading}
						<span class="hidden text-xs text-base-content/50 sm:inline">
							Updated {formatLastUpdated(lastUpdated)}
						</span>
					{/if}
					<button
						class="btn btn-sm btn-primary gap-1"
						on:click={handleRefresh}
						disabled={refreshing || loading}
						title="Refresh Recommendations"
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 20 20"
							fill="currentColor"
							class="h-4 w-4 {refreshing ? 'animate-spin' : ''}"
						>
							<path
								fill-rule="evenodd"
								d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H3.989a.75.75 0 00-.75.75v4.242a.75.75 0 001.5 0v-2.43l.31.31a7 7 0 0011.712-3.138.75.75 0 00-1.449-.39zm1.23-3.723a.75.75 0 00.219-.53V2.929a.75.75 0 00-1.5 0v2.43l-.31-.31A7 7 0 003.239 8.188a.75.75 0 101.448.389A5.5 5.5 0 0113.89 6.11l.311.31h-2.432a.75.75 0 000 1.5h4.243a.75.75 0 00.53-.219z"
								clip-rule="evenodd"
							/>
						</svg>
						<span class="hidden sm:inline">Refresh</span>
					</button>
				</div>
			</div>
		</div>
	</div>

	{#if error && !discoverData}
		<div class="mt-16 flex flex-col items-center justify-center px-4">
			<div class="mb-4 text-4xl">😕</div>
			<p class="text-base-content/70">{error}</p>
			<button class="btn btn-primary mt-4" on:click={() => loadDiscoverData(true)}>Try Again</button
			>
		</div>
	{:else}
		<div class="space-y-6 px-4 sm:space-y-8 sm:px-6 lg:px-8">
			{#if servicePrompts.length > 0}
				<div class="space-y-3">
					{#each servicePrompts as prompt}
						<ServicePromptCard {prompt} />
					{/each}
				</div>
			{/if}

			{#if loading && !discoverData}
				{#each Array(3) as _}
					<section>
						<div class="skeleton mb-4 h-6 w-48"></div>
						<div class="scrollbar-hide flex gap-3 overflow-x-auto pb-2 sm:gap-4">
							{#each Array(6) as _}
								<div class="w-32 flex-shrink-0 sm:w-36 md:w-44">
									<div class="skeleton aspect-square w-full rounded-lg"></div>
									<div class="skeleton mt-2 h-4 w-3/4"></div>
									<div class="skeleton mt-1 h-3 w-1/2"></div>
								</div>
							{/each}
						</div>
					</section>
				{/each}
			{:else if discoverData}
				{#if discoverData.because_you_listen_to.length > 0}
					<div class="section-group-discover -mx-4 px-4 py-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
						{#each discoverData.because_you_listen_to as entry (entry.seed_artist_mbid)}
							<div>
								<HomeSection
									section={{
										...entry.section,
										title: `Because You Listen to ${entry.seed_artist}`
									}}
								/>
								{#if entry.listen_count > 0}
									<p class="listen-count-tooltip mt-1">
										Based on your {entry.listen_count} listens this week
									</p>
								{/if}
							</div>
						{/each}
					</div>
				{/if}

				<DiscoverQueueCard onLaunch={() => (queueModalOpen = true)} />

				{#if discoverData.fresh_releases && discoverData.fresh_releases.items.length > 0}
					<HomeSection section={discoverData.fresh_releases} />
				{/if}

				{#if discoverData.missing_essentials && discoverData.missing_essentials.items.length > 0}
					<HomeSection section={discoverData.missing_essentials} />
				{/if}

				{#if discoverData.rediscover && discoverData.rediscover.items.length > 0}
					<HomeSection section={discoverData.rediscover} />
				{/if}

				{#if discoverData.artists_you_might_like && discoverData.artists_you_might_like.items.length > 0}
					<HomeSection section={discoverData.artists_you_might_like} />
				{/if}

				{#if discoverData.popular_in_your_genres && discoverData.popular_in_your_genres.items.length > 0}
					<HomeSection section={discoverData.popular_in_your_genres} />
				{/if}

				{#if discoverData.genre_list && discoverData.genre_list.items.length > 0}
					<GenreGrid title={discoverData.genre_list.title} genres={discoverData.genre_list.items} />
				{/if}

				{#if discoverData.globally_trending && discoverData.globally_trending.items.length > 0}
					<HomeSection section={discoverData.globally_trending} />
				{/if}

				{#if !hasContent && servicePrompts.length === 0}
					{#if discoverData.refreshing || isUpdating}
						<div class="flex flex-col items-center justify-center py-12 sm:py-16">
							<span class="loading loading-spinner loading-lg text-primary mb-4"></span>
							<h2 class="mb-2 text-center text-xl font-bold sm:text-2xl">
								Building Your Recommendations
							</h2>
							<p class="max-w-md px-4 text-center text-sm text-base-content/70 sm:text-base">
								We're analyzing your listening history and building personalized recommendations.
								This may take a moment on first load.
							</p>
						</div>
					{:else}
						<div class="flex flex-col items-center justify-center py-12 sm:py-16">
							<div class="mb-4 text-5xl sm:mb-6 sm:text-6xl">🧭</div>
							<h2 class="mb-2 text-center text-xl font-bold sm:text-2xl">
								Building Recommendations
							</h2>
							<p class="mb-6 max-w-md px-4 text-center text-sm text-base-content/70 sm:text-base">
								Your personalized recommendations are being prepared. Try refreshing in a moment.
							</p>
							<button class="btn btn-primary" on:click={handleRefresh} disabled={refreshing}>
								{#if refreshing}
									<span class="loading loading-spinner loading-sm"></span>
								{/if}
								Refresh Recommendations
							</button>
						</div>
					{/if}
				{:else if !hasContent && servicePrompts.length > 0}
					<div class="flex flex-col items-center justify-center py-12 sm:py-16">
						<div class="mb-4 text-5xl sm:mb-6 sm:text-6xl">🧭</div>
						<h2 class="mb-2 text-center text-xl font-bold sm:text-2xl">Nothing to Discover Yet</h2>
						<p class="mb-6 max-w-md px-4 text-center text-sm text-base-content/70 sm:text-base">
							Connect your music services to get personalized recommendations. The more services you
							connect, the better your recommendations will be.
						</p>
						<a href="/settings" class="btn btn-primary">Connect Services</a>
					</div>
				{/if}
			{/if}
		</div>
	{/if}
</div>

<DiscoverQueueModal bind:open={queueModalOpen} />

<style>
	.section-group-discover {
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		background: linear-gradient(135deg, rgba(56, 189, 248, 0.06) 0%, rgba(59, 130, 246, 0.02) 100%);
		border: 1px solid rgba(56, 189, 248, 0.12);
	}

	.listen-count-tooltip {
		font-size: 0.75rem;
		color: oklch(var(--bc) / 0.5);
		margin-left: 0.5rem;
	}
</style>
