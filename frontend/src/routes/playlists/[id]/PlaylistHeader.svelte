<script lang="ts">
	import {
		updatePlaylist,
		uploadPlaylistCover,
		deletePlaylistCover,
		type PlaylistDetail
	} from '$lib/api/playlists';
	import { toastStore } from '$lib/stores/toast';
	import { formatTotalDurationSec, formatRelativeTime } from '$lib/utils/formatting';
	import PlaylistMosaic from '$lib/components/PlaylistMosaic.svelte';
	import ContextMenu from '$lib/components/ContextMenu.svelte';
	import type { MenuItem } from '$lib/components/ContextMenu.svelte';
	import { Play, Shuffle, Pencil, Check, X } from 'lucide-svelte';

	interface Props {
		playlist: PlaylistDetail;
		onplayall: () => void;
		onshuffleall: () => void;
		ondeleteclick: () => void;
		onplaylistupdate: (updated: PlaylistDetail) => void;
	}

	let { playlist, onplayall, onshuffleall, ondeleteclick, onplaylistupdate }: Props = $props();

	import { Trash2 } from 'lucide-svelte';

	let editingName = $state(false);
	let nameInput = $state('');
	let savingName = $state(false);
	let nameInputEl = $state<HTMLInputElement | null>(null);
	let saveBtnEl = $state<HTMLButtonElement | null>(null);

	let coverInput = $state<HTMLInputElement | null>(null);
	let uploading = $state(false);
	let coverPreview = $state<string | null>(null);

	$effect(() => {
		if (editingName && nameInputEl) {
			nameInputEl.focus();
			nameInputEl.select();
		}
	});

	$effect(() => {
		if (saveBtnEl) {
			const btn = saveBtnEl;
			const handler = () => {
				void saveName();
			};
			btn.addEventListener('click', handler);
			return () => btn.removeEventListener('click', handler);
		}
	});

	function buildUpdatedPlaylist(changes: Partial<PlaylistDetail>): PlaylistDetail {
		return {
			...playlist,
			...changes
		};
	}

	function startEditName() {
		nameInput = playlist.name;
		editingName = true;
	}

	async function saveName() {
		if (savingName) return;
		const trimmed = nameInput.trim();
		if (!trimmed || trimmed === playlist.name) {
			editingName = false;
			return;
		}
		savingName = true;
		try {
			const updated = await updatePlaylist(playlist.id, { name: trimmed });
			editingName = false;
			onplaylistupdate(
				buildUpdatedPlaylist({
					name: updated.name,
					updated_at: updated.updated_at
				})
			);
			toastStore.show({ message: 'Playlist renamed', type: 'success' });
		} catch {
			toastStore.show({ message: "Couldn't rename the playlist", type: 'error' });
		} finally {
			savingName = false;
		}
	}

	function cancelEditName() {
		editingName = false;
		nameInput = '';
	}

	function handleNameKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') void saveName();
		if (e.key === 'Escape') cancelEditName();
	}

	function triggerCoverUpload() {
		coverInput?.click();
	}

	async function handleCoverSelect(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		if (!file.type.match(/^image\/(jpeg|png|webp)$/)) {
			toastStore.show({ message: 'Please select a JPEG, PNG, or WebP image', type: 'error' });
			input.value = '';
			return;
		}
		if (file.size > 2 * 1024 * 1024) {
			toastStore.show({ message: 'Image must be under 2MB', type: 'error' });
			input.value = '';
			return;
		}

		coverPreview = URL.createObjectURL(file);
		uploading = true;
		try {
			const result = await uploadPlaylistCover(playlist.id, file);
			onplaylistupdate(
				buildUpdatedPlaylist({
					custom_cover_url: result.cover_url + '?t=' + Date.now()
				})
			);
			toastStore.show({ message: 'Cover updated', type: 'success' });
		} catch {
			toastStore.show({ message: "Couldn't upload the cover", type: 'error' });
		} finally {
			if (coverPreview) {
				URL.revokeObjectURL(coverPreview);
				coverPreview = null;
			}
			uploading = false;
			input.value = '';
		}
	}

	async function removeCover() {
		try {
			await deletePlaylistCover(playlist.id);
			onplaylistupdate(buildUpdatedPlaylist({ custom_cover_url: null }));
			toastStore.show({ message: 'Cover removed', type: 'success' });
		} catch {
			toastStore.show({ message: "Couldn't remove the cover", type: 'error' });
		}
	}

	function getHeaderMenuItems(): MenuItem[] {
		return [
			{
				label: 'Delete Playlist',
				icon: Trash2,
				className: 'text-error',
				onclick: ondeleteclick
			}
		];
	}

	let coverDisplayUrl = $derived(coverPreview ?? playlist.custom_cover_url ?? null);

	export function cleanupPreview() {
		if (coverPreview) {
			URL.revokeObjectURL(coverPreview);
			coverPreview = null;
		}
	}
