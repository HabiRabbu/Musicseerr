<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import HomeSection from '$lib/components/HomeSection.svelte';
	import ServicePromptCard from '$lib/components/ServicePromptCard.svelte';
	import GenreGrid from '$lib/components/GenreGrid.svelte';
	import type { HomeResponse, HomeSection as HomeSectionType } from '$lib/types';
	import { integrationStore } from '$lib/stores/integration';
	import {
		getHomeCachedData,
		setHomeCachedData,
		formatLastUpdated,
		getGreeting
	} from '$lib/utils/homeCache';

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
			refreshInBackground();
			return;
		}

		if (abortController) {
			abortController.abort();
		}
		abortController = new AbortController();

		if (!homeData) {
			loading = true;
		} else {
			refreshing = true;
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
			refreshing = false;
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

	function handleRefresh() {
		loadHomeData(true);
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
	<div
		class="relative mb-6 overflow-hidden bg-gradient-to-br from-primary/30 via-secondary/20 to-accent/10"
	>
		<div class="absolute inset-0 bg-gradient-to-t from-base-100 to-transparent"></div>
		<div class="relative px-4 py-8 sm:px-6 sm:py-12 lg:px-8">
			<div class="flex items-start justify-between">
				<div>
					<h1 class="mb-2 text-3xl font-bold sm:text-4xl lg:text-5xl">
						{getGreeting()} 👋
					</h1>
					<p class="max-w-xl text-sm text-base-content/70 sm:text-base">
						Discover music, explore your library, and find new favorites.
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
						title="Refresh"
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
						<div class="text-6xl mb-4">🎶</div>
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
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								class="h-5 w-5"
							>
								<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
							</svg>
							Connect Lidarr
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 20 20"
								fill="currentColor"
								class="h-5 w-5"
							>
								<path
									fill-rule="evenodd"
									d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z"
									clip-rule="evenodd"
								/>
							</svg>
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
						<div class="scrollbar-hide flex gap-3 overflow-x-auto pb-2 sm:gap-4">
							{#each Array(6) as _}
								<div class="w-32 flex-shrink-0 sm:w-36 md:w-44">
									<div class="skeleton aspect-square w-full rounded-lg"></div>
									<div class="skeleton mt-2 h-4 w-3/4"></div>
								</div>
							{/each}
						</div>
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
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="2"
									stroke-linecap="round"
									stroke-linejoin="round"
									class="h-5 w-5"
								>
									<circle cx="12" cy="12" r="10"></circle>
									<polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"
									></polygon>
								</svg>
								Explore More on Discover
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="h-5 w-5"
								>
									<path
										fill-rule="evenodd"
										d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z"
										clip-rule="evenodd"
									/>
								</svg>
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
					<div class="mb-4 text-5xl sm:mb-6 sm:text-6xl">🎵</div>
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
	.scrollbar-hide {
		-ms-overflow-style: none;
		scrollbar-width: none;
	}
	.scrollbar-hide::-webkit-scrollbar {
		display: none;
	}

	.section-group {
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.section-group-library {
		background: linear-gradient(135deg, rgba(34, 197, 94, 0.06) 0%, rgba(34, 197, 94, 0.02) 100%);
		border: 1px solid rgba(34, 197, 94, 0.12);
	}

	.section-group-listenbrainz {
		background: linear-gradient(135deg, rgba(251, 146, 60, 0.06) 0%, rgba(251, 146, 60, 0.02) 100%);
		border: 1px solid rgba(251, 146, 60, 0.12);
	}

	.section-group-jellyfin {
		background: linear-gradient(135deg, rgba(168, 85, 247, 0.06) 0%, rgba(168, 85, 247, 0.02) 100%);
		border: 1px solid rgba(168, 85, 247, 0.12);
	}

	.section-group-discover {
		background: linear-gradient(135deg, rgba(56, 189, 248, 0.06) 0%, rgba(59, 130, 246, 0.02) 100%);
		border: 1px solid rgba(56, 189, 248, 0.12);
	}
</style>
