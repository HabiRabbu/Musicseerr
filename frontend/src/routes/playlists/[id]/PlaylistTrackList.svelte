<script lang="ts">
	import { tick } from 'svelte';
	import { slide, fly } from 'svelte/transition';
	import {
		removeTrackFromPlaylist,
		removeTracksFromPlaylist,
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
	import { Music, Trash2, ListPlus, ListStart, GripVertical, Play, X } from 'lucide-svelte';

	interface Props {
		playlist: PlaylistDetail;
		ontrackchange: () => void;
		onsourcechange?: () => void;
		onplaytrack?: (index: number) => void;
	}

	let { playlist, ontrackchange, onsourcechange, onplaytrack }: Props = $props();

	let dragIndex = $state<number | null>(null);
	let dragOverIndex = $state<number | null>(null);
	let removingTrackIds = $state<Set<string>>(new Set());
	let liveMessage = $state('');

	let reorderTimeout: ReturnType<typeof setTimeout> | null = null;
	let pendingReorderTrackId: string | null = null;
	let pendingReorderPosition: number | null = null;
	let preKeyboardTracks: PlaylistTrack[] | null = null;

	let selectedIds = $state<Set<string>>(new Set());
	let lastClickedIndex = $state<number | null>(null);
	let bulkRemoving = $state(false);
	let selectionMode = $derived(selectedIds.size > 0);

	function toggleTrackSelection(trackId: string, index: number, shiftKey: boolean) {
		const next = new Set(selectedIds);
		if (shiftKey && lastClickedIndex !== null) {
			const from = Math.min(lastClickedIndex, index);
			const to = Math.max(lastClickedIndex, index);
			for (let j = from; j <= to; j++) {
				next.add(playlist.tracks[j].id);
			}
		} else if (next.has(trackId)) {
			next.delete(trackId);
		} else {
			next.add(trackId);
		}
		selectedIds = next;
		lastClickedIndex = index;
	}

	function toggleSelectAll() {
		if (selectedIds.size === playlist.tracks.length) {
			selectedIds = new Set();
		} else {
			selectedIds = new Set(playlist.tracks.map((t) => t.id));
		}
	}

	function clearSelection() {
		selectedIds = new Set();
		lastClickedIndex = null;
	}

	async function removeSelectedTracks() {
		if (bulkRemoving || selectedIds.size === 0) return;
		const ids = [...selectedIds];
		const count = ids.length;
		const prevTracks = [...playlist.tracks];
		const prevDuration = playlist.total_duration;
		const prevCount = playlist.track_count;

		bulkRemoving = true;
		const removedDuration = prevTracks
			.filter((t) => selectedIds.has(t.id))
			.reduce((sum, t) => sum + (t.duration ?? 0), 0);
		playlist.tracks = playlist.tracks.filter((t) => !selectedIds.has(t.id));
		playlist.track_count = playlist.tracks.length;
		playlist.total_duration = Math.max(0, (playlist.total_duration ?? 0) - removedDuration);
		clearSelection();

		try {
			await removeTracksFromPlaylist(playlist.id, ids);
			toastStore.show({ message: `Removed ${count} track${count === 1 ? '' : 's'}`, type: 'info' });
			liveMessage = `${count} track${count === 1 ? '' : 's'} removed from playlist`;
			ontrackchange();
		} catch {
			playlist.tracks = prevTracks;
			playlist.track_count = prevCount;
			playlist.total_duration = prevDuration;
			toastStore.show({ message: 'Failed to remove tracks', type: 'error' });
		} finally {
			bulkRemoving = false;
		}
	}

	function handleWindowKeydown(e: KeyboardEvent) {
		if (!selectionMode) return;
		const tag = (e.target as HTMLElement)?.tagName;
		if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
		if (e.key === 'Delete' || e.key === 'Backspace') {
			e.preventDefault();
			void removeSelectedTracks();
		}
		if (e.key === 'Escape') {
			e.preventDefault();
			clearSelection();
		}
	}

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
		const prevSourceId = track.track_source_id;
		const prevFormat = track.format;
		const prevAvailableSources = track.available_sources;
		track.source_type = newSourceType;
		try {
			const updated = await updatePlaylistTrack(playlist.id, track.id, { source_type: newSourceType });
			track.track_source_id = updated.track_source_id;
			track.source_type = updated.source_type;
			track.format = updated.format;
			if (updated.available_sources && updated.available_sources.length > (prevAvailableSources?.length ?? 0)) {
				track.available_sources = updated.available_sources;
			}
			onsourcechange?.();
		} catch {
			track.source_type = prevSource;
			track.track_source_id = prevSourceId;
			track.format = prevFormat;
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

	export function clearSelectionState() {
		clearSelection();
	}
</script>

<svelte:window onkeydown={handleWindowKeydown} />

{#if playlist.tracks.length === 0}
	<div class="flex flex-col items-center justify-center py-16 gap-3">
		<Music class="h-12 w-12 text-base-content/20" />
		<h2 class="text-base font-semibold text-base-content/60">This playlist is empty</h2>
		<p class="text-sm text-base-content/40">Add tracks from album pages using the context menu</p>
	</div>
{:else}
	<ul class="list bg-base-200 rounded-box overflow-visible">
		{#if playlist.tracks.length > 1}
			<li class="px-3 sm:px-4 py-2 border-b border-base-300/50">
				<label class="flex items-center gap-2 cursor-pointer text-xs text-base-content/50">
					<input
						type="checkbox"
						class="checkbox checkbox-xs"
						checked={selectedIds.size === playlist.tracks.length}
						indeterminate={selectedIds.size > 0 && selectedIds.size < playlist.tracks.length}
						onchange={toggleSelectAll}
					/>
					Select all
				</label>
			</li>
		{/if}
		{#each playlist.tracks as track, i (track.id)}
			<li
				transition:slide={{ duration: 200 }}
				class="group transition-colors p-3 sm:p-4 {selectedIds.has(track.id) ? 'bg-primary/5' : 'hover:bg-base-300/50'}"
				class:opacity-50={dragIndex === i}
				class:border-t-2={dragOverIndex === i && dragIndex !== null && dragIndex !== i}
				class:border-accent={dragOverIndex === i && dragIndex !== null && dragIndex !== i}
				draggable={!selectionMode}
				ondragstart={(e) => handleDragStart(e, i)}
				ondragover={(e) => handleDragOver(e, i)}
				ondragleave={handleDragLeave}
				ondrop={(e) => void handleDrop(e, i)}
				ondragend={handleDragEnd}
				role="listitem"
				aria-roledescription="sortable"
			>
				<div class="flex items-center gap-4 w-full">
					{#if !selectionMode}
						<button
							class="cursor-grab active:cursor-grabbing p-1 touch-none flex-shrink-0"
							aria-label="Drag to reorder"
							onkeydown={(e) => void handleTrackKeydown(e, i)}
							tabindex="0"
						>
							<GripVertical class="h-4 w-4 text-base-content/30" />
						</button>
					{/if}

					<input
						type="checkbox"
						class="checkbox checkbox-sm flex-shrink-0"
						checked={selectedIds.has(track.id)}
						onclick={(e: MouseEvent) => {
							e.stopPropagation();
							toggleTrackSelection(track.id, i, e.shiftKey);
						}}
						aria-label="Select {track.track_name}"
					/>

					<span class="text-base-content/40 text-sm w-6 text-center tabular-nums flex-shrink-0 group-hover:hidden">{i + 1}</span>
					<button
						class="w-6 text-center flex-shrink-0 hidden group-hover:flex items-center justify-center cursor-pointer"
						aria-label="Play {track.track_name}"
						onclick={(e) => { e.stopPropagation(); onplaytrack?.(i); }}
					>
						<Play class="h-4 w-4 fill-current text-primary" />
					</button>

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

	{#if selectionMode}
		<div
			class="fixed left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 bg-base-300 border border-base-content/10 rounded-box px-4 py-3 shadow-xl {playerStore.isPlayerVisible && playerStore.nowPlaying ? 'bottom-28' : 'bottom-4'}"
			transition:fly={{ y: 40, duration: 200 }}
		>
			<span class="text-sm font-medium">
				{selectedIds.size} selected
			</span>
			<button class="btn btn-ghost btn-sm" onclick={clearSelection}>
				<X class="h-4 w-4" />
				Deselect
			</button>
			<button
				class="btn btn-error btn-sm"
				onclick={() => void removeSelectedTracks()}
				disabled={bulkRemoving}
			>
				{#if bulkRemoving}
					<span class="loading loading-spinner loading-xs"></span>
				{:else}
					<Trash2 class="h-4 w-4" />
				{/if}
				Delete
			</button>
		</div>
	{/if}
{/if}

<div class="sr-only" aria-live="polite" role="status">{liveMessage}</div>
