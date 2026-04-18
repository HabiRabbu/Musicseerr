<script lang="ts">
	import { API } from '$lib/constants';
	import { api } from '$lib/api/client';
	import { launchEmbyPlayback } from '$lib/player/launchEmbyPlayback';
	import type { EmbyArtistPaginatedResponse, EmbyArtistSummary, EmbyArtistDetail, EmbyAlbumDetail } from '$lib/types';
	import { onMount } from 'svelte';

	const PAGE_SIZE = 50;

	let artists = $state<EmbyArtistSummary[]>([]);
	let total = $state(0);
	let offset = $state(0);
	let loading = $state(true);
	let loadingMore = $state(false);
	let error = $state('');
	let search = $state('');
	let searchDebounce: ReturnType<typeof setTimeout> | null = null;

	let selectedArtist = $state<EmbyArtistDetail | null>(null);
	let artistModalOpen = $state(false);
	let artistLoading = $state(false);

	let selectedAlbum = $state<EmbyAlbumDetail | null>(null);
	let albumModalOpen = $state(false);
	let albumLoading = $state(false);

	async function loadArtists(reset = false) {
		if (reset) {
			offset = 0;
			artists = [];
		}
		if (reset) loading = true;
		else loadingMore = true;
		error = '';
		try {
			const url = API.embyLibrary.artists(PAGE_SIZE, offset, search);
			const data = await api.get<EmbyArtistPaginatedResponse>(url);
			artists = reset ? data.items : [...artists, ...data.items];
			total = data.total;
			offset = artists.length;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load artists';
		} finally {
			loading = false;
			loadingMore = false;
		}
	}

	function handleSearch(value: string) {
		search = value;
		if (searchDebounce) clearTimeout(searchDebounce);
		searchDebounce = setTimeout(() => loadArtists(true), 300);
	}

	async function openArtist(artist: EmbyArtistSummary) {
		artistModalOpen = true;
		artistLoading = true;
		selectedArtist = null;
		try {
			selectedArtist = await api.get<EmbyArtistDetail>(API.embyLibrary.artistDetail(artist.emby_id));
		} catch {
			artistModalOpen = false;
		} finally {
			artistLoading = false;
		}
	}

	async function openAlbum(embyId: string, _artistName: string) {
		albumModalOpen = true;
		albumLoading = true;
		selectedAlbum = null;
		try {
			selectedAlbum = await api.get<EmbyAlbumDetail>(API.embyLibrary.albumDetail(embyId));
		} catch {
			albumModalOpen = false;
		} finally {
			albumLoading = false;
		}
	}

	function playAlbum(album: EmbyAlbumDetail, startIndex = 0) {
		launchEmbyPlayback(album.tracks, startIndex, false, {
			albumId: album.emby_id,
			albumName: album.name,
			artistName: album.artist_name,
			coverUrl: album.image_url ?? null,
			artistId: undefined
		});
		albumModalOpen = false;
	}

	onMount(() => {
		loadArtists(true);
	});
</script>

