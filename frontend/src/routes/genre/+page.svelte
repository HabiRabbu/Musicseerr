<script lang="ts">
	import { page } from '$app/stores';
	import { onMount, onDestroy } from 'svelte';
	import { goto, beforeNavigate } from '$app/navigation';
	import GenreArtistCard from '$lib/components/GenreArtistCard.svelte';
	import GenreAlbumCard from '$lib/components/GenreAlbumCard.svelte';
	import type { GenreDetailResponse } from '$lib/types';

	let genreName = $state('');
	let genreData: GenreDetailResponse | null = $state(null);
	let loading = $state(true);
	let error = $state('');
	let heroArtistMbid: string | null = $state(null);
	let heroImageLoaded = $state(false);
	let abortController: AbortController | null = null;
	let lastLoadedGenre = '';

	let artistOffset = $state(0);
	let albumOffset = $state(0);
	let loadingMoreArtists = $state(false);
	let loadingMoreAlbums = $state(false);
	const PAGE_SIZE = 50;

	let activeTab: 'artists' | 'albums' = $state('artists');

	$effect(() => {
		genreName = $page.url.searchParams.get('name') || '';
	});

	async function loadHeroArtist() {
		if (!genreName) return;
		heroArtistMbid = null;
		heroImageLoaded = false;
		try {
			const response = await fetch(`/api/home/genre-artist/${encodeURIComponent(genreName)}`, { signal: abortController?.signal });
			if (response.ok) {
				const data = await response.json();
				heroArtistMbid = data.artist_mbid;
			}
		} catch {}
	}

	async function loadGenreData() {
		if (!genreName) { error = 'No genre specified'; loading = false; return; }
		loading = true;
		error = '';
		artistOffset = 0;
		albumOffset = 0;

		try {
			const response = await fetch(`/api/home/genre/${encodeURIComponent(genreName)}?limit=${PAGE_SIZE}`, { signal: abortController?.signal });
			if (response.ok) {
				genreData = await response.json();
			} else {
				error = 'Failed to load genre data';
			}
		} catch {
			error = 'Failed to load genre data';
		} finally {
			loading = false;
		}
	}

	async function loadMoreArtists() {
		if (!genreData || loadingMoreArtists || !genreData.popular?.has_more_artists) return;
		loadingMoreArtists = true;
		artistOffset += PAGE_SIZE;

		try {
			const response = await fetch(`/api/home/genre/${encodeURIComponent(genreName)}?limit=${PAGE_SIZE}&artist_offset=${artistOffset}`);
			if (response.ok) {
				const data: GenreDetailResponse = await response.json();
				if (genreData.popular && data.popular) {
					genreData.popular.artists = [...genreData.popular.artists, ...data.popular.artists];
					genreData.popular.has_more_artists = data.popular.has_more_artists;
				}
			}
		} catch {}
		loadingMoreArtists = false;
	}

	async function loadMoreAlbums() {
		if (!genreData || loadingMoreAlbums || !genreData.popular?.has_more_albums) return;
		loadingMoreAlbums = true;
		albumOffset += PAGE_SIZE;

		try {
			const response = await fetch(`/api/home/genre/${encodeURIComponent(genreName)}?limit=${PAGE_SIZE}&album_offset=${albumOffset}`);
			if (response.ok) {
				const data: GenreDetailResponse = await response.json();
				if (genreData.popular && data.popular) {
					genreData.popular.albums = [...genreData.popular.albums, ...data.popular.albums];
					genreData.popular.has_more_albums = data.popular.has_more_albums;
				}
			}
		} catch {}
		loadingMoreAlbums = false;
	}

	function loadData() {
		if (abortController) abortController.abort();
		abortController = new AbortController();
		lastLoadedGenre = genreName;
		loadGenreData();
		loadHeroArtist();
	}

	function cleanup() {
		if (abortController) { abortController.abort(); abortController = null; }
	}

	onMount(() => { if (genreName) loadData(); });
	onDestroy(cleanup);
	beforeNavigate(cleanup);

	$effect(() => {
		if (genreName && genreName !== lastLoadedGenre) loadData();
	});

	const hasLibraryContent = $derived(
		(genreData?.library?.artists?.length ?? 0) > 0 || (genreData?.library?.albums?.length ?? 0) > 0
	);
