<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { API } from '$lib/constants';
	import AlbumImage from '$lib/components/AlbumImage.svelte';
	import SourceAlbumModal from '$lib/components/SourceAlbumModal.svelte';
	import {
		getJellyfinSidebarCachedData,
		isJellyfinSidebarCacheStale,
		setJellyfinSidebarCachedData
	} from '$lib/utils/jellyfinLibraryCache';
	import { launchJellyfinPlayback } from '$lib/player/launchJellyfinPlayback';
	import type {
	import { Tv, ArrowDown, CircleX , Play} from 'lucide-svelte';
		JellyfinAlbumSummary,
		JellyfinPaginatedResponse,
		JellyfinLibraryStats,
		JellyfinTrackInfo
	} from '$lib/types';

	let albums = $state<JellyfinAlbumSummary[]>([]);
	let recentAlbums = $state<JellyfinAlbumSummary[]>([]);
	let favoriteAlbums = $state<JellyfinAlbumSummary[]>([]);
	let genres = $state<string[]>([]);
	let stats = $state<JellyfinLibraryStats | null>(null);
	let total = $state(0);
	let loading = $state(true);
	let loadingMore = $state(false);
	let fetchError = $state('');

	let sortBy = $state<'SortName' | 'DateCreated' | 'ProductionYear'>('SortName');
	let sortOrder = $state<'Ascending' | 'Descending'>('Ascending');
	let selectedGenre = $state('');
	let searchQuery = $state('');
	let searchTimeout: ReturnType<typeof setTimeout> | null = null;
	let fetchId = 0;
	let sidebarAbortController: AbortController | null = null;
	let playingAlbumId = $state<string | null>(null);

	let detailModalOpen = $state(false);
	let selectedAlbum = $state<JellyfinAlbumSummary | null>(null);

	const PAGE_SIZE = 48;

	async function fetchAlbums(reset: boolean = false): Promise<void> {
		const id = ++fetchId;
		fetchError = '';
		if (reset) {
			loading = true;
			albums = [];
		} else {
			loadingMore = true;
		}

		try {
			const offset = reset ? 0 : albums.length;

			if (searchQuery.trim()) {
				const res = await fetch(API.jellyfinLibrary.search(searchQuery.trim()));
				if (id !== fetchId) return;
				if (res.ok) {
					const data = await res.json();
					albums = data.albums ?? [];
					total = albums.length;
				} else {
					fetchError = 'Failed to search albums';
				}
			} else {
				const res = await fetch(
					API.jellyfinLibrary.albums(PAGE_SIZE, offset, sortBy, selectedGenre || undefined, sortOrder)
				);
				if (id !== fetchId) return;
				if (res.ok) {
					const data: JellyfinPaginatedResponse = await res.json();
					albums = reset ? data.items : [...albums, ...data.items];
					total = data.total;
				} else {
					fetchError = 'Failed to load albums';
				}
			}
		} catch {
			if (id === fetchId) fetchError = 'Failed to connect to Jellyfin';
		} finally {
			if (id === fetchId) {
				loading = false;
				loadingMore = false;
			}
		}
	}

	function applySidebarData(data: {
		recentAlbums: JellyfinAlbumSummary[];
		favoriteAlbums: JellyfinAlbumSummary[];
		genres: string[];
		stats: JellyfinLibraryStats | null;
	}): void {
		recentAlbums = data.recentAlbums;
		favoriteAlbums = data.favoriteAlbums;
		genres = data.genres;
		stats = data.stats;
	}

	async function fetchSidebar(forceRefresh: boolean = false): Promise<void> {
		const cached = getJellyfinSidebarCachedData();
		if (cached && !forceRefresh) {
			applySidebarData(cached.data);
			if (!isJellyfinSidebarCacheStale(cached.timestamp)) {
				return;
			}
		}

		if (sidebarAbortController) {
			sidebarAbortController.abort();
		}
		sidebarAbortController = new AbortController();

		try {
			const [recentRes, favRes, genreRes, statsRes] = await Promise.allSettled([
				fetch(API.jellyfinLibrary.recent(), { signal: sidebarAbortController.signal }),
				fetch(API.jellyfinLibrary.favorites(), { signal: sidebarAbortController.signal }),
				fetch(API.jellyfinLibrary.genres(), { signal: sidebarAbortController.signal }),
				fetch(API.jellyfinLibrary.stats(), { signal: sidebarAbortController.signal })
			]);

			let nextRecentAlbums = recentAlbums;
			let nextFavoriteAlbums = favoriteAlbums;
			let nextGenres = genres;
			let nextStats = stats;
			let hasFreshData = false;

			if (recentRes.status === 'fulfilled' && recentRes.value.ok) {
				nextRecentAlbums = await recentRes.value.json();
				hasFreshData = true;
			}
			if (favRes.status === 'fulfilled' && favRes.value.ok) {
				nextFavoriteAlbums = await favRes.value.json();
				hasFreshData = true;
			}
			if (genreRes.status === 'fulfilled' && genreRes.value.ok) {
				nextGenres = await genreRes.value.json();
				hasFreshData = true;
			}
			if (statsRes.status === 'fulfilled' && statsRes.value.ok) {
				nextStats = await statsRes.value.json();
				hasFreshData = true;
			}

			recentAlbums = nextRecentAlbums;
			favoriteAlbums = nextFavoriteAlbums;
			genres = nextGenres;
			stats = nextStats;

			if (hasFreshData) {
				setJellyfinSidebarCachedData({
					recentAlbums: nextRecentAlbums,
					favoriteAlbums: nextFavoriteAlbums,
					genres: nextGenres,
					stats: nextStats
				});
			}
		} catch (e) {
			if (e instanceof Error && e.name === 'AbortError') {
				return;
			}
		}
	}

	function openDetail(album: JellyfinAlbumSummary): void {
		selectedAlbum = album;
		detailModalOpen = true;
	}

	function handleDetailClose(): void {
		selectedAlbum = null;
	}

	function handleSortChange(e: Event): void {
		const newSort = (e.target as HTMLSelectElement).value as typeof sortBy;
		if (newSort !== sortBy) {
			sortBy = newSort;
			sortOrder = newSort === 'SortName' ? 'Ascending' : 'Descending';
		}
		fetchAlbums(true);
	}

	function toggleSortOrder(): void {
		sortOrder = sortOrder === 'Ascending' ? 'Descending' : 'Ascending';
		fetchAlbums(true);
	}

	function handleGenreChange(e: Event): void {
		selectedGenre = (e.target as HTMLSelectElement).value;
		fetchAlbums(true);
	}

	function handleSearch(): void {
		if (searchTimeout) clearTimeout(searchTimeout);
		searchTimeout = setTimeout(() => {
			fetchAlbums(true);
		}, 300);
	}

	function loadMore(): void {
		if (!loadingMore && albums.length < total) {
			fetchAlbums(false);
		}
	}

	async function quickPlay(album: JellyfinAlbumSummary, e: Event): Promise<void> {
		e.stopPropagation();
		playingAlbumId = album.jellyfin_id;
		try {
			const res = await fetch(API.jellyfinLibrary.albumTracks(album.jellyfin_id));
			if (!res.ok) return;
			const tracks: JellyfinTrackInfo[] = await res.json();
			if (tracks.length === 0) return;
			launchJellyfinPlayback(tracks, 0, false, {
				albumId: album.musicbrainz_id || album.jellyfin_id,
				albumName: album.name,
				artistName: album.artist_name,
				coverUrl: album.image_url ?? ''
			});
		} catch {} finally {
			playingAlbumId = null;
		}
	}

	onMount(() => {
		fetchAlbums(true);
		fetchSidebar();
	});

	onDestroy(() => {
		if (searchTimeout) clearTimeout(searchTimeout);
		if (sidebarAbortController) {
			sidebarAbortController.abort();
			sidebarAbortController = null;
		}
	});
