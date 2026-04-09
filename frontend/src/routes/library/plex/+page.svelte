<script lang="ts">
	import { API } from '$lib/constants';
	import { api } from '$lib/api/client';
	import { getCoverUrl } from '$lib/utils/errorHandling';
	import { buildQueueItemsFromPlex } from '$lib/player/queueHelpers';
	import { launchPlexPlayback } from '$lib/player/launchPlexPlayback';
	import { resetPlexScrobblePreference } from '$lib/player/plexPlaybackApi';
	import {
		getPlexSidebarCachedData,
		getPlexAlbumsListCachedData,
		isPlexSidebarCacheStale,
		isPlexAlbumsListCacheStale,
		setPlexAlbumsListCachedData,
		setPlexSidebarCachedData
	} from '$lib/utils/plexLibraryCache';
	import {
		createLibraryController,
		type LibraryAdapter,
		type SidebarData
	} from '$lib/utils/libraryController.svelte';
	import LibraryPage from '$lib/components/LibraryPage.svelte';
	import PlexIcon from '$lib/components/PlexIcon.svelte';
	import type {
		PlexAlbumSummary,
		PlexAlbumDetail,
		PlexPaginatedResponse,
		PlexSearchResponse,
		PlexLibraryStats,
		PlexTrackInfo,
		PlexConnectionSettings
	} from '$lib/types';

	let scrobbleEnabled = $state(true);
	let scrobbleLoading = $state(false);

	$effect(() => {
		(async () => {
			try {
				const settings = await api.get<PlexConnectionSettings>(API.settingsPlex());
				scrobbleEnabled = settings.scrobble_to_plex ?? false;
			} catch {
				scrobbleEnabled = false;
			}
		})();
	});

	async function toggleScrobble() {
		scrobbleLoading = true;
		try {
			const settings = await api.get<PlexConnectionSettings>(API.settingsPlex());
			settings.scrobble_to_plex = !scrobbleEnabled;
			await api.global.put(API.settingsPlex(), settings);
			scrobbleEnabled = settings.scrobble_to_plex;
			resetPlexScrobblePreference();
		} catch (e) {
			console.warn('[Plex] Failed to toggle scrobble setting:', e);
		} finally {
			scrobbleLoading = false;
		}
	}

	const adapter: LibraryAdapter<PlexAlbumSummary> = {
		sourceType: 'plex',

		getAlbumId: (a) => a.plex_id,
		getAlbumName: (a) => a.name,
		getArtistName: (a) => a.artist_name,
		getAlbumMbid: (a) => a.musicbrainz_id ?? undefined,
		getAlbumImageUrl: (a) => a.image_url ?? null,
		getAlbumYear: (a) => a.year ?? null,

		async fetchAlbums({ limit, offset, sortBy, sortOrder, genre, search, signal }) {
			if (search) {
				const data: PlexSearchResponse = await api.get(API.plexLibrary.search(search), {
					signal
				});
				const items = data.albums ?? [];
				return { items, total: items.length };
			}
			const data: PlexPaginatedResponse = await api.get(
				API.plexLibrary.albums(limit, offset, sortBy, genre || undefined, sortOrder),
				{ signal }
			);
			return { items: data.items, total: data.total };
		},

		async fetchSidebarData(signal, current) {
			const [recentRes, genreRes, statsRes] = await Promise.allSettled([
				api.get<PlexAlbumSummary[]>(API.plexLibrary.recent(), { signal }),
				api.get<string[]>(API.plexLibrary.genres(), { signal }),
				api.get<PlexLibraryStats>(API.plexLibrary.stats(), { signal })
			]);
			const hasFreshData =
				recentRes.status === 'fulfilled' ||
				genreRes.status === 'fulfilled' ||
				statsRes.status === 'fulfilled';
			return {
				data: {
					recentAlbums: recentRes.status === 'fulfilled' ? recentRes.value : current.recentAlbums,
					favoriteAlbums: current.favoriteAlbums,
					genres: genreRes.status === 'fulfilled' ? genreRes.value : current.genres,
					stats:
						statsRes.status === 'fulfilled'
							? (statsRes.value as unknown as Record<string, unknown>)
							: current.stats
				},
				hasFreshData
			};
		},

		async fetchAlbumQueueItems(album) {
			const detail: PlexAlbumDetail = await api.get(
				API.plexLibrary.albumDetail(album.plex_id)
			);
			const tracks: PlexTrackInfo[] = detail.tracks ?? [];
			if (tracks.length === 0) return [];
			const sorted = [...tracks].sort((a, b) => a.track_number - b.track_number);
			return buildQueueItemsFromPlex(sorted, {
				albumId: album.musicbrainz_id || album.plex_id,
				albumName: album.name,
				artistName: album.artist_name,
				coverUrl: album.image_url ?? null,
				artistId: album.artist_musicbrainz_id ?? undefined
			});
		},

		async launchPlayback(album, shuffle) {
			const detail: PlexAlbumDetail = await api.get(
				API.plexLibrary.albumDetail(album.plex_id)
			);
			const tracks: PlexTrackInfo[] = detail.tracks ?? [];
			if (tracks.length === 0) return;
			launchPlexPlayback(tracks, 0, shuffle, {
				albumId: album.musicbrainz_id || album.plex_id,
				albumName: album.name,
				artistName: album.artist_name,
				coverUrl: getCoverUrl(album.image_url ?? null, album.musicbrainz_id || album.plex_id)
			});
		},

		getAlbumsListCached: (key) => getPlexAlbumsListCachedData(key),
		setAlbumsListCached: (key, data) => setPlexAlbumsListCachedData(data, key),
		isAlbumsListCacheStale: (ts) => isPlexAlbumsListCacheStale(ts),
		getSidebarCached: () => {
			const c = getPlexSidebarCachedData();
			if (!c) return null;
			return {
				data: {
					...c.data,
					favoriteAlbums: [],
					genres: c.data.genres ?? []
				} as SidebarData<PlexAlbumSummary>,
				timestamp: c.timestamp
			};
		},
		setSidebarCached: (data) =>
			setPlexSidebarCachedData({
				recentAlbums: data.recentAlbums,
				genres: data.genres,
				stats: data.stats as PlexLibraryStats | null
			}),
		isSidebarCacheStale: (ts) => isPlexSidebarCacheStale(ts),

		sortOptions: [
			{ value: 'name', label: 'Name' },
			{ value: 'date_added', label: 'Date Added' },
			{ value: 'year', label: 'Year' }
		],
		defaultSortBy: 'name',
		ascValue: 'asc',
		descValue: 'desc',
		getDefaultSortOrder: (field) => (field === 'name' ? 'asc' : 'desc'),
		supportsGenres: true,
		supportsFavorites: false,
		supportsShuffle: true,
		errorMessage: "Couldn't reach Plex"
	};

	const ctrl = createLibraryController(adapter);
