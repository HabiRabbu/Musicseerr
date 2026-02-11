<script lang="ts">
	import { goto } from '$app/navigation';
	import { API, TOAST_DURATION } from '$lib/constants';
	import { colors } from '$lib/colors';
	import { toastStore } from '$lib/stores/toast';
	import { playerStore } from '$lib/stores/player.svelte';
	import { launchYouTubePlayback } from '$lib/player/launchYouTubePlayback';
	import { launchTrackPlayback } from '$lib/player/launchTrackPlayback';
	import { getCoverUrl } from '$lib/utils/errorHandling';
	import AlbumImage from '$lib/components/AlbumImage.svelte';
	import PlayIcon from '$lib/components/PlayIcon.svelte';
	import YouTubeIcon from '$lib/components/YouTubeIcon.svelte';
	import type { YouTubeLink, YouTubeTrackLink } from '$lib/types';

	interface Props {
		open: boolean;
		link: YouTubeLink | null;
		onclose: () => void;
		onedit: (link: YouTubeLink) => void;
		ondelete: (albumId: string) => void;
	}

	let { open = $bindable(), link, onclose, onedit, ondelete }: Props = $props();

	let tracks = $state<YouTubeTrackLink[]>([]);
	let loadingTracks = $state(false);
	let confirmingDelete = $state(false);
	let deleting = $state(false);
	let fetchId = 0;

	let canNavigate = $derived(!link?.is_manual && !!link?.album_id);

	$effect(() => {
		if (open && link) {
			confirmingDelete = false;
			deleting = false;
			fetchTracks(link.album_id);
		}
		if (!open) {
			tracks = [];
		}
	});

	async function fetchTracks(albumId: string): Promise<void> {
		const id = ++fetchId;
		loadingTracks = true;
		try {
			const res = await fetch(API.youtube.trackLinks(albumId));
			if (id !== fetchId) return;
			if (res.ok) tracks = await res.json();
		} catch {} finally {
			if (id === fetchId) loadingTracks = false;
		}
	}

	function handleClose(): void {
		open = false;
		onclose();
	}

	function goToAlbum(): void {
		if (!canNavigate || !link) return;
		const albumId = link.album_id;
		handleClose();
		goto(`/album/${albumId}`);
	}

	async function playFullAlbum(): Promise<void> {
		if (!link?.video_id) return;
		try {
			await launchYouTubePlayback(
				{
					albumId: link.album_id,
					albumName: link.album_name,
					artistName: link.artist_name,
					coverUrl: getCoverUrl(link.cover_url, link.album_id),
					videoId: link.video_id,
					embedUrl: link.embed_url ?? undefined
				},
				{
					onLoadError: () => {
						toastStore.show({ message: 'Failed to load video', type: 'error', duration: TOAST_DURATION });
					}
				}
			);
		} catch {}
	}

	function playAllTracks(shuffle: boolean = false): void {
		if (!link || tracks.length === 0) return;
		launchTrackPlayback(tracks, 0, shuffle, {
			albumId: link.album_id,
			albumName: link.album_name,
			artistName: link.artist_name,
			coverUrl: getCoverUrl(link.cover_url, link.album_id)
		});
	}

	function playTrack(trackNumber: number): void {
		if (!link) return;
		const idx = tracks.findIndex((t) => t.track_number === trackNumber);
		if (idx === -1) return;
		launchTrackPlayback(tracks, idx, false, {
			albumId: link.album_id,
			albumName: link.album_name,
			artistName: link.artist_name,
			coverUrl: getCoverUrl(link.cover_url, link.album_id)
		});
	}

	function handleEdit(): void {
		if (!link) return;
		onedit(link);
	}

	async function handleDelete(): Promise<void> {
		if (!link) return;
		if (!confirmingDelete) {
			confirmingDelete = true;
			return;
		}
		deleting = true;
		try {
			const res = await fetch(API.youtube.deleteLink(link.album_id), { method: 'DELETE' });
			if (res.ok) {
				toastStore.show({ message: 'Link removed', type: 'success', duration: TOAST_DURATION });
				open = false;
				ondelete(link.album_id);
			} else {
				toastStore.show({ message: 'Failed to delete link', type: 'error', duration: TOAST_DURATION });
			}
		} catch {
			toastStore.show({ message: 'Failed to delete link', type: 'error', duration: TOAST_DURATION });
		} finally {
			deleting = false;
			confirmingDelete = false;
		}
	}

	function formatDate(iso: string): string {
		return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
	}
</script>