</script>

<div class="container mx-auto p-6">
	<div class="flex items-center gap-3 mb-2">
		<Tv class="h-8 w-8 text-info" />
		<h1 class="text-2xl font-bold">Jellyfin Library</h1>
		{#if stats}
			<span class="badge badge-neutral">{stats.total_albums} albums</span>
		{/if}
	</div>

	{#if recentAlbums.length > 0}
		<div class="mb-8">
			<h2 class="text-lg font-semibold mb-3 opacity-80">Recently Played</h2>
			<div class="flex gap-3 overflow-x-auto pb-2">
				{#each recentAlbums as album (album.jellyfin_id)}
					<button
						class="flex-shrink-0 w-36 group cursor-pointer transition-transform hover:scale-105 active:scale-95"
						onclick={() => openDetail(album)}
					>
						<div class="aspect-square rounded-lg overflow-hidden shadow-sm">
							<AlbumImage
								mbid={album.musicbrainz_id ?? album.jellyfin_id}
								customUrl={album.image_url}
								alt={album.name}
								size="full"
								rounded="none"
								className="w-full h-full"
							/>
						</div>
						<p class="text-sm font-medium mt-1 line-clamp-1">{album.name}</p>
						<p class="text-xs opacity-60 line-clamp-1">{album.artist_name}</p>
					</button>
				{/each}
			</div>
		</div>
	{/if}

	{#if favoriteAlbums.length > 0}
		<div class="mb-8">
			<h2 class="text-lg font-semibold mb-3 opacity-80">Favorites</h2>
			<div class="flex gap-3 overflow-x-auto pb-2">
				{#each favoriteAlbums as album (album.jellyfin_id)}
					<button
						class="flex-shrink-0 w-36 group cursor-pointer transition-transform hover:scale-105 active:scale-95"
						onclick={() => openDetail(album)}
					>
						<div class="aspect-square rounded-lg overflow-hidden shadow-sm">
							<AlbumImage
								mbid={album.musicbrainz_id ?? album.jellyfin_id}
								customUrl={album.image_url}
								alt={album.name}
								size="full"
								rounded="none"
								className="w-full h-full"
							/>
						</div>
						<p class="text-sm font-medium mt-1 line-clamp-1">{album.name}</p>
						<p class="text-xs opacity-60 line-clamp-1">{album.artist_name}</p>
					</button>
				{/each}
			</div>
		</div>
	{/if}

	<div class="mb-6">
		<h2 class="text-lg font-semibold mb-3 opacity-80">All Albums</h2>
		<div class="flex flex-wrap items-center gap-3 mb-4">
			<input
				type="text"
				placeholder="Search albums..."
				class="input input-sm w-48"
				bind:value={searchQuery}
				oninput={handleSearch}
				aria-label="Search albums"
			/>
			<select class="select select-sm" onchange={handleSortChange}>
				<option value="SortName" selected={sortBy === 'SortName'}>Name</option>
				<option value="DateCreated" selected={sortBy === 'DateCreated'}>Date Added</option>
				<option value="ProductionYear" selected={sortBy === 'ProductionYear'}>Year</option>
			</select>
			<button
				class="btn btn-sm btn-ghost btn-square"
				onclick={toggleSortOrder}
				aria-label="Toggle sort order"
				title={sortOrder === 'Ascending' ? 'Ascending' : 'Descending'}
			>
				<ArrowDown class="h-4 w-4 transition-transform {sortOrder === 'Descending' ? 'rotate-180' : ''}" />
			</button>
			{#if genres.length > 0}
				<select class="select select-sm" onchange={handleGenreChange}>
					<option value="">All Genres</option>
					{#each genres as genre}
						<option value={genre} selected={selectedGenre === genre}>{genre}</option>
					{/each}
				</select>
			{/if}
			{#if !loading}
				<span class="text-sm opacity-50">{total} results</span>
			{/if}
		</div>
	</div>

	{#if fetchError}
		<div role="alert" class="alert alert-error alert-soft mb-4">
			<CircleX class="h-6 w-6 shrink-0" />
			<span>{fetchError}</span>
			<button class="btn btn-sm btn-ghost" onclick={() => fetchAlbums(true)}>Retry</button>
		</div>
	{/if}

	{#if loading}
		<div
			class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
		>
			{#each Array(12) as _}
				<div class="card bg-base-100 shadow-sm animate-pulse">
					<div class="aspect-square bg-base-300"></div>
					<div class="card-body p-3">
						<div class="h-4 bg-base-300 rounded w-3/4"></div>
						<div class="h-3 bg-base-300 rounded w-1/2 mt-1"></div>
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<div
			class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
		>
			{#each albums as album (album.jellyfin_id)}
				<div
					class="card bg-base-100 w-full shadow-sm group relative cursor-pointer transition-transform hover:scale-105 hover:shadow-lg active:scale-95"
					onclick={() => openDetail(album)}
					onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), openDetail(album))}
					role="button"
					tabindex="0"
				>
					<figure class="aspect-square overflow-hidden relative">
						<AlbumImage
							mbid={album.musicbrainz_id ?? album.jellyfin_id}
							customUrl={album.image_url}
							alt={album.name}
							size="full"
							rounded="none"
							className="w-full h-full"
						/>
						<div class="absolute top-2 left-2">
							<div
								class="badge badge-sm gap-1 badge-info"
							>
								<Tv class="h-3 w-3" />
							</div>
						</div>
						{#if album.year}
							<div class="absolute top-2 right-2">
								<div class="badge badge-sm badge-ghost">{album.year}</div>
							</div>
						{/if}
						<div class="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
							<button
								class="btn btn-circle btn-sm btn-primary shadow-md"
								onclick={(e) => quickPlay(album, e)}
								aria-label="Play {album.name}"
							>
								{#if playingAlbumId === album.jellyfin_id}
									<span class="loading loading-spinner loading-xs"></span>
								{:else}
									<Play class="h-4 w-4 fill-current" />
								{/if}
							</button>
						</div>
					</figure>

					<div class="card-body p-3">
						<h2 class="card-title text-sm line-clamp-2 min-h-[2.5rem]">{album.name}</h2>
						<p class="text-xs opacity-70 line-clamp-1">{album.artist_name}</p>
					</div>
				</div>
			{/each}
		</div>

		{#if albums.length === 0}
			<div class="card bg-base-200 mt-4">
				<div class="card-body items-center text-center">
					<Tv class="h-12 w-12 opacity-20" />
					<p class="text-lg opacity-60">No albums found</p>
					<p class="text-sm opacity-40">
						Make sure your Jellyfin server is configured and has music libraries.
					</p>
				</div>
			</div>
		{/if}

		{#if albums.length < total}
			<div class="flex justify-center mt-6">
				<button class="btn btn-ghost" onclick={loadMore} disabled={loadingMore}>
					{#if loadingMore}
						<span class="loading loading-spinner loading-sm"></span>
					{/if}
					Load More
				</button>
			</div>
		{/if}
	{/if}
</div>

<SourceAlbumModal
	bind:open={detailModalOpen}
	sourceType="jellyfin"
	album={selectedAlbum}
	onclose={handleDetailClose}
/>
