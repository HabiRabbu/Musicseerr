<script lang="ts">
	import { run } from 'svelte/legacy';

	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import type {
		ArtistInfo,
		ArtistReleases,
		SimilarArtistsResponse,
		TopSongsResponse,
		TopAlbumsResponse,
		LastFmArtistEnrichment,
		ReleaseGroup
	} from '$lib/types';
	import { colors } from '$lib/colors';
	import ArtistHeaderSkeleton from '$lib/components/ArtistHeaderSkeleton.svelte';
	import AlbumGridSkeleton from '$lib/components/AlbumGridSkeleton.svelte';
	import ReleaseList from '$lib/components/ReleaseList.svelte';
	import Toast from '$lib/components/Toast.svelte';
	import ArtistHero from '$lib/components/ArtistHero.svelte';
	import ArtistDescription from '$lib/components/ArtistDescription.svelte';
	import SimilarArtistsCarousel from '$lib/components/SimilarArtistsCarousel.svelte';
	import TopSongsList from '$lib/components/TopSongsList.svelte';
	import TopAlbumsList from '$lib/components/TopAlbumsList.svelte';
	import ArtistRemovedModal from '$lib/components/ArtistRemovedModal.svelte';
	import SourceSwitcher from '$lib/components/SourceSwitcher.svelte';
	import LastFmEnrichment from '$lib/components/LastFmEnrichment.svelte';
	import LibraryAlbumsCarousel from '$lib/components/LibraryAlbumsCarousel.svelte';
	import ArtistPageToc from '$lib/components/ArtistPageToc.svelte';
	import { requestAlbum } from '$lib/utils/albumRequest';
	import { getArtistDiscoveryCache, setArtistDiscoveryCache } from '$lib/stores/discoveryCache';
	import { integrationStore } from '$lib/stores/integration';
	import { musicSourceStore, type MusicSource } from '$lib/stores/musicSource';
	import { monitoredArtistsStore } from '$lib/stores/monitoredArtists';
	import {
		artistBasicCache,
		artistExtendedCache,
		artistLastFmCache
	} from '$lib/utils/artistDetailCache';
	import { hydrateDetailCacheEntry } from '$lib/utils/detailCacheHydration';
	import { isAbortError } from '$lib/utils/errorHandling';
	import { api } from '$lib/api/client';
	import { extractServiceStatus } from '$lib/utils/serviceStatus';

	interface Props {
		data: { artistId: string };
	}

	let { data }: Props = $props();

	let artist: ArtistInfo | null = $state(null);
	let loadingBasic = $state(true);
	let loadingExtended = $state(true);
	let refreshingArtist = $state(false);
	let error: string | null = $state(null);
	let showToast = $state(false);
	let toastMessage = 'Added to Library';
	let showArtistRemovedModal = $state(false);
	let removedArtistName = $state('');
	let requestingAlbums = $state(new Set<string>());
	let abortController: AbortController | null = null;
	let albumsCollapsed = $state(false);
	let epsCollapsed = $state(false);
	let singlesCollapsed = $state(false);
	let loadingMoreReleases = $state(false);
	let currentOffset = 50;
	let hasMoreReleases = $state(false);
	let totalReleaseCount = $state(0);
	let loadedReleaseCount = $state(0);
	const BATCH_SIZE = 50;
	let fetchMoreTimeoutId: ReturnType<typeof setTimeout> | null = null;

	let similarArtists: SimilarArtistsResponse | null = $state(null);
	let topSongs: TopSongsResponse | null = $state(null);
	let topAlbums: TopAlbumsResponse | null = $state(null);
	let loadingSimilar = $state(true);
	let loadingTopSongs = $state(true);
	let loadingTopAlbums = $state(true);

	let lastfmEnrichment: LastFmArtistEnrichment | null = $state(null);
	let loadingLastfm = $state(true);

	type ArtistReleasePaginationState = {
		loadedReleaseCount: number;
		hasMoreReleases: boolean;
		totalReleaseCount: number;
		currentOffset: number;
	};

	type ArtistReleaseSortingResult = {
		artistInfo: ArtistInfo;
		pagination: ArtistReleasePaginationState;
	};

	type ArtistTocSection = {
		id: string;
		label: string;
	};

	let tocSections: ArtistTocSection[] = $state([]);

	function sortReleasesByYear(releases: ArtistInfo['albums']) {
		return [...releases].sort((a, b) => {
			const yearA = a.year;
			const yearB = b.year;
			if (yearA === null || yearA === undefined) return 1;
			if (yearB === null || yearB === undefined) return -1;
			return yearB - yearA;
		});
	}

	function applyArtistReleaseSorting(artistInfo: ArtistInfo): ArtistReleaseSortingResult {
		const sortedArtistInfo: ArtistInfo = {
			...artistInfo,
			albums: sortReleasesByYear(artistInfo.albums),
			singles: sortReleasesByYear(artistInfo.singles),
			eps: sortReleasesByYear(artistInfo.eps)
		};
		const nextLoadedReleaseCount =
			sortedArtistInfo.albums.length +
			sortedArtistInfo.singles.length +
			sortedArtistInfo.eps.length;

		const releaseGroupCount = sortedArtistInfo.release_group_count || 0;
		const nextHasMoreReleases =
			releaseGroupCount > nextLoadedReleaseCount ||
			(releaseGroupCount === 0 && nextLoadedReleaseCount >= BATCH_SIZE);
		const nextTotalReleaseCount = nextHasMoreReleases
			? releaseGroupCount || nextLoadedReleaseCount
			: nextLoadedReleaseCount;
		const nextOffset = nextHasMoreReleases ? BATCH_SIZE : 0;

		return {
			artistInfo: sortedArtistInfo,
			pagination: {
				loadedReleaseCount: nextLoadedReleaseCount,
				hasMoreReleases: nextHasMoreReleases,
				totalReleaseCount: nextTotalReleaseCount,
				currentOffset: nextOffset
			}
		};
	}

	function applyArtistReleasePaginationState(pagination: ArtistReleasePaginationState): void {
		loadedReleaseCount = pagination.loadedReleaseCount;
		hasMoreReleases = pagination.hasMoreReleases;
		totalReleaseCount = pagination.totalReleaseCount;
		currentOffset = pagination.currentOffset;
	}

	function hydrateFromCache(artistId: string): {
		refreshBasic: boolean;
		refreshExtended: boolean;
		refreshLastfm: boolean;
	} {
		const refreshBasic = hydrateDetailCacheEntry({
			cache: artistBasicCache,
			cacheKey: artistId,
			onHydrate: (cachedArtist) => {
				const sortedResult = applyArtistReleaseSorting(cachedArtist);
				artist = sortedResult.artistInfo;
				applyArtistReleasePaginationState(sortedResult.pagination);
				loadingBasic = false;
			}
		});

		const refreshExtended = artist
			? hydrateDetailCacheEntry({
					cache: artistExtendedCache,
					cacheKey: artistId,
					onHydrate: (cachedExtended) => {
						artist = {
							...artist!,
							description: cachedExtended.description,
							image: cachedExtended.image
						};
						loadingExtended = false;
					}
				})
			: true;

		const refreshLastfm = hydrateDetailCacheEntry({
			cache: artistLastFmCache,
			cacheKey: artistId,
			onHydrate: (cachedLastFmEnrichment) => {
				lastfmEnrichment = cachedLastFmEnrichment;
				loadingLastfm = false;
			}
		});

		return { refreshBasic, refreshExtended, refreshLastfm };
	}

	async function fetchArtist(force = false) {
		const hasPendingMonitor = !!monitoredArtistsStore.getPendingMonitor(data.artistId);
		const {
			refreshBasic: cacheRefreshBasic,
			refreshExtended,
			refreshLastfm
		} = force
			? { refreshBasic: true, refreshExtended: true, refreshLastfm: true }
			: hydrateFromCache(data.artistId);
		const staleLibraryFlags = artist && artist.in_library && !artist.in_lidarr;
		const refreshBasic = cacheRefreshBasic || hasPendingMonitor || !!staleLibraryFlags;

		if (!artist || refreshBasic) loadingBasic = true;
		if (!artist || refreshExtended) loadingExtended = true;
		if (refreshLastfm) loadingLastfm = true;
		if (!similarArtists && !topSongs && !topAlbums) {
			loadingSimilar = true;
			loadingTopSongs = true;
			loadingTopAlbums = true;
		}
		error = null;

		if (abortController) {
			abortController.abort();
		}
		abortController = new AbortController();

		// Fire discovery immediately — only needs artistId (from URL), not basic data
		const sourceLoadPromise = musicSourceStore.load();
		const currentController = abortController;
		sourceLoadPromise.then(() => {
			if (currentController.signal.aborted) return;
			void fetchDiscoveryData(musicSourceStore.getPageSource('artist'));
		});

		const forceBasic = force || !!staleLibraryFlags || hasPendingMonitor;
		if (refreshBasic || !artist) {
			await Promise.all([fetchBasicInfo(forceBasic), sourceLoadPromise]);
		} else {
			await sourceLoadPromise;
		}

		if (artist) {
			const secondaryPromises: Promise<void>[] = [];
			if (refreshExtended) {
				secondaryPromises.push(fetchExtendedInfo(force, artist));
			}
			if (refreshLastfm) {
				secondaryPromises.push(fetchLastFmEnrichment());
			}

			// Start background release loading after all other data has settled
			if (hasMoreReleases) {
				Promise.allSettled(secondaryPromises).then(() => {
					if (abortController && !abortController.signal.aborted) {
						void fetchMoreReleases();
					}
				});
			}
		}
	}

	async function fetchBasicInfo(force = false) {
		try {
			const now = Date.now();
			const cacheBuster = force ? `?t=${now}` : '';
			const artistData: ArtistInfo = await api.get(
				`/api/v1/artists/${data.artistId}${cacheBuster}`,
				{
					signal: abortController?.signal,
					cache: force ? 'no-cache' : 'default'
				}
			);

			if (artistData) {
				extractServiceStatus(artistData);
				const sortedResult = applyArtistReleaseSorting(artistData);
				artist = sortedResult.artistInfo;
				applyArtistReleasePaginationState(sortedResult.pagination);
				artistBasicCache.set(artist, data.artistId);
				if (artistData.in_lidarr) {
					monitoredArtistsStore.removePendingMonitor(data.artistId);
				}
			}
		} catch (e) {
			if (isAbortError(e)) {
				return;
			}
			error = 'Error loading artist';
		} finally {
			loadingBasic = false;
		}
	}

	async function fetchExtendedInfo(force = false, artistRef: ArtistInfo) {
		try {
			const now = Date.now();
			const cacheBuster = force ? `?t=${now}` : '';
			const extendedInfo = await api.get<{ description?: string; image?: string }>(
				`/api/v1/artists/${data.artistId}/extended${cacheBuster}`,
				{
					signal: abortController?.signal,
					cache: force ? 'no-cache' : 'default'
				}
			);

			if (artist && artist === artistRef) {
				artist.description = extendedInfo.description;
				artist.image = extendedInfo.image;
				artist = artist;
				artistExtendedCache.set(
					{
						description: extendedInfo.description ?? null,
						image: extendedInfo.image ?? null
					},
					data.artistId
				);
				artistBasicCache.set(artist, data.artistId);
			}
		} catch (e) {
			if (isAbortError(e)) {
				return;
			}
		} finally {
			loadingExtended = false;
		}
	}

	async function fetchDiscoveryData(sourceOverride?: MusicSource) {
		const activeSource = sourceOverride ?? musicSourceStore.getPageSource('artist');
		const cacheKey = `${data.artistId}:${activeSource}`;
		const cached = getArtistDiscoveryCache(cacheKey);
		if (cached) {
			similarArtists = cached.similarArtists;
			topSongs = cached.topSongs;
			topAlbums = cached.topAlbums;
			loadingSimilar = false;
			loadingTopSongs = false;
			loadingTopAlbums = false;
			return;
		}

		similarArtists = null;
		topSongs = null;
		topAlbums = null;
		loadingSimilar = true;
		loadingTopSongs = true;
		loadingTopAlbums = true;

		const signal = abortController?.signal;

		const similarPromise = api
			.get<SimilarArtistsResponse>(
				`/api/v1/artists/${data.artistId}/similar?count=15&source=${activeSource}`,
				{ signal }
			)
			.then((data) => {
				similarArtists = data;
			})
			.catch((e) => {
				if (!isAbortError(e)) {
					/* ignore */
				}
			})
			.finally(() => {
				loadingSimilar = false;
			});

		const songsPromise = api
			.get<TopSongsResponse>(
				`/api/v1/artists/${data.artistId}/top-songs?count=10&source=${activeSource}`,
				{ signal }
			)
			.then((data) => {
				topSongs = data;
			})
			.catch((e) => {
				if (!isAbortError(e)) {
					/* ignore */
				}
			})
			.finally(() => {
				loadingTopSongs = false;
			});

		const albumsPromise = api
			.get<TopAlbumsResponse>(
				`/api/v1/artists/${data.artistId}/top-albums?count=10&source=${activeSource}`,
				{ signal }
			)
			.then((data) => {
				topAlbums = data;
			})
			.catch((e) => {
				if (!isAbortError(e)) {
					/* ignore */
				}
			})
			.finally(() => {
				loadingTopAlbums = false;
			});

		await Promise.all([similarPromise, songsPromise, albumsPromise]);

		const sa = similarArtists as SimilarArtistsResponse | null;
		const ts = topSongs as TopSongsResponse | null;
		const ta = topAlbums as TopAlbumsResponse | null;
		if (sa?.similar_artists?.length || ts?.songs?.length || ta?.albums?.length) {
			setArtistDiscoveryCache(cacheKey, { similarArtists, topSongs, topAlbums });
		}
	}

	async function fetchLastFmEnrichment() {
		if (!artist) {
			loadingLastfm = false;
			return;
		}
		await integrationStore.ensureLoaded();
		if (!$integrationStore.lastfm) {
			loadingLastfm = false;
			return;
		}
		loadingLastfm = true;
		try {
			const params = new URLSearchParams({ artist_name: artist.name });
			lastfmEnrichment = await api.get<LastFmArtistEnrichment>(
				`/api/v1/artists/${data.artistId}/lastfm?${params.toString()}`,
				{ signal: abortController?.signal }
			);
			if (lastfmEnrichment) {
				artistLastFmCache.set(lastfmEnrichment, data.artistId);
			}
		} catch (e) {
			if (isAbortError(e)) return;
		} finally {
			loadingLastfm = false;
		}
	}

	function handleSourceChange(source: MusicSource) {
		similarArtists = null;
		topSongs = null;
		topAlbums = null;
		loadingSimilar = true;
		loadingTopSongs = true;
		loadingTopAlbums = true;
		fetchDiscoveryData(source);
	}

	async function fetchMoreReleases() {
		if (!artist || loadingMoreReleases || !hasMoreReleases) {
			return;
		}

		loadingMoreReleases = true;

		try {
			const url = `/api/v1/artists/${data.artistId}/releases?offset=${currentOffset}&limit=${BATCH_SIZE}`;
			const moreReleases: ArtistReleases = await api.get(url, { signal: abortController?.signal });

			if (artist) {
				const newAlbums = moreReleases.albums.filter(
					(a: ReleaseGroup) =>
						!artist!.albums.some((existing: ReleaseGroup) => existing.id === a.id)
				);
				const newSingles = moreReleases.singles.filter(
					(s: ReleaseGroup) =>
						!artist!.singles.some((existing: ReleaseGroup) => existing.id === s.id)
				);
				const newEps = moreReleases.eps.filter(
					(e: ReleaseGroup) => !artist!.eps.some((existing: ReleaseGroup) => existing.id === e.id)
				);

				artist.albums = sortReleasesByYear([...artist.albums, ...newAlbums]);
				artist.singles = sortReleasesByYear([...artist.singles, ...newSingles]);
				artist.eps = sortReleasesByYear([...artist.eps, ...newEps]);
				artist = artist;

				currentOffset += BATCH_SIZE;
				hasMoreReleases = moreReleases.has_more;
				loadedReleaseCount = artist.albums.length + artist.singles.length + artist.eps.length;

				if (hasMoreReleases) {
					if (fetchMoreTimeoutId) clearTimeout(fetchMoreTimeoutId);
					fetchMoreTimeoutId = setTimeout(() => fetchMoreReleases(), 500);
				}
			}
		} catch (e) {
			if (isAbortError(e)) {
				return;
			}
			hasMoreReleases = false;
		} finally {
			loadingMoreReleases = false;
		}
	}

	let currentArtistId: string | null = $state(null);

	function resetState() {
		artist = null;
		loadingBasic = true;
		loadingExtended = true;
		loadingSimilar = true;
		loadingTopSongs = true;
		loadingTopAlbums = true;
		loadingLastfm = true;
		similarArtists = null;
		topSongs = null;
		topAlbums = null;
		lastfmEnrichment = null;
		error = null;
		currentOffset = 50;
		hasMoreReleases = false;
		loadedReleaseCount = 0;
		if (abortController) {
			abortController.abort();
			abortController = null;
		}
	}

	async function handleRefreshClick() {
		refreshingArtist = true;
		try {
			await fetchArtist(true);
		} finally {
			refreshingArtist = false;
		}
	}

	onMount(() => {
		if (browser) {
			const handleRefresh = () => fetchArtist(true);
			window.addEventListener('artist-refresh', handleRefresh);

			return () => {
				window.removeEventListener('artist-refresh', handleRefresh);
			};
		}
	});

	onDestroy(() => {
		if (abortController) {
			abortController.abort();
			abortController = null;
		}
		if (fetchMoreTimeoutId) {
			clearTimeout(fetchMoreTimeoutId);
			fetchMoreTimeoutId = null;
		}
	});

	async function handleRequest(albumId: string, albumTitle?: string) {
		requestingAlbums.add(albumId);
		requestingAlbums = requestingAlbums;

		try {
			const result = await requestAlbum(albumId, {
				artist: artist?.name,
				album: albumTitle
			});

			if (result.success && artist) {
				const allReleases = [...artist.albums, ...artist.singles, ...artist.eps];
				const release = allReleases.find((rg) => rg.id === albumId);
				if (release) {
					release.requested = true;
					artist = artist;
					artistBasicCache.set(artist, data.artistId);
				}

				showToast = true;
			}
		} finally {
			requestingAlbums.delete(albumId);
			requestingAlbums = requestingAlbums;
		}
	}

	function handleReleaseRemoved(result: { artist_removed: boolean; artist_name?: string | null }) {
		if (!artist) return;

		if (result.artist_removed) {
			artist.in_library = false;
			removedArtistName = result.artist_name || artist.name;
			showArtistRemovedModal = true;
		}
		artist = artist;
		artistBasicCache.set(artist, data.artistId);
	}
	run(() => {
		tocSections = artist
			? [
					{ id: 'section-overview', label: 'Overview' },
					{ id: 'section-about', label: 'About' },
					{ id: 'section-similar', label: 'Similar Artists' },
					...(artist.albums.length > 0 ? [{ id: 'section-albums', label: 'Albums' }] : []),
					...(artist.eps.length > 0 ? [{ id: 'section-eps', label: 'EPs' }] : []),
					...(artist.singles.length > 0 ? [{ id: 'section-singles', label: 'Singles' }] : [])
				]
			: [];
	});
	run(() => {
		if (browser && data.artistId && data.artistId !== currentArtistId) {
			currentArtistId = data.artistId;
			resetState();
			fetchArtist();
		}
	});
