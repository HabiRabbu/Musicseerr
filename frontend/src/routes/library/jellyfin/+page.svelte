<script lang="ts">
	import { API } from '$lib/constants';
	import { api } from '$lib/api/client';
	import { getCoverUrl } from '$lib/utils/errorHandling';
	import { buildQueueItemsFromJellyfin } from '$lib/player/queueHelpers';
	import { launchJellyfinPlayback } from '$lib/player/launchJellyfinPlayback';
	import {
		getJellyfinSidebarCachedData,
		getJellyfinAlbumsListCachedData,
		isJellyfinSidebarCacheStale,
		isJellyfinAlbumsListCacheStale,
		setJellyfinAlbumsListCachedData,
		setJellyfinSidebarCachedData
	} from '$lib/utils/jellyfinLibraryCache';
	import {
		createLibraryController,
		type LibraryAdapter,
		type SidebarData
	} from '$lib/utils/libraryController.svelte';
	import LibraryPage from '$lib/components/LibraryPage.svelte';
	import type {
		JellyfinAlbumSummary,
		JellyfinPaginatedResponse,
		JellyfinLibraryStats,
		JellyfinTrackInfo
	} from '$lib/types';
	import { Tv } from 'lucide-svelte';

	const adapter: LibraryAdapter<JellyfinAlbumSummary> = {
		sourceType: 'jellyfin',

		getAlbumId: (a) => a.jellyfin_id,
		getAlbumName: (a) => a.name,
		getArtistName: (a) => a.artist_name,
		getAlbumMbid: (a) => a.musicbrainz_id ?? undefined,
		getAlbumImageUrl: (a) => a.image_url ?? null,
		getAlbumYear: (a) => a.year,

		async fetchAlbums({ limit, offset, sortBy, sortOrder, genre, search, signal }) {
			if (search) {
				const data = await api.get<{ albums?: JellyfinAlbumSummary[] }>(
					API.jellyfinLibrary.search(search),
					{ signal }
				);
				const items = data.albums ?? [];
				return { items, total: items.length };
			}
			const data: JellyfinPaginatedResponse = await api.get(
				API.jellyfinLibrary.albums(limit, offset, sortBy, genre, sortOrder),
				{ signal }
			);
			return { items: data.items, total: data.total };
		},

		async fetchSidebarData(signal, current) {
			const [recentRes, favRes, genreRes, statsRes] = await Promise.allSettled([
				api.get<JellyfinAlbumSummary[]>(API.jellyfinLibrary.recent(), { signal }),
				api.get<JellyfinAlbumSummary[]>(API.jellyfinLibrary.favorites(), { signal }),
				api.get<string[]>(API.jellyfinLibrary.genres(), { signal }),
				api.get<JellyfinLibraryStats>(API.jellyfinLibrary.stats(), { signal })
			]);
			const hasFreshData =
				recentRes.status === 'fulfilled' ||
				favRes.status === 'fulfilled' ||
				genreRes.status === 'fulfilled' ||
				statsRes.status === 'fulfilled';
			return {
				data: {
					recentAlbums:
						recentRes.status === 'fulfilled' ? recentRes.value : current.recentAlbums,
					favoriteAlbums:
						favRes.status === 'fulfilled' ? favRes.value : current.favoriteAlbums,
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
			const tracks: JellyfinTrackInfo[] = await api.get(
				API.jellyfinLibrary.albumTracks(album.jellyfin_id)
			);
			if (tracks.length === 0) return [];
			const sorted = [...tracks].sort((a, b) => a.track_number - b.track_number);
			return buildQueueItemsFromJellyfin(sorted, {
				albumId: album.musicbrainz_id || album.jellyfin_id,
				albumName: album.name,
				artistName: album.artist_name,
				coverUrl: album.image_url ?? null,
				artistId: album.artist_musicbrainz_id ?? undefined
			});
		},

		async launchPlayback(album, shuffle) {
			const tracks: JellyfinTrackInfo[] = await api.get(
				API.jellyfinLibrary.albumTracks(album.jellyfin_id)
			);
			if (tracks.length === 0) return;
			launchJellyfinPlayback(tracks, 0, shuffle, {
				albumId: album.musicbrainz_id || album.jellyfin_id,
				albumName: album.name,
				artistName: album.artist_name,
				coverUrl: getCoverUrl(album.image_url, album.musicbrainz_id || album.jellyfin_id)
			});
		},

		getAlbumsListCached: (key) => getJellyfinAlbumsListCachedData(key),
		setAlbumsListCached: (key, data) => setJellyfinAlbumsListCachedData(data, key),
		isAlbumsListCacheStale: (ts) => isJellyfinAlbumsListCacheStale(ts),
		getSidebarCached: () => {
			const c = getJellyfinSidebarCachedData();
			if (!c) return null;
			return {
				data: { ...c.data, favoriteAlbums: c.data.favoriteAlbums ?? [], genres: c.data.genres ?? [] } as SidebarData<JellyfinAlbumSummary>,
				timestamp: c.timestamp
			};
		},
		setSidebarCached: (data) =>
			setJellyfinSidebarCachedData({
				recentAlbums: data.recentAlbums,
				favoriteAlbums: data.favoriteAlbums,
				genres: data.genres,
				stats: data.stats as JellyfinLibraryStats | null
			}),
		isSidebarCacheStale: (ts) => isJellyfinSidebarCacheStale(ts),

		sortOptions: [
			{ value: 'SortName', label: 'Name' },
			{ value: 'DateCreated', label: 'Date Added' },
			{ value: 'ProductionYear', label: 'Year' }
		],
		defaultSortBy: 'SortName',
		ascValue: 'Ascending',
		descValue: 'Descending',
		getDefaultSortOrder: (field) => (field === 'SortName' ? 'Ascending' : 'Descending'),
		supportsGenres: true,
		supportsFavorites: true,
		supportsShuffle: true,
		errorMessage: "Couldn't reach Jellyfin"
	};

	const ctrl = createLibraryController(adapter);
</script>

<LibraryPage
	{ctrl}
	headerTitle="Jellyfin Library"
	emptyTitle="No albums found"
	emptyDescription="Make sure your Jellyfin server is configured and has music libraries."
>
	{#snippet headerIcon()}
		<Tv class="h-8 w-8 text-info" />
	{/snippet}

	{#snippet cardTopLeftBadge(_album)}
		<div class="badge badge-sm gap-1 badge-info">
			<Tv class="h-3 w-3" />
		</div>
	{/snippet}

	{#snippet emptyIcon()}
		<Tv class="h-12 w-12 opacity-20" />
	{/snippet}
</LibraryPage>
