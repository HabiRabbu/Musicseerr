<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import HomeSection from '$lib/components/HomeSection.svelte';
	import type { HomeResponse, HomeSection as HomeSectionType } from '$lib/types';

	const CACHE_KEY = 'musicseerr_home_cache';
	const CACHE_TTL = 60 * 60 * 1000; // 1 hour in milliseconds

	let homeData: HomeResponse | null = null;
	let loading = true;
	let refreshing = false;
	let error = '';
	let lastUpdated: Date | null = null;
	
	let genreArtists: Record<string, string | null> = {};

	interface CachedData {
		data: HomeResponse;
		timestamp: number;
	}

	function getCachedData(): CachedData | null {
		if (!browser) return null;
		try {
			const cached = sessionStorage.getItem(CACHE_KEY);
			if (cached) {
				return JSON.parse(cached);
			}
		} catch (e) {
			console.warn('Failed to read cache:', e);
		}
		return null;
	}

	function setCachedData(data: HomeResponse): void {
		if (!browser) return;
		try {
			const cacheEntry: CachedData = {
				data,
				timestamp: Date.now()
			};
			sessionStorage.setItem(CACHE_KEY, JSON.stringify(cacheEntry));
		} catch (e) {
			console.warn('Failed to write cache:', e);
		}
	}

	function isCacheStale(timestamp: number): boolean {
		return Date.now() - timestamp > CACHE_TTL;
	}

	async function loadHomeData(forceRefresh = false) {
		if (!forceRefresh) {
			const cached = getCachedData();
			if (cached) {
				homeData = cached.data;
				lastUpdated = new Date(cached.timestamp);
				loading = false;

				if (isCacheStale(cached.timestamp)) {
					refreshInBackground();
				}
				return;
			}
		}

		if (!homeData) {
			loading = true;
		} else {
			refreshing = true;
		}

		error = '';

		try {
			const response = await fetch('/api/home');
			if (response.ok) {
				const data = await response.json();
				homeData = data;
				lastUpdated = new Date();
				setCachedData(data);
			} else {
				if (!homeData) {
					error = 'Failed to load home data';
				}
			}
		} catch (e) {
			console.error('Failed to load home data:', e);
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
		refreshing = true;

		try {
			const response = await fetch('/api/home');
			if (response.ok) {
				const data = await response.json();
				homeData = data;
				lastUpdated = new Date();
				setCachedData(data);
			}
		} catch (e) {
			console.error('Background refresh failed:', e);
		} finally {
			refreshing = false;
		}
	}

	function handleRefresh() {
		loadHomeData(true);
	}

	onMount(() => {
		loadHomeData();
	});

	function getGreeting(): string {
		const hour = new Date().getHours();
		if (hour < 12) return 'Good morning';
		if (hour < 18) return 'Good afternoon';
		return 'Good evening';
	}

	function getSections(): { key: string; section: HomeSectionType; link?: string }[] {
		if (!homeData) return [];

		const sections: { key: string; section: HomeSectionType; link?: string }[] = [];

		if (homeData.popular_albums && homeData.popular_albums.items.length > 0) {
			sections.push({ key: 'popular_albums', section: homeData.popular_albums, link: '/popular' });
		}
		if (homeData.trending_artists && homeData.trending_artists.items.length > 0) {
			sections.push({ key: 'trending_artists', section: homeData.trending_artists, link: '/trending' });
		}
		if (homeData.recently_added && homeData.recently_added.items.length > 0) {
			sections.push({ key: 'recently_added', section: homeData.recently_added, link: '/library/albums' });
		}

		return sections;
	}

	function getPostGenreSections(): { key: string; section: HomeSectionType; link?: string }[] {
		if (!homeData) return [];

		const sections: { key: string; section: HomeSectionType; link?: string }[] = [];

		if (homeData.library_artists && homeData.library_artists.items.length > 0) {
			sections.push({ key: 'library_artists', section: homeData.library_artists, link: '/library/artists' });
		}
		if (homeData.library_albums && homeData.library_albums.items.length > 0) {
			sections.push({ key: 'library_albums', section: homeData.library_albums, link: '/library/albums' });
		}
		if (homeData.recommended_artists && homeData.recommended_artists.items.length > 0) {
			sections.push({ key: 'recommended_artists', section: homeData.recommended_artists });
		}
		if (homeData.fresh_releases && homeData.fresh_releases.items.length > 0) {
			sections.push({ key: 'fresh_releases', section: homeData.fresh_releases });
		}
		if (homeData.recently_played && homeData.recently_played.items.length > 0) {
			sections.push({ key: 'recently_played', section: homeData.recently_played });
		}
		if (homeData.favorite_artists && homeData.favorite_artists.items.length > 0) {
			sections.push({ key: 'favorite_artists', section: homeData.favorite_artists });
		}

		return sections;
	}

	function getPromptGradient(color: string): string {
		switch (color) {
			case 'primary':
				return 'from-primary/20 to-primary/5 border-primary/30';
			case 'secondary':
				return 'from-secondary/20 to-secondary/5 border-secondary/30';
			case 'accent':
				return 'from-accent/20 to-accent/5 border-accent/30';
			default:
				return 'from-base-200 to-base-100 border-base-300';
		}
	}

	function getPromptButtonClass(color: string): string {
		switch (color) {
			case 'primary':
				return 'btn-primary';
			case 'secondary':
				return 'btn-secondary';
			case 'accent':
				return 'btn-accent';
			default:
				return 'btn-neutral';
		}
	}

	async function loadGenreArtist(genreName: string) {
		if (genreArtists[genreName] !== undefined) return;
		genreArtists[genreName] = null;
		try {
			const response = await fetch(`/api/home/genre-artist/${encodeURIComponent(genreName)}`);
			if (response.ok) {
				const data = await response.json();
				genreArtists[genreName] = data.artist_mbid;
				genreArtists = genreArtists;
			}
		} catch {}
	}

	$: if (homeData?.genre_list?.items) {
		for (const genre of homeData.genre_list.items.slice(0, 20)) {
			const genreItem = genre as { name: string };
			loadGenreArtist(genreItem.name);
		}
	}

	const genreColors = [
		'from-rose-500 to-pink-600',
		'from-violet-500 to-purple-600',
		'from-blue-500 to-cyan-600',
		'from-emerald-500 to-teal-600',
		'from-amber-500 to-orange-600',
		'from-red-500 to-rose-600',
		'from-indigo-500 to-violet-600',
		'from-cyan-500 to-blue-600',
		'from-green-500 to-emerald-600',
		'from-orange-500 to-amber-600'
	];

	function getGenreColor(name: string): string {
		return genreColors[name.length % genreColors.length];
	}

	function formatLastUpdated(date: Date | null): string {
		if (!date) return '';
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffMins = Math.floor(diffMs / 60000);

		if (diffMins < 1) return 'Just now';
		if (diffMins < 60) return `${diffMins}m ago`;
		const diffHours = Math.floor(diffMins / 60);
		if (diffHours < 24) return `${diffHours}h ago`;
		return date.toLocaleDateString();
	}

	$: sections = homeData ? getSections() : [];
	$: postGenreSections = homeData ? getPostGenreSections() : [];
	$: hasContent =
		sections.length > 0 ||
		postGenreSections.length > 0 ||
		(homeData?.genre_list?.items?.length ?? 0) > 0;
	$: servicePrompts = homeData?.service_prompts || [];
</script>

<svelte:head>
	<title>Home - Musicseerr</title>
</svelte:head>

<style>
	.scrollbar-hide {
		-ms-overflow-style: none;
		scrollbar-width: none;
	}
	.scrollbar-hide::-webkit-scrollbar {
		display: none;
	}
</style>

<div class="min-h-[calc(100vh-200px)]">
	<!-- Hero Banner - Always visible -->
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
				<!-- Refresh Button -->
				<div class="flex items-center gap-2">
					{#if lastUpdated && !loading}
						<span class="hidden text-xs text-base-content/50 sm:inline">
							Updated {formatLastUpdated(lastUpdated)}
						</span>
					{/if}
					<button
						class="btn btn-circle btn-ghost btn-sm"
						on:click={handleRefresh}
						disabled={refreshing || loading}
						title="Refresh"
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 20 20"
							fill="currentColor"
							class="h-5 w-5 {refreshing ? 'animate-spin' : ''}"
						>
							<path
								fill-rule="evenodd"
								d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H3.989a.75.75 0 00-.75.75v4.242a.75.75 0 001.5 0v-2.43l.31.31a7 7 0 0011.712-3.138.75.75 0 00-1.449-.39zm1.23-3.723a.75.75 0 00.219-.53V2.929a.75.75 0 00-1.5 0v2.43l-.31-.31A7 7 0 003.239 8.188a.75.75 0 101.448.389A5.5 5.5 0 0113.89 6.11l.311.31h-2.432a.75.75 0 000 1.5h4.243a.75.75 0 00.53-.219z"
								clip-rule="evenodd"
							/>
						</svg>
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
			<!-- Service Connection Prompts -->
			{#if servicePrompts.length > 0}
				<div class="space-y-3">
					{#each servicePrompts as prompt}
						<div
							class="card overflow-hidden border bg-gradient-to-r shadow-lg {getPromptGradient(
								prompt.color
							)}"
						>
							<div class="card-body flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:p-6">
								<div class="flex-shrink-0 text-4xl sm:text-5xl">{prompt.icon}</div>
								<div class="min-w-0 flex-1">
									<h3 class="card-title mb-1 text-base sm:text-lg">{prompt.title}</h3>
									<p class="mb-2 text-xs text-base-content/70 sm:mb-3 sm:text-sm">
										{prompt.description}
									</p>
									<div class="flex flex-wrap gap-1 sm:gap-2">
										{#each prompt.features as feature}
											<span class="badge badge-ghost badge-xs sm:badge-sm">{feature}</span>
										{/each}
									</div>
								</div>
								<div class="flex-shrink-0">
									<a
										href="/settings"
										class="btn btn-sm sm:btn-md {getPromptButtonClass(prompt.color)}"
									>
										Connect
										<svg
											xmlns="http://www.w3.org/2000/svg"
											viewBox="0 0 20 20"
											fill="currentColor"
											class="h-4 w-4"
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
						</div>
					{/each}
				</div>
			{/if}

			<!-- Main Sections (Popular, Trending, Recently Added) -->
			{#if loading && !homeData}
				<!-- Only show full skeleton when we have no data at all -->
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

			<!-- Genre Grid -->
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
				<section>
					<div class="mb-4 flex items-center justify-between">
						<h2 class="text-lg font-bold sm:text-xl">{homeData.genre_list.title}</h2>
					</div>
					<div class="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 md:grid-cols-4 lg:grid-cols-5">
						{#each homeData.genre_list.items.slice(0, 20) as genre}
							{@const genreItem = genre as { name: string }}
							{@const artistMbid = genreArtists[genreItem.name]}
							<a
								href="/genre?name={encodeURIComponent(genreItem.name)}"
								class="card text-white shadow-lg transition-all duration-200 hover:scale-105 hover:shadow-xl active:scale-95 overflow-hidden relative"
							>
								<!-- Base gradient background -->
								<div class="absolute inset-0 bg-gradient-to-br {getGenreColor(genreItem.name)}"></div>
								<!-- Artist image overlay -->
								{#if artistMbid}
									<img
										src="/api/covers/artist/{artistMbid}?size=250"
										alt=""
										class="absolute inset-0 w-full h-full object-cover opacity-25 pointer-events-none"
										style="z-index: 5;"
										loading="lazy"
									/>
								{/if}
								<!-- Dark gradient for text readability -->
								<div class="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" style="z-index: 6;"></div>
								<!-- Content -->
								<div class="card-body min-h-24 justify-end p-3 sm:min-h-28 sm:p-4 relative" style="z-index: 10;">
									<h3 class="text-xs font-bold sm:text-sm drop-shadow-lg">{genreItem.name}</h3>
								</div>
							</a>
						{/each}
					</div>
				</section>
			{/if}

			<!-- Post-Genre Sections (Library Artists/Albums, Recommendations, etc.) -->
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
				{#each postGenreSections as { key, section, link } (key)}
					<HomeSection {section} headerLink={link} />
				{/each}
			{/if}

			<!-- Empty state -->
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
