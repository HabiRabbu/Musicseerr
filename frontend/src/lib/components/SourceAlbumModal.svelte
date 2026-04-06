<script lang="ts">
	import { Shuffle, Play, X, ListPlus, ListStart, ListMusic } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { API } from '$lib/constants';
	import { playerStore } from '$lib/stores/player.svelte';
	import { launchJellyfinPlayback } from '$lib/player/launchJellyfinPlayback';
	import { launchLocalPlayback } from '$lib/player/launchLocalPlayback';
	import { launchNavidromePlayback } from '$lib/player/launchNavidromePlayback';
	import ContextMenu from '$lib/components/ContextMenu.svelte';
	import type { MenuItem } from '$lib/components/ContextMenu.svelte';
	import AddToPlaylistModal from '$lib/components/AddToPlaylistModal.svelte';
	import AlbumImage from '$lib/components/AlbumImage.svelte';
	import {
		buildQueueItem,
		buildQueueItemsFromJellyfin,
		buildQueueItemsFromLocal,
		buildQueueItemsFromNavidrome,
		compareDiscTrack,
		normalizeDiscNumber,
		type TrackMeta,
		type TrackSourceData
	} from '$lib/player/queueHelpers';
	import type { QueueItem } from '$lib/player/types';
	import { getCoverUrl } from '$lib/utils/errorHandling';
	import { api } from '$lib/api/client';
	import NowPlayingIndicator from '$lib/components/NowPlayingIndicator.svelte';
	import type {
		JellyfinTrackInfo,
		LocalTrackInfo,
		NavidromeTrackInfo,
		NavidromeAlbumDetail,
		JellyfinAlbumSummary,
		LocalAlbumSummary,
		NavidromeAlbumSummary
	} from '$lib/types';

	type SourceType = 'jellyfin' | 'local' | 'navidrome';

	interface Props {
		open: boolean;
		sourceType: SourceType;
		album: JellyfinAlbumSummary | LocalAlbumSummary | NavidromeAlbumSummary | null;
		onclose: () => void;
	}

	let { open = $bindable(), sourceType, album, onclose }: Props = $props();

	let jellyfinTracks = $state<JellyfinTrackInfo[]>([]);
	let localTracks = $state<LocalTrackInfo[]>([]);
	let navidromeTracks = $state<NavidromeTrackInfo[]>([]);
	let loadingTracks = $state(false);
	let trackError = $state('');
	let fetchId = 0;
	let playlistModalRef = $state<{ open: (tracks: QueueItem[]) => void } | null>(null);

	let albumName = $derived(album?.name ?? '');
	let artistName = $derived(album?.artist_name ?? '');
	let year = $derived(album?.year);
	let albumId = $derived(getAlbumId());
	let mbid = $derived(getMbid());
	let artistMbid = $derived(getArtistMbid());
	let coverUrl = $derived(getCoverUrl(getAlbumCoverUrl() || null, mbid ?? albumId));
	let canNavigate = $derived(!!mbid || !!albumName);
	let canNavigateArtist = $derived(!!artistMbid);
	let trackCount = $derived(
		sourceType === 'jellyfin'
			? jellyfinTracks.length
			: sourceType === 'navidrome'
				? navidromeTracks.length
				: localTracks.length
	);

	function getAlbumCoverUrl(): string {
		if (!album) return '';
		if (sourceType === 'jellyfin') {
			return (album as JellyfinAlbumSummary).image_url ?? '';
		}
		if (sourceType === 'navidrome') {
			return (album as NavidromeAlbumSummary).image_url ?? '';
		}
		return (album as LocalAlbumSummary).cover_url ?? '';
	}

	function getAlbumId(): string {
		if (!album) return '';
		if (sourceType === 'jellyfin') return (album as JellyfinAlbumSummary).jellyfin_id;
		if (sourceType === 'navidrome') return (album as NavidromeAlbumSummary).navidrome_id;
		return String((album as LocalAlbumSummary).lidarr_album_id);
	}

	function getMbid(): string | null {
		if (!album) return null;
		if (sourceType === 'jellyfin') return (album as JellyfinAlbumSummary).musicbrainz_id ?? null;
		if (sourceType === 'navidrome') return (album as NavidromeAlbumSummary).musicbrainz_id ?? null;
		return (album as LocalAlbumSummary).musicbrainz_id ?? null;
	}

	function getArtistMbid(): string | null {
		if (!album) return null;
		if (sourceType === 'jellyfin')
			return (album as JellyfinAlbumSummary).artist_musicbrainz_id ?? null;
		if (sourceType === 'navidrome')
			return (album as NavidromeAlbumSummary).artist_musicbrainz_id ?? null;
		return (album as LocalAlbumSummary).artist_mbid ?? null;
	}

	$effect(() => {
		if (open && album) {
			fetchTracks();
		}
		if (!open) {
			jellyfinTracks = [];
			localTracks = [];
			navidromeTracks = [];
			trackError = '';
		}
	});

	async function fetchTracks(): Promise<void> {
		const id = ++fetchId;
		loadingTracks = true;
		trackError = '';
		try {
			if (sourceType === 'jellyfin') {
				const jfAlbum = album as JellyfinAlbumSummary;
				const data = await api.global.get<JellyfinTrackInfo[]>(
					API.jellyfinLibrary.albumTracks(jfAlbum.jellyfin_id)
				);
				if (id !== fetchId) return;
				jellyfinTracks = data;
			} else if (sourceType === 'navidrome') {
				const ndAlbum = album as NavidromeAlbumSummary;
				const detail = await api.global.get<NavidromeAlbumDetail>(
					API.navidromeLibrary.albumDetail(ndAlbum.navidrome_id)
				);
				if (id !== fetchId) return;
				navidromeTracks = detail.tracks ?? [];
			} else {
				const localAlbum = album as LocalAlbumSummary;
				const data = await api.global.get<LocalTrackInfo[]>(
					API.local.albumTracks(localAlbum.lidarr_album_id)
				);
				if (id !== fetchId) return;
				localTracks = data;
			}
		} catch (e) {
			if (id === fetchId)
				trackError = e instanceof Error ? e.message : "Couldn't load the track list";
		} finally {
			if (id === fetchId) loadingTracks = false;
		}
	}

	function handleClose(): void {
		open = false;
		onclose();
	}

	function goToAlbum(): void {
		if (!canNavigate) return;
		if (mbid) {
			const target = mbid;
			handleClose();
			goto(`/album/${target}`);
		} else if (albumName) {
			handleClose();
			goto(`/search?q=${encodeURIComponent(albumName)}`);
		}
	}

	function goToArtist(): void {
		if (!canNavigateArtist || !artistMbid) return;
		const target = artistMbid;
		handleClose();
		goto(`/artist/${target}`);
	}

	function playAll(shuffle: boolean = false): void {
		if (!album) return;
		const meta = {
			albumId: mbid ?? albumId,
			albumName,
			artistName,
			coverUrl
		};

		if (sourceType === 'jellyfin' && jellyfinTracks.length > 0) {
			launchJellyfinPlayback([...jellyfinTracks].sort(compareDiscTrack), 0, shuffle, meta);
		} else if (sourceType === 'navidrome' && navidromeTracks.length > 0) {
			launchNavidromePlayback([...navidromeTracks].sort(compareDiscTrack), 0, shuffle, meta);
		} else if (sourceType === 'local' && localTracks.length > 0) {
			launchLocalPlayback([...localTracks].sort(compareDiscTrack), 0, shuffle, meta);
		}
	}

	function playTrack(index: number): void {
		if (!album) return;
		const meta = {
			albumId: mbid ?? albumId,
			albumName,
			artistName,
			coverUrl
		};

		if (sourceType === 'jellyfin') {
			const sorted = [...jellyfinTracks].sort(compareDiscTrack);
			const track = jellyfinTracks[index];
			const sortedIdx = track ? sorted.indexOf(track) : index;
			launchJellyfinPlayback(sorted, sortedIdx >= 0 ? sortedIdx : index, false, meta);
		} else if (sourceType === 'navidrome') {
			const sorted = [...navidromeTracks].sort(compareDiscTrack);
			const track = navidromeTracks[index];
			const sortedIdx = track ? sorted.indexOf(track) : index;
			launchNavidromePlayback(sorted, sortedIdx >= 0 ? sortedIdx : index, false, meta);
		} else {
			const sorted = [...localTracks].sort(compareDiscTrack);
			const track = localTracks[index];
			const sortedIdx = track ? sorted.indexOf(track) : index;
			launchLocalPlayback(sorted, sortedIdx >= 0 ? sortedIdx : index, false, meta);
		}
	}

	function getTrackMeta(): TrackMeta {
		return {
			albumId: mbid ?? albumId,
			albumName,
			artistName,
			coverUrl: getAlbumCoverUrl() || null,
			artistId: artistMbid ?? undefined
		};
	}

	function buildTrackQueueItem(index: number): QueueItem | null {
		const meta = getTrackMeta();
		if (sourceType === 'jellyfin') {
			const track = jellyfinTracks[index];
			if (!track) return null;
			const sourceData: TrackSourceData = {
				trackPosition: track.track_number,
				discNumber: normalizeDiscNumber(track.disc_number),
				trackTitle: track.title,
				trackLength: track.duration_seconds,
				jellyfinTrack: track
			};
			return buildQueueItem(meta, sourceData);
		}

		if (sourceType === 'navidrome') {
			const track = navidromeTracks[index];
			if (!track) return null;
			const sourceData: TrackSourceData = {
				trackPosition: track.track_number,
				discNumber: normalizeDiscNumber(track.disc_number),
				trackTitle: track.title,
				trackLength: track.duration_seconds,
				navidromeTrack: track
			};
			return buildQueueItem(meta, sourceData);
		}

		const track = localTracks[index];
		if (!track) return null;
		const sourceData: TrackSourceData = {
			trackPosition: track.track_number,
			discNumber: normalizeDiscNumber(track.disc_number),
			trackTitle: track.title,
			trackLength: track.duration_seconds ?? undefined,
			localTrack: track
		};
		return buildQueueItem(meta, sourceData);
	}

	function buildAlbumQueueItems(): QueueItem[] {
		const meta = getTrackMeta();
		if (sourceType === 'jellyfin') {
			return buildQueueItemsFromJellyfin([...jellyfinTracks].sort(compareDiscTrack), meta);
		}
		if (sourceType === 'navidrome') {
			return buildQueueItemsFromNavidrome([...navidromeTracks].sort(compareDiscTrack), meta);
		}
		return buildQueueItemsFromLocal([...localTracks].sort(compareDiscTrack), meta);
	}

	function addAllToQueue(): void {
		const queueItems = buildAlbumQueueItems();
		if (queueItems.length === 0) return;
		playerStore.addMultipleToQueue(queueItems);
	}

	function playAllNext(): void {
		const queueItems = buildAlbumQueueItems();
		if (queueItems.length === 0) return;
		playerStore.playMultipleNext(queueItems);
	}

	function addAllToPlaylist(): void {
		const queueItems = buildAlbumQueueItems();
		if (queueItems.length === 0) return;
		playlistModalRef?.open(queueItems);
	}

	function addTrackToPlaylist(index: number): void {
		const queueItem = buildTrackQueueItem(index);
		if (!queueItem) return;
		playlistModalRef?.open([queueItem]);
	}

	function getBulkMenuItems(): MenuItem[] {
		return [
			{ label: 'Add All to Queue', icon: ListPlus, onclick: addAllToQueue },
			{ label: 'Play All Next', icon: ListStart, onclick: playAllNext },
			{ label: 'Add All to Playlist', icon: ListMusic, onclick: addAllToPlaylist }
		];
	}

	function getTrackContextMenuItems(index: number): MenuItem[] {
		const queueItem = buildTrackQueueItem(index);
		const hasQueueItem = queueItem !== null;
		return [
			{
				label: 'Add to Queue',
				icon: ListPlus,
				onclick: () => {
					if (queueItem) playerStore.addToQueue(queueItem);
				},
				disabled: !hasQueueItem
			},
			{
				label: 'Play Next',
				icon: ListStart,
				onclick: () => {
					if (queueItem) playerStore.playNext(queueItem);
				},
				disabled: !hasQueueItem
			},
			{
				label: 'Add to Playlist',
				icon: ListMusic,
				onclick: () => addTrackToPlaylist(index),
				disabled: !hasQueueItem
			}
		];
	}

	function getTrackName(index: number): string {
		if (sourceType === 'jellyfin') return jellyfinTracks[index]?.title ?? '';
		if (sourceType === 'navidrome') return navidromeTracks[index]?.title ?? '';
		return localTracks[index]?.title ?? '';
	}

	function getTrackNumber(index: number): number {
		if (sourceType === 'jellyfin') return jellyfinTracks[index]?.track_number ?? 0;
		if (sourceType === 'navidrome') return navidromeTracks[index]?.track_number ?? 0;
		return localTracks[index]?.track_number ?? 0;
	}

	function getTrackDiscNumber(index: number): number {
		if (sourceType === 'jellyfin') return normalizeDiscNumber(jellyfinTracks[index]?.disc_number);
		if (sourceType === 'navidrome') return normalizeDiscNumber(navidromeTracks[index]?.disc_number);
		return normalizeDiscNumber(localTracks[index]?.disc_number);
	}

	function formatDuration(seconds?: number | null): string {
		if (seconds == null) return '';
		const m = Math.floor(seconds / 60);
		const s = Math.floor(seconds % 60);
		return `${m}:${s.toString().padStart(2, '0')}`;
	}

	function formatSize(bytes: number): string {
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function isTrackPlaying(trackNum: number, discNumber: number = 1): boolean {
		return (
			playerStore.nowPlaying?.albumId === (mbid ?? albumId) &&
			(playerStore.currentQueueItem?.discNumber ?? 1) === discNumber &&
			playerStore.currentQueueItem?.trackNumber === trackNum &&
			playerStore.isPlaying
		);
	}
</script>

{#if open && album}
	<dialog class="modal modal-open">
		<div class="modal-box max-w-4xl p-0 overflow-hidden">
			<div class="flex gap-5 p-6 pb-4">
				<div class="shrink-0">
					{#if canNavigate}
						<button
							onclick={goToAlbum}
							class="block rounded-lg overflow-hidden shadow-lg hover:shadow-xl transition-shadow cursor-pointer"
							aria-label="Go to album"
						>
							<AlbumImage
								mbid={mbid ?? albumId}
								customUrl={coverUrl || null}
								alt={albumName}
								size="xl"
								rounded="none"
								className="w-36 h-36"
							/>
						</button>
					{:else}
						<div class="rounded-lg overflow-hidden shadow-lg">
							<AlbumImage
								mbid={albumId}
								customUrl={coverUrl || null}
								alt={albumName}
								size="xl"
								rounded="none"
								className="w-36 h-36"
							/>
						</div>
					{/if}
				</div>

				<div class="flex flex-col justify-center min-w-0 flex-1">
					{#if canNavigate}
						<button
							onclick={goToAlbum}
							class="text-xl font-bold truncate text-left hover:text-accent transition-colors cursor-pointer"
						>
							{albumName}
						</button>
					{:else}
						<h3 class="text-xl font-bold truncate">{albumName}</h3>
					{/if}
					{#if canNavigateArtist}
						<button
							onclick={goToArtist}
							class="text-base opacity-70 truncate text-left hover:text-accent transition-colors cursor-pointer"
						>
							{artistName}
						</button>
					{:else}
						<p class="text-base opacity-70 truncate">{artistName}</p>
					{/if}
					<div class="flex items-center gap-2 mt-2 flex-wrap">
						{#if year}
							<span class="badge badge-sm badge-ghost">{year}</span>
						{/if}
						{#if sourceType === 'jellyfin'}
							<span class="badge badge-sm badge-info">Jellyfin</span>
						{:else if sourceType === 'navidrome'}
							<span class="badge badge-sm badge-primary">Navidrome</span>
						{:else}
							{@const localAlbum = album as LocalAlbumSummary}
							<span class="badge badge-sm badge-accent">Local</span>
							{#if localAlbum.primary_format}
								<span class="badge badge-sm badge-ghost">{localAlbum.primary_format}</span>
							{/if}
							{#if localAlbum.total_size_bytes > 0}
								<span class="badge badge-sm badge-ghost"
									>{formatSize(localAlbum.total_size_bytes)}</span
								>
							{/if}
						{/if}
						{#if !mbid && albumName}
							<span class="badge badge-sm badge-info badge-outline">Search only</span>
						{/if}
					</div>
				</div>

				<button class="btn btn-sm btn-circle btn-ghost self-start -mr-2 -mt-2" onclick={handleClose}
					><X class="h-4 w-4" /></button
				>
			</div>

			<div class="flex items-center gap-2 px-6 pb-4 flex-wrap">
				{#if trackCount > 0}
					<button class="btn btn-sm btn-accent gap-1" onclick={() => playAll(false)}>
						<Play class="h-4 w-4 fill-current" />
						Play All
					</button>
					<button class="btn btn-sm btn-ghost gap-1" onclick={() => playAll(true)}>
						<Shuffle class="h-4 w-4" />
						Shuffle
					</button>
					<ContextMenu items={getBulkMenuItems()} position="end" size="sm" />
				{/if}
			</div>

			<div class="divider my-0 px-6"></div>

			<div class="px-6 pt-3 pb-5 max-h-112 overflow-y-auto">
				{#if loadingTracks}
					<div class="flex justify-center py-6">
						<span class="loading loading-spinner loading-md"></span>
					</div>
				{:else if trackError}
					<div role="alert" class="alert alert-error alert-soft">
						<span>{trackError}</span>
						<button class="btn btn-sm btn-ghost" onclick={fetchTracks}>Retry</button>
					</div>
				{:else if trackCount > 0}
					<div class="flex flex-col">
						{#each { length: trackCount } as _, i (`track-${i}`)}
							{@const trackNum = getTrackNumber(i)}
							{@const discNum = getTrackDiscNumber(i)}
							{@const playing = isTrackPlaying(trackNum, discNum)}
							<div
								class="group/row flex items-center gap-2 w-full py-1 px-1 rounded-lg transition-colors {playing
									? 'bg-accent/10'
									: 'hover:bg-base-200'}"
							>
								<button
									class="flex items-center gap-3 flex-1 py-1.5 px-1 rounded-lg text-left group/track"
									onclick={() => playTrack(i)}
								>
									<span
										class="font-mono w-6 text-right text-sm shrink-0 {playing
											? 'text-accent'
											: 'opacity-40'}"
									>
										{#if playing}
											<NowPlayingIndicator />
										{:else}
											{trackNum}
										{/if}
									</span>
									<span class="text-sm truncate flex-1 {playing ? 'text-accent' : ''}"
										>{getTrackName(i)}</span
									>
									{#if sourceType === 'jellyfin'}
										{@const dur = jellyfinTracks[i]?.duration_seconds}
										{#if dur}
											<span class="text-xs opacity-40 shrink-0">{formatDuration(dur)}</span>
										{/if}
									{:else if sourceType === 'navidrome'}
										{@const dur = navidromeTracks[i]?.duration_seconds}
										{#if dur}
											<span class="text-xs opacity-40 shrink-0">{formatDuration(dur)}</span>
										{/if}
									{:else}
										{@const lt = localTracks[i]}
										{#if lt?.duration_seconds}
											<span class="text-xs opacity-40 shrink-0"
												>{formatDuration(lt.duration_seconds)}</span
											>
										{/if}
									{/if}
									<span class={playing ? 'text-accent' : ''}>
										<Play
											class="h-4 w-4 shrink-0 transition-opacity {playing
												? 'opacity-100'
												: 'text-accent opacity-0 group-hover/track:opacity-100'} fill-current"
										/>
									</span>
								</button>
								<div>
									<ContextMenu items={getTrackContextMenuItems(i)} position="end" size="xs" />
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<p class="text-sm opacity-50 text-center py-6">No tracks found</p>
				{/if}
			</div>
		</div>

		<form method="dialog" class="modal-backdrop">
			<button onclick={handleClose}>close</button>
		</form>
	</dialog>
{/if}

<AddToPlaylistModal bind:this={playlistModalRef} />
