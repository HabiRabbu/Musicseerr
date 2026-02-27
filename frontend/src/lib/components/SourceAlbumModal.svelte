<script lang="ts">
	import { Shuffle, Play, X } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { API } from '$lib/constants';
	import { playerStore } from '$lib/stores/player.svelte';
	import { launchJellyfinPlayback } from '$lib/player/launchJellyfinPlayback';
	import { launchLocalPlayback } from '$lib/player/launchLocalPlayback';
	import AlbumImage from '$lib/components/AlbumImage.svelte';
	import { getCoverUrl } from '$lib/utils/errorHandling';
	import type { JellyfinTrackInfo, LocalTrackInfo, JellyfinAlbumSummary, LocalAlbumSummary } from '$lib/types';

	type SourceType = 'jellyfin' | 'local';

	interface Props {
		open: boolean;
		sourceType: SourceType;
		album: JellyfinAlbumSummary | LocalAlbumSummary | null;
		onclose: () => void;
	}

	let { open = $bindable(), sourceType, album, onclose }: Props = $props();

	let jellyfinTracks = $state<JellyfinTrackInfo[]>([]);
	let localTracks = $state<LocalTrackInfo[]>([]);
	let loadingTracks = $state(false);
	let trackError = $state('');
	let fetchId = 0;

	let albumName = $derived(album?.name ?? '');
	let artistName = $derived(album?.artist_name ?? '');
	let year = $derived(album?.year);
	let albumId = $derived(getAlbumId());
	let mbid = $derived(getMbid());
	let artistMbid = $derived(getArtistMbid());
	let coverUrl = $derived(getCoverUrl(getAlbumCoverUrl() || null, mbid ?? albumId));
	let canNavigate = $derived(!!mbid);
	let canNavigateArtist = $derived(!!artistMbid);
	let trackCount = $derived(sourceType === 'jellyfin' ? jellyfinTracks.length : localTracks.length);

	function getAlbumCoverUrl(): string {
		if (!album) return '';
		if (sourceType === 'jellyfin') {
			return (album as JellyfinAlbumSummary).image_url ?? '';
		}
		return (album as LocalAlbumSummary).cover_url ?? '';
	}

	function getAlbumId(): string {
		if (!album) return '';
		if (sourceType === 'jellyfin') return (album as JellyfinAlbumSummary).jellyfin_id;
		return String((album as LocalAlbumSummary).lidarr_album_id);
	}

	function getMbid(): string | null {
		if (!album) return null;
		if (sourceType === 'jellyfin') return (album as JellyfinAlbumSummary).musicbrainz_id ?? null;
		return (album as LocalAlbumSummary).musicbrainz_id ?? null;
	}

	function getArtistMbid(): string | null {
		if (!album) return null;
		if (sourceType === 'jellyfin')
			return (album as JellyfinAlbumSummary).artist_musicbrainz_id ?? null;
		return (album as LocalAlbumSummary).artist_mbid ?? null;
	}

	$effect(() => {
		if (open && album) {
			fetchTracks();
		}
		if (!open) {
			jellyfinTracks = [];
			localTracks = [];
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
				const res = await fetch(API.jellyfinLibrary.albumTracks(jfAlbum.jellyfin_id));
				if (id !== fetchId) return;
				if (res.ok) {
					jellyfinTracks = await res.json();
				} else {
					trackError = `Failed to load Jellyfin tracks (${res.status})`;
				}
			} else {
				const localAlbum = album as LocalAlbumSummary;
				const res = await fetch(API.local.albumTracks(localAlbum.lidarr_album_id));
				if (id !== fetchId) return;
				if (res.ok) {
					localTracks = await res.json();
				} else {
					trackError = `Failed to load local tracks (${res.status})`;
				}
			}
		} catch {
			if (id === fetchId) trackError = 'Failed to load tracks';
		} finally {
			if (id === fetchId) loadingTracks = false;
		}
	}

	function handleClose(): void {
		open = false;
		onclose();
	}

	function goToAlbum(): void {
		if (!canNavigate || !mbid) return;
		const target = mbid;
		handleClose();
		goto(`/album/${target}`);
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
			launchJellyfinPlayback(jellyfinTracks, 0, shuffle, meta);
		} else if (sourceType === 'local' && localTracks.length > 0) {
			launchLocalPlayback(localTracks, 0, shuffle, meta);
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
			launchJellyfinPlayback(jellyfinTracks, index, false, meta);
		} else {
			launchLocalPlayback(localTracks, index, false, meta);
		}
	}

	function getTrackName(index: number): string {
		if (sourceType === 'jellyfin') return jellyfinTracks[index]?.title ?? '';
		return localTracks[index]?.title ?? '';
	}

	function getTrackNumber(index: number): number {
		if (sourceType === 'jellyfin') return jellyfinTracks[index]?.track_number ?? 0;
		return localTracks[index]?.track_number ?? 0;
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

	function isTrackPlaying(trackNum: number): boolean {
		return (
			playerStore.nowPlaying?.albumId === (mbid ?? albumId) &&
			playerStore.currentQueueItem?.trackNumber === trackNum &&
			playerStore.isPlaying
		);
	}
</script>

{#if open && album}
	<dialog class="modal modal-open">
		<div class="modal-box max-w-4xl p-0 overflow-hidden">
			<div class="flex gap-5 p-6 pb-4">
				<div class="flex-shrink-0">
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
						{:else}
							{@const localAlbum = album as LocalAlbumSummary}
							<span class="badge badge-sm badge-accent">Local</span>
							{#if localAlbum.primary_format}
								<span class="badge badge-sm badge-ghost">{localAlbum.primary_format}</span>
							{/if}
							{#if localAlbum.total_size_bytes > 0}
								<span class="badge badge-sm badge-ghost">{formatSize(localAlbum.total_size_bytes)}</span>
							{/if}
						{/if}
						{#if !canNavigate}
							<span class="badge badge-sm badge-warning badge-outline">No MBID</span>
						{/if}
					</div>
				</div>

				<button
					class="btn btn-sm btn-circle btn-ghost self-start -mr-2 -mt-2"
					onclick={handleClose}><X class="h-4 w-4" /></button
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
				{/if}
			</div>

			<div class="divider my-0 px-6"></div>

			<div class="px-6 pt-3 pb-5 max-h-[28rem] overflow-y-auto">
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
						{#each { length: trackCount } as _, i}
							{@const trackNum = getTrackNumber(i)}
							{@const playing = isTrackPlaying(trackNum)}
							<button
								class="flex items-center gap-3 w-full py-2 px-2 rounded-lg transition-colors text-left group/track {playing
									? 'bg-accent/10'
									: 'hover:bg-base-200'}"
								onclick={() => playTrack(i)}
							>
								<span
									class="font-mono w-6 text-right text-sm flex-shrink-0 {playing ? 'text-accent' : 'opacity-40'}"
									>{trackNum}</span
								>
								<span
									class="text-sm truncate flex-1 {playing ? 'text-accent' : ''}"
									>{getTrackName(i)}</span
								>
								{#if sourceType === 'jellyfin'}
									{@const dur = jellyfinTracks[i]?.duration_seconds}
									{#if dur}
										<span class="text-xs opacity-40 flex-shrink-0">{formatDuration(dur)}</span>
									{/if}
								{:else}
									{@const lt = localTracks[i]}
									{#if lt?.duration_seconds}
										<span class="text-xs opacity-40 flex-shrink-0"
											>{formatDuration(lt.duration_seconds)}</span
										>
									{/if}
								{/if}
							<span class={playing ? 'text-accent' : ''}>
									<Play class="h-4 w-4 flex-shrink-0 transition-opacity {playing
											? 'opacity-100'
											: 'text-accent opacity-0 group-hover/track:opacity-100'} fill-current" />
								</span>
							</button>
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
