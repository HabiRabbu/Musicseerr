<script lang="ts">
	import { API } from '$lib/constants';
	import { api } from '$lib/api/client';
	import { getCoverUrl } from '$lib/utils/errorHandling';
	import { buildQueueItemsFromLocal } from '$lib/player/queueHelpers';
	import { launchLocalPlayback } from '$lib/player/launchLocalPlayback';
	import {
		getLocalFilesSidebarCachedData,
		getLocalFilesAlbumsListCachedData,
		isLocalFilesSidebarCacheStale,
		isLocalFilesAlbumsListCacheStale,
		setLocalFilesAlbumsListCachedData,
		setLocalFilesSidebarCachedData
	} from '$lib/utils/localFilesCache';
	import {
		createLibraryController,
		type LibraryAdapter,
		type SidebarData
	} from '$lib/utils/libraryController.svelte';
	import LibraryPage from '$lib/components/LibraryPage.svelte';
	import type {
		LocalAlbumSummary,
		LocalPaginatedResponse,
		LocalStorageStats,
		LocalTrackInfo
	} from '$lib/types';
	import { Headphones } from 'lucide-svelte';

	function formatSize(bytes: number): string {
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
		return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
	}

	const adapter: LibraryAdapter<LocalAlbumSummary> = {
		sourceType: 'local',

		getAlbumId: (a) => a.lidarr_album_id,
		getAlbumName: (a) => a.name,
		getArtistName: (a) => a.artist_name,
		getAlbumMbid: (a) => a.musicbrainz_id ?? undefined,
		getAlbumImageUrl: (a) => a.cover_url ?? null,
		getAlbumYear: (a) => a.year,

		async fetchAlbums({ limit, offset, sortBy, sortOrder, search, signal }) {
			const url = API.local.albums(limit, offset, sortBy, search, sortOrder);
			const data: LocalPaginatedResponse = await api.get(url, { signal });
			return { items: data.items, total: data.total };
		},

		async fetchSidebarData(signal, current) {
			const [recentRes, statsRes] = await Promise.allSettled([
				api.get<LocalAlbumSummary[]>(API.local.recent(), { signal }),
				api.get<LocalStorageStats>(API.local.stats(), { signal })
			]);
			const hasFreshData = recentRes.status === 'fulfilled' || statsRes.status === 'fulfilled';
			return {
				data: {
					recentAlbums: recentRes.status === 'fulfilled' ? recentRes.value : current.recentAlbums,
					favoriteAlbums: [],
					genres: [],
					stats:
						statsRes.status === 'fulfilled'
							? (statsRes.value as unknown as Record<string, unknown>)
							: current.stats
				},
				hasFreshData
			};
		},

		async fetchAlbumQueueItems(album) {
			const tracks: LocalTrackInfo[] = await api.get(API.local.albumTracks(album.lidarr_album_id));
			if (tracks.length === 0) return [];
			const sorted = [...tracks].sort((a, b) => a.track_number - b.track_number);
			return buildQueueItemsFromLocal(sorted, {
				albumId: album.musicbrainz_id || String(album.lidarr_album_id),
				albumName: album.name,
				artistName: album.artist_name,
				coverUrl: album.cover_url ?? null,
				artistId: album.artist_mbid ?? undefined
			});
		},

		async launchPlayback(album, shuffle) {
			const tracks: LocalTrackInfo[] = await api.get(API.local.albumTracks(album.lidarr_album_id));
			if (tracks.length === 0) return;
			launchLocalPlayback(tracks, 0, shuffle, {
				albumId: album.musicbrainz_id || String(album.lidarr_album_id),
				albumName: album.name,
				artistName: album.artist_name,
				coverUrl: getCoverUrl(
					album.cover_url,
					album.musicbrainz_id || String(album.lidarr_album_id)
				)
			});
		},

		getAlbumsListCached: (key) => getLocalFilesAlbumsListCachedData(key),
		setAlbumsListCached: (key, data) => setLocalFilesAlbumsListCachedData(data, key),
		isAlbumsListCacheStale: (ts) => isLocalFilesAlbumsListCacheStale(ts),
		getSidebarCached: () => {
			const c = getLocalFilesSidebarCachedData();
			if (!c) return null;
			return {
				data: {
					recentAlbums: c.data.recentAlbums,
					favoriteAlbums: [],
					genres: [],
					stats: c.data.stats as unknown as Record<string, unknown> | null
				} as SidebarData<LocalAlbumSummary>,
				timestamp: c.timestamp
			};
		},
		setSidebarCached: (data) =>
			setLocalFilesSidebarCachedData({
				recentAlbums: data.recentAlbums,
				stats: data.stats as LocalStorageStats | null
			}),
		isSidebarCacheStale: (ts) => isLocalFilesSidebarCacheStale(ts),

		sortOptions: [
			{ value: 'name', label: 'Name' },
			{ value: 'date_added', label: 'Date Added' },
			{ value: 'year', label: 'Year' }
		],
		defaultSortBy: 'name',
		ascValue: 'asc',
		descValue: 'desc',
		getDefaultSortOrder: (field) => (field === 'name' ? 'asc' : 'desc'),
		supportsGenres: false,
		supportsFavorites: false,
		supportsShuffle: true,
		errorMessage: "Couldn't reach the local files service"
	};

	const ctrl = createLibraryController(adapter);
	const typedStats = $derived(ctrl.stats as LocalStorageStats | null);