</script>

<svelte:head>
	<title>{genreName ? `${genreName}` : 'Genre'} - Musicseerr</title>
</svelte:head>

<div class="min-h-screen bg-base-100 relative overflow-hidden">
	{#if heroArtistMbid}
		<div class="absolute inset-x-0 top-0 h-80 overflow-hidden pointer-events-none" style="z-index: 0;">
			<img src="/api/covers/artist/{heroArtistMbid}?size=500" alt="" class="w-full object-contain object-top transition-opacity duration-500 {heroImageLoaded ? 'opacity-20' : 'opacity-0'}" onload={() => heroImageLoaded = true} />
			<div class="absolute inset-0 bg-gradient-to-b from-transparent via-base-100/70 to-base-100"></div>
		</div>
	{/if}

	<div class="container mx-auto p-4 max-w-7xl relative" style="z-index: 1;">
		<div class="mb-8">
			<a href="/" class="btn btn-ghost btn-sm gap-2 mb-4 -ml-2">
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
					<path fill-rule="evenodd" d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z" clip-rule="evenodd" />
				</svg>
				Back
			</a>
			<div class="flex items-center gap-4">
				<div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/30 to-secondary/30 flex items-center justify-center text-4xl">🎵</div>
				<div>
					<h1 class="text-4xl font-bold capitalize">{genreName || 'Genre'}</h1>
					{#if genreData}
						<p class="text-base-content/60 mt-1">
							{#if hasLibraryContent}
								{genreData.library?.artist_count ?? 0} artists · {genreData.library?.album_count ?? 0} albums in library
							{:else}
								Explore popular {genreName} music
							{/if}
						</p>
					{/if}
				</div>
			</div>
		</div>

		{#if loading}
			<section class="mb-12">
				<div class="flex items-center gap-3 mb-6">
					<div class="skeleton w-10 h-10 rounded-xl"></div>
					<div><div class="skeleton h-6 w-48 mb-2"></div><div class="skeleton h-4 w-32"></div></div>
				</div>
				<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
					{#each Array(12) as _}
						<div class="card bg-base-200/50"><div class="skeleton aspect-square rounded-t-2xl"></div><div class="p-3"><div class="skeleton h-4 w-3/4"></div></div></div>
					{/each}
				</div>
			</section>
		{:else if error}
			<div class="flex flex-col items-center justify-center py-24">
				<div class="text-6xl mb-4">😕</div>
				<p class="text-base-content/70 text-lg">{error}</p>
				<button class="btn btn-primary mt-6" onclick={loadGenreData}>Try Again</button>
			</div>
		{:else if genreData}
			{#if hasLibraryContent}
				<section class="mb-12">
					<div class="flex items-center gap-3 mb-6">
						<div class="w-10 h-10 rounded-xl bg-success/20 flex items-center justify-center text-success">
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5"><path d="M10.75 16.82A7.462 7.462 0 0115 15.5c.71 0 1.396.098 2.046.282A.75.75 0 0018 15.06v-11a.75.75 0 00-.546-.721A9.006 9.006 0 0015 3a8.963 8.963 0 00-4.25 1.065V16.82zM9.25 4.065A8.963 8.963 0 005 3c-.85 0-1.673.118-2.454.339A.75.75 0 002 4.06v11a.75.75 0 00.954.721A7.506 7.506 0 015 15.5c1.579 0 3.042.487 4.25 1.32V4.065z" /></svg>
						</div>
						<div>
							<h2 class="text-2xl font-bold">From Your Library</h2>
							<p class="text-sm text-base-content/60">{genreData.library?.artist_count ?? 0} artists · {genreData.library?.album_count ?? 0} albums</p>
						</div>
					</div>

					{#if (genreData.library?.artists?.length ?? 0) > 0}
						<h3 class="text-lg font-semibold mb-4 text-base-content/80">Artists</h3>
						<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 mb-8">
							{#each genreData.library?.artists ?? [] as artist (artist.mbid || artist.name)}
								<GenreArtistCard {artist} showLibraryBadge={true} onclick={() => artist.mbid && goto(`/artist/${artist.mbid}`)} />
							{/each}
						</div>
					{/if}

					{#if (genreData.library?.albums?.length ?? 0) > 0}
						<h3 class="text-lg font-semibold mb-4 text-base-content/80">Albums</h3>
						<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
							{#each genreData.library?.albums ?? [] as album (album.mbid || album.name)}
								<GenreAlbumCard {album} showLibraryBadge={true} onclick={() => album.mbid && goto(`/album/${album.mbid}`)} />
							{/each}
						</div>
					{/if}
				</section>
				<div class="divider my-8"></div>
			{/if}

			<section>
				<div class="flex items-center gap-3 mb-6">
					<div class="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center text-primary">
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5"><path fill-rule="evenodd" d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401Z" clip-rule="evenodd" /></svg>
					</div>
					<div>
						<h2 class="text-2xl font-bold">Popular in {genreName}</h2>
						<p class="text-sm text-base-content/60">Discover the best {genreName} music</p>
					</div>
				</div>

				<div class="tabs tabs-box mb-6">
					<button class="tab {activeTab === 'artists' ? 'tab-active' : ''}" onclick={() => activeTab = 'artists'}>
						Artists {#if genreData.popular?.artists?.length}<span class="badge badge-sm ml-2">{genreData.popular.artists.length}</span>{/if}
					</button>
					<button class="tab {activeTab === 'albums' ? 'tab-active' : ''}" onclick={() => activeTab = 'albums'}>
						Albums {#if genreData.popular?.albums?.length}<span class="badge badge-sm ml-2">{genreData.popular.albums.length}</span>{/if}
					</button>
				</div>

				{#if activeTab === 'artists'}
					{#if (genreData.popular?.artists?.length ?? 0) === 0}
						<div class="flex flex-col items-center justify-center py-16">
							<div class="text-5xl mb-4 opacity-30">🎤</div>
							<p class="text-base-content/50">No artists found for this genre</p>
						</div>
					{:else}
						<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
							{#each genreData.popular?.artists ?? [] as artist (artist.mbid || artist.name)}
								<GenreArtistCard {artist} onclick={() => artist.mbid && goto(`/artist/${artist.mbid}`)} />
							{/each}
						</div>
						{#if genreData.popular?.has_more_artists}
							<div class="flex justify-center mt-8">
								<button class="btn btn-outline btn-wide gap-2" onclick={loadMoreArtists} disabled={loadingMoreArtists}>
									{#if loadingMoreArtists}<span class="loading loading-spinner loading-sm"></span>{/if}
									Load More Artists
								</button>
							</div>
						{/if}
					{/if}
				{/if}

				{#if activeTab === 'albums'}
					{#if (genreData.popular?.albums?.length ?? 0) === 0}
						<div class="flex flex-col items-center justify-center py-16">
							<div class="text-5xl mb-4 opacity-30">💿</div>
							<p class="text-base-content/50">No albums found for this genre</p>
						</div>
					{:else}
						<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
							{#each genreData.popular?.albums ?? [] as album (album.mbid || album.name)}
								<GenreAlbumCard {album} onclick={() => album.mbid && goto(`/album/${album.mbid}`)} />
							{/each}
						</div>
						{#if genreData.popular?.has_more_albums}
							<div class="flex justify-center mt-8">
								<button class="btn btn-outline btn-wide gap-2" onclick={loadMoreAlbums} disabled={loadingMoreAlbums}>
									{#if loadingMoreAlbums}<span class="loading loading-spinner loading-sm"></span>{/if}
									Load More Albums
								</button>
							</div>
						{/if}
					{/if}
				{/if}
			</section>
		{/if}
	</div>
</div>
