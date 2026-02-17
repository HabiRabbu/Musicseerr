<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import type { AlbumBasicInfo, AlbumTracksInfo, SimilarAlbumsResponse, MoreByArtistResponse, YouTubeTrackLink, YouTubeLink, YouTubeQuotaStatus, JellyfinAlbumMatch, LocalAlbumMatch } from '$lib/types';
	import { colors } from '$lib/colors';
	import { libraryStore } from '$lib/stores/library';
	import { API } from '$lib/constants';
	import AlbumImage from '$lib/components/AlbumImage.svelte';
	import Toast from '$lib/components/Toast.svelte';
	import DiscoveryAlbumCarousel from '$lib/components/DiscoveryAlbumCarousel.svelte';
	import { requestAlbum } from '$lib/utils/albumRequest';
	import { formatDuration, formatTotalDuration } from '$lib/utils/formatting';
	import { integrationStore } from '$lib/stores/integration';
	import { playerStore } from '$lib/stores/player.svelte';
	import AlbumYouTubeBar from '$lib/components/AlbumYouTubeBar.svelte';
	import AlbumSourceBar from '$lib/components/AlbumSourceBar.svelte';
	import TrackPlayButton from '$lib/components/TrackPlayButton.svelte';
	import TrackSourceButton from '$lib/components/TrackSourceButton.svelte';
	import JellyfinIcon from '$lib/components/JellyfinIcon.svelte';
	import LocalFilesIcon from '$lib/components/LocalFilesIcon.svelte';
	import DeleteAlbumModal from '$lib/components/DeleteAlbumModal.svelte';
	import ArtistRemovedModal from '$lib/components/ArtistRemovedModal.svelte';
	import { launchJellyfinPlayback } from '$lib/player/launchJellyfinPlayback';
	import { launchLocalPlayback } from '$lib/player/launchLocalPlayback';
	import { getCoverUrl } from '$lib/utils/errorHandling';
	import type { PlaybackMeta } from '$lib/player/types';

	export let data: { albumId: string };

	let album: AlbumBasicInfo | null = null;
	let tracksInfo: AlbumTracksInfo | null = null;
	let error: string | null = null;
	let loadingBasic: boolean = true;
	let loadingTracks: boolean = true;
	let showToast = false;
	let requesting = false;
	let showDeleteModal = false;
	let showArtistRemovedModal = false;
	let removedArtistName = '';
	let toastMessage = 'Added to Library';
	let toastType: 'success' | 'error' | 'info' | 'warning' = 'success';

	let moreByArtist: MoreByArtistResponse | null = null;
	let similarAlbums: SimilarAlbumsResponse | null = null;
	let loadingDiscovery = true;

	let trackLinks: YouTubeTrackLink[] = [];
	let albumLink: YouTubeLink | null = null;
	let quota: YouTubeQuotaStatus | null = null;

	let jellyfinMatch: JellyfinAlbumMatch | null = null;
	let localMatch: LocalAlbumMatch | null = null;
	let loadingJellyfin = false;
	let loadingLocal = false;

	$: trackLinkMap = new Map(trackLinks.map(tl => [tl.track_number, tl]));
	$: jellyfinTrackMap = new Map(jellyfinMatch?.tracks.map(t => [t.track_number, t]) ?? []);
	$: localTrackMap = new Map(localMatch?.tracks.map(t => [t.track_number, t]) ?? []);

	let currentAlbumId: string | null = null;

	$: inLibrary = $libraryStore.initialized
		? libraryStore.isInLibrary(album?.musicbrainz_id)
		: (album?.in_library ?? false);
	$: isRequested = album && !inLibrary && (album.requested || libraryStore.isRequested(album.musicbrainz_id));

	$: if (browser && data.albumId && data.albumId !== currentAlbumId) {
		currentAlbumId = data.albumId;
		resetState();
		loadAlbum();
	}

	function resetState() {
		album = null;
		tracksInfo = null;
		error = null;
		loadingBasic = true;
		loadingTracks = true;
		loadingDiscovery = true;
		moreByArtist = null;
		similarAlbums = null;
		trackLinks = [];
		albumLink = null;
		quota = null;
		jellyfinMatch = null;
		localMatch = null;
		loadingJellyfin = false;
		loadingLocal = false;
	}

	async function loadAlbum() {
		await fetchBasicInfo();
		if (album) {
			fetchTracksInfo();
			fetchDiscoveryData();
			fetchYouTubeData();
			await integrationStore.ensureLoaded();
			fetchJellyfinAlbumData();
			fetchLocalAlbumData();
		}
	}

	async function fetchBasicInfo() {
		try {
			const res = await fetch(`/api/album/${data.albumId}/basic`);
			if (res.ok) {
				album = await res.json();
			} else {
				error = 'Failed to load album';
			}
		} catch (e) {
			error = 'Error loading album';
		} finally {
			loadingBasic = false;
		}
	}

	async function fetchTracksInfo() {
		try {
			const res = await fetch(`/api/album/${data.albumId}/tracks`);
			if (res.ok) {
				tracksInfo = await res.json();
			}
		} catch (e) {
		}
		loadingTracks = false;
	}

	async function fetchDiscoveryData() {
		if (!album?.artist_id) {
			loadingDiscovery = false;
			return;
		}
		loadingDiscovery = true;
		try {
			const [moreRes, similarRes] = await Promise.all([
				fetch(`/api/album/${data.albumId}/more-by-artist?artist_id=${album.artist_id}`),
				fetch(`/api/album/${data.albumId}/similar?artist_id=${album.artist_id}`)
			]);

			if (moreRes.ok) moreByArtist = await moreRes.json();
			if (similarRes.ok) similarAlbums = await similarRes.json();
		} catch (e) {
		} finally {
			loadingDiscovery = false;
		}
	}

	async function fetchYouTubeData() {
		try {
			const [linkRes, tracksRes] = await Promise.all([
				fetch(API.youtube.link(data.albumId)),
				fetch(API.youtube.trackLinks(data.albumId))
			]);
			if (linkRes.status === 200) albumLink = await linkRes.json();
			if (tracksRes.ok) trackLinks = await tracksRes.json();
		} catch {}
	}

	async function fetchJellyfinAlbumData() {
		if (!$integrationStore.jellyfin) return;
		loadingJellyfin = true;
		try {
			const res = await fetch(API.jellyfinLibrary.albumMatch(data.albumId));
			if (res.ok) {
				jellyfinMatch = await res.json();
			}
		} catch (e) {
			console.error('Failed to fetch Jellyfin album data:', e);
		} finally {
			loadingJellyfin = false;
		}
	}

	async function fetchLocalAlbumData() {
		if (!$integrationStore.localfiles) return;
		loadingLocal = true;
		try {
			const res = await fetch(API.local.albumMatch(data.albumId));
			if (res.ok) {
				localMatch = await res.json();
			}
		} catch (e) {
			console.error('Failed to fetch local album data:', e);
		} finally {
			loadingLocal = false;
		}
	}

	function handleTrackGenerated(link: YouTubeTrackLink): void {
		trackLinks = [...trackLinks.filter((tl) => tl.track_number !== link.track_number), link]
			.sort((a, b) => a.track_number - b.track_number);
	}

	function handleTrackLinksUpdate(links: YouTubeTrackLink[]): void {
		trackLinks = links;
	}

	function handleAlbumLinkUpdate(link: YouTubeLink): void {
		albumLink = link;
	}

	function handleQuotaUpdate(q: YouTubeQuotaStatus): void {
		quota = q;
	}

	async function handleRequest() {
		if (!album || requesting) return;

		requesting = true;

		try {
			const result = await requestAlbum(album.musicbrainz_id, {
				artist: album.artist_name ?? undefined,
				album: album.title,
				year: album.year ?? undefined
			});

			if (result.success && album) {
				album.requested = true;
				album = album;
				toastMessage = 'Added to Library';
				toastType = 'success';
				showToast = true;
			}
		} finally {
			requesting = false;
		}
	}

	function handleDeleteClick() {
		showDeleteModal = true;
	}

	function handleDeleted(result: { artist_removed: boolean; artist_name?: string | null }) {
		showDeleteModal = false;
		if (album) {
			album.in_library = false;
			album.requested = false;
			album = album;
		}
		toastMessage = 'Removed from Library';
		toastType = 'success';
		showToast = true;
		if (result.artist_removed && result.artist_name) {
			removedArtistName = result.artist_name;
			showArtistRemovedModal = true;
		}
	}

	function goBack() {
		if (browser && window.history.length > 1) {
			window.history.back();
		} else {
			goto('/');
		}
	}

	function goToArtist() {
		if (album?.artist_id) {
			goto(`/artist/${album.artist_id}`);
		}
	}

	function getPlaybackMeta() {
		return {
			albumId: album!.musicbrainz_id,
			albumName: album!.title,
			artistName: album!.artist_name,
			coverUrl: getCoverUrl(album!.cover_url ?? null, album!.musicbrainz_id),
			artistId: album!.artist_id
		};
	}

	function playSource<T extends { track_number: number }>(
		match: { tracks: T[] } | null,
		launcher: (tracks: T[], startIndex: number, shuffle: boolean, meta: PlaybackMeta) => void,
		opts: { startTrack?: number; shuffle?: boolean } = {}
	): void {
		if (!match?.tracks.length) return;
		let idx = 0;
		if (opts.startTrack !== undefined) {
			idx = match.tracks.findIndex((t) => t.track_number === opts.startTrack);
			if (idx === -1) return;
		}
		launcher(match.tracks, idx, opts.shuffle ?? false, getPlaybackMeta());
	}