</script>

<div class="w-full px-2 sm:px-4 lg:px-8 py-4 sm:py-8 max-w-7xl mx-auto">
	{#if error}
		<div class="flex items-center justify-center min-h-[50vh]">
			<div class="alert alert-error">
				<span>{error}</span>
			</div>
		</div>
	{:else if loadingBasic && !artist}
		<div class="space-y-4 sm:space-y-8">
			<ArtistHeaderSkeleton />
			<AlbumGridSkeleton title="Albums" count={12} />
		</div>
	{:else if artist}
		<div class="xl:grid xl:grid-cols-[9rem_minmax(0,1fr)] xl:gap-4">
			<ArtistPageToc sections={tocSections} />

			<div class="xl:col-start-2 xl:row-start-1 space-y-4 sm:space-y-6 lg:space-y-8">
				<section id="section-overview" class="space-y-4 scroll-mt-24">
					<ArtistHero
						{artist}
						showBackButton
						refreshing={refreshingArtist}
						onrefresh={handleRefreshClick}
					/>

					<div class="flex flex-wrap items-center gap-x-4 gap-y-2 justify-center sm:justify-start">
						{#if artist.country}
							<span class="text-sm text-base-content/80 flex items-center gap-1.5">
								<span>🌍</span>
								{artist.country}
							</span>
						{/if}
						{#if artist.life_span?.begin}
							<span class="text-sm text-base-content/80 flex items-center gap-1.5">
								<span>📅</span>
								{artist.life_span.begin}{#if artist.life_span.end}&nbsp;–&nbsp;{artist.life_span
										.end}{/if}
							</span>
						{/if}
						{#if artist.albums.length + artist.eps.length + artist.singles.length > 0}
							<span class="text-sm text-base-content/80 flex items-center gap-1.5">
								<span>💿</span>
								{artist.albums.length + artist.eps.length + artist.singles.length} releases
							</span>
						{/if}
					</div>

					{#if artist.tags.length > 0}
						<div class="flex flex-wrap gap-2 justify-center sm:justify-start -mt-2">
							{#each [...new Set(artist.tags)].slice(0, 10) as tag (tag)}
								<a
									href="/genre?name={encodeURIComponent(tag)}"
									class="badge badge-lg cursor-pointer hover:opacity-80 transition-opacity"
									style="background-color: {colors.primary}; color: {colors.secondary};">{tag}</a
								>
							{/each}
						</div>
					{/if}
				</section>

				<section id="section-about" class="space-y-4 scroll-mt-24">
					{#if !lastfmEnrichment?.bio}
						<ArtistDescription description={artist.description} loading={loadingExtended} />
					{/if}

					{#if $integrationStore.lastfm}
						<LastFmEnrichment
							enrichment={lastfmEnrichment}
							loading={loadingLastfm}
							enabled={$integrationStore.lastfm}
						/>
					{/if}
				</section>

				<LibraryAlbumsCarousel
					releases={[...artist.albums, ...artist.eps, ...artist.singles]}
					artistName={artist.name}
					loading={loadingBasic}
				/>

				<div class="flex items-center justify-end mt-8 mb-4">
					<SourceSwitcher pageKey="artist" onSourceChange={handleSourceChange} />
				</div>

				<div class="flex flex-col md:flex-row gap-6 md:items-stretch">
					<div class="flex-1 min-w-0">
						<TopAlbumsList
							albums={topAlbums?.albums || []}
							loading={loadingTopAlbums}
							configured={topAlbums?.configured ?? true}
							source={topAlbums?.source || ''}
						/>
					</div>
					<div
						class="shrink-0 bg-base-content/25 h-px w-full md:w-px md:h-auto md:self-stretch"
						aria-hidden="true"
					></div>
					<div class="flex-1 min-w-0">
						<TopSongsList
							songs={topSongs?.songs || []}
							loading={loadingTopSongs}
							configured={topSongs?.configured ?? true}
							source={topSongs?.source || ''}
							ytConfigured={$integrationStore.youtube_api}
						/>
					</div>
				</div>

				<section id="section-similar" class="mt-8 scroll-mt-24">
					<SimilarArtistsCarousel
						artists={similarArtists?.similar_artists || []}
						loading={loadingSimilar}
						configured={similarArtists?.configured ?? true}
					/>
				</section>

				{#if hasMoreReleases || loadingMoreReleases}
					<div
						class="flex items-center justify-center gap-3 p-4 bg-base-300 rounded-box mb-6"
						style="border: 2px solid {colors.accent};"
					>
						<span class="loading loading-spinner loading-md" style="color: {colors.accent};"></span>
						<div class="flex flex-col items-start">
							<span class="font-semibold text-base" style="color: {colors.accent};"
								>Loading releases...</span
							>
							<span class="text-sm text-base-content/70"
								>Loaded {loadedReleaseCount} of {totalReleaseCount} releases</span
							>
						</div>
					</div>
				{/if}

				{#if artist.albums.length > 0}
					<section id="section-albums" class="scroll-mt-24">
						<ReleaseList
							title="Albums"
							releases={artist.albums}
							collapsed={albumsCollapsed}
							requestingIds={requestingAlbums}
							showLoadingIndicator={hasMoreReleases || loadingMoreReleases}
							artistName={artist.name}
							onRequest={handleRequest}
							onRemoved={handleReleaseRemoved}
							onToggleCollapse={() => (albumsCollapsed = !albumsCollapsed)}
						/>
					</section>
				{/if}

				{#if artist.eps.length > 0}
					<section id="section-eps" class="scroll-mt-24">
						<ReleaseList
							title="EPs"
							releases={artist.eps}
							collapsed={epsCollapsed}
							requestingIds={requestingAlbums}
							showLoadingIndicator={hasMoreReleases || loadingMoreReleases}
							artistName={artist.name}
							onRequest={handleRequest}
							onRemoved={handleReleaseRemoved}
							onToggleCollapse={() => (epsCollapsed = !epsCollapsed)}
						/>
					</section>
				{/if}

				{#if artist.singles.length > 0}
					<section id="section-singles" class="scroll-mt-24">
						<ReleaseList
							title="Singles"
							releases={artist.singles}
							collapsed={singlesCollapsed}
							requestingIds={requestingAlbums}
							showLoadingIndicator={hasMoreReleases || loadingMoreReleases}
							artistName={artist.name}
							onRequest={handleRequest}
							onRemoved={handleReleaseRemoved}
							onToggleCollapse={() => (singlesCollapsed = !singlesCollapsed)}
						/>
					</section>
				{/if}
			</div>
		</div>
	{:else}
		<div class="flex items-center justify-center min-h-[50vh]">
			<p class="text-base-content/60">Artist not found</p>
		</div>
	{/if}
</div>

<Toast bind:show={showToast} message={toastMessage} />

{#if showArtistRemovedModal}
	<ArtistRemovedModal
		artistName={removedArtistName}
		onclose={() => {
			showArtistRemovedModal = false;
		}}
	/>
{/if}
