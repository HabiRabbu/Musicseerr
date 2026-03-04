<script lang="ts">
	import { tick } from 'svelte';
	import { slide } from 'svelte/transition';
	import {
		removeTrackFromPlaylist,
		updatePlaylistTrack,
		reorderPlaylistTrack,
		type PlaylistDetail,
		type PlaylistTrack
	} from '$lib/api/playlists';
	import { playlistTrackToQueueItem } from '$lib/player/queueHelpers';
	import { playerStore } from '$lib/stores/player.svelte';
	import { toastStore } from '$lib/stores/toast';
	import { formatDurationSec } from '$lib/utils/formatting';
	import ContextMenu from '$lib/components/ContextMenu.svelte';
	import type { MenuItem } from '$lib/components/ContextMenu.svelte';
	import SourcePickerDropdown from '$lib/components/SourcePickerDropdown.svelte';
	import { Music, Trash2, ListPlus, ListStart, GripVertical } from 'lucide-svelte';

	interface Props {
		playlist: PlaylistDetail;
		ontrackchange: () => void;
	}

	let { playlist, ontrackchange }: Props = $props();

	let dragIndex = $state<number | null>(null);
	let dragOverIndex = $state<number | null>(null);
	let removingTrackIds = $state<Set<string>>(new Set());
	let liveMessage = $state('');

	let reorderTimeout: ReturnType<typeof setTimeout> | null = null;
	let pendingReorderTrackId: string | null = null;
	let pendingReorderPosition: number | null = null;
	let preKeyboardTracks: PlaylistTrack[] | null = null;

	async function removeTrack(track: PlaylistTrack) {
		if (removingTrackIds.has(track.id)) return;
		const prevTracks = [...playlist.tracks];
		const prevDuration = playlist.total_duration;
		removingTrackIds = new Set([...removingTrackIds, track.id]);
		playlist.tracks = playlist.tracks.filter((t) => t.id !== track.id);
		playlist.track_count = playlist.tracks.length;
		playlist.total_duration = Math.max(0, (playlist.total_duration ?? 0) - (track.duration ?? 0));
		try {
			await removeTrackFromPlaylist(playlist.id, track.id);
			toastStore.show({ message: `Removed "${track.track_name}"`, type: 'info' });
			liveMessage = `${track.track_name} removed from playlist`;
			ontrackchange();
		} catch {
			playlist.tracks = prevTracks;
			playlist.track_count = prevTracks.length;
			playlist.total_duration = prevDuration;
			toastStore.show({ message: 'Failed to remove track', type: 'error' });
		} finally {
			const next = new Set(removingTrackIds);
			next.delete(track.id);
			removingTrackIds = next;
		}
	}

	function addTrackToQueue(track: PlaylistTrack) {
		const item = playlistTrackToQueueItem(track);
		if (!item) {
			toastStore.show({ message: 'Track is not playable', type: 'error' });
			return;
		}
		playerStore.addToQueue(item);
	}

	function playTrackNext(track: PlaylistTrack) {
		const item = playlistTrackToQueueItem(track);
		if (!item) {
			toastStore.show({ message: 'Track is not playable', type: 'error' });
			return;
		}
		playerStore.playNext(item);
	}

	async function handleSourceChange(track: PlaylistTrack, newSourceType: string) {
		const prevSource = track.source_type;
		track.source_type = newSourceType;
		try {
			await updatePlaylistTrack(playlist.id, track.id, { source_type: newSourceType });
		} catch {
			track.source_type = prevSource;
			toastStore.show({ message: 'Failed to update source', type: 'error' });
		}
	}

	function handleDragStart(e: DragEvent, index: number) {
		if (e.dataTransfer) {
			e.dataTransfer.effectAllowed = 'move';
			e.dataTransfer.setData('text/plain', String(index));
		}
		dragIndex = index;
	}

	function handleDragOver(e: DragEvent, index: number) {
		e.preventDefault();
		dragOverIndex = index;
	}

	function handleDragLeave() {
		dragOverIndex = null;
	}

	async function handleDrop(e: DragEvent, toIndex: number) {
		e.preventDefault();
		if (dragIndex === null || dragIndex === toIndex) {
			dragIndex = null;
			dragOverIndex = null;
			return;
		}

		const fromIndex = dragIndex;
		const track = playlist.tracks[fromIndex];
		const prevTracks = [...playlist.tracks];

		const newTracks = [...playlist.tracks];
		newTracks.splice(fromIndex, 1);
		newTracks.splice(toIndex, 0, track);
		playlist.tracks = newTracks;

		dragIndex = null;
		dragOverIndex = null;

		try {
			await reorderPlaylistTrack(playlist.id, track.id, toIndex);
			liveMessage = `Track moved to position ${toIndex + 1}`;
		} catch {
			playlist.tracks = prevTracks;
			toastStore.show({ message: 'Failed to reorder track', type: 'error' });
		}
	}

	function handleDragEnd() {
		dragIndex = null;
		dragOverIndex = null;
	}

	async function handleTrackKeydown(e: KeyboardEvent, index: number) {
		let newIndex: number | null = null;
		if (e.key === 'ArrowUp' && index > 0) {
			e.preventDefault();
			newIndex = index - 1;
		} else if (e.key === 'ArrowDown' && index < playlist.tracks.length - 1) {
			e.preventDefault();
			newIndex = index + 1;
		}
		if (newIndex === null) return;

		const track = playlist.tracks[index];

		if (preKeyboardTracks === null) {
			preKeyboardTracks = [...playlist.tracks];
		}

		const newTracks = [...playlist.tracks];
		newTracks.splice(index, 1);
		newTracks.splice(newIndex, 0, track);
		playlist.tracks = newTracks;

		tick().then(() => {
			const handles = document.querySelectorAll<HTMLElement>('[aria-label="Drag to reorder"]');
			handles[newIndex!]?.focus();
		});

		liveMessage = `Track moved to position ${newIndex + 1}`;
		pendingReorderTrackId = track.id;
		pendingReorderPosition = newIndex;

		if (reorderTimeout) clearTimeout(reorderTimeout);
		reorderTimeout = setTimeout(async () => {
			const savedTracks = preKeyboardTracks;
			const trackId = pendingReorderTrackId!;
			const position = pendingReorderPosition!;
			preKeyboardTracks = null;
			pendingReorderTrackId = null;
			pendingReorderPosition = null;
			reorderTimeout = null;
			try {
				await reorderPlaylistTrack(playlist.id, trackId, position);
			} catch {
				if (savedTracks) playlist.tracks = savedTracks;
				toastStore.show({ message: 'Failed to reorder track', type: 'error' });
			}
		}, 400);
	}

	function getTrackMenuItems(track: PlaylistTrack): MenuItem[] {
		return [
			{
				label: 'Add to Queue',
				icon: ListPlus,
				onclick: () => addTrackToQueue(track)
			},
			{
				label: 'Play Next',
				icon: ListStart,
				onclick: () => playTrackNext(track)
			},
			{
				label: 'Remove',
				icon: Trash2,
				onclick: () => void removeTrack(track)
			}
		];
	}

	export function clearReorderState() {
		if (reorderTimeout) {
			clearTimeout(reorderTimeout);
			reorderTimeout = null;
		}
		preKeyboardTracks = null;
		pendingReorderTrackId = null;
		pendingReorderPosition = null;
	}