{#if open && link}
	<dialog class="modal modal-open">
		<div class="modal-box max-w-2xl p-0 overflow-hidden">
			<div class="flex gap-5 p-6 pb-4">
				<div class="flex-shrink-0">
					{#if canNavigate}
						<button onclick={goToAlbum} class="block rounded-lg overflow-hidden shadow-lg hover:shadow-xl transition-shadow cursor-pointer" aria-label="Go to album">
							<AlbumImage
								mbid={link.album_id}
								customUrl={link.cover_url}
								alt={link.album_name}
								size="xl"
								rounded="none"
								className="w-36 h-36"
							/>
						</button>
					{:else}
						<div class="rounded-lg overflow-hidden shadow-lg">
							<AlbumImage
								mbid={link.album_id}
								customUrl={link.cover_url}
								alt={link.album_name}
								size="xl"
								rounded="none"
								className="w-36 h-36"
							/>
						</div>
					{/if}
				</div>

				<div class="flex flex-col justify-center min-w-0 flex-1">
					{#if canNavigate}
						<button onclick={goToAlbum} class="text-xl font-bold truncate text-left hover:text-accent transition-colors cursor-pointer">
							{link.album_name}
						</button>
					{:else}
						<h3 class="text-xl font-bold truncate">{link.album_name}</h3>
					{/if}
					<p class="text-base opacity-70 truncate">{link.artist_name}</p>
					<div class="flex items-center gap-2 mt-2">
						<YouTubeIcon class="h-4 w-4 text-red-500" />
						<span class="text-xs opacity-50">{formatDate(link.created_at)}</span>
					</div>
					{#if link.is_manual}
						<span class="badge badge-xs badge-ghost mt-1">Manual</span>
					{/if}
				</div>

				<button class="btn btn-sm btn-circle btn-ghost self-start -mr-2 -mt-2" onclick={handleClose}>✕</button>
			</div>

			<div class="flex items-center gap-2 px-6 pb-4 flex-wrap">
				{#if link.video_id}
					<button class="btn btn-sm btn-accent gap-1" onclick={playFullAlbum}>
						<PlayIcon class="h-4 w-4" />
						Full Album
					</button>
				{/if}
				{#if tracks.length > 0}
					<button class="btn btn-sm btn-accent gap-1" onclick={() => playAllTracks(false)}>
						<PlayIcon class="h-4 w-4" />
						Play All
					</button>
					<button class="btn btn-sm btn-ghost gap-1" onclick={() => playAllTracks(true)}>
						<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5" />
						</svg>
						Shuffle
					</button>
				{/if}
				<div class="flex-1"></div>
				<button class="btn btn-sm btn-ghost gap-1" onclick={handleEdit}>
					<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
						<path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
					</svg>
					Edit
				</button>
				{#if confirmingDelete}
					<button class="btn btn-sm btn-error gap-1" onclick={handleDelete} disabled={deleting}>
						{#if deleting}
							<span class="loading loading-spinner loading-xs"></span>
						{:else}
							Confirm
						{/if}
					</button>
					<button class="btn btn-sm btn-ghost" onclick={() => { confirmingDelete = false; }}>Cancel</button>
				{:else}
					<button class="btn btn-sm btn-ghost text-error gap-1" onclick={handleDelete}>
						<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
						</svg>
						Delete
					</button>
				{/if}
			</div>

			<div class="divider my-0 px-6"></div>

			<div class="px-6 pt-3 pb-5 max-h-96 overflow-y-auto">
				{#if loadingTracks}
					<div class="flex justify-center py-6">
						<span class="loading loading-spinner loading-md"></span>
					</div>
				{:else if tracks.length > 0}
					<div class="flex flex-col">
						{#each tracks as track}
							{@const isCurrentlyPlaying = playerStore.nowPlaying?.albumId === link.album_id && playerStore.currentQueueItem?.trackNumber === track.track_number && playerStore.isPlaying}
							<button
								class="flex items-center gap-3 w-full py-2 px-2 rounded-lg transition-colors text-left group/track {isCurrentlyPlaying ? '' : 'hover:bg-base-200'}"
								style={isCurrentlyPlaying ? `background-color: ${colors.accent}20;` : ''}
								onclick={() => playTrack(track.track_number)}
							>
								<span class="font-mono w-6 text-right text-sm flex-shrink-0 {isCurrentlyPlaying ? '' : 'opacity-40'}" style={isCurrentlyPlaying ? `color: ${colors.accent};` : ''}>{track.track_number}</span>
								<span class="text-sm truncate flex-1" style={isCurrentlyPlaying ? `color: ${colors.accent};` : ''}>{track.track_name}</span>
								<span style={isCurrentlyPlaying ? `color: ${colors.accent};` : ''}>
									<PlayIcon class="h-4 w-4 flex-shrink-0 transition-opacity {isCurrentlyPlaying ? 'opacity-100' : 'text-accent opacity-0 group-hover/track:opacity-100'}" />
								</span>
							</button>
						{/each}
					</div>
				{:else if !link.video_id}
					<p class="text-sm opacity-50 text-center py-6">No tracks linked yet</p>
				{:else}
					<p class="text-sm opacity-50 text-center py-6">Album-level link only — no individual tracks</p>
				{/if}
			</div>
		</div>

		<form method="dialog" class="modal-backdrop">
			<button onclick={handleClose}>close</button>
		</form>
	</dialog>
{/if}
