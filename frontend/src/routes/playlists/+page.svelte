<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { fetchPlaylists, createPlaylist, type PlaylistSummary } from '$lib/api/playlists';
	import { toastStore } from '$lib/stores/toast';
	import { ListMusic, Plus } from 'lucide-svelte';
	import PlaylistCard from '$lib/components/PlaylistCard.svelte';
	import PlaylistCardSkeleton from '$lib/components/PlaylistCardSkeleton.svelte';

	let playlists = $state<PlaylistSummary[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	let showNewInput = $state(false);
	let newName = $state('');
	let creating = $state(false);
	let newNameInputEl = $state<HTMLInputElement | null>(null);

	$effect(() => {
		if (showNewInput && newNameInputEl) {
			newNameInputEl.focus();
		}
	});

	async function load() {
		loading = true;
		error = null;
		try {
			playlists = await fetchPlaylists();
		} catch (e) {
			error = e instanceof Error ? e.message : "Couldn't load playlists";
		} finally {
			loading = false;
		}
	}

	async function handleCreate() {
		const trimmed = newName.trim();
		if (!trimmed || creating) return;
		creating = true;
		try {
			const created = await createPlaylist(trimmed);
			newName = '';
			showNewInput = false;
			await goto(`/playlists/${created.id}`);
		} catch (_e) {
			toastStore.show({ message: "Couldn't create the playlist", type: 'error' });
		} finally {
			creating = false;
		}
	}

	function handleCreateKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') void handleCreate();
		if (e.key === 'Escape') {
			showNewInput = false;
			newName = '';
		}
	}

	function handleCardDelete(playlistId: string) {
		playlists = playlists.filter((p) => p.id !== playlistId);
	}

	onMount(() => {
		void load();
	});
</script>

<svelte:head>
	<title>Playlists - Musicseerr</title>
</svelte:head>

<div class="space-y-4 px-4 sm:px-6 lg:px-8">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-bold sm:text-3xl">Playlists</h1>
		<button
			class="btn btn-accent btn-sm"
			onclick={() => {
				showNewInput = true;
			}}
		>
			<Plus class="h-4 w-4" />
			New Playlist
		</button>
	</div>

	{#if showNewInput}
		<div class="flex items-center gap-2">
			<input
				type="text"
				class="input input-sm flex-1"
				placeholder="Playlist name..."
				bind:this={newNameInputEl}
				bind:value={newName}
				onkeydown={handleCreateKeydown}
			/>
			<button
				class="btn btn-accent btn-sm"
				onclick={() => void handleCreate()}
				disabled={!newName.trim() || creating}
			>
				{#if creating}
					<span class="loading loading-spinner loading-xs"></span>
				{:else}
					Create
				{/if}
			</button>
			<button
				class="btn btn-ghost btn-sm"
				onclick={() => {
					showNewInput = false;
					newName = '';
				}}
			>
				Cancel
			</button>
		</div>
	{/if}

	{#if loading}
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
			{#each Array(8) as _, i (`skeleton-${i}`)}
				<PlaylistCardSkeleton />
			{/each}
		</div>
	{:else if error}
		<div role="alert" class="alert alert-error">
			<span>{error}</span>
			<button class="btn btn-sm btn-ghost" onclick={() => void load()}>Retry</button>
		</div>
	{:else if playlists.length === 0}
		<div class="flex flex-col items-center justify-center py-20 gap-4">
			<ListMusic class="h-16 w-16 text-base-content/20" />
			<h2 class="text-lg font-semibold text-base-content/60">No playlists yet</h2>
			<button
				class="btn btn-accent btn-sm"
				onclick={() => {
					showNewInput = true;
				}}
			>
				<Plus class="h-4 w-4" />
				Create your first playlist
			</button>
		</div>
	{:else}
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
			{#each playlists as playlist (playlist.id)}
				<PlaylistCard {playlist} ondelete={handleCardDelete} />
			{/each}
		</div>
	{/if}
</div>
