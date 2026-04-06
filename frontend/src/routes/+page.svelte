<script lang="ts">
	import { Shield, Music, CircleAlert, TrendingUp, Sparkles, Library } from 'lucide-svelte';
	import { onMount, onDestroy } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import HomeSection from '$lib/components/HomeSection.svelte';
	import WeeklyExploration from '$lib/components/WeeklyExploration.svelte';
	import ServicePromptCard from '$lib/components/ServicePromptCard.svelte';
	import GenreGrid from '$lib/components/GenreGrid.svelte';
	import SourceSwitcher from '$lib/components/SourceSwitcher.svelte';
	import SectionDivider from '$lib/components/SectionDivider.svelte';
	import type {
		HomeResponse,
		HomeSection as HomeSectionType,
		WeeklyExplorationSection as WeeklyExplorationSectionType
	} from '$lib/types';
	import { integrationStore } from '$lib/stores/integration';
	import { musicSourceStore, type MusicSource } from '$lib/stores/musicSource';
	import CarouselSkeleton from '$lib/components/CarouselSkeleton.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import {
		getHomeCachedData,
		setHomeCachedData,
		isHomeCacheStale,
		getGreeting
	} from '$lib/utils/homeCache';
	import { isAbortError } from '$lib/utils/errorHandling';
	import { api } from '$lib/api/client';
	import { removeQueueCachedData } from '$lib/utils/discoverQueueCache';
	import { isDismissed } from '$lib/utils/dismissedPrompts';

	let homeData = $state<HomeResponse | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let isUpdating = $state(false);
	let error = $state('');
	let lastUpdated = $state<Date | null>(null);
	let abortController: AbortController | null = null;
	let activeSource: MusicSource = 'listenbrainz';

	function resolveHomeSource(source?: MusicSource): MusicSource {
		return source ?? activeSource;
	}

	async function loadHomeData(forceRefresh = false, sourceOverride?: MusicSource) {
		const source = resolveHomeSource(sourceOverride);
		const cached = getHomeCachedData(source);
		if (cached && !forceRefresh) {
			homeData = cached.data;
			lastUpdated = new Date(cached.timestamp);
			loading = false;
			if (isHomeCacheStale(cached.timestamp)) {
				refreshInBackground(source);
			}
			return;
		}

		if (abortController) {
			abortController.abort();
		}
		abortController = new AbortController();

		if (!homeData) {
			loading = true;
		}

		error = '';

		try {
			const data = await api.get<HomeResponse>(
				`/api/v1/home?source=${encodeURIComponent(source)}`,
				{
					signal: abortController.signal
				}
			);
			homeData = data;
			lastUpdated = new Date();
			setHomeCachedData(data, source);
			if (data.integration_status) {
				integrationStore.setStatus(data.integration_status);
			}
		} catch (e) {
			if (isAbortError(e)) {
				return;
			}
			if (!homeData) {
				error = "Couldn't load the home page";
			}
		} finally {
			loading = false;
		}
	}

	async function refreshInBackground(sourceOverride?: MusicSource) {
		if (refreshing) return;

		if (abortController) {
			abortController.abort();
		}
		abortController = new AbortController();
		refreshing = true;
		isUpdating = true;
		const source = resolveHomeSource(sourceOverride);

		try {
			const data = await api.get<HomeResponse>(
				`/api/v1/home?source=${encodeURIComponent(source)}`,
				{
					signal: abortController.signal
				}
			);
			homeData = data;
			lastUpdated = new Date();
			setHomeCachedData(data, source);
			if (data.integration_status) {
				integrationStore.setStatus(data.integration_status);
			}
		} catch (e) {
			if (isAbortError(e)) {
				return;
			}
		} finally {
			refreshing = false;
			isUpdating = false;
		}
	}

	async function handleRefresh() {
		refreshing = true;
		isUpdating = true;
		const minDelay = new Promise((r) => setTimeout(r, 500));
		try {
			await loadHomeData(true, activeSource);
		} finally {
			await minDelay;
			refreshing = false;
			isUpdating = false;
			lastUpdated = new Date();
		}
	}

	function cleanup() {
		if (abortController) {
			abortController.abort();
			abortController = null;
		}
	}

	onMount(() => {
		activeSource = musicSourceStore.getPageSource('home');
		loadHomeData(false, activeSource);

		musicSourceStore.load().then(() => {
			const actualSource = musicSourceStore.getPageSource('home');
			if (actualSource !== activeSource) {
				const dataBefore = homeData;
				loadHomeData(true, actualSource).then(() => {
					if (homeData !== dataBefore) {
						activeSource = actualSource;
					}
				});
			}
		});
	});

	onDestroy(cleanup);
	beforeNavigate(cleanup);

	function handleSourceChange(source: MusicSource) {
		activeSource = source;
		removeQueueCachedData();
		loadHomeData(true, source);
	}

	type PreGenreBlock =
		| { key: string; kind: 'section'; section: HomeSectionType; link?: string }
		| { key: 'weekly_exploration'; kind: 'weekly'; section: WeeklyExplorationSectionType };

	function getPreGenreBlocks(): PreGenreBlock[] {
		if (!homeData) return [];
		const blocks: PreGenreBlock[] = [];
		if (homeData.popular_albums && homeData.popular_albums.items.length > 0) {
			blocks.push({
				key: 'popular_albums',
				kind: 'section',
				section: homeData.popular_albums,
				link: '/popular'
			});
		}
		if (homeData.trending_artists && homeData.trending_artists.items.length > 0) {
			blocks.push({
				key: 'trending_artists',
				kind: 'section',
				section: homeData.trending_artists,
				link: '/trending'
			});
		}
		if (
			activeSource === 'listenbrainz' &&
			homeData.weekly_exploration &&
			homeData.weekly_exploration.tracks.length > 0
		) {
			blocks.push({
				key: 'weekly_exploration',
				kind: 'weekly',
				section: homeData.weekly_exploration
			});
		}
		if (homeData.your_top_albums && homeData.your_top_albums.items.length > 0) {
			blocks.push({
				key: 'your_top_albums',
				kind: 'section',
				section: homeData.your_top_albums,
				link: '/your-top'
			});
		}
		if (homeData.recently_played && homeData.recently_played.items.length > 0) {
			blocks.push({
				key: 'recently_played',
				kind: 'section',
				section: homeData.recently_played
			});
		}
		if (homeData.recently_added && homeData.recently_added.items.length > 0) {
			blocks.push({
				key: 'recently_added',
				kind: 'section',
				section: homeData.recently_added,
				link: '/library/albums'
			});
		}
		return blocks;
	}

	function getPostGenreSections(): { key: string; section: HomeSectionType; link?: string }[] {
		if (!homeData) return [];
		const sections: { key: string; section: HomeSectionType; link?: string }[] = [];
		if (homeData.favorite_artists && homeData.favorite_artists.items.length > 0) {
			sections.push({
				key: 'favorite_artists',
				section: homeData.favorite_artists
			});
		}
		if (homeData.library_artists && homeData.library_artists.items.length > 0) {
			sections.push({
				key: 'library_artists',
				section: homeData.library_artists,
				link: '/library/artists'
			});
		}
		if (homeData.library_albums && homeData.library_albums.items.length > 0) {
			sections.push({
				key: 'library_albums',
				section: homeData.library_albums,
				link: '/library/albums'
			});
		}
		return sections;
	}
	let preGenreBlocks = $derived(homeData ? getPreGenreBlocks() : []);
	let postGenreSections = $derived(homeData ? getPostGenreSections() : []);

	const whatsHotKeys = new Set(['popular_albums', 'trending_artists']);
	let whatsHotBlocks = $derived(preGenreBlocks.filter((b) => whatsHotKeys.has(b.key)));
	let forYouBlocks = $derived(preGenreBlocks.filter((b) => !whatsHotKeys.has(b.key)));
	let hasContent = $derived(
		preGenreBlocks.length > 0 ||
			postGenreSections.length > 0 ||
			(homeData?.genre_list?.items?.length ?? 0) > 0
	);
	let servicePrompts = $derived(homeData?.service_prompts || []);
	let lidarrConfigured = $derived(homeData?.integration_status?.lidarr ?? true);
	let lidarrPrompt = $derived(servicePrompts.find((p) => p.service === 'lidarr-connection'));

	const getOtherPrompts = () => {
		return servicePrompts.filter(
			(p) => p.service !== 'lidarr-connection' && !isDismissed(p.service)
		);
	};
	let otherPrompts = $derived(getOtherPrompts());

	function handlePromptDismiss(_service: string) {
		otherPrompts = getOtherPrompts();
	}
