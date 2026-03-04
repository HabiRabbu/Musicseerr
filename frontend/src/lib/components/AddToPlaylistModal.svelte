<script lang="ts">
	import { CirclePlus, Check, Plus, CircleCheck } from 'lucide-svelte';
	import {
		fetchPlaylists,
		createPlaylist,
		addTracksToPlaylist,
		queueItemToTrackData,
		checkTrackMembership
	} from '$lib/api/playlists';
	import type { PlaylistSummary } from '$lib/api/playlists';
	import type { QueueItem } from '$lib/player/types';
	import PlaylistMosaic from './PlaylistMosaic.svelte';

	let dialogEl: HTMLDialogElement | undefined = $state();
	let pendingTracks: QueueItem[] = [];
	let trackCount = $state(0);
	let playlists = $state<PlaylistSummary[]>([]);
	let loading = $state(true);
	let fetchError = $state<string | null>(null);
	let addedSet = $state(new Set<string>());
	let addingSet = $state(new Set<string>());
	let membership = $state<Record<string, number[]>>({});
	let newName = $state('');
	let creating = $state(false);
	let statusMessage = $state<{ text: string; type: 'success' | 'error' } | null>(null);

	function existingCount(playlistId: string): number {
		return membership[playlistId]?.length ?? 0;
	}

	function allTracksExist(playlistId: string): boolean {
		return trackCount > 0 && existingCount(playlistId) >= trackCount;
	}

	function someTracksExist(playlistId: string): boolean {
		const count = existingCount(playlistId);
		return count > 0 && count < trackCount;
	}

	export function open(items: QueueItem[]) {
		pendingTracks = items;
		trackCount = items.length;
		addedSet = new Set();
		addingSet = new Set();
		membership = {};
		newName = '';
		fetchError = null;
		statusMessage = null;
		loading = true;
		dialogEl?.showModal();
		loadPlaylists();
	}

	export function close() {
		dialogEl?.close();
	}

	async function loadPlaylists() {
		try {
			playlists = await fetchPlaylists();
			if (pendingTracks.length > 0) {
				const trackIdentifiers = pendingTracks.map((t) => ({
					track_name: t.trackName,
					artist_name: t.artistName,
					album_name: t.albumName
				}));
				membership = await checkTrackMembership(trackIdentifiers);
			}
		} catch {
			fetchError = 'Failed to load playlists';
		} finally {
			loading = false;
		}
	}

	function showStatus(text: string, type: 'success' | 'error') {
		statusMessage = { text, type };
		setTimeout(() => { statusMessage = null; }, 3000);
	}

	async function handleAdd(playlist: PlaylistSummary) {
		if (addedSet.has(playlist.id) || addingSet.has(playlist.id)) return;
		if (allTracksExist(playlist.id)) return;
		if (pendingTracks.length === 0) return;
		addingSet = new Set([...addingSet, playlist.id]);
		try {
			const existingIndices = new Set(membership[playlist.id] ?? []);
			const tracksToAdd = pendingTracks.filter((_, i) => !existingIndices.has(i));
			if (tracksToAdd.length === 0) {
				addedSet = new Set([...addedSet, playlist.id]);
				return;
			}
			const trackData = tracksToAdd.map(queueItemToTrackData);
			await addTracksToPlaylist(playlist.id, trackData);
			addedSet = new Set([...addedSet, playlist.id]);
			const allIndices = Array.from({ length: trackCount }, (_, i) => i);
			membership = { ...membership, [playlist.id]: allIndices };
			playlists = playlists.map((p) =>
				p.id === playlist.id ? { ...p, track_count: p.track_count + trackData.length } : p
			);
			const addedCount = trackData.length;
			if (existingIndices.size > 0) {
				showStatus(`Added ${addedCount} new track${addedCount === 1 ? '' : 's'} to '${playlist.name}' (${existingIndices.size} already existed)`, 'success');
			} else {
				showStatus(`Added to '${playlist.name}'`, 'success');
			}
		} catch {
			showStatus('Failed to add tracks', 'error');
		} finally {
			const next = new Set(addingSet);
			next.delete(playlist.id);
			addingSet = next;
		}
	}

	async function handleCreate() {
		const name = newName.trim();
		if (!name || creating || pendingTracks.length === 0) return;
		creating = true;
		try {
			const detail = await createPlaylist(name);
			const trackData = pendingTracks.map(queueItemToTrackData);
			await addTracksToPlaylist(detail.id, trackData);
			addedSet = new Set([...addedSet, detail.id]);
			const allIndices = Array.from({ length: trackCount }, (_, i) => i);
			membership = { ...membership, [detail.id]: allIndices };
			playlists = [
				{
					id: detail.id,
					name: detail.name,
					track_count: trackData.length,
					total_duration: detail.total_duration,
					cover_urls: detail.cover_urls,
					custom_cover_url: detail.custom_cover_url,
					created_at: detail.created_at,
					updated_at: detail.updated_at
				},
				...playlists
			];
			newName = '';
			showStatus(`Created '${name}' and added tracks`, 'success');
		} catch {
			showStatus('Failed to create playlist', 'error');
		} finally {
			creating = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleCreate();
		}
	}

	let trackLabel = $derived(trackCount === 1 ? '1 track' : `${trackCount} tracks`);
	let canAdd = $derived(trackCount > 0);
