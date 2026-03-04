<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { API } from '$lib/constants';
	import AlbumImage from '$lib/components/AlbumImage.svelte';
	import ContextMenu from '$lib/components/ContextMenu.svelte';
	import type { MenuItem } from '$lib/components/ContextMenu.svelte';
	import AddToPlaylistModal from '$lib/components/AddToPlaylistModal.svelte';
	import SourceAlbumModal from '$lib/components/SourceAlbumModal.svelte';
	import { toastStore } from '$lib/stores/toast';
	import { playerStore } from '$lib/stores/player.svelte';
	import { buildQueueItemsFromLocal, type TrackMeta } from '$lib/player/queueHelpers';
	import type { QueueItem } from '$lib/player/types';
	import {
		getLocalFilesSidebarCachedData,
		getLocalFilesAlbumsListCachedData,
		isLocalFilesSidebarCacheStale,
		isLocalFilesAlbumsListCacheStale,
		setLocalFilesAlbumsListCachedData,
		setLocalFilesSidebarCachedData
	} from '$lib/utils/localFilesCache';
	import { launchLocalPlayback } from '$lib/player/launchLocalPlayback';
	import { getCoverUrl, isAbortError } from '$lib/utils/errorHandling';
	import type {
		LocalAlbumSummary,
		LocalPaginatedResponse,
		LocalStorageStats,
		LocalTrackInfo
	} from '$lib/types';
	import { Headphones, ArrowDown, CircleX, Play, ListPlus, ListStart, ListMusic } from 'lucide-svelte';

	let albums = $state<LocalAlbumSummary[]>([]);
	let recentAlbums = $state<LocalAlbumSummary[]>([]);
	let stats = $state<LocalStorageStats | null>(null);
	let total = $state(0);
	let loading = $state(true);
	let loadingMore = $state(false);
	let fetchError = $state('');

	let sortBy = $state<'name' | 'date_added' | 'year'>('name');
	let sortOrder = $state<'asc' | 'desc'>('asc');
	let searchQuery = $state('');
	let searchTimeout: ReturnType<typeof setTimeout> | null = null;
	let fetchId = 0;
	let albumsAbortController: AbortController | null = null;
	let sidebarAbortController: AbortController | null = null;
	let playingAlbumId = $state<number | null>(null);

	let detailModalOpen = $state(false);
	let selectedAlbum = $state<LocalAlbumSummary | null>(null);
	let menuLoadingAlbumId = $state<number | null>(null);
	let playlistModalRef = $state<{ open: (tracks: QueueItem[]) => void } | null>(null);

	const PAGE_SIZE = 48;

	function getAlbumsListCacheKey(offset: number): string {
		const search = searchQuery.trim() || '';
		return `${sortBy}:${sortOrder}:${search}:${PAGE_SIZE}:${offset}`;
	}

	async function fetchAlbums(reset: boolean = false): Promise<void> {
		const id = ++fetchId;
		fetchError = '';

		if (albumsAbortController) {
			albumsAbortController.abort();
		}
		albumsAbortController = new AbortController();
		const signal = albumsAbortController.signal;

		if (reset) {
			loading = true;
			albums = [];
		} else {
			loadingMore = true;
		}

		try {
			const offset = reset ? 0 : albums.length;
			const cacheKey = getAlbumsListCacheKey(offset);
			const cached = getLocalFilesAlbumsListCachedData(cacheKey);
			if (cached) {
				albums = reset ? cached.data.items : [...albums, ...cached.data.items];
				total = cached.data.total;
				loading = false;
				loadingMore = false;
				if (!isLocalFilesAlbumsListCacheStale(cached.timestamp)) {
					return;
				}
			}

			const url = API.local.albums(
				PAGE_SIZE,
				offset,
				sortBy,
				searchQuery.trim() || undefined,
				sortOrder
			);
			const res = await fetch(url, { signal });
			if (id !== fetchId) return;
			if (res.ok) {
				const data: LocalPaginatedResponse = await res.json();
				albums = reset ? data.items : [...albums, ...data.items];
				total = data.total;
				setLocalFilesAlbumsListCachedData(
					{
						items: data.items,
						total: data.total
					},
					cacheKey
				);
			} else {
				fetchError = 'Failed to load albums';
			}
		} catch (e) {
			if (isAbortError(e)) {
				return;
			}
			if (id === fetchId) fetchError = 'Failed to connect to local files service';
		} finally {
			if (id === fetchId) {
				loading = false;
				loadingMore = false;
			}
		}
	}

	function applySidebarData(data: {
		recentAlbums: LocalAlbumSummary[];
		stats: LocalStorageStats | null;
	}): void {
		recentAlbums = data.recentAlbums;
		stats = data.stats;
	}

	async function fetchSidebar(forceRefresh: boolean = false): Promise<void> {
		const cached = getLocalFilesSidebarCachedData();
		if (cached && !forceRefresh) {
			applySidebarData(cached.data);
			if (!isLocalFilesSidebarCacheStale(cached.timestamp)) {
				return;
			}
		}

		if (sidebarAbortController) {
			sidebarAbortController.abort();
		}
		sidebarAbortController = new AbortController();

		try {
			const [recentRes, statsRes] = await Promise.allSettled([
				fetch(API.local.recent(), { signal: sidebarAbortController.signal }),
				fetch(API.local.stats(), { signal: sidebarAbortController.signal })
			]);

			let nextRecentAlbums = recentAlbums;
			let nextStats = stats;
			let hasFreshData = false;

			if (recentRes.status === 'fulfilled' && recentRes.value.ok) {
				nextRecentAlbums = await recentRes.value.json();
				hasFreshData = true;
			}
			if (statsRes.status === 'fulfilled' && statsRes.value.ok) {
				nextStats = await statsRes.value.json();
				hasFreshData = true;
			}

			recentAlbums = nextRecentAlbums;
			stats = nextStats;

			if (hasFreshData) {
				setLocalFilesSidebarCachedData({
					recentAlbums: nextRecentAlbums,
					stats: nextStats
				});
			}
		} catch (e) {
			if (isAbortError(e)) {
				return;
			}
		}
	}

	function openDetail(album: LocalAlbumSummary): void {
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
			sortOrder = newSort === 'name' ? 'asc' : 'desc';
		}
		fetchAlbums(true);
	}

	function toggleSortOrder(): void {
		sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
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

	function formatSize(bytes: number): string {
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
		return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
	}

	async function quickPlay(album: LocalAlbumSummary, e: Event): Promise<void> {
		e.stopPropagation();
		playingAlbumId = album.lidarr_album_id;
		try {
			const res = await fetch(API.local.albumTracks(album.lidarr_album_id));
			if (!res.ok) return;
			const tracks: LocalTrackInfo[] = await res.json();
			if (tracks.length === 0) return;
			launchLocalPlayback(tracks, 0, false, {
				albumId: album.musicbrainz_id || String(album.lidarr_album_id),
				albumName: album.name,
				artistName: album.artist_name,
				coverUrl: getCoverUrl(
					album.cover_url,
					album.musicbrainz_id || String(album.lidarr_album_id)
				)
			});
		} catch {} finally {
			playingAlbumId = null;
		}
	}

	function getTrackMetaForAlbum(album: LocalAlbumSummary): TrackMeta {
		return {
			albumId: album.musicbrainz_id || String(album.lidarr_album_id),
			albumName: album.name,
			artistName: album.artist_name,
			coverUrl: album.cover_url ?? null,
			artistId: album.artist_mbid ?? undefined
		};
	}

	async function fetchAlbumQueueItems(album: LocalAlbumSummary): Promise<QueueItem[]> {
		const res = await fetch(API.local.albumTracks(album.lidarr_album_id));
		if (!res.ok) {
			throw new Error(`Failed to load tracks (${res.status})`);
		}
		const tracks: LocalTrackInfo[] = await res.json();
		if (tracks.length === 0) return [];
		const sortedTracks = [...tracks].sort((a, b) => a.track_number - b.track_number);
		return buildQueueItemsFromLocal(sortedTracks, getTrackMetaForAlbum(album));
	}

	async function addAlbumToQueue(album: LocalAlbumSummary): Promise<void> {
		menuLoadingAlbumId = album.lidarr_album_id;
		try {
			const queueItems = await fetchAlbumQueueItems(album);
			if (queueItems.length === 0) {
				toastStore.show({ message: 'No tracks found for this album', type: 'info' });
				return;
			}
			playerStore.addMultipleToQueue(queueItems);
		} catch {
			toastStore.show({ message: 'Failed to load album tracks', type: 'error' });
		} finally {
			menuLoadingAlbumId = null;
		}
	}

	async function playAlbumNext(album: LocalAlbumSummary): Promise<void> {
		menuLoadingAlbumId = album.lidarr_album_id;
		try {
			const queueItems = await fetchAlbumQueueItems(album);
			if (queueItems.length === 0) {
				toastStore.show({ message: 'No tracks found for this album', type: 'info' });
				return;
			}
			playerStore.playMultipleNext(queueItems);
		} catch {
			toastStore.show({ message: 'Failed to load album tracks', type: 'error' });
		} finally {
			menuLoadingAlbumId = null;
		}
	}

	async function addAlbumToPlaylist(album: LocalAlbumSummary): Promise<void> {
		menuLoadingAlbumId = album.lidarr_album_id;
		try {
			const queueItems = await fetchAlbumQueueItems(album);
			if (queueItems.length === 0) {
				toastStore.show({ message: 'No tracks found for this album', type: 'info' });
				return;
			}
			playlistModalRef?.open(queueItems);
		} catch {
			toastStore.show({ message: 'Failed to load album tracks', type: 'error' });
		} finally {
			menuLoadingAlbumId = null;
		}
	}

	function getAlbumMenuItems(album: LocalAlbumSummary): MenuItem[] {
		const loadingMenu = menuLoadingAlbumId === album.lidarr_album_id;
		return [
			{
				label: 'Add to Queue',
				icon: ListPlus,
				onclick: () => void addAlbumToQueue(album),
				disabled: loadingMenu
			},
			{
				label: 'Play Next',
				icon: ListStart,
				onclick: () => void playAlbumNext(album),
				disabled: loadingMenu
			},
			{
				label: 'Add to Playlist',
				icon: ListMusic,
				onclick: () => void addAlbumToPlaylist(album),
				disabled: loadingMenu
			}
		];
	}

	onMount(() => {
		fetchAlbums(true);
		fetchSidebar();
	});

	onDestroy(() => {
		if (searchTimeout) clearTimeout(searchTimeout);
		if (albumsAbortController) {
			albumsAbortController.abort();
			albumsAbortController = null;
		}
		if (sidebarAbortController) {
			sidebarAbortController.abort();
			sidebarAbortController = null;
		}
	});
</script>

<div class="container mx-auto p-6">
	<div class="flex items-center gap-3 mb-2">
		<Headphones class="h-8 w-8 text-accent" />
		<h1 class="text-2xl font-bold">Local Files</h1>
		{#if stats}
			<span class="badge badge-neutral">{stats.total_albums} albums</span>
		{/if}
	</div>

	{#if stats}
		<div class="stats stats-vertical sm:stats-horizontal shadow-sm w-full mb-6 bg-base-200">
			<div class="stat px-4 py-3">
				<div class="stat-title text-xs">Tracks</div>
				<div class="stat-value text-lg">{stats.total_tracks.toLocaleString()}</div>
			</div>
			<div class="stat px-4 py-3">
				<div class="stat-title text-xs">Artists</div>
				<div class="stat-value text-lg">{stats.total_artists}</div>
			</div>
			<div class="stat px-4 py-3">
				<div class="stat-title text-xs">Total Size</div>
				<div class="stat-value text-lg">{stats.total_size_human}</div>
			</div>
			<div class="stat px-4 py-3">
				<div class="stat-title text-xs">Disk Free</div>
				<div class="stat-value text-lg">{stats.disk_free_human}</div>
			</div>
			{#if Object.keys(stats.format_breakdown).length > 0}
				<div class="stat px-4 py-3">
					<div class="stat-title text-xs">Formats</div>
					<div class="flex gap-1 mt-1 flex-wrap">
						{#each Object.entries(stats.format_breakdown) as [fmt, info]}
							<span class="badge badge-xs badge-ghost">{fmt}: {info.count}</span>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}

	{#if recentAlbums.length > 0}
		<div class="mb-8">
			<h2 class="text-lg font-semibold mb-3 opacity-80">Recently Added</h2>
			<div class="flex gap-3 overflow-x-auto pb-2">
				{#each recentAlbums as album (album.lidarr_album_id)}
					<button
						class="flex-shrink-0 w-36 group cursor-pointer transition-transform hover:scale-105 active:scale-95"
						onclick={() => openDetail(album)}
					>
						<div class="aspect-square rounded-lg overflow-hidden shadow-sm relative">
							<AlbumImage
								mbid={album.musicbrainz_id ?? String(album.lidarr_album_id)}
								customUrl={album.cover_url}
								alt={album.name}
								size="full"
								rounded="none"
								className="w-full h-full"
							/>
							{#if album.primary_format}
								<div class="absolute bottom-1 right-1">
									<span class="badge badge-xs badge-ghost">{album.primary_format}</span>
								</div>
							{/if}
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
				<option value="name" selected={sortBy === 'name'}>Name</option>
				<option value="date_added" selected={sortBy === 'date_added'}>Date Added</option>
				<option value="year" selected={sortBy === 'year'}>Year</option>
			</select>
			<button
				class="btn btn-sm btn-ghost btn-square"
				onclick={toggleSortOrder}
				aria-label="Toggle sort order"
				title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
			>
				<ArrowDown class="h-4 w-4 transition-transform {sortOrder === 'desc' ? 'rotate-180' : ''}" />
			</button>
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
			{#each albums as album (album.lidarr_album_id)}
				<div
					class="card bg-base-100 w-full shadow-sm group relative cursor-pointer transition-transform hover:scale-105 hover:shadow-lg active:scale-95"
					onclick={() => openDetail(album)}
					onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), openDetail(album))}
					role="button"
					tabindex="0"
				>
					<figure class="aspect-square overflow-hidden relative">
						<AlbumImage
							mbid={album.musicbrainz_id ?? String(album.lidarr_album_id)}
							customUrl={album.cover_url}
							alt={album.name}
							size="full"
							rounded="none"
							className="w-full h-full"
						/>
						<div class="absolute top-2 left-2">
							<div
								class="badge badge-sm gap-1 badge-accent"
							>
								<Headphones class="h-3 w-3" />
							</div>
						</div>
						<div class="absolute top-2 right-2 flex items-start gap-1">
							{#if album.primary_format}
								<div class="badge badge-sm badge-ghost">{album.primary_format}</div>
							{/if}
							<div>
								<ContextMenu items={getAlbumMenuItems(album)} position="end" size="xs" />
							</div>
						</div>
						{#if album.year}
							<div class="absolute bottom-2 left-2">
								<div class="badge badge-sm badge-ghost">{album.year}</div>
							</div>
						{/if}
						<div class="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
							<button
								class="btn btn-circle btn-sm btn-primary shadow-md"
								onclick={(e) => quickPlay(album, e)}
								aria-label="Play {album.name}"
							>
								{#if playingAlbumId === album.lidarr_album_id}
									<span class="loading loading-spinner loading-xs"></span>
								{:else}
									<Play class="h-4 w-4 fill-current" />
								{/if}
							</button>
						</div>
					</figure>

					<div class="card-body p-3">
						<h2 class="card-title text-sm line-clamp-2 min-h-[2.5rem]">{album.name}</h2>
						<div class="flex items-center justify-between">
							<p class="text-xs opacity-70 line-clamp-1 flex-1">{album.artist_name}</p>
							{#if album.total_size_bytes > 0}
								<span class="text-xs opacity-40 flex-shrink-0 ml-1"
									>{formatSize(album.total_size_bytes)}</span
								>
							{/if}
						</div>
					</div>
				</div>
			{/each}
		</div>

		{#if albums.length === 0}
			<div class="card bg-base-200 mt-4">
				<div class="card-body items-center text-center">
					<Headphones class="h-12 w-12 opacity-20" />
					<p class="text-lg opacity-60">No local files found</p>
					<p class="text-sm opacity-40">
						Make sure your music directory is mounted and configured in Settings.
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

<AddToPlaylistModal bind:this={playlistModalRef} />

<SourceAlbumModal
	bind:open={detailModalOpen}
	sourceType="local"
	album={selectedAlbum}
	onclose={handleDetailClose}
/>