</script>

<div class="w-full px-2 sm:px-4 lg:px-8 py-4 sm:py-8 max-w-7xl mx-auto">
	<button 
		on:click={goBack}
		class="btn btn-ghost btn-circle mb-4"
		aria-label="Go back"
	>
		<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
		</svg>
	</button>

	{#if error}
		<div class="flex items-center justify-center min-h-[50vh]">
			<div class="alert alert-error">
				<span>{error}</span>
			</div>
		</div>
	{:else if loadingBasic || !album}
		<div class="space-y-6 sm:space-y-8">
			<div class="flex flex-col lg:flex-row gap-6 lg:gap-8">
				<div class="skeleton w-full lg:w-64 xl:w-80 aspect-square rounded-box flex-shrink-0"></div>
				<div class="flex-1 flex flex-col justify-end space-y-4">
					<div class="skeleton h-4 w-20"></div>
					<div class="skeleton h-12 w-3/4"></div>
					<div class="skeleton h-6 w-1/2"></div>
					<div class="flex gap-4 mt-6">
						<div class="skeleton h-12 w-32"></div>
						<div class="skeleton h-12 w-32"></div>
					</div>
				</div>
			</div>

			<div class="space-y-2">
				<div class="skeleton h-8 w-32 mb-4"></div>
				{#each Array(8) as _, i}
					<div class="skeleton h-12 w-full"></div>
				{/each}
			</div>
		</div>
	{:else if album}
		<div class="space-y-6 sm:space-y-8">
			<div class="flex flex-col lg:flex-row gap-6 lg:gap-8">
				<div class="w-full lg:w-64 xl:w-80 flex-shrink-0">
					<AlbumImage
						mbid={album.musicbrainz_id}
						customUrl={album.cover_url}
						alt={album.title}
						size="hero"
						lazy={false}
						rounded="xl"
						className="w-full aspect-square shadow-2xl"
					/>
				</div>

				<div class="flex-1 flex flex-col lg:justify-end space-y-4">
					<div class="text-xs sm:text-sm font-semibold uppercase tracking-wider opacity-70">
						{album.type || 'Album'}
					</div>
					
					<h1 class="text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-bold leading-tight">
						{album.title}
					</h1>
					
					{#if album.disambiguation}
						<p class="text-sm opacity-60 italic">({album.disambiguation})</p>
					{/if}
					
					<div class="flex flex-wrap items-center gap-2 text-sm">
						<button 
							on:click={goToArtist}
							class="font-semibold hover:underline cursor-pointer"
						>
							{album.artist_name}
						</button>
						
						{#if album.year}
							<span class="opacity-50">•</span>
							<span>{album.year}</span>
						{/if}
						
						{#if tracksInfo && tracksInfo.total_tracks > 0}
							<span class="opacity-50">•</span>
							<span>{tracksInfo.total_tracks} {tracksInfo.total_tracks === 1 ? 'track' : 'tracks'}</span>
						{:else if loadingTracks}
							<span class="opacity-50">•</span>
							<span class="skeleton w-16 h-4 inline-block"></span>
						{/if}
						
						{#if tracksInfo?.total_length}
							<span class="opacity-50">•</span>
							<span>{formatTotalDuration(tracksInfo.total_length)}</span>
						{/if}
					</div>

					<div class="flex flex-wrap gap-x-4 gap-y-2 text-xs sm:text-sm opacity-70">
						{#if tracksInfo?.label}
							<div>
								<span class="font-semibold">Label:</span> {tracksInfo.label}
							</div>
						{/if}
						{#if tracksInfo?.country}
							<div>
								<span class="font-semibold">Country:</span> {tracksInfo.country}
							</div>
						{/if}
						{#if tracksInfo?.barcode}
							<div>
								<span class="font-semibold">Barcode:</span> {tracksInfo.barcode}
							</div>
						{/if}
					</div>

					<div class="pt-4 flex flex-wrap items-start gap-3">
						{#if inLibrary}
							<div class="badge badge-lg gap-2" style="background-color: {colors.accent}; color: {colors.secondary};">
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
									<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
								</svg>
								In Library
							</div>
							<button
								class="btn btn-sm btn-error btn-outline gap-1"
								on:click={handleDeleteClick}
							>
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
									<path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
								</svg>
								Remove
							</button>
						{:else if isRequested}
							<div class="badge badge-lg gap-2" style="background-color: #F59E0B; color: {colors.secondary};">
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
									<path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
								</svg>
								Requested
							</div>
							<button
								class="btn btn-sm btn-error btn-outline gap-1"
								on:click={handleDeleteClick}
							>
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
									<path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
								</svg>
								Remove
							</button>
						{:else}
							<button
								class="btn btn-lg gap-2"
								style="background-color: {colors.accent}; color: {colors.secondary}; border: none;"
								on:click={handleRequest}
								disabled={requesting}
							>
								{#if requesting}
									<span class="loading loading-spinner loading-sm"></span>
									Requesting...
								{:else}
									<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
										<path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
									</svg>
									Add to Library
								{/if}
							</button>
						{/if}
					</div>
				</div>
			</div>

			{#if loadingTracks}
				<div class="space-y-3">
					<h2 class="text-xl sm:text-2xl font-bold">Tracks</h2>
					<div class="bg-base-200 rounded-box overflow-hidden">
						<ul class="list">
							{#each Array(8) as _, i}
								<li class="list-row p-3 sm:p-4">
									<div class="flex items-center gap-4 w-full">
										<div class="skeleton w-8 h-4"></div>
										<div class="skeleton flex-1 h-4"></div>
										<div class="skeleton w-12 h-4"></div>
									</div>
								</li>
							{/each}
						</ul>
					</div>
				</div>
			{:else if tracksInfo && tracksInfo.tracks.length > 0}
				<div class="space-y-3">
					<div class="flex items-center justify-between flex-wrap gap-2">
						<h2 class="text-xl sm:text-2xl font-bold">Tracks</h2>
						{#if quota}
							<div class="flex items-center gap-2">
								<progress class="progress progress-accent w-20 h-1.5" value={quota.used} max={quota.limit}></progress>
								<span class="text-xs opacity-60">{quota.remaining}/{quota.limit}</span>
							</div>
						{/if}
					</div>

					{#if $integrationStore.youtube}
						<AlbumYouTubeBar
							albumId={album.musicbrainz_id}
							albumName={album.title}
							artistName={album.artist_name}
							artistId={album.artist_id}
							coverUrl={album.cover_url ?? null}
							tracks={tracksInfo.tracks}
							{trackLinks}
							{albumLink}
							onTrackLinksUpdate={handleTrackLinksUpdate}
							onAlbumLinkUpdate={handleAlbumLinkUpdate}
							onQuotaUpdate={handleQuotaUpdate}
						/>
					{/if}

					{#if $integrationStore.jellyfin}
						{#if loadingJellyfin}
							<div class="skeleton h-14 w-full rounded-box"></div>
						{:else if jellyfinMatch?.found}
							<AlbumSourceBar
								sourceLabel="Jellyfin"
								sourceColor="rgb(var(--brand-jellyfin))"
								trackCount={jellyfinMatch.tracks.length}
								totalTracks={tracksInfo.tracks.length}
							onPlayAll={() => playSource(jellyfinMatch, launchJellyfinPlayback)}
							onShuffle={() => playSource(jellyfinMatch, launchJellyfinPlayback, { shuffle: true })}
							>
								{#snippet icon()}
									<JellyfinIcon class="h-5 w-5" />
								{/snippet}
							</AlbumSourceBar>
						{/if}
					{/if}

					{#if $integrationStore.localfiles}
						{#if loadingLocal}
							<div class="skeleton h-14 w-full rounded-box"></div>
						{:else if localMatch?.found}
							<AlbumSourceBar
								sourceLabel="Local Files"
								sourceColor="rgb(var(--brand-localfiles))"
								trackCount={localMatch.tracks.length}
								totalTracks={tracksInfo.tracks.length}
								extraBadge={localMatch.primary_format?.toUpperCase() ?? null}
							onPlayAll={() => playSource(localMatch, launchLocalPlayback)}
							onShuffle={() => playSource(localMatch, launchLocalPlayback, { shuffle: true })}
							>
								{#snippet icon()}
									<LocalFilesIcon class="h-5 w-5" />
								{/snippet}
							</AlbumSourceBar>
						{/if}
					{/if}
					
					<div class="bg-base-200 rounded-box overflow-hidden">
						<ul class="list">
							{#each tracksInfo.tracks as track, index}
								{@const tl = trackLinkMap.get(track.position) ?? null}
								{@const jellyfinTrack = jellyfinTrackMap.get(track.position) ?? null}
								{@const localTrack = localTrackMap.get(track.position) ?? null}
								{@const isCurrentlyPlaying = playerStore.nowPlaying?.albumId === album.musicbrainz_id && playerStore.currentQueueItem?.trackNumber === track.position && playerStore.isPlaying}
								{@const showJellyfinBtn = $integrationStore.jellyfin && jellyfinMatch?.found}
								{@const showLocalBtn = $integrationStore.localfiles && localMatch?.found}
								<li
									class="hover:bg-base-300/50 transition-colors p-3 sm:p-4"
									style={isCurrentlyPlaying ? `background-color: ${colors.accent}20;` : ''}
								>
									<div class="flex items-center gap-4 w-full">
										<div class="font-medium w-8 text-center flex-shrink-0 {isCurrentlyPlaying ? '' : 'text-base-content/60'}" style={isCurrentlyPlaying ? `color: ${colors.accent};` : ''}>
											{track.position}
										</div>

										<div class="flex-1 min-w-0">
											<div class="font-medium truncate" style={isCurrentlyPlaying ? `color: ${colors.accent};` : ''}>
												{track.title}
											</div>
										</div>

										<div class="text-base-content/60 text-sm flex-shrink-0">
											{formatDuration(track.length)}
										</div>

										{#if $integrationStore.youtube || showJellyfinBtn || showLocalBtn}
											<div class="flex items-center gap-1.5 flex-shrink-0 ml-auto">
												{#if $integrationStore.youtube}
													<TrackPlayButton
														trackNumber={track.position}
														trackName={track.title}
														trackLink={tl}
														allTrackLinks={trackLinks}
														albumId={album.musicbrainz_id}
														albumName={album.title}
														artistName={album.artist_name}
														coverUrl={album.cover_url ?? null}
														artistId={album.artist_id}
														onGenerated={handleTrackGenerated}
														onQuotaUpdate={handleQuotaUpdate}
													/>
												{/if}

												{#if showJellyfinBtn}
													<TrackSourceButton
														available={jellyfinTrack !== null}
														sourceColor="rgb(var(--brand-jellyfin))"
												onclick={() => playSource(jellyfinMatch, launchJellyfinPlayback, { startTrack: track.position })}
														ariaLabel={jellyfinTrack ? 'Play on Jellyfin' : 'Not available on Jellyfin'}
													>
														{#snippet icon()}
															<JellyfinIcon class="h-4 w-4" />
														{/snippet}
													</TrackSourceButton>
												{/if}

												{#if showLocalBtn}
													<TrackSourceButton
														available={localTrack !== null}
														sourceColor="rgb(var(--brand-localfiles))"
												onclick={() => playSource(localMatch, launchLocalPlayback, { startTrack: track.position })}
														ariaLabel={localTrack ? 'Play local file' : 'Not available locally'}
													>
														{#snippet icon()}
														<LocalFilesIcon class="h-4 w-4" />
														{/snippet}
													</TrackSourceButton>
												{/if}
											</div>
										{/if}
									</div>
								</li>
							{/each}
						</ul>
					</div>
				</div>
			{/if}

			{#if album.release_date}
				<div class="text-xs opacity-60">
					<span class="font-semibold">Release Date:</span> {album.release_date}
				</div>
			{/if}

			<!-- More by Artist Section -->
			<div class="mt-8">
				<DiscoveryAlbumCarousel 
					albums={moreByArtist?.albums || []}
					loading={loadingDiscovery}
					configured={true}
					title="More by {moreByArtist?.artist_name || album.artist_name}"
					emptyMessage="No other albums found"
				/>
			</div>

			<!-- Similar Albums Section -->
			<DiscoveryAlbumCarousel 
				albums={similarAlbums?.albums || []}
				loading={loadingDiscovery}
				configured={similarAlbums?.configured ?? true}
				title="You Might Also Like"
				emptyMessage="No similar albums found"
			/>
		</div>
	{:else}
		<div class="flex items-center justify-center min-h-[50vh]">
			<p class="text-base-content/60">Album not found</p>
		</div>
	{/if}
</div>

<Toast bind:show={showToast} message={toastMessage} type={toastType} />

{#if showDeleteModal && album}
	<DeleteAlbumModal
		albumTitle={album.title}
		artistName={album.artist_name}
		musicbrainzId={album.musicbrainz_id}
		ondeleted={handleDeleted}
		onclose={() => { showDeleteModal = false; }}
	/>
{/if}

{#if showArtistRemovedModal}
	<ArtistRemovedModal
		artistName={removedArtistName}
		onclose={() => { showArtistRemovedModal = false; }}
	/>
{/if}
