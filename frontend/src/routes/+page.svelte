<script lang="ts">
	import { Shield, Music, ArrowRight } from 'lucide-svelte';
	import { onMount, onDestroy } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import HomeSection from '$lib/components/HomeSection.svelte';
	import ServicePromptCard from '$lib/components/ServicePromptCard.svelte';
	import GenreGrid from '$lib/components/GenreGrid.svelte';
	import SourceSwitcher from '$lib/components/SourceSwitcher.svelte';
	import type { HomeResponse, HomeSection as HomeSectionType } from '$lib/types';
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
	import { removeQueueCachedData } from '$lib/utils/discoverQueueCache';

	let homeData: HomeResponse | null = null;
	let loading = true;
	let refreshing = false;
	let isUpdating = false;
	let error = '';
	let lastUpdated: Date | null = null;
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
			const response = await fetch(`/api/home?source=${encodeURIComponent(source)}`, {
				signal: abortController.signal
			});
			if (response.ok) {
				const data = await response.json();
				homeData = data;
				lastUpdated = new Date();
				setHomeCachedData(data, source);
				if (data.integration_status) {
					integrationStore.setStatus(data.integration_status);
				}
			} else {
				if (!homeData) {
					error = 'Failed to load home data';
				}
			}
		} catch (e) {
			if (isAbortError(e)) {
				return;
			}
			if (!homeData) {
				error = 'Failed to load home data';
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
			const response = await fetch(`/api/home?source=${encodeURIComponent(source)}`, {
				signal: abortController.signal
			});
			if (response.ok) {
				const data = await response.json();
				homeData = data;
				lastUpdated = new Date();
				setHomeCachedData(data, source);
				if (data.integration_status) {
					integrationStore.setStatus(data.integration_status);
				}
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

	onMount(async () => {
		await musicSourceStore.load();
		activeSource = musicSourceStore.getPageSource('home');
		loadHomeData(false, activeSource);
	});

	onDestroy(cleanup);
	beforeNavigate(cleanup);

	function handleSourceChange(source: MusicSource) {
		activeSource = source;
		removeQueueCachedData();
		loadHomeData(true, source);
	}

	function getPreGenreSections(): { key: string; section: HomeSectionType; link?: string }[] {
		if (!homeData) return [];
		const sections: { key: string; section: HomeSectionType; link?: string }[] = [];
		if (homeData.popular_albums && homeData.popular_albums.items.length > 0) {
			sections.push({ key: 'popular_albums', section: homeData.popular_albums, link: '/popular' });
		}
		if (homeData.trending_artists && homeData.trending_artists.items.length > 0) {
			sections.push({
				key: 'trending_artists',
				section: homeData.trending_artists,
				link: '/trending'
			});
		}
		if (homeData.your_top_albums && homeData.your_top_albums.items.length > 0) {
			sections.push({
				key: 'your_top_albums',
				section: homeData.your_top_albums,
				link: '/your-top'
			});
		}
		if (homeData.recently_played && homeData.recently_played.items.length > 0) {
			sections.push({
				key: 'recently_played',
				section: homeData.recently_played
			});
		}
		if (homeData.recently_added && homeData.recently_added.items.length > 0) {
			sections.push({
				key: 'recently_added',
				section: homeData.recently_added,
				link: '/library/albums'
			});
		}
		return sections;
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
	$: preGenreSections = homeData ? getPreGenreSections() : [];
	$: postGenreSections = homeData ? getPostGenreSections() : [];
	$: hasContent =
		preGenreSections.length > 0 ||
		postGenreSections.length > 0 ||
		(homeData?.genre_list?.items?.length ?? 0) > 0;
	$: servicePrompts = homeData?.service_prompts || [];
	$: lidarrConfigured = homeData?.integration_status?.lidarr ?? true;
	$: lidarrPrompt = servicePrompts.find((p) => p.service === 'lidarr-connection');
	$: otherPrompts = servicePrompts.filter((p) => p.service !== 'lidarr-connection');
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
			{getGreeting()} 👋
		{/snippet}
	</PageHeader>

	<div class="flex justify-end px-4 -mt-4 mb-4 sm:px-6 lg:px-8">
		<SourceSwitcher pageKey="home" onSourceChange={handleSourceChange} />
	</div>

	{#if error && !homeData}
		<div class="mt-16 flex flex-col items-center justify-center px-4">
			<div class="mb-4 text-4xl">😕</div>
			<p class="text-base-content/70">{error}</p>
			<button class="btn btn-primary mt-4" on:click={() => loadHomeData(true)}>Try Again</button>
		</div>
	{:else}
		<div class="space-y-6 px-4 sm:space-y-8 sm:px-6 lg:px-8">
			{#if !lidarrConfigured && lidarrPrompt}
				<div
					class="card bg-gradient-to-br from-accent/20 via-accent/10 to-base-200 border-2 border-accent/40 shadow-xl"
				>
					<div class="card-body items-center text-center py-12">
						<Music class="h-16 w-16 mb-4" />
						<h2 class="card-title text-2xl sm:text-3xl mb-2">Welcome to Musicseerr!</h2>
						<p class="text-base-content/70 max-w-lg mb-6">
							To get started, connect your Lidarr server. This is required to manage your music
							library, request albums, and track your collection.
						</p>
						<div class="flex flex-wrap justify-center gap-2 mb-6">
							{#each lidarrPrompt.features as feature}
								<span class="badge badge-accent badge-lg">{feature}</span>
							{/each}
						</div>
						<a href="/settings?tab=lidarr-connection" class="btn btn-accent btn-lg gap-2">
							<Shield class="h-5 w-5" />
							Connect Lidarr
							<ArrowRight class="h-5 w-5" />
						</a>
					</div>
				</div>
			{/if}

			{#if otherPrompts.length > 0 && lidarrConfigured}
				<div class="space-y-3">
					{#each otherPrompts as prompt}
						<ServicePromptCard {prompt} />
					{/each}
				</div>
			{/if}

			{#if loading && !homeData}
				<section>
					<div class="skeleton mb-4 h-6 w-40"></div>
					<CarouselSkeleton />
				</section>
			{:else}
				{#each preGenreSections as { key, section, link } (key)}
					<HomeSection {section} headerLink={link} />
				{/each}
			{/if}

			{#if loading && !homeData}
				<section>
					<div class="skeleton mb-4 h-6 w-36"></div>
					<div class="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 md:grid-cols-4 lg:grid-cols-5">
						{#each Array(10) as _}
							<div class="skeleton h-20 rounded-lg sm:h-24"></div>
						{/each}
					</div>
				</section>
			{:else if homeData?.genre_list && homeData.genre_list.items.length > 0}
				<GenreGrid
					title={homeData.genre_list.title}
					genres={homeData.genre_list.items}
					genreArtists={homeData.genre_artists}
				/>
			{/if}

			{#if loading && !homeData}
				{#each Array(4) as _}
					<section>
						<div class="skeleton mb-4 h-6 w-32"></div>
						<CarouselSkeleton showSubtitle={false} />
					</section>
				{/each}
			{:else}
				{#each postGenreSections as { key, section, link } (key)}
					<HomeSection {section} headerLink={link} />
				{/each}
			{/if}

			{#if !loading && !hasContent && servicePrompts.length === 0}
				<div class="flex flex-col items-center justify-center py-12 sm:py-16">
					<Music class="h-12 w-12 sm:h-16 sm:w-16 mb-4 sm:mb-6" />
					<h2 class="mb-2 text-center text-xl font-bold sm:text-2xl">Welcome to Musicseerr</h2>
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
