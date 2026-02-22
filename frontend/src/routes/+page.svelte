<script lang="ts">
import { Shield, ArrowRight, Compass, Music } from 'lucide-svelte';
	import { onMount, onDestroy } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import HomeSection from '$lib/components/HomeSection.svelte';
	import ServicePromptCard from '$lib/components/ServicePromptCard.svelte';
	import GenreGrid from '$lib/components/GenreGrid.svelte';
	import type { HomeResponse, HomeSection as HomeSectionType } from '$lib/types';
	import { integrationStore } from '$lib/stores/integration';
	import CarouselSkeleton from '$lib/components/CarouselSkeleton.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import {
		getHomeCachedData,
		setHomeCachedData,
		isHomeCacheStale,
		getGreeting
	} from '$lib/utils/homeCache';
	import { formatLastUpdated } from '$lib/utils/formatting';

	let homeData: HomeResponse | null = null;
	let loading = true;
	let refreshing = false;
	let isUpdating = false;
	let error = '';
	let lastUpdated: Date | null = null;
	let abortController: AbortController | null = null;

	async function loadHomeData(forceRefresh = false) {
		const cached = getHomeCachedData();
		if (cached && !forceRefresh) {
			homeData = cached.data;
			lastUpdated = new Date(cached.timestamp);
			loading = false;
			if (isHomeCacheStale(cached.timestamp)) {
				refreshInBackground();
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
			const response = await fetch('/api/home', { signal: abortController.signal });
			if (response.ok) {
				const data = await response.json();
				homeData = data;
				lastUpdated = new Date();
				setHomeCachedData(data);
				if (data.integration_status) {
					integrationStore.setStatus(data.integration_status);
				}
			} else {
				if (!homeData) {
					error = 'Failed to load home data';
				}
			}
		} catch (e) {
			if (e instanceof Error && e.name === 'AbortError') {
				return;
			}
			if (!homeData) {
				error = 'Failed to load home data';
			}
		} finally {
			loading = false;
		}
	}

	async function refreshInBackground() {
		if (refreshing) return;

		if (abortController) {
			abortController.abort();
		}
		abortController = new AbortController();
		refreshing = true;
		isUpdating = true;

		try {
			const response = await fetch('/api/home', { signal: abortController.signal });
			if (response.ok) {
				const data = await response.json();
				homeData = data;
				lastUpdated = new Date();
				setHomeCachedData(data);
				if (data.integration_status) {
					integrationStore.setStatus(data.integration_status);
				}
			}
		} catch (e) {
			if (e instanceof Error && e.name === 'AbortError') {
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
			await loadHomeData(true);
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
		loadHomeData();
	});

	onDestroy(cleanup);
	beforeNavigate(cleanup);

	function getSections(): { key: string; section: HomeSectionType; link?: string }[] {
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
		if (homeData.recently_added && homeData.recently_added.items.length > 0) {
			sections.push({
				key: 'recently_added',
				section: homeData.recently_added,
				link: '/library/albums'
			});
		}

		return sections;
	}

	function getLibrarySections(): { key: string; section: HomeSectionType; link?: string }[] {
		if (!homeData) return [];
		const sections: { key: string; section: HomeSectionType; link?: string }[] = [];
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

	function getListenBrainzSections(): { key: string; section: HomeSectionType; link?: string }[] {
		if (!homeData) return [];
		const sections: { key: string; section: HomeSectionType; link?: string }[] = [];
		if (homeData.fresh_releases && homeData.fresh_releases.items.length > 0) {
			sections.push({ key: 'fresh_releases', section: homeData.fresh_releases });
		}
		return sections;
	}

	function getJellyfinSections(): { key: string; section: HomeSectionType; link?: string }[] {
		if (!homeData) return [];
		const sections: { key: string; section: HomeSectionType; link?: string }[] = [];
		if (homeData.recently_played && homeData.recently_played.items.length > 0) {
			sections.push({ key: 'recently_played', section: homeData.recently_played });
		}
		if (homeData.favorite_artists && homeData.favorite_artists.items.length > 0) {
			sections.push({ key: 'favorite_artists', section: homeData.favorite_artists });
		}
		return sections;
	}

	$: sections = homeData ? getSections() : [];
	$: librarySections = homeData ? getLibrarySections() : [];
	$: listenbrainzSections = homeData ? getListenBrainzSections() : [];
	$: jellyfinSections = homeData ? getJellyfinSections() : [];
	$: hasContent =
		sections.length > 0 ||
		librarySections.length > 0 ||
		listenbrainzSections.length > 0 ||
		jellyfinSections.length > 0 ||
		(homeData?.genre_list?.items?.length ?? 0) > 0;
	$: servicePrompts = homeData?.service_prompts || [];
	$: lidarrConfigured = homeData?.integration_status?.lidarr ?? true;
	$: lidarrPrompt = servicePrompts.find((p) => p.service === 'lidarr-connection');
	$: otherPrompts = servicePrompts.filter((p) => p.service !== 'lidarr-connection');
	$: discoverPreview = homeData?.discover_preview ?? null;
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
				{#each sections as { key, section, link } (key)}
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
				{#each Array(3) as _}
					<section>
						<div class="skeleton mb-4 h-6 w-32"></div>
						<CarouselSkeleton showSubtitle={false} />
					</section>
				{/each}
			{:else}
				{#if librarySections.length > 0}
					<div
						class="section-group section-group-library -mx-4 px-4 py-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8"
					>
						{#each librarySections as { key, section, link } (key)}
							<HomeSection {section} headerLink={link} />
						{/each}
					</div>
				{/if}

				{#if listenbrainzSections.length > 0}
					<div
						class="section-group section-group-listenbrainz -mx-4 px-4 py-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8"
					>
						{#each listenbrainzSections as { key, section, link } (key)}
							<HomeSection {section} headerLink={link} />
						{/each}
					</div>
				{/if}

				{#if discoverPreview && discoverPreview.items.length > 0}
					<div
						class="section-group section-group-discover -mx-4 px-4 py-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8"
					>
						<HomeSection
							section={{
								title: `Because You Listen to ${discoverPreview.seed_artist}`,
								type: 'artists',
								items: discoverPreview.items,
								source: null,
								fallback_message: null,
								connect_service: null
							}}
						/>
						<div class="flex items-center justify-center pt-2 pb-2">
							<a href="/discover" class="btn btn-primary gap-2">
								<Compass class="h-5 w-5" />
								Explore More on Discover
								<ArrowRight class="h-5 w-5" />
							</a>
						</div>
					</div>
				{/if}

				{#if jellyfinSections.length > 0}
					<div
						class="section-group section-group-jellyfin -mx-4 px-4 py-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8"
					>
						{#each jellyfinSections as { key, section, link } (key)}
							<HomeSection {section} headerLink={link} />
						{/each}
					</div>
				{/if}
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

<style>
	.section-group {
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.section-group-library {
		background: linear-gradient(
			135deg,
			rgb(var(--brand-library) / 0.06) 0%,
			rgb(var(--brand-library) / 0.02) 100%
		);
		border: 1px solid rgb(var(--brand-library) / 0.12);
	}

	.section-group-listenbrainz {
		background: linear-gradient(
			135deg,
			rgb(var(--brand-listenbrainz) / 0.06) 0%,
			rgb(var(--brand-listenbrainz) / 0.02) 100%
		);
		border: 1px solid rgb(var(--brand-listenbrainz) / 0.12);
	}

	.section-group-jellyfin {
		background: linear-gradient(
			135deg,
			rgb(var(--brand-jellyfin) / 0.06) 0%,
			rgb(var(--brand-jellyfin) / 0.02) 100%
		);
		border: 1px solid rgb(var(--brand-jellyfin) / 0.12);
	}

	.section-group-discover {
		background: linear-gradient(
			135deg,
			rgb(var(--brand-discover) / 0.06) 0%,
			rgb(var(--brand-discover) / 0.02) 100%
		);
		border: 1px solid rgb(var(--brand-discover) / 0.12);
	}
</style>
