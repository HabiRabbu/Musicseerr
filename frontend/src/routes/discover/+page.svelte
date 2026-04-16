<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import HomeSection from '$lib/components/HomeSection.svelte';
	import GenreGrid from '$lib/components/GenreGrid.svelte';
	import DiscoverQueueCard from '$lib/components/DiscoverQueueCard.svelte';
	import DiscoverQueueModal from '$lib/components/DiscoverQueueModal.svelte';
	import WeeklyExploration from '$lib/components/WeeklyExploration.svelte';
	import ServicePromptCard from '$lib/components/ServicePromptCard.svelte';
	import DiscoverArtistHero from '$lib/components/DiscoverArtistHero.svelte';
	import SectionDivider from '$lib/components/SectionDivider.svelte';
	import CarouselSkeleton from '$lib/components/CarouselSkeleton.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { removeAllQueueCachedData } from '$lib/utils/discoverQueueCache';
	import { isDismissed } from '$lib/utils/dismissedPrompts';
	import { type MusicSource } from '$lib/stores/musicSource';
	import { discoverQueueStatusStore } from '$lib/stores/discoverQueueStatus';
	import { Compass, CircleAlert, Sparkles, Music, BarChart3 } from 'lucide-svelte';
	import { PAGE_SOURCE_KEYS } from '$lib/constants';
	import type { PageProps } from './$types';
	import { PersistedState } from 'runed';
	import { getDiscoverQuery } from '$lib/queries/discover/DiscoverQueries.svelte';
	import SimpleSourceSwitcher from '$lib/components/SimpleSourceSwitcher.svelte';
	import { createDiscoverRefreshMutation } from '$lib/queries/discover/DiscoverMutations.svelte';

	const { data }: PageProps = $props();

	// svelte-ignore state_referenced_locally
	const activeSource = new PersistedState<MusicSource>(
		PAGE_SOURCE_KEYS['discover'],
		data.primarySource
	);

	const discoverQuery = getDiscoverQuery(() => activeSource.current);
	const discoverData = $derived(discoverQuery.data);

	const discoverRefreshMutation = createDiscoverRefreshMutation();

	const loading = $derived(discoverQuery.isLoading);
	let isUpdating = $derived(discoverQuery.isRefetching);
	const lastUpdated = $derived(
		discoverQuery.dataUpdatedAt ? new Date(discoverQuery.dataUpdatedAt) : null
	);
	let queueModalOpen = $state(false);

	function cleanup() {
		discoverQueueStatusStore.stopPolling();
	}

	onMount(() => {
		discoverQueueStatusStore.init(activeSource.current);
	});
	onDestroy(cleanup);
	beforeNavigate(cleanup);

	function handleRefresh() {
		discoverRefreshMutation.mutate();
	}

	function handleSourceChange(source: MusicSource) {
		activeSource.current = source;
		removeAllQueueCachedData();
		discoverQueueStatusStore.reset();
		discoverQueueStatusStore.init(source);
	}

	let hasContent = $derived(
		(discoverData?.because_you_listen_to?.length ?? 0) > 0 ||
			discoverData?.fresh_releases != null ||
			discoverData?.missing_essentials != null ||
			discoverData?.rediscover != null ||
			discoverData?.artists_you_might_like != null ||
			discoverData?.popular_in_your_genres != null ||
			discoverData?.globally_trending != null ||
			discoverData?.lastfm_weekly_artist_chart != null ||
			discoverData?.lastfm_weekly_album_chart != null ||
			discoverData?.lastfm_recent_scrobbles != null ||
			(discoverData?.genre_list?.items?.length ?? 0) > 0
	);
	let servicePrompts = $derived(
		(discoverData?.service_prompts ?? []).filter((p) => !isDismissed(p.service))
	);

	let hasCuratedGroup = $derived(
		(discoverData?.because_you_listen_to?.length ?? 0) > 0 ||
			discoverData?.discover_queue_enabled ||
			(activeSource.current === 'listenbrainz' &&
				discoverData?.weekly_exploration &&
				discoverData.weekly_exploration.tracks.length > 0)
	);

	let hasExploreGroup = $derived(
		(discoverData?.fresh_releases?.items?.length ?? 0) > 0 ||
			(discoverData?.missing_essentials?.items?.length ?? 0) > 0 ||
			(discoverData?.rediscover?.items?.length ?? 0) > 0 ||
			(discoverData?.artists_you_might_like?.items?.length ?? 0) > 0 ||
			(discoverData?.popular_in_your_genres?.items?.length ?? 0) > 0
	);

	let hasChartsGroup = $derived(
		(discoverData?.globally_trending?.items?.length ?? 0) > 0 ||
			(discoverData?.lastfm_recent_scrobbles?.items?.length ?? 0) > 0 ||
			(discoverData?.lastfm_weekly_artist_chart?.items?.length ?? 0) > 0 ||
			(discoverData?.lastfm_weekly_album_chart?.items?.length ?? 0) > 0 ||
			(discoverData?.genre_list?.items?.length ?? 0) > 0
	);

	function handlePromptDismiss(_service: string) {
		servicePrompts = (discoverData?.service_prompts ?? []).filter((p) => !isDismissed(p.service));
	}
