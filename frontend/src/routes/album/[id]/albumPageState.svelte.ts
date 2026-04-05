import { browser } from '$app/environment';
import { get } from 'svelte/store';
import { untrack } from 'svelte';
import type {
	AlbumBasicInfo,
	AlbumTracksInfo,
	MoreByArtistResponse,
	SimilarAlbumsResponse,
	YouTubeTrackLink,
	YouTubeLink,
	YouTubeQuotaStatus,
	JellyfinAlbumMatch,
	JellyfinTrackInfo,
	LocalAlbumMatch,
	LocalTrackInfo,
	NavidromeAlbumMatch,
	NavidromeTrackInfo,
	LastFmAlbumEnrichment
} from '$lib/types';
import { libraryStore } from '$lib/stores/library';
import { integrationStore } from '$lib/stores/integration';
import { isAbortError } from '$lib/utils/errorHandling';
import { extractServiceStatus } from '$lib/utils/serviceStatus';
import {
	albumBasicCache,
	albumDiscoveryCache,
	albumLastFmCache,
	albumTracksCache,
	albumYouTubeCache,
	albumSourceMatchCache
} from '$lib/utils/albumDetailCache';
import { hydrateDetailCacheEntry } from '$lib/utils/detailCacheHydration';
import { compareDiscTrack, getDiscTrackKey } from '$lib/player/queueHelpers';
import type { QueueItem } from '$lib/player/types';
import { launchJellyfinPlayback } from '$lib/player/launchJellyfinPlayback';
import { launchLocalPlayback } from '$lib/player/launchLocalPlayback';
import { launchNavidromePlayback } from '$lib/player/launchNavidromePlayback';
import type { MenuItem } from '$lib/components/ContextMenu.svelte';
import {
	fetchAlbumBasic,
	fetchAlbumTracks,
	fetchDiscovery,
	fetchYouTubeAlbumLink,
	fetchYouTubeTrackLinks,
	fetchJellyfinMatch,
	fetchLocalMatch,
	fetchNavidromeMatch,
	fetchLastFm
} from './albumFetchers';
import { buildRenderedTrackSections, buildSortedTrackMap } from './albumTrackResolvers';
import type { RenderedTrackSection } from './albumTrackResolvers';
import { createEventHandlers } from './albumEventHandlers';
import {
	playSourceTrack as playSourceTrackImpl,
	getTrackContextMenuItems as getTrackContextMenuItemsImpl,
	buildSourceCallbacks
} from './albumPlaybackHandlers';

export interface SourceCallbacks {
	onPlayAll: () => void;
	onShuffle: () => void;
	onAddAllToQueue: () => void;
	onPlayAllNext: () => void;
	onAddAllToPlaylist: () => void;
}