</script>

<div class="flex flex-col lg:flex-row gap-6 lg:gap-8">
	<div class="relative group w-full lg:w-64 xl:w-80 shrink-0">
		<PlaylistMosaic
			coverUrls={playlist.cover_urls}
			customCoverUrl={coverDisplayUrl}
			size="w-full aspect-square"
			rounded="rounded-box"
		/>
		<div class="absolute inset-0 rounded-box shadow-2xl pointer-events-none"></div>
		{#if uploading}
			<div class="absolute inset-0 flex items-center justify-center bg-base-100/60 rounded-box">
				<span class="loading loading-spinner loading-md"></span>
			</div>
		{/if}
		<div
			class="absolute bottom-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity"
		>
			<button
				type="button"
				class="btn btn-circle btn-xs bg-base-100/80 hover:bg-base-100 border-0"
				onclick={triggerCoverUpload}
				aria-label="Upload cover image"
				disabled={uploading}
			>
				<Pencil class="h-3 w-3" />
			</button>
			{#if playlist.custom_cover_url}
				<button
					type="button"
					class="btn btn-circle btn-xs bg-base-100/80 hover:bg-error/80 border-0"
					onclick={() => void removeCover()}
					aria-label="Remove custom cover"
				>
					<X class="h-3 w-3" />
				</button>
			{/if}
		</div>
		<input
			type="file"
			accept="image/jpeg,image/png,image/webp"
			class="hidden"
			bind:this={coverInput}
			onchange={handleCoverSelect}
		/>
	</div>

	<div class="flex flex-col gap-1.5 flex-1 min-w-0 lg:justify-end">
		<span class="text-xs sm:text-sm font-semibold text-base-content/50 uppercase tracking-wider">
			Playlist
		</span>

		{#if editingName}
			<div class="flex items-center gap-2">
				<input
					type="text"
					bind:this={nameInputEl}
					bind:value={nameInput}
					onkeydown={handleNameKeydown}
					class="input input-sm text-3xl sm:text-4xl font-bold w-full"
					placeholder="Playlist name"
					maxlength={100}
				/>
				<button
					bind:this={saveBtnEl}
					class="btn btn-ghost btn-sm btn-circle"
					aria-label="Save name"
				>
					<Check class="h-4 w-4 text-success" />
				</button>
				<button
					onclick={cancelEditName}
					class="btn btn-ghost btn-sm btn-circle"
					aria-label="Cancel"
				>
					<X class="h-4 w-4 text-error" />
				</button>
			</div>
		{:else}
			<button
				type="button"
				onclick={startEditName}
				class="group/name flex items-center gap-2 text-left"
				aria-label="Edit playlist name"
			>
				<h1 class="text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-bold leading-tight truncate">
					{playlist.name}
				</h1>
				<Pencil
					class="h-4 w-4 shrink-0 text-base-content/30 opacity-0 group-hover/name:opacity-100 transition-opacity"
				/>
			</button>
		{/if}

		<div class="flex flex-wrap items-center gap-2 text-sm text-base-content/60">
			<span>{playlist.track_count} track{playlist.track_count === 1 ? '' : 's'}</span>
			{#if playlist.total_duration}
				<span class="opacity-50">•</span>
				<span>{formatTotalDurationSec(playlist.total_duration)}</span>
			{/if}
			<span class="opacity-50">•</span>
			<span>Created {formatRelativeTime(new Date(playlist.created_at))}</span>
		</div>

		<div class="flex items-center gap-3 pt-4">
			<button
				type="button"
				class="btn btn-accent"
				onclick={onplayall}
				disabled={playlist.track_count === 0}
			>
				<Play class="h-4 w-4" />
				Play All
			</button>
			<button
				type="button"
				class="btn btn-ghost"
				onclick={onshuffleall}
				disabled={playlist.track_count < 2}
			>
				<Shuffle class="h-4 w-4" />
				Shuffle
			</button>
			<ContextMenu items={getHeaderMenuItems()} position="end" size="sm" />
		</div>
	</div>
</div>
