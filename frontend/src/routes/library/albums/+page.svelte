<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import AlbumCard from '$lib/components/AlbumCard.svelte';
	import type { Album } from '$lib/types';

	type LibraryAlbum = {
		album: string;
		artist: string;
		artist_mbid: string | null;
		foreignAlbumId: string | null;
		year: number | null;
		monitored: boolean;
		cover_url: string | null;
		date_added: number | null;
	};

	let allAlbums: LibraryAlbum[] = [];
	let loading = true;
	let error: string | null = null;

	onMount(async () => {
		await loadAlbums();
	});

	async function loadAlbums() {
		loading = true;
		error = null;
		try {
			const res = await fetch('/api/library/albums');
			if (res.ok) {
				const data = await res.json();
				allAlbums = data.albums;
			} else {
				console.error('Failed to load albums:', res.status);
				error = 'Failed to load albums';
			}
		} catch (e) {
			console.error('Failed to load albums:', e);
			error = 'Failed to load albums';
		} finally {
			loading = false;
		}
	}

	function convertToAlbum(libAlbum: LibraryAlbum): Album {
		return {
			title: libAlbum.album,
			artist: libAlbum.artist,
			year: libAlbum.year,
			musicbrainz_id: libAlbum.foreignAlbumId || '',
			in_library: true,
			cover_url: libAlbum.cover_url
		};
	}

	$: albumsByArtist = allAlbums.reduce((acc, album) => {
		const artistName = album.artist || 'Unknown Artist';
		if (!acc[artistName]) acc[artistName] = [];
		acc[artistName].push(album);
		return acc;
	}, {} as Record<string, LibraryAlbum[]>);

	$: sortedArtistNames = Object.keys(albumsByArtist).sort((a, b) => a.localeCompare(b));
</script>

<div class="container mx-auto p-4 md:p-6 lg:p-8">
	<div class="flex items-center gap-4 mb-6">
		<button
			class="btn btn-ghost btn-circle"
			onclick={() => goto('/library')}
			aria-label="Back to library"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
				stroke-width="2"
				stroke="currentColor"
				class="w-6 h-6"
			>
				<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
			</svg>
		</button>
		<div>
			<h1 class="text-3xl font-bold">All Albums</h1>
			<p class="text-base-content/70 text-sm mt-1">
				{allAlbums.length} {allAlbums.length === 1 ? 'album' : 'albums'}
			</p>
		</div>
	</div>

	{#if error}
		<div class="alert alert-error mb-6">
			<span>{error}</span>
			<button class="btn btn-sm btn-ghost" onclick={loadAlbums}>Retry</button>
		</div>
	{:else if loading}
		<div class="flex justify-center items-center min-h-[400px]">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else if allAlbums.length === 0}
		<div class="flex flex-col items-center justify-center min-h-[400px] text-center">
			<div class="text-6xl mb-4">💿</div>
			<h2 class="text-2xl font-semibold mb-2">No albums found</h2>
			<p class="text-base-content/70 mb-4">
				Your library doesn't contain any albums yet.
			</p>
		</div>
	{:else}
		<div class="space-y-8">
			{#each sortedArtistNames as artistName}
				<div>
					<div class="divider divider-start text-xl font-bold text-secondary">{artistName}</div>
					<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
						{#each albumsByArtist[artistName] as album}
							<AlbumCard album={convertToAlbum(album)} />
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