export function createAlbumPageState(albumIdGetter: () => string) {
	let album = $state<AlbumBasicInfo | null>(null);
	let tracksInfo = $state<AlbumTracksInfo | null>(null);
	let error = $state<string | null>(null);
	let loadingBasic = $state(true);
	let loadingTracks = $state(true);
	let tracksError = $state(false);
	let showToast = $state(false);
	let toastMessage = $state('Added to Library');
	let toastType = $state<'success' | 'error' | 'info' | 'warning'>('success');
	let requesting = $state(false);
	let showDeleteModal = $state(false);
	let showArtistRemovedModal = $state(false);
	let removedArtistName = $state('');
	let moreByArtist = $state<MoreByArtistResponse | null>(null);
	let similarAlbums = $state<SimilarAlbumsResponse | null>(null);
	let loadingDiscovery = $state(true);
	let trackLinks = $state<YouTubeTrackLink[]>([]);
	let albumLink = $state<YouTubeLink | null>(null);
	let quota = $state<YouTubeQuotaStatus | null>(null);
	let jellyfinMatch = $state<JellyfinAlbumMatch | null>(null);
	let localMatch = $state<LocalAlbumMatch | null>(null);
	let navidromeMatch = $state<NavidromeAlbumMatch | null>(null);
	let loadingJellyfin = $state(false);
	let loadingLocal = $state(false);
	let loadingNavidrome = $state(false);
	let lastfmEnrichment = $state<LastFmAlbumEnrichment | null>(null);
	let loadingLastfm = $state(true);
	let renderedTrackSections = $state<RenderedTrackSection[]>([]);
	let playlistModalRef = $state<{ open: (tracks: QueueItem[]) => void } | null>(null);
	let abortController: AbortController | null = null;

	// eslint-disable-next-line svelte/prefer-svelte-reactivity -- derived Map is recreated each time, reactive by nature
	const trackLinkMap = $derived(new Map(trackLinks.map((tl) => [getDiscTrackKey(tl), tl])));
	const jellyfinTracks = $derived([...(jellyfinMatch?.tracks ?? [])].sort(compareDiscTrack));
	const localTracks = $derived([...(localMatch?.tracks ?? [])].sort(compareDiscTrack));
	const navidromeTracks = $derived([...(navidromeMatch?.tracks ?? [])].sort(compareDiscTrack));
	const jellyfinTrackMap = $derived(buildSortedTrackMap(jellyfinMatch?.tracks ?? []));
	const localTrackMap = $derived(buildSortedTrackMap(localMatch?.tracks ?? []));
	const navidromeTrackMap = $derived(buildSortedTrackMap(navidromeMatch?.tracks ?? []));
	const inLibrary = $derived(
		libraryStore.isInLibrary(album?.musicbrainz_id) || album?.in_library || false
	);
	const isRequested = $derived(
		!!(album && !inLibrary && (album.requested || libraryStore.isRequested(album.musicbrainz_id)))
	);

	function resetState() {
		if (abortController) {
			abortController.abort();
			abortController = null;
		}
		album = null;
		tracksInfo = null;
		renderedTrackSections = [];
		error = null;
		loadingBasic = true;
		loadingTracks = true;
		tracksError = false;
		loadingDiscovery = true;
		moreByArtist = null;
		similarAlbums = null;
		trackLinks = [];
		albumLink = null;
		quota = null;
		jellyfinMatch = null;
		localMatch = null;
		navidromeMatch = null;
		loadingJellyfin = false;
		loadingLocal = false;
		loadingNavidrome = false;
		lastfmEnrichment = null;
		loadingLastfm = true;
	}

	function hydrateFromCache(albumId: string) {
		const refreshBasic = hydrateDetailCacheEntry({
			cache: albumBasicCache,
			cacheKey: albumId,
			onHydrate: (cached) => {
				album = cached;
				loadingBasic = false;
			}
		});
		const refreshTracks = hydrateDetailCacheEntry({
			cache: albumTracksCache,
			cacheKey: albumId,
			onHydrate: (cached) => {
				tracksInfo = cached;
				renderedTrackSections = buildRenderedTrackSections(cached.tracks);
				loadingTracks = false;
			}
		});
		const refreshDiscovery = hydrateDetailCacheEntry({
			cache: albumDiscoveryCache,
			cacheKey: albumId,
			onHydrate: (cached) => {
				moreByArtist = cached.moreByArtist;
				similarAlbums = cached.similarAlbums;
				loadingDiscovery = false;
			}
		});
		const refreshLastfm = hydrateDetailCacheEntry({
			cache: albumLastFmCache,
			cacheKey: albumId,
			onHydrate: (cached) => {
				lastfmEnrichment = cached;
				loadingLastfm = false;
			}
		});
		const refreshSourceMatch = (() => {
			const cached = albumSourceMatchCache.get(albumId);
			if (cached && !albumSourceMatchCache.isStale(cached.timestamp)) {
				jellyfinMatch = cached.data.jellyfin;
				localMatch = cached.data.local;
				navidromeMatch = cached.data.navidrome;
				loadingJellyfin = false;
				loadingLocal = false;
				loadingNavidrome = false;
				return false;
			}
			return true;
		})();
		return { refreshBasic, refreshTracks, refreshDiscovery, refreshLastfm, refreshSourceMatch };
	}

	async function doFetchBasic(albumId: string, signal: AbortSignal) {
		try {
			const result = await fetchAlbumBasic(albumId, signal);
			if (result) {
				album = result;
				extractServiceStatus(album);
				albumBasicCache.set(album, albumId);
			}
		} catch (e) {
			if (isAbortError(e)) return;
			if (!album) error = 'Error loading album';
		} finally {
			if (!signal.aborted) loadingBasic = false;
		}
	}

	async function doFetchTracks(albumId: string, signal: AbortSignal) {
		tracksError = false;
		try {
			const result = await fetchAlbumTracks(albumId, signal);
			if (result) {
				tracksInfo = result;
				renderedTrackSections = buildRenderedTrackSections(result.tracks);
				albumTracksCache.set(result, albumId);
			}
		} catch (e) {
			if (isAbortError(e)) return;
			if (!tracksInfo) tracksError = true;
		}
		if (!signal.aborted) loadingTracks = false;
	}

	async function doFetchDiscovery(albumId: string, signal: AbortSignal) {
		if (!album?.artist_id) {
			loadingDiscovery = false;
			return;
		}
		loadingDiscovery = true;
		try {
			const result = await fetchDiscovery(albumId, album.artist_id, signal);
			if (result.moreByArtist) moreByArtist = result.moreByArtist;
			if (result.similarAlbums) similarAlbums = result.similarAlbums;
			albumDiscoveryCache.set({ moreByArtist, similarAlbums }, albumId);
		} catch (e) {
			if (isAbortError(e)) return;
		} finally {
			if (!signal.aborted) loadingDiscovery = false;
		}
	}

	async function doFetchYouTube(albumId: string, signal: AbortSignal) {
		const cached = albumYouTubeCache.get(albumId);
		if (cached && !albumYouTubeCache.isStale(cached.timestamp)) {
			albumLink = cached.data.albumLink;
			trackLinks = cached.data.trackLinks;
			return;
		}
		try {
			const [linkData, tracksData] = await Promise.all([
				fetchYouTubeAlbumLink(albumId, signal),
				fetchYouTubeTrackLinks(albumId, signal)
			]);
			if (linkData) albumLink = linkData;
			if (tracksData) trackLinks = tracksData;
			albumYouTubeCache.set({ albumLink: linkData, trackLinks: tracksData ?? [] }, albumId);
		} catch (e) {
			if (isAbortError(e)) return;
		}
	}

	async function doFetchSourceMatch<T>(
		signal: AbortSignal,
		fetcher: () => Promise<T | null>,
		setter: (v: T | null) => void,
		loadingSetter: (v: boolean) => void,
		label: string,
		albumId: string,
		cacheField: 'jellyfin' | 'local' | 'navidrome'
	) {
		loadingSetter(true);
		try {
			const result = await fetcher();
			setter(result);
			const existing = albumSourceMatchCache.get(albumId)?.data ?? {
				jellyfin: null,
				local: null,
				navidrome: null
			};
			albumSourceMatchCache.set({ ...existing, [cacheField]: result }, albumId);
		} catch (e) {
			if (isAbortError(e)) return;
			console.error(`Failed to fetch ${label} album data:`, e);
		} finally {
			if (!signal.aborted) loadingSetter(false);
		}
	}

	async function doFetchLastFm(albumId: string, signal: AbortSignal) {
		if (!album) {
			loadingLastfm = false;
			return;
		}
		await integrationStore.ensureLoaded();
		if (!get(integrationStore).lastfm) {
			loadingLastfm = false;
			return;
		}
		loadingLastfm = true;
		try {
			const result = await fetchLastFm(
				albumId,
				{ artistName: album.artist_name, albumName: album.title },
				signal
			);
			if (result) {
				lastfmEnrichment = result;
				albumLastFmCache.set(result, albumId);
			}
		} catch (e) {
			if (isAbortError(e)) return;
			console.error('Failed to fetch Last.fm album data:', e);
		} finally {
			if (!signal.aborted) loadingLastfm = false;
		}
	}

	async function loadAlbum(albumId: string) {
		const { refreshBasic, refreshTracks, refreshDiscovery, refreshLastfm, refreshSourceMatch } =
			hydrateFromCache(albumId);
		if (abortController) abortController.abort();
		abortController = new AbortController();
		const signal = abortController.signal;

		// Fire source matches that only need albumId immediately (before basic loads)
		if (refreshSourceMatch) {
			void (async () => {
				try {
					await integrationStore.ensureLoaded();
					if (signal.aborted) return;
					const integrations = get(integrationStore);
					if (integrations.jellyfin)
						void doFetchSourceMatch(
							signal,
							() => fetchJellyfinMatch(albumId, signal),
							(v) => (jellyfinMatch = v),
							(v) => (loadingJellyfin = v),
							'Jellyfin',
							albumId,
							'jellyfin'
						);
					if (integrations.localfiles)
						void doFetchSourceMatch(
							signal,
							() => fetchLocalMatch(albumId, signal),
							(v) => (localMatch = v),
							(v) => (loadingLocal = v),
							'local',
							albumId,
							'local'
						);
				} catch {
					/* ignore integration loading errors */
				}
			})();
		}

		if (refreshBasic) {
			if (refreshTracks) void doFetchTracks(albumId, signal);
			void doFetchYouTube(albumId, signal);
			await doFetchBasic(albumId, signal);
		} else {
			void doFetchBasic(albumId, signal);
		}
		if (signal.aborted || !album) return;
		if (refreshTracks && !refreshBasic) void doFetchTracks(albumId, signal);
		if (refreshDiscovery) void doFetchDiscovery(albumId, signal);
		if (!refreshBasic) void doFetchYouTube(albumId, signal);
		if (refreshLastfm) void doFetchLastFm(albumId, signal);
		// Navidrome match needs album title/artist — fire after basic loads
		if (refreshSourceMatch) {
			void (async () => {
				try {
					await integrationStore.ensureLoaded();
					if (signal.aborted) return;
					const integrations = get(integrationStore);
					if (integrations.navidrome)
						void doFetchSourceMatch(
							signal,
							() =>
								fetchNavidromeMatch(
									albumId,
									{ albumTitle: album?.title, artistName: album?.artist_name },
									signal
								),
							(v) => (navidromeMatch = v),
							(v) => (loadingNavidrome = v),
							'Navidrome',
							albumId,
							'navidrome'
						);
				} catch {
					/* ignore integration loading errors */
				}
			})();
		}
	}

	$effect(() => {
		const albumId = albumIdGetter();
		if (!browser || !albumId) return;
		untrack(() => {
			resetState();
			void loadAlbum(albumId);
		});
		return () => {
			if (abortController) {
				abortController.abort();
				abortController = null;
			}
		};
	});

	const eventHandlers = createEventHandlers({
		getAlbum: () => album,
		setAlbum: (a) => (album = a),
		getAlbumId: albumIdGetter,
		albumBasicCacheSet: (data, key) => albumBasicCache.set(data, key),
		setTrackLinks: (tl) => (trackLinks = tl),
		getTrackLinks: () => trackLinks,
		setAlbumLink: (l) => (albumLink = l),
		setQuota: (q) => (quota = q),
		setRequesting: (v) => (requesting = v),
		getRequesting: () => requesting,
		setShowDeleteModal: (v) => (showDeleteModal = v),
		setShowArtistRemovedModal: (v) => (showArtistRemovedModal = v),
		setRemovedArtistName: (v) => (removedArtistName = v),
		setToast: (msg, type) => {
			toastMessage = msg;
			toastType = type;
		},
		setShowToast: (v) => (showToast = v)
	});

	function retryTracks(): void {
		loadingTracks = true;
		tracksError = false;
		const signal = abortController?.signal ?? new AbortController().signal;
		void doFetchTracks(albumIdGetter(), signal);
	}

	const tracksGetters = {
		jellyfin: () => jellyfinTracks,
		local: () => localTracks,
		navidrome: () => navidromeTracks
	};
	const albumGetter = () => album;
	const playlistRefGetter = () => playlistModalRef;

	function playSourceTrack(
		source: 'jellyfin' | 'local' | 'navidrome',
		trackPosition: number,
		discNumber: number,
		title: string
	): void {
		if (!album) return;
		playSourceTrackImpl(
			source,
			trackPosition,
			discNumber,
			title,
			album,
			jellyfinMatch,
			localMatch,
			navidromeMatch
		);
	}

	function getTrackContextMenuItems(
		track: { position: number; disc_number?: number | null; title: string },
		resolvedLocal: LocalTrackInfo | null,
		resolvedJellyfin: JellyfinTrackInfo | null,
		resolvedNavidrome: NavidromeTrackInfo | null = null
	): MenuItem[] {
		if (!album) return [];
		return getTrackContextMenuItemsImpl(
			track,
			album,
			resolvedLocal,
			resolvedJellyfin,
			resolvedNavidrome,
			playlistModalRef
		);
	}

	const jellyfinCallbacks: SourceCallbacks = buildSourceCallbacks(
		() => jellyfinMatch,
		launchJellyfinPlayback,
		'jellyfin',
		albumGetter,
		tracksGetters,
		playlistRefGetter
	);
	const localCallbacks: SourceCallbacks = buildSourceCallbacks(
		() => localMatch,
		launchLocalPlayback,
		'local',
		albumGetter,
		tracksGetters,
		playlistRefGetter
	);
	const navidromeCallbacks: SourceCallbacks = buildSourceCallbacks(
		() => navidromeMatch,
		launchNavidromePlayback,
		'navidrome',
		albumGetter,
		tracksGetters,
		playlistRefGetter
	);

	return {
		get album() {
			return album;
		},
		get tracksInfo() {
			return tracksInfo;
		},
		get error() {
			return error;
		},
		get loadingBasic() {
			return loadingBasic;
		},
		get loadingTracks() {
			return loadingTracks;
		},
		get tracksError() {
			return tracksError;
		},
		get showToast() {
			return showToast;
		},
		set showToast(v: boolean) {
			showToast = v;
		},
		get toastMessage() {
			return toastMessage;
		},
		get toastType() {
			return toastType;
		},
		get requesting() {
			return requesting;
		},
		get showDeleteModal() {
			return showDeleteModal;
		},
		set showDeleteModal(v: boolean) {
			showDeleteModal = v;
		},
		get showArtistRemovedModal() {
			return showArtistRemovedModal;
		},
		set showArtistRemovedModal(v: boolean) {
			showArtistRemovedModal = v;
		},
		get removedArtistName() {
			return removedArtistName;
		},
		get moreByArtist() {
			return moreByArtist;
		},
		get similarAlbums() {
			return similarAlbums;
		},
		get loadingDiscovery() {
			return loadingDiscovery;
		},
		get trackLinks() {
			return trackLinks;
		},
		get albumLink() {
			return albumLink;
		},
		get quota() {
			return quota;
		},
		get jellyfinMatch() {
			return jellyfinMatch;
		},
		get localMatch() {
			return localMatch;
		},
		get navidromeMatch() {
			return navidromeMatch;
		},
		get loadingJellyfin() {
			return loadingJellyfin;
		},
		get loadingLocal() {
			return loadingLocal;
		},
		get loadingNavidrome() {
			return loadingNavidrome;
		},
		get lastfmEnrichment() {
			return lastfmEnrichment;
		},
		get loadingLastfm() {
			return loadingLastfm;
		},
		get renderedTrackSections() {
			return renderedTrackSections;
		},
		get trackLinkMap() {
			return trackLinkMap;
		},
		get jellyfinTracks() {
			return jellyfinTracks;
		},
		get localTracks() {
			return localTracks;
		},
		get navidromeTracks() {
			return navidromeTracks;
		},
		get jellyfinTrackMap() {
			return jellyfinTrackMap;
		},
		get localTrackMap() {
			return localTrackMap;
		},
		get navidromeTrackMap() {
			return navidromeTrackMap;
		},
		get inLibrary() {
			return inLibrary;
		},
		get isRequested() {
			return isRequested;
		},
		get playlistModalRef() {
			return playlistModalRef;
		},
		set playlistModalRef(v) {
			playlistModalRef = v;
		},
		jellyfinCallbacks,
		localCallbacks,
		navidromeCallbacks,
		...eventHandlers,
		retryTracks,
		playSourceTrack,
		getTrackContextMenuItems
	};
}