</script>

{#if playlist.tracks.length === 0}
	<div class="flex flex-col items-center justify-center py-16 gap-3">
		<Music class="h-12 w-12 text-base-content/20" />
		<h2 class="text-base font-semibold text-base-content/60">This playlist is empty</h2>
		<p class="text-sm text-base-content/40">Add tracks from album pages using the context menu</p>
	</div>
{:else}
	<ul class="list bg-base-200 rounded-box overflow-visible">
		{#each playlist.tracks as track, i (track.id)}
			<li
				transition:slide={{ duration: 200 }}
				class="group hover:bg-base-300/50 transition-colors p-3 sm:p-4"
				class:opacity-50={dragIndex === i}
				class:border-t-2={dragOverIndex === i && dragIndex !== null && dragIndex !== i}
				class:border-accent={dragOverIndex === i && dragIndex !== null && dragIndex !== i}
				draggable="true"
				ondragstart={(e) => handleDragStart(e, i)}
				ondragover={(e) => handleDragOver(e, i)}
				ondragleave={handleDragLeave}
				ondrop={(e) => void handleDrop(e, i)}
				ondragend={handleDragEnd}
				role="listitem"
				aria-roledescription="sortable"
			>
				<div class="flex items-center gap-4 w-full">
					<button
						class="cursor-grab active:cursor-grabbing p-1 touch-none flex-shrink-0"
						aria-label="Drag to reorder"
						onkeydown={(e) => void handleTrackKeydown(e, i)}
						tabindex="0"
					>
						<GripVertical class="h-4 w-4 text-base-content/30" />
					</button>

					<span class="text-base-content/40 text-sm w-6 text-center tabular-nums flex-shrink-0">{i + 1}</span>

					<div class="w-10 h-10 rounded-md overflow-hidden flex-shrink-0 bg-base-300">
						{#if track.cover_url}
							<img
								src={track.cover_url}
								alt=""
								class="w-full h-full object-cover"
								loading="lazy"
							/>
						{:else}
							<div class="w-full h-full flex items-center justify-center">
								<Music class="h-4 w-4 text-base-content/30" />
							</div>
						{/if}
					</div>

					<div class="flex-1 min-w-0">
						{#if track.album_id}
							<a href="/album/{track.album_id}" class="font-medium truncate text-sm block hover:underline">{track.track_name}</a>
						{:else}
							<span class="font-medium truncate text-sm block">{track.track_name}</span>
						{/if}
						<span class="text-xs text-base-content/60 truncate block">
							{#if track.artist_id}
								<a href="/artist/{track.artist_id}" class="hover:underline">{track.artist_name}</a>
							{:else}
								{track.artist_name}
							{/if}
							{#if track.album_name}
								<span class="text-base-content/30"> · </span>
								{#if track.album_id}
									<a href="/album/{track.album_id}" class="text-base-content/40 hover:underline">{track.album_name}</a>
								{:else}
									<span class="text-base-content/40">{track.album_name}</span>
								{/if}
							{/if}
						</span>
					</div>

					<span class="text-sm text-base-content/40 tabular-nums flex-shrink-0">
						{formatDurationSec(track.duration)}
					</span>

					<SourcePickerDropdown
						currentSource={track.source_type}
						availableSources={track.available_sources ?? [track.source_type]}
						onchange={(src) => void handleSourceChange(track, src)}
					/>

					<div
						class="opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity flex-shrink-0"
					>
						<ContextMenu items={getTrackMenuItems(track)} position="end" size="xs" />
					</div>
				</div>
			</li>
		{/each}
	</ul>
{/if}

<div class="sr-only" aria-live="polite" role="status">{liveMessage}</div>