</script>

<dialog bind:this={dialogEl} class="modal">
	<div class="modal-box max-w-md">
		<h3 class="text-lg font-bold">Add to Playlist</h3>
		<p class="text-sm text-base-content/60 mt-1">{trackLabel}</p>

		<div class="flex items-center gap-2 mt-4">
			<input
				type="text"
				class="input input-sm flex-1"
				placeholder="New playlist name..."
				bind:value={newName}
				onkeydown={handleKeydown}
				disabled={creating}
			/>
			<button
				class="btn btn-sm btn-accent btn-circle"
				onclick={handleCreate}
				disabled={!newName.trim() || creating || !canAdd}
				aria-label="Create playlist"
			>
				{#if creating}
					<span class="loading loading-spinner loading-xs"></span>
				{:else}
					<Plus class="h-4 w-4" />
				{/if}
			</button>
		</div>

		<div class="divider my-1"></div>

		{#if loading}
			<div class="flex flex-col gap-2">
				<div class="skeleton h-10 w-full" data-testid="playlist-skeleton"></div>
				<div class="skeleton h-10 w-full" data-testid="playlist-skeleton"></div>
				<div class="skeleton h-10 w-full" data-testid="playlist-skeleton"></div>
			</div>
		{:else if fetchError}
			<div role="alert" class="alert alert-error">
				<span>{fetchError}</span>
			</div>
		{:else if playlists.length === 0}
			<p class="text-center text-base-content/50 py-4">No playlists yet</p>
		{:else}
			<div class="max-h-64 overflow-y-auto">
				{#each playlists as playlist (playlist.id)}
					<div class="flex items-center gap-3 p-2 rounded-lg hover:bg-base-200">
						<PlaylistMosaic
							coverUrls={playlist.cover_urls}
							customCoverUrl={playlist.custom_cover_url}
							size="w-10 h-10"
							rounded="rounded-md"
						/>
						<span class="truncate flex-1">{playlist.name}</span>
						<span class="text-sm text-base-content/60">{playlist.track_count}</span>
						{#if addedSet.has(playlist.id) || allTracksExist(playlist.id)}
							<button class="btn btn-ghost btn-sm btn-circle text-success" disabled aria-label="Already in playlist">
								<Check class="h-4 w-4" />
							</button>
						{:else if addingSet.has(playlist.id)}
							<button class="btn btn-ghost btn-sm btn-circle" disabled aria-label="Adding">
								<span class="loading loading-spinner loading-sm"></span>
							</button>
						{:else if someTracksExist(playlist.id)}
							<div class="tooltip tooltip-left" data-tip="{existingCount(playlist.id)} of {trackCount} already in playlist">
								<button
									class="btn btn-ghost btn-sm btn-circle text-warning"
									onclick={() => handleAdd(playlist)}
									disabled={!canAdd}
									aria-label="Add new tracks to {playlist.name}"
								>
									<CircleCheck class="h-4 w-4" />
								</button>
							</div>
						{:else}
							<button
								class="btn btn-ghost btn-sm btn-circle"
								onclick={() => handleAdd(playlist)}
								disabled={!canAdd}
								aria-label="Add to {playlist.name}"
							>
								<CirclePlus class="h-4 w-4" />
							</button>
						{/if}
					</div>
				{/each}
			</div>
		{/if}

		<div class="modal-action">
			{#if statusMessage}
				<div class="flex-1">
					<div role="alert" class="alert {statusMessage.type === 'success' ? 'alert-success' : 'alert-error'} alert-sm py-1 px-3">
						<span class="text-sm">{statusMessage.text}</span>
					</div>
				</div>
			{/if}
			<form method="dialog">
				<button class="btn btn-ghost">Done</button>
			</form>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button>close</button>
	</form>
</dialog>