</script>

<LibraryPage
	{ctrl}
	headerTitle="Local Files"
	recentLabel="Recently Added"
	contextMenuBackdrop
	emptyTitle="No local files found"
	emptyDescription="Make sure your music directory is mounted and configured in Settings."
>
	{#snippet headerIcon()}
		<Headphones class="h-8 w-8 text-accent" />
	{/snippet}

	{#snippet statsPanel()}
		{#if typedStats}
			<div class="stats stats-vertical sm:stats-horizontal shadow-sm w-full mb-6 bg-base-200">
				<div class="stat px-4 py-3">
					<div class="stat-title text-xs">Tracks</div>
					<div class="stat-value text-lg">{typedStats.total_tracks.toLocaleString()}</div>
				</div>
				<div class="stat px-4 py-3">
					<div class="stat-title text-xs">Artists</div>
					<div class="stat-value text-lg">{typedStats.total_artists}</div>
				</div>
				<div class="stat px-4 py-3">
					<div class="stat-title text-xs">Total Size</div>
					<div class="stat-value text-lg">{typedStats.total_size_human}</div>
				</div>
				<div class="stat px-4 py-3">
					<div class="stat-title text-xs">Disk Free</div>
					<div class="stat-value text-lg">{typedStats.disk_free_human}</div>
				</div>
				{#if Object.keys(typedStats.format_breakdown).length > 0}
					<div class="stat px-4 py-3">
						<div class="stat-title text-xs">Formats</div>
						<div class="flex gap-1 mt-1 flex-wrap">
							{#each Object.entries(typedStats.format_breakdown) as [fmt, info] (fmt)}
								<span class="badge badge-xs badge-ghost">{fmt}: {info.count}</span>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}
	{/snippet}

	{#snippet recentCardOverlay(album)}
		{#if album.primary_format}
			<div class="absolute bottom-1 right-1">
				<span class="badge badge-xs badge-ghost">{album.primary_format}</span>
			</div>
		{/if}
	{/snippet}

	{#snippet cardTopLeftBadge(_album)}
		<div class="badge badge-sm gap-1 badge-accent">
			<Headphones class="h-3 w-3" />
		</div>
	{/snippet}

	{#snippet cardTopRightExtra(album)}
		{#if album.primary_format}
			<div class="badge badge-sm badge-ghost">{album.primary_format}</div>
		{/if}
	{/snippet}

	{#snippet cardBottomLeft(album)}
		{#if album.year}
			<div class="badge badge-sm badge-ghost">{album.year}</div>
		{/if}
	{/snippet}

	{#snippet cardBodyExtra(album)}
		<div class="flex items-center justify-between">
			<p class="text-xs opacity-70 line-clamp-1 flex-1">{album.artist_name}</p>
			{#if album.total_size_bytes > 0}
				<span class="text-xs opacity-40 shrink-0 ml-1">{formatSize(album.total_size_bytes)}</span>
			{/if}
		</div>
	{/snippet}

	{#snippet emptyIcon()}
		<Headphones class="h-12 w-12 opacity-20" />
	{/snippet}
</LibraryPage>