<div class="container mx-auto p-4 max-w-7xl">
	<div class="flex items-center gap-3 mb-6">
		<a href="/library/emby" class="btn btn-ghost btn-sm">← Emby</a>
		<h1 class="text-2xl font-bold">Artists</h1>
		{#if total > 0}
			<span class="text-base-content/50 text-sm">({total.toLocaleString()})</span>
		{/if}
	</div>

	<div class="mb-4">
		<input
			type="search"
			placeholder="Search artists..."
			class="input input-bordered w-full max-w-sm"
			oninput={(e) => handleSearch((e.target as HTMLInputElement).value)}
		/>
	</div>

	{#if loading}
		<div class="flex justify-center py-20">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else if error}
		<div class="alert alert-error">{error}</div>
	{:else if artists.length === 0}
		<p class="text-center text-base-content/50 py-20">No artists found</p>
	{:else}
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
			{#each artists as artist (artist.emby_id)}
				<button class="group text-left" onclick={() => openArtist(artist)}>
					<div class="aspect-square rounded-full overflow-hidden bg-base-300 mb-2">
						{#if artist.image_url}
							<img
								src={artist.image_url}
								alt={artist.name}
								class="w-full h-full object-cover group-hover:scale-105 transition-transform"
								onerror={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
							/>
						{:else}
							<div class="w-full h-full flex items-center justify-center text-base-content/30 text-4xl font-bold">
								{artist.name[0]?.toUpperCase() ?? '?'}
							</div>
						{/if}
					</div>
					<p class="font-medium text-sm truncate text-center">{artist.name}</p>
					{#if artist.album_count > 0}
						<p class="text-xs text-base-content/40 text-center">{artist.album_count} albums</p>
					{/if}
				</button>
			{/each}
		</div>

		{#if artists.length < total}
			<div class="flex justify-center mt-8">
				<button
					class="btn btn-outline"
					disabled={loadingMore}
					onclick={() => loadArtists(false)}
				>
					{#if loadingMore}
						<span class="loading loading-spinner loading-sm"></span>
					{/if}
					Load more ({total - artists.length} remaining)
				</button>
			</div>
		{/if}
	{/if}
</div>

{#if artistModalOpen && !albumModalOpen}
	<dialog class="modal modal-open" onclose={() => (artistModalOpen = false)}>
		<div class="modal-box w-11/12 max-w-2xl">
			{#if artistLoading}
				<div class="flex justify-center py-12">
					<span class="loading loading-spinner loading-lg"></span>
				</div>
			{:else if selectedArtist}
				<div class="flex gap-4 mb-6">
					{#if selectedArtist.image_url}
						<img
							src={selectedArtist.image_url}
							alt={selectedArtist.name}
							class="w-20 h-20 rounded-full object-cover flex-shrink-0"
						/>
					{/if}
					<div>
						<h3 class="text-xl font-bold">{selectedArtist.name}</h3>
						<p class="text-sm text-base-content/50">{selectedArtist.albums.length} albums</p>
					</div>
				</div>

				<div class="grid grid-cols-2 sm:grid-cols-3 gap-4 max-h-96 overflow-y-auto">
					{#each selectedArtist.albums as album (album.emby_id)}
						<button
							class="group text-left"
							onclick={() => openAlbum(album.emby_id, selectedArtist!.name)}
						>
							<div class="aspect-square rounded-lg overflow-hidden bg-base-300 mb-1">
								<img
									src={album.image_url ?? API.embyLibrary.image(album.emby_id)}
									alt={album.name}
									class="w-full h-full object-cover group-hover:scale-105 transition-transform"
									onerror={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
								/>
							</div>
							<p class="text-sm font-medium truncate">{album.name}</p>
							{#if album.year}<p class="text-xs text-base-content/40">{album.year}</p>{/if}
						</button>
					{/each}
				</div>
			{/if}
			<div class="modal-action">
				<button class="btn" onclick={() => (artistModalOpen = false)}>Close</button>
			</div>
		</div>
		<form method="dialog" class="modal-backdrop">
			<button onclick={() => (artistModalOpen = false)}>close</button>
		</form>
	</dialog>
{/if}

{#if albumModalOpen}
	<dialog class="modal modal-open" onclose={() => (albumModalOpen = false)}>
		<div class="modal-box w-11/12 max-w-2xl">
			{#if albumLoading}
				<div class="flex justify-center py-12">
					<span class="loading loading-spinner loading-lg"></span>
				</div>
			{:else if selectedAlbum}
				<div class="flex gap-4 mb-4">
					<img
						src={selectedAlbum.image_url ?? API.embyLibrary.image(selectedAlbum.emby_id)}
						alt={selectedAlbum.name}
						class="w-24 h-24 rounded-lg object-cover flex-shrink-0"
						onerror={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
					/>
					<div>
						<h3 class="text-xl font-bold">{selectedAlbum.name}</h3>
						<p class="text-base-content/60">{selectedAlbum.artist_name}</p>
						{#if selectedAlbum.year}<p class="text-sm text-base-content/40">{selectedAlbum.year}</p>{/if}
						<p class="text-sm text-base-content/50 mt-1">{selectedAlbum.track_count} tracks</p>
					</div>
				</div>

				{#if selectedAlbum.tracks.length > 0}
					<button class="btn btn-primary btn-sm mb-4" onclick={() => playAlbum(selectedAlbum!)}>
						Play Album
					</button>
					<div class="divide-y divide-base-300 max-h-80 overflow-y-auto">
						{#each selectedAlbum.tracks as track, i (track.emby_id)}
							<button
								class="w-full flex items-center gap-3 py-2 px-1 hover:bg-base-200 rounded text-left"
								onclick={() => playAlbum(selectedAlbum!, i)}
							>
								<span class="text-xs text-base-content/40 w-6 text-right">{track.track_number}</span>
								<span class="flex-1 truncate text-sm">{track.title}</span>
								<span class="text-xs text-base-content/40">
									{Math.floor(track.duration_seconds / 60)}:{String(Math.floor(track.duration_seconds % 60)).padStart(2, '0')}
								</span>
							</button>
						{/each}
					</div>
				{/if}
			{/if}
			<div class="modal-action">
				<button class="btn" onclick={() => (albumModalOpen = false)}>Close</button>
			</div>
		</div>
		<form method="dialog" class="modal-backdrop">
			<button onclick={() => (albumModalOpen = false)}>close</button>
		</form>
	</dialog>
{/if}
