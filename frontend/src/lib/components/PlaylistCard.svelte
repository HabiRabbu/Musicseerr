<script lang="ts">
	import { onDestroy } from 'svelte';
	import type { PlaylistSummary } from '$lib/api/playlists';
	import { fetchPlaylist, deletePlaylist } from '$lib/api/playlists';
	import { playlistTrackToQueueItem } from '$lib/player/queueHelpers';
	import { playerStore } from '$lib/stores/player.svelte';
	import { toastStore } from '$lib/stores/toast';
	import { formatTotalDurationSec } from '$lib/utils/formatting';
	import { Play, Shuffle, Trash2 } from 'lucide-svelte';
	import PlaylistMosaic from './PlaylistMosaic.svelte';

	interface Props {
		playlist: PlaylistSummary;
		ondelete?: (playlistId: string) => void;
	}

	let { playlist, ondelete }: Props = $props();

	let playLoading = $state(false);
	let shuffleLoading = $state(false);
	let deleteConfirming = $state(false);
	let deleting = $state(false);
	let confirmTimer: ReturnType<typeof setTimeout> | undefined;

	let durationText = $derived(
		playlist.total_duration ? formatTotalDurationSec(playlist.total_duration) : ''
	);

	let subtitle = $derived(
		`${playlist.track_count} track${playlist.track_count === 1 ? '' : 's'}${durationText ? ` · ${durationText}` : ''}`
	);

	let hasPlayableTracks = $derived(playlist.track_count > 0);

	async function handlePlay(e: Event) {
		e.preventDefault();
		e.stopPropagation();
		if (playLoading || shuffleLoading || !hasPlayableTracks) return;
		playLoading = true;
		try {
			const detail = await fetchPlaylist(playlist.id);
			const items = detail.tracks
				.map(playlistTrackToQueueItem)
				.filter((item): item is NonNullable<typeof item> => item !== null);
			if (items.length === 0) {
				toastStore.show({ message: 'Nothing here can be played right now', type: 'info' });
				return;
			}
			playerStore.playQueue(items, 0, false);
		} catch {
			toastStore.show({ message: "Couldn't load this playlist", type: 'error' });
		} finally {
			playLoading = false;
		}
	}

	async function handleShuffle(e: Event) {
		e.preventDefault();
		e.stopPropagation();
		if (shuffleLoading || playLoading || !hasPlayableTracks) return;
		shuffleLoading = true;
		try {
			const detail = await fetchPlaylist(playlist.id);
			const items = detail.tracks
				.map(playlistTrackToQueueItem)
				.filter((item): item is NonNullable<typeof item> => item !== null);
			if (items.length === 0) {
				toastStore.show({ message: 'Nothing here can be played right now', type: 'info' });
				return;
			}
			playerStore.playQueue(items, 0, true);
		} catch {
			toastStore.show({ message: "Couldn't load this playlist", type: 'error' });
		} finally {
			shuffleLoading = false;
		}
	}

	function handleDeleteClick(e: Event) {
		e.preventDefault();
		e.stopPropagation();
		if (deleting) return;

		if (!deleteConfirming) {
			deleteConfirming = true;
			confirmTimer = setTimeout(() => {
				deleteConfirming = false;
			}, 3000);
			return;
		}

		void confirmDelete();
	}

	async function confirmDelete() {
		clearTimeout(confirmTimer);
		deleting = true;
		try {
			await deletePlaylist(playlist.id);
			toastStore.show({ message: 'Playlist deleted', type: 'success' });
			ondelete?.(playlist.id);
		} catch {
			toastStore.show({ message: "Couldn't delete the playlist", type: 'error' });
		} finally {
			deleting = false;
			deleteConfirming = false;
		}
	}

	onDestroy(() => {
		clearTimeout(confirmTimer);
	});
</script>

<div
	class="card card-sm bg-base-100 w-full shadow-sm shrink-0 group relative transition-all hover:shadow-[0_0_20px_rgba(174,213,242,0.15)]"
>
	<a
		href="/playlists/{playlist.id}"
		class="block relative z-0 transition-transform active:scale-95 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-base-100 rounded-t-box"
		aria-label="Open {playlist.name}"
	>
		<figure class="aspect-square overflow-hidden relative">
			<div
				class="w-full h-full transition-transform duration-200 group-hover:scale-105 transform-gpu"
			>
				<PlaylistMosaic
					coverUrls={playlist.cover_urls}
					customCoverUrl={playlist.custom_cover_url}
					size="w-full h-full"
					rounded="none"
				/>
			</div>
		</figure>
		<div class="px-3 pt-3 pb-1">
			<h3 class="text-sm font-semibold line-clamp-1">{playlist.name}</h3>
			<p class="text-xs text-base-content/60 mt-0.5">{subtitle}</p>
		</div>
	</a>

	<div class="flex items-center gap-1 px-3 pb-2.5 pt-1.5">
		<button
			class="btn btn-circle btn-sm bg-success text-success-content border-none shadow-md hover:scale-110 active:scale-95 transition-transform duration-150"
			onclick={handlePlay}
			disabled={!hasPlayableTracks || playLoading}
			aria-label="Play {playlist.name}"
			title={hasPlayableTracks ? `Play ${playlist.name}` : 'No tracks to play'}
		>
			{#if playLoading}
				<span class="loading loading-spinner loading-xs"></span>
			{:else}
				<Play class="h-4 w-4 fill-current" />
			{/if}
		</button>

		<button
			class="btn btn-circle btn-sm btn-ghost text-base-content/50 hover:text-base-content transition-colors duration-150"
			onclick={handleShuffle}
			disabled={!hasPlayableTracks || shuffleLoading}
			aria-label="Shuffle {playlist.name}"
			title={hasPlayableTracks ? `Shuffle ${playlist.name}` : 'No tracks to shuffle'}
		>
			{#if shuffleLoading}
				<span class="loading loading-spinner loading-xs"></span>
			{:else}
				<Shuffle class="h-3.5 w-3.5" />
			{/if}
		</button>

		<div class="ml-auto">
			<button
				class="btn btn-circle btn-sm transition-all duration-150 {deleteConfirming
					? 'btn-error shadow-md animate-pulse'
					: 'btn-ghost text-base-content/50 hover:text-error'}"
				onclick={handleDeleteClick}
				disabled={deleting}
				aria-label={deleteConfirming
					? `Confirm delete ${playlist.name}`
					: `Delete ${playlist.name}`}
				title={deleteConfirming ? 'Click again to confirm' : `Delete ${playlist.name}`}
			>
				{#if deleting}
					<span class="loading loading-spinner loading-xs"></span>
				{:else}
					<Trash2 class="h-3.5 w-3.5" />
				{/if}
			</button>
		</div>
	</div>
</div>