</script>

<svelte:head>
	<title>Discover - Musicseerr</title>
</svelte:head>

<div class="min-h-[calc(100vh-200px)]">
	<PageHeader
		subtitle="Personalized music recommendations based on your listening habits."
		gradientClass="bg-gradient-to-br from-info/30 via-primary/20 to-secondary/10"
		{loading}
		refreshing={isUpdating}
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

	<div class="flex justify-end px-4 -mt-4 mb-4 sm:px-6 lg:px-8">
		<SimpleSourceSwitcher
			currentSource={activeSource.current}
			onSourceChange={handleSourceChange}
		/>
	</div>

	{#if discoverQuery.error && !discoverData}
		<div class="mt-16 flex flex-col items-center justify-center px-4">
			<CircleAlert class="mb-4 h-10 w-10 text-base-content/50" />
			<p class="text-base-content/70">
				{discoverQuery.error.message ?? 'Failed to load Discover data'}
			</p>
			<button class="btn btn-primary mt-4" onclick={() => discoverQuery.refetch()}>Try Again</button
			>
		</div>
	{:else}
		<div class="px-4 sm:px-6 lg:px-8">
			{#if servicePrompts.length > 0}
				<div class="space-y-3 mb-6">
					{#each servicePrompts as prompt, i (`service-prompt-${prompt.service}-${i}`)}
						<ServicePromptCard {prompt} ondismiss={handlePromptDismiss} />
					{/each}
				</div>
			{/if}

			{#if loading && !discoverData}
				<div class="space-y-8">
					{#each Array(3) as _, i (`loading-section-${i}`)}
						<section>
							<div class="skeleton skeleton-shimmer mb-4 h-6 w-48"></div>
							<CarouselSkeleton />
						</section>
					{/each}
				</div>
			{:else if discoverData}
				<div class="space-y-10 sm:space-y-12">
					{#if hasCuratedGroup}
						<div>
							<SectionDivider label="Curated For You">
								{#snippet icon()}<Sparkles class="w-3.5 h-3.5" />{/snippet}
							</SectionDivider>

							<div class="discover-section-enter space-y-5 sm:space-y-6">
								{#if discoverData.because_you_listen_to.length > 0}
									{#each discoverData.because_you_listen_to as entry (entry.seed_artist_mbid || entry.seed_artist)}
										<div>
											<DiscoverArtistHero {entry} />
										</div>
									{/each}
								{/if}

								<div>
									<DiscoverQueueCard
										source={activeSource.current}
										onLaunch={() => (queueModalOpen = true)}
									/>
								</div>

								{#if activeSource.current === 'listenbrainz' && discoverData.weekly_exploration && discoverData.weekly_exploration.tracks.length > 0}
									<div>
										<WeeklyExploration
											section={discoverData.weekly_exploration}
											ytConfigured={discoverData.integration_status?.youtube ?? false}
										/>
									</div>
								{/if}
							</div>
						</div>
					{:else}
						<div>
							<DiscoverQueueCard
								source={activeSource.current}
								onLaunch={() => (queueModalOpen = true)}
							/>
						</div>
					{/if}

					{#if hasExploreGroup}
						<div>
							<SectionDivider label="Explore New Music">
								{#snippet icon()}<Music class="w-3.5 h-3.5" />{/snippet}
							</SectionDivider>

							<div class="discover-section-enter space-y-2">
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
							</div>
						</div>
					{/if}

					{#if hasChartsGroup}
						<div>
							<SectionDivider label="Charts & Activity">
								{#snippet icon()}
									<BarChart3 class="w-3.5 h-3.5" />
								{/snippet}
							</SectionDivider>

							<div class="discover-section-enter space-y-2">
								{#if discoverData.globally_trending && discoverData.globally_trending.items.length > 0}
									<HomeSection section={discoverData.globally_trending} />
								{/if}

								{#if discoverData.lastfm_recent_scrobbles && discoverData.lastfm_recent_scrobbles.items.length > 0}
									<HomeSection section={discoverData.lastfm_recent_scrobbles} />
								{/if}

								{#if discoverData.lastfm_weekly_artist_chart && discoverData.lastfm_weekly_artist_chart.items.length > 0}
									<HomeSection section={discoverData.lastfm_weekly_artist_chart} />
								{/if}

								{#if discoverData.genre_list && discoverData.genre_list.items.length > 0}
									<div class="mt-4 mb-4">
										<GenreGrid
											title={discoverData.genre_list.title}
											genres={discoverData.genre_list.items}
											genreArtists={discoverData.genre_artists}
											genreArtistImages={discoverData.genre_artist_images}
										/>
									</div>
								{/if}

								{#if discoverData.lastfm_weekly_album_chart && discoverData.lastfm_weekly_album_chart.items.length > 0}
									<HomeSection section={discoverData.lastfm_weekly_album_chart} />
								{/if}
							</div>
						</div>
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
								<Compass class="mb-4 h-12 w-12 sm:mb-6 sm:h-14 sm:w-14 text-base-content/50" />
								<h2 class="mb-2 text-center text-xl font-bold sm:text-2xl">
									Building Recommendations
								</h2>
								<p class="mb-6 max-w-md px-4 text-center text-sm text-base-content/70 sm:text-base">
									Your personalized recommendations are being prepared. Try refreshing in a moment.
								</p>
								<button
									class="btn btn-primary"
									onclick={() => discoverQuery.refetch()}
									disabled={isUpdating}
								>
									{#if isUpdating}
										<span class="loading loading-spinner loading-sm"></span>
									{/if}
									Refresh Recommendations
								</button>
							</div>
						{/if}
					{:else if !hasContent && servicePrompts.length > 0}
						<div class="flex flex-col items-center justify-center py-12 sm:py-16">
							<Compass class="mb-4 h-12 w-12 sm:mb-6 sm:h-14 sm:w-14 text-base-content/50" />
							<h2 class="mb-2 text-center text-xl font-bold sm:text-2xl">
								Nothing to Discover Yet
							</h2>
							<p class="mb-6 max-w-md px-4 text-center text-sm text-base-content/70 sm:text-base">
								Connect your music services to get personalized recommendations. The more services
								you connect, the better your recommendations will be.
							</p>
							<a href="/settings" class="btn btn-primary">Connect Services</a>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>

<DiscoverQueueModal bind:open={queueModalOpen} source={activeSource.current} />