</script>

<svelte:head>
	<title>Home - Musicseerr</title>
</svelte:head>

<div class="min-h-[calc(100vh-200px)]">
	<PageHeader
		subtitle="Discover music, explore your library, and find new favorites."
		{loading}
		{refreshing}
		{isUpdating}
		{lastUpdated}
		onRefresh={handleRefresh}
	>
		{#snippet title()}
			<Music class="inline h-8 w-8 sm:h-10 sm:w-10 lg:h-12 lg:w-12 mr-2 align-text-bottom" />
			{getGreeting()}
		{/snippet}
	</PageHeader>

	<div class="flex justify-end px-4 -mt-4 mb-4 sm:px-6 lg:px-8">
		<SourceSwitcher pageKey="home" onSourceChange={handleSourceChange} />
	</div>

	{#if error && !homeData}
		<div class="mt-16 flex flex-col items-center justify-center px-4">
			<CircleAlert class="mb-4 h-10 w-10 text-base-content/50" />
			<p class="text-base-content/70">{error}</p>
			<button class="btn btn-primary mt-4" onclick={() => loadHomeData(true)}>Try Again</button>
		</div>
	{:else}
		<div class="space-y-10 px-4 sm:space-y-12 sm:px-6 lg:px-8">
			{#if !lidarrConfigured && lidarrPrompt}
				<div
					class="card bg-linear-to-br from-accent/20 via-accent/10 to-base-200 border-2 border-accent/40 shadow-xl relative overflow-hidden"
				>
					<div class="absolute inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
						<span class="absolute left-[15%] bottom-4 text-accent/10 text-2xl animate-note-float"
							>♪</span
						>
						<span
							class="absolute left-[40%] bottom-8 text-primary/10 text-lg animate-note-float"
							style="animation-delay: 2s;">♫</span
						>
						<span
							class="absolute right-[20%] bottom-2 text-accent/10 text-xl animate-note-float"
							style="animation-delay: 4s;">♪</span
						>
						<span
							class="absolute right-[35%] bottom-6 text-primary/10 text-2xl animate-note-float"
							style="animation-delay: 1s;">♩</span
						>
					</div>
					<div class="card-body items-center text-center py-12 stagger-fade-in">
						<Music class="h-16 w-16 mb-4 animate-float text-accent" />
						<h2 class="card-title text-3xl sm:text-4xl lg:text-5xl font-bold mb-2">
							Welcome to <span class="text-primary">Musicseerr</span>!
						</h2>
						<p class="text-base-content/70 max-w-lg mb-6">
							To get started, connect your Lidarr server. This is required to manage your music
							library, request albums, and track your collection.
						</p>
						<div class="flex flex-wrap justify-center gap-2 mb-6">
							{#each lidarrPrompt.features as feature (feature)}
								<span class="badge badge-accent badge-lg">{feature}</span>
							{/each}
						</div>
						<a href="/settings?tab=lidarr-connection" class="btn btn-accent btn-lg gap-2">
							<Shield class="h-5 w-5" />
							Connect Lidarr
						</a>
					</div>
				</div>
			{/if}

			{#if otherPrompts.length > 0 && lidarrConfigured}
				<div class="space-y-3">
					{#each otherPrompts as prompt, i (`prompt-${i}`)}
						<ServicePromptCard {prompt} ondismiss={handlePromptDismiss} />
					{/each}
				</div>
			{/if}

			{#if loading && !homeData}
				<section>
					<div class="skeleton skeleton-shimmer mb-4 h-6 w-40"></div>
					<CarouselSkeleton />
				</section>
			{:else}
				{#if whatsHotBlocks.length > 0}
					<div>
						<SectionDivider label="What's Hot">
							{#snippet icon()}<TrendingUp class="w-3.5 h-3.5" />{/snippet}
						</SectionDivider>
						<div class="discover-section-enter space-y-2">
							{#each whatsHotBlocks as block (block.key)}
								<div>
									{#if block.kind === 'section'}
										<HomeSection section={block.section} headerLink={block.link} />
									{:else}
										<WeeklyExploration
											section={block.section}
											ytConfigured={homeData?.integration_status?.youtube ?? false}
										/>
									{/if}
								</div>
							{/each}
						</div>
					</div>
				{/if}

				{#if forYouBlocks.length > 0}
					<div>
						<SectionDivider label="For You">
							{#snippet icon()}<Sparkles class="w-3.5 h-3.5" />{/snippet}
						</SectionDivider>
						<div class="discover-section-enter space-y-2">
							{#each forYouBlocks as block (block.key)}
								<div>
									{#if block.kind === 'section'}
										<HomeSection section={block.section} headerLink={block.link} />
									{:else}
										<WeeklyExploration
											section={block.section}
											ytConfigured={homeData?.integration_status?.youtube ?? false}
										/>
									{/if}
								</div>
							{/each}
						</div>
					</div>
				{/if}
			{/if}

			{#if loading && !homeData}
				<section>
					<div class="skeleton skeleton-shimmer mb-4 h-6 w-36"></div>
					<div class="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 md:grid-cols-4 lg:grid-cols-5">
						{#each Array(10) as _, i (`genre-skeleton-${i}`)}
							<div class="skeleton skeleton-shimmer h-20 rounded-lg sm:h-24"></div>
						{/each}
					</div>
				</section>
			{:else if homeData?.genre_list && homeData.genre_list.items.length > 0}
				<div class="mt-10 mb-10">
					<GenreGrid
						title={homeData.genre_list.title}
						genres={homeData.genre_list.items}
						genreArtists={homeData.genre_artists}
						genreArtistImages={homeData.genre_artist_images}
					/>
				</div>
			{/if}

			{#if loading && !homeData}
				{#each Array(4) as _, i (`post-genre-skeleton-${i}`)}
					<section>
						<div class="skeleton skeleton-shimmer mb-4 h-6 w-32"></div>
						<CarouselSkeleton showSubtitle={false} />
					</section>
				{/each}
			{:else if postGenreSections.length > 0}
				<div>
					<SectionDivider label="Your Library">
						{#snippet icon()}<Library class="w-3.5 h-3.5" />{/snippet}
					</SectionDivider>
					<div class="discover-section-enter space-y-2">
						{#each postGenreSections as { key, section, link } (key)}
							<div>
								<HomeSection {section} headerLink={link} />
							</div>
						{/each}
					</div>
				</div>
			{/if}

			{#if !loading && !hasContent && servicePrompts.length === 0}
				<div class="flex flex-col items-center justify-center py-12 sm:py-16">
					<Music class="h-12 w-12 sm:h-16 sm:w-16 mb-4 sm:mb-6" />
					<h2 class="mb-2 text-center text-3xl font-bold sm:text-4xl lg:text-5xl">
						Welcome to <span class="text-primary">Musicseerr</span>
					</h2>
					<p class="mb-6 max-w-md px-4 text-center text-sm text-base-content/70 sm:text-base">
						Your music library appears to be empty. Add some albums in Lidarr to get started, or
						connect additional services for personalized recommendations.
					</p>
					<a href="/settings" class="btn btn-primary"> Settings </a>
				</div>
			{/if}
		</div>
	{/if}
</div>
