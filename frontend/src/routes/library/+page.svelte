<script lang="ts">
	import { onMount } from 'svelte';
	import { fade } from 'svelte/transition';
	import ArtistCard from '$lib/components/ArtistCard.svelte';
	import AlbumCard from '$lib/components/AlbumCard.svelte';
	import ArtistCardSkeleton from '$lib/components/ArtistCardSkeleton.svelte';
	import AlbumCardSkeleton from '$lib/components/AlbumCardSkeleton.svelte';
	import CacheSyncIndicator from '$lib/components/CacheSyncIndicator.svelte';
	import HorizontalCarousel from '$lib/components/HorizontalCarousel.svelte';
	import Pagination from '$lib/components/Pagination.svelte';
	import { recentlyAddedStore } from '$lib/stores/recentlyAdded';
	import type { Artist, Album } from '$lib/types';

	type LibraryArtist = {
		name: string;
		mbid: string;
		album_count: number;
		date_added: string | null;
	};

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

	type LibraryStats = {
		artist_count: number;
		album_count: number;
		last_sync: number | null;
		db_size_mb: number;
	};

	let allArtists: LibraryArtist[] = [];
	let allAlbums: LibraryAlbum[] = [];
	let stats: LibraryStats = { artist_count: 0, album_count: 0, last_sync: null, db_size_mb: 0 };

	let loadingArtists = true;
	let loadingAlbums = true;
	let loadingStats = true;
	let syncing = false;
	let error: string | null = null;

	let albumsPerPage = 50;
	let currentAlbumPage = 1;
	let artistsVisibleCount = 15;
	const ARTISTS_LOAD_MORE = 15;

	$: recentlyAdded = $recentlyAddedStore.data ?? { artists: [], albums: [] };
	$: loadingRecentlyAdded = $recentlyAddedStore.loading && !$recentlyAddedStore.data;

	onMount(() => {
		recentlyAddedStore.initialize();
		loadArtists();
		loadAlbums();
		loadStats();
	});

	async function loadArtists() {
		try {
			const res = await fetch('/api/library/artists');
			if (res.ok) {
				const data = await res.json();
				allArtists = data.artists;
			} else {
				console.error('Failed to load artists:', res.status);
				error = 'Failed to load artists';
			}
		} catch (e) {
			console.error('Failed to load artists:', e);
			error = 'Failed to load artists';
		} finally {
			loadingArtists = false;
		}
	}

	async function loadAlbums() {
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
			loadingAlbums = false;
		}
	}

	async function loadStats() {
		try {
			const res = await fetch('/api/library/stats');
			if (res.ok) {
				stats = await res.json();
			}
		} catch (e) {
			console.error('Failed to load stats:', e);
		} finally {
			loadingStats = false;
		}
	}

	async function loadLibrary() {
		error = null;
		loadingArtists = true;
		loadingAlbums = true;
		loadingStats = true;
		try {
			await Promise.all([recentlyAddedStore.refresh(), loadArtists(), loadAlbums(), loadStats()]);
		} finally {
			loadingStats = false;
		}
	}

	async function syncLibrary() {
		syncing = true;
		error = null;
		try {
			const res = await fetch('/api/library/sync', { method: 'POST' });
			if (res.ok) {
				window.dispatchEvent(new CustomEvent('library-sync-triggered'));
				await loadLibrary();
			} else {
				const data = await res.json().catch(() => ({}));
				console.error('Sync failed:', res.status, data);
				error = data.detail || 'Failed to sync library';
			}
		} catch (e) {
			console.error('Sync failed:', e);
			error = 'Failed to sync library - network error';
		} finally {
			syncing = false;
		}
	}

	function loadMoreArtists() {
		artistsVisibleCount = Math.min(artistsVisibleCount + ARTISTS_LOAD_MORE, allArtists.length);
	}

	function convertToArtist(libArtist: LibraryArtist): Artist {
		return { title: libArtist.name, musicbrainz_id: libArtist.mbid, in_library: true };
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

	$: displayedArtists = allArtists.slice(0, artistsVisibleCount);
	$: totalAlbumPages = Math.ceil(allAlbums.length / albumsPerPage);
	$: displayedAlbums = allAlbums.slice(
		(currentAlbumPage - 1) * albumsPerPage,
		currentAlbumPage * albumsPerPage
	);
	$: lastSyncText = stats.last_sync
		? new Date(stats.last_sync * 1000).toLocaleString()
		: 'Never';
</script>

<CacheSyncIndicator />

<div class="container mx-auto p-4 md:p-6 lg:p-8">
	{#if error}
		<div class="alert alert-error mb-6">
			<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 shrink-0 stroke-current" fill="none" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
			</svg>
			<span>{error}</span>
			<div class="flex gap-2">
				<button class="btn btn-sm" onclick={() => { error = null; loadLibrary(); }}>Retry</button>
				<button class="btn btn-sm btn-circle btn-ghost" onclick={() => error = null} aria-label="Dismiss">
					<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>
		</div>
	{/if}

	<div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
		<div>
			<h1 class="text-3xl font-bold">Library</h1>
			<p class="text-base-content/70 text-sm mt-1">
				{#if loadingStats}
					<span class="skeleton h-4 w-64 inline-block"></span>
				{:else}
					{stats.artist_count} artists • {stats.album_count} albums • Last sync: {lastSyncText}
				{/if}
			</p>
		</div>
		<button class="btn btn-primary" class:btn-disabled={syncing} onclick={syncLibrary} disabled={syncing}>
			{#if syncing}<span class="loading loading-spinner loading-sm"></span>{/if}
			{syncing ? 'Syncing...' : 'Sync Library'}
		</button>
	</div>

	<section class="mb-8">
		<h2 class="text-2xl font-semibold mb-4">Recently Added</h2>
		{#if loadingRecentlyAdded}
			<div class="flex gap-4 p-4 bg-base-200 rounded-box overflow-x-auto scrollbar-hide">
				{#each Array(6) as _}<div class="w-48 flex-shrink-0"><AlbumCardSkeleton /></div>{/each}
			</div>
		{:else if recentlyAdded.artists.length > 0 || recentlyAdded.albums.length > 0}
			<div in:fade={{ duration: 300 }}>
				<HorizontalCarousel class="p-4 bg-base-200 rounded-box">
					{#each recentlyAdded.artists as artist}
						<div class="w-48 flex-shrink-0"><ArtistCard artist={convertToArtist(artist)} /></div>
					{/each}
					{#each recentlyAdded.albums as album}
						<div class="w-48 flex-shrink-0"><AlbumCard album={convertToAlbum(album)} /></div>
					{/each}
				</HorizontalCarousel>
			</div>
		{:else}
			<div class="p-8 bg-base-200 rounded-box text-center text-base-content/50">
				<p>No recently added items</p>
			</div>
		{/if}
	</section>

	<section class="mb-8">
		<div class="flex justify-between items-center mb-4">
			<a href="/library/artists" class="flex items-center gap-2 hover:text-primary transition-colors group">
				<h2 class="text-2xl font-semibold">Artists</h2>
				<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5 transition-transform group-hover:translate-x-1">
					<path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
				</svg>
			</a>
		</div>
		{#if loadingArtists}
			<div class="flex gap-4 overflow-x-auto scrollbar-hide pb-2">
				{#each Array(8) as _}<div class="w-32 sm:w-36 md:w-44 flex-shrink-0"><ArtistCardSkeleton /></div>{/each}
			</div>
		{:else if allArtists.length > 0}
			<div in:fade={{ duration: 300 }}>
				<HorizontalCarousel class="pb-2" onNearEnd={loadMoreArtists}>
					{#each displayedArtists as artist (artist.mbid)}
						<div class="w-32 sm:w-36 md:w-44 flex-shrink-0"><ArtistCard artist={convertToArtist(artist)} /></div>
					{/each}
					{#if artistsVisibleCount < allArtists.length}
						<div class="w-32 sm:w-36 md:w-44 flex-shrink-0 flex items-center justify-center">
							<button class="btn btn-ghost btn-sm" onclick={loadMoreArtists}>Load more...</button>
						</div>
					{/if}
				</HorizontalCarousel>
			</div>
		{:else}
			<div class="p-8 bg-base-200 rounded-box text-center text-base-content/50">
				<p>No artists in library</p>
			</div>
		{/if}
	</section>

	<section>
		<div class="flex justify-between items-center mb-4">
			<a href="/library/albums" class="flex items-center gap-2 hover:text-primary transition-colors group">
				<h2 class="text-2xl font-semibold">Albums</h2>
				<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5 transition-transform group-hover:translate-x-1">
					<path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
				</svg>
			</a>
			{#if !loadingAlbums && totalAlbumPages > 1}
				<Pagination current={currentAlbumPage} total={totalAlbumPages} onchange={(p) => currentAlbumPage = p} />
			{/if}
		</div>
		{#if loadingAlbums}
			<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
				{#each Array(12) as _}<AlbumCardSkeleton />{/each}
			</div>
		{:else if allAlbums.length > 0}
			<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4" in:fade={{ duration: 300 }}>
				{#each displayedAlbums as album, index (album.foreignAlbumId || `${album.album}-${album.artist}-${index}`)}
					<AlbumCard album={convertToAlbum(album)} />
				{/each}
			</div>
			{#if totalAlbumPages > 1}
				<div class="flex justify-center mt-6">
					<Pagination current={currentAlbumPage} total={totalAlbumPages} onchange={(p) => currentAlbumPage = p} />
				</div>
			{/if}
		{:else}
			<div class="p-8 bg-base-200 rounded-box text-center text-base-content/50">
				<p>No albums in library</p>
			</div>
		{/if}
	</section>

	{#if !loadingArtists && !loadingAlbums && allArtists.length === 0 && allAlbums.length === 0}
		<div class="flex flex-col items-center justify-center min-h-[200px] text-center mt-8">
			<div class="text-6xl mb-4">📚</div>
			<h2 class="text-2xl font-semibold mb-2">No items in library</h2>
			<p class="text-base-content/70 mb-4">Your Lidarr library is empty or hasn't been synced yet.</p>
			<button class="btn btn-primary" onclick={syncLibrary} disabled={syncing}>
				{syncing ? 'Syncing...' : 'Sync Now'}
			</button>
		</div>
	{/if}
</div>