</script>

<LibraryPage
	{ctrl}
	headerTitle="Plex Library"
	contextMenuBackdrop
	emptyTitle="No albums found"
	emptyDescription="Make sure your Plex server is configured and has music libraries."
>
	{#snippet headerIcon()}
		<span style="color: rgb(var(--brand-plex));">
			<PlexIcon class="h-8 w-8" />
		</span>
	{/snippet}

	{#snippet statsPanel()}
		<div class="flex items-center gap-2 mb-4">
			<label class="label cursor-pointer gap-2 px-0">
				<span class="label-text text-sm opacity-70">Scrobble to Plex</span>
				<input
					type="checkbox"
					class="toggle toggle-sm"
					style="--tglbg: rgb(var(--brand-plex));"
					checked={scrobbleEnabled}
					disabled={scrobbleLoading}
					onchange={toggleScrobble}
				/>
			</label>
		</div>
	{/snippet}

	{#snippet cardTopLeftBadge(album)}
		<div class="badge badge-sm gap-1" style="background-color: rgb(var(--brand-plex)); color: #000;">
			<PlexIcon class="h-3 w-3" />
		</div>
		{#if !album.musicbrainz_id}
			<div
				class="badge badge-sm badge-warning gap-1 opacity-80"
				title="Not matched in Lidarr — search only"
			>
				?
			</div>
		{/if}
	{/snippet}

	{#snippet emptyIcon()}
		<PlexIcon class="h-12 w-12 opacity-20" />
	{/snippet}
</LibraryPage>
