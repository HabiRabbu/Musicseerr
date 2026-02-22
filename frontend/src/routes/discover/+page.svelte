<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import HomeSection from '$lib/components/HomeSection.svelte';
	import GenreGrid from '$lib/components/GenreGrid.svelte';
	import DiscoverQueueCard from '$lib/components/DiscoverQueueCard.svelte';
	import DiscoverQueueModal from '$lib/components/DiscoverQueueModal.svelte';
	import ServicePromptCard from '$lib/components/ServicePromptCard.svelte';
	import type { DiscoverResponse } from '$lib/types';
	import CarouselSkeleton from '$lib/components/CarouselSkeleton.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { getDiscoverCachedData, setDiscoverCachedData, isDiscoverCacheStale } from '$lib/utils/discoverCache';
	import { formatLastUpdated } from '$lib/utils/formatting';
	import { Compass } from 'lucide-svelte';

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
			// Guard: when the backend is still computing async recommendations,
			// all personalized sections are null/empty. Don't use a cached response
			// that has no content — it represents a transient "still computing" state.
			const cachedHasContent =
				(cached.data.because_you_listen_to?.length ?? 0) > 0 ||
				cached.data.fresh_releases != null ||
				cached.data.missing_essentials != null ||
				cached.data.globally_trending != null;
			if (cachedHasContent) {
				discoverData = cached.data;
				lastUpdated = new Date(cached.timestamp);
				loading = false;
				if (isDiscoverCacheStale(cached.timestamp)) {
					refreshInBackground();
				}
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
				// Only cache responses that have actual content — empty responses
				// indicate the backend hasn't finished async computation yet
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
				// Only update cached data if the response has content — empty means
				// the backend is still computing and we should keep showing stale data
				const hasContent =
					(data.because_you_listen_to?.length ?? 0) > 0 ||
					data.fresh_releases != null ||
					data.missing_essentials != null ||
					data.globally_trending != null;
				if (hasContent) {
					discoverData = data;
					lastUpdated = new Date();
					setDiscoverCachedData(data);
				}
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
	<PageHeader
		subtitle="Personalized music recommendations based on your listening habits."
		gradientClass="bg-gradient-to-br from-info/30 via-primary/20 to-secondary/10"
		{loading}
		{refreshing}
		{isUpdating}
		{lastUpdated}
		refreshLabel="Refresh"
		onRefresh={handleRefresh}
	>
		{#snippet title()}
			<Compass class="inline h-8 w-8 sm:h-10 sm:w-10 lg:h-12 lg:w-12 mr-2 align-text-bottom" />
			Discover
		{/snippet}
	</PageHeader>

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
						<CarouselSkeleton />
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
		background: linear-gradient(
			135deg,
			rgb(var(--brand-discover) / 0.06) 0%,
			rgb(var(--brand-discover) / 0.02) 100%
		);
		border: 1px solid rgb(var(--brand-discover) / 0.12);
	}

	.listen-count-tooltip {
		font-size: 0.75rem;
		color: color-mix(in srgb, var(--color-base-content) 50%, transparent);
		margin-left: 0.5rem;
	}
</style>
