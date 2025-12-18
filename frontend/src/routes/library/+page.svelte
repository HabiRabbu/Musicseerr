<script lang="ts">
	import { onMount } from 'svelte';
	import { fade } from 'svelte/transition';
	import ArtistCard from '$lib/components/ArtistCard.svelte';
	import AlbumCard from '$lib/components/AlbumCard.svelte';
	import ArtistCardSkeleton from '$lib/components/ArtistCardSkeleton.svelte';
	import AlbumCardSkeleton from '$lib/components/AlbumCardSkeleton.svelte';
	import CacheSyncIndicator from '$lib/components/CacheSyncIndicator.svelte';
	import { recentlyAddedStore } from '$lib/stores/library';
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
	let stats: LibraryStats = {
		artist_count: 0,
		album_count: 0,
		last_sync: null,
		db_size_mb: 0
	};

	let loadingArtists = true;
	let loadingAlbums = true;
	let loadingStats = true;

	let albumsPerPage = 50;
	let currentAlbumPage = 1;
	let syncing = false;

	let recentlyAddedContainer: HTMLDivElement;
	let showLeftArrow = false;
	let showRightArrow = true;

	let artistsContainer: HTMLDivElement;
	let artistsShowLeftArrow = false;
	let artistsShowRightArrow = true;
	let artistsVisibleCount = 15;
	const ARTISTS_LOAD_MORE = 15;

	function updateArrowVisibility() {
		if (!recentlyAddedContainer) return;
		const { scrollLeft, scrollWidth, clientWidth } = recentlyAddedContainer;
		showLeftArrow = scrollLeft > 10;
		showRightArrow = scrollLeft < scrollWidth - clientWidth - 10;
	}

	function scrollCarouselLeft() {
		if (!recentlyAddedContainer) return;
		const scrollAmount = recentlyAddedContainer.clientWidth * 0.8;
		recentlyAddedContainer.scrollBy({ left: -scrollAmount, behavior: 'smooth' });
	}

	function scrollCarouselRight() {
		if (!recentlyAddedContainer) return;
		const scrollAmount = recentlyAddedContainer.clientWidth * 0.8;
		recentlyAddedContainer.scrollBy({ left: scrollAmount, behavior: 'smooth' });
	}

	function updateArtistsArrowVisibility() {
		if (!artistsContainer) return;
		const { scrollLeft, scrollWidth, clientWidth } = artistsContainer;
		artistsShowLeftArrow = scrollLeft > 10;
		artistsShowRightArrow = scrollLeft < scrollWidth - clientWidth - 10;

		const scrollPercentage = (scrollLeft + clientWidth) / scrollWidth;
		if (scrollPercentage > 0.8 && artistsVisibleCount < allArtists.length) {
			artistsVisibleCount = Math.min(artistsVisibleCount + ARTISTS_LOAD_MORE, allArtists.length);
		}
	}

	function scrollArtistsLeft() {
		if (!artistsContainer) return;
		const scrollAmount = artistsContainer.clientWidth * 0.8;
		artistsContainer.scrollBy({ left: -scrollAmount, behavior: 'smooth' });
	}

	function scrollArtistsRight() {
		if (!artistsContainer) return;
		const scrollAmount = artistsContainer.clientWidth * 0.8;
		artistsContainer.scrollBy({ left: scrollAmount, behavior: 'smooth' });
	}

	function loadMoreArtists() {
		artistsVisibleCount = Math.min(artistsVisibleCount + ARTISTS_LOAD_MORE, allArtists.length);
	}

	$: recentlyAdded = $recentlyAddedStore.data ?? { artists: [], albums: [] };
	$: loadingRecentlyAdded = $recentlyAddedStore.loading && !$recentlyAddedStore.data;

	onMount(async () => {
		recentlyAddedStore.initialize();

		// Load other data
		loadArtists();
		loadAlbums();
		loadStats();

		setTimeout(() => {
			updateArrowVisibility();
			updateArtistsArrowVisibility();
		}, 100);
	});

	$: if (allArtists.length > 0 && artistsContainer) {
		setTimeout(() => updateArtistsArrowVisibility(), 100);
	}

	async function loadArtists() {
		try {
			const res = await fetch('/api/library/artists');
			if (res.ok) {
				const data = await res.json();
				allArtists = data.artists;
			}
		} catch (error) {
			console.error('Failed to load artists:', error);
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
			}
		} catch (error) {
			console.error('Failed to load albums:', error);
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
		} catch (error) {
			console.error('Failed to load stats:', error);
		} finally {
			loadingStats = false;
		}
	}

	async function loadLibrary() {
		loadingArtists = true;
		loadingAlbums = true;
		loadingStats = true;

		try {
			await Promise.all([
				recentlyAddedStore.refresh(),
				loadArtists(),
				loadAlbums(),
				loadStats()
			]);
		} finally {
			loadingStats = false;
		}
	}

	async function syncLibrary() {
		syncing = true;
		try {
			const res = await fetch('/api/library/sync', { method: 'POST' });
			if (res.ok) {
				await loadLibrary();
			}
		} catch (error) {
			console.error('Failed to sync library:', error);
		} finally {
			syncing = false;
		}
	}

	function convertToArtist(libArtist: LibraryArtist): Artist {
		return {
			title: libArtist.name,
			musicbrainz_id: libArtist.mbid,
			in_library: true
		};
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
	<!-- Header with sync button -->
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
		<button
			class="btn btn-primary"
			class:btn-disabled={syncing}
			on:click={syncLibrary}
			disabled={syncing}
		>
			{#if syncing}
				<span class="loading loading-spinner loading-sm"></span>
			{/if}
			{syncing ? 'Syncing...' : 'Sync Library'}
		</button>
	</div>

	<!-- Recently Added Carousel -->
	<section class="mb-8">
		<h2 class="text-2xl font-semibold mb-4">Recently Added</h2>

		{#if loadingRecentlyAdded}
			<div class="relative group">
				<div class="flex gap-4 p-4 bg-base-200 rounded-box overflow-x-auto scrollbar-hide">
					{#each Array(6) as _, i}
						<div class="w-48 flex-shrink-0">
							<AlbumCardSkeleton />
						</div>
					{/each}
				</div>
			</div>
		{:else if recentlyAdded.artists.length > 0 || recentlyAdded.albums.length > 0}
			<div class="relative group" in:fade={{ duration: 300 }}>
				<!-- Left Arrow -->
				{#if showLeftArrow}
					<button
						class="absolute left-2 top-1/2 -translate-y-1/2 z-10 btn btn-circle btn-sm bg-base-100/90 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity hidden sm:flex"
						on:click={scrollCarouselLeft}
						aria-label="Scroll left"
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
							<path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd" />
						</svg>
					</button>
				{/if}

				<!-- Carousel -->
				<div
					bind:this={recentlyAddedContainer}
					on:scroll={updateArrowVisibility}
					class="flex gap-4 p-4 bg-base-200 rounded-box overflow-x-auto scrollbar-hide"
				>
					{#each recentlyAdded.artists as artist}
						<div class="w-48 flex-shrink-0">
							<ArtistCard artist={convertToArtist(artist)} />
						</div>
					{/each}
					{#each recentlyAdded.albums as album}
						<div class="w-48 flex-shrink-0">
							<AlbumCard album={convertToAlbum(album)} />
						</div>
					{/each}
				</div>

				<!-- Right Arrow -->
				{#if showRightArrow}
					<button
						class="absolute right-2 top-1/2 -translate-y-1/2 z-10 btn btn-circle btn-sm bg-base-100/90 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity hidden sm:flex"
						on:click={scrollCarouselRight}
						aria-label="Scroll right"
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
							<path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" />
						</svg>
					</button>
				{/if}
			</div>
		{:else}
			<div class="p-8 bg-base-200 rounded-box text-center text-base-content/50">
				<p>No recently added items</p>
			</div>
		{/if}
	</section>

	<!-- Artists Section -->
	<section class="mb-8">
		<div class="flex justify-between items-center mb-4">
			<a href="/library/artists" class="flex items-center gap-2 hover:text-primary transition-colors group">
				<h2 class="text-2xl font-semibold">Artists</h2>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					stroke-width="2"
					stroke="currentColor"
					class="w-5 h-5 transition-transform group-hover:translate-x-1"
				>
					<path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
				</svg>
			</a>
		</div>

		{#if loadingArtists}
			<div class="relative group">
				<div class="flex gap-4 overflow-x-auto scrollbar-hide pb-2">
					{#each Array(8) as _}
						<div class="w-32 sm:w-36 md:w-44 flex-shrink-0">
							<ArtistCardSkeleton />
						</div>
					{/each}
				</div>
			</div>
		{:else if allArtists.length > 0}
			<div class="relative group" in:fade={{ duration: 300 }}>
				<!-- Left Arrow -->
				{#if artistsShowLeftArrow}
					<button
						class="absolute left-0 top-1/2 -translate-y-1/2 z-10 btn btn-circle btn-sm bg-base-100/90 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity hidden sm:flex"
						on:click={scrollArtistsLeft}
						aria-label="Scroll left"
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
							<path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd" />
						</svg>
					</button>
				{/if}

				<!-- Carousel -->
				<div
					bind:this={artistsContainer}
					on:scroll={updateArtistsArrowVisibility}
					class="flex gap-3 sm:gap-4 overflow-x-auto scrollbar-hide pb-2"
				>
					{#each displayedArtists as artist (artist.mbid)}
						<div class="w-32 sm:w-36 md:w-44 flex-shrink-0">
							<ArtistCard artist={convertToArtist(artist)} />
						</div>
					{/each}
					{#if artistsVisibleCount < allArtists.length}
						<div class="w-32 sm:w-36 md:w-44 flex-shrink-0 flex items-center justify-center">
							<button
								class="btn btn-ghost btn-sm"
								on:click={loadMoreArtists}
							>
								Load more...
							</button>
						</div>
					{/if}
				</div>

				<!-- Right Arrow -->
				{#if artistsShowRightArrow}
					<button
						class="absolute right-0 top-1/2 -translate-y-1/2 z-10 btn btn-circle btn-sm bg-base-100/90 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity hidden sm:flex"
						on:click={scrollArtistsRight}
						aria-label="Scroll right"
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
							<path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" />
						</svg>
					</button>
				{/if}
			</div>
		{:else}
			<div class="p-8 bg-base-200 rounded-box text-center text-base-content/50">
				<p>No artists in library</p>
			</div>
		{/if}
	</section>

	<!-- Albums Section -->
	<section>
		<div class="flex justify-between items-center mb-4">
			<a href="/library/albums" class="flex items-center gap-2 hover:text-primary transition-colors group">
				<h2 class="text-2xl font-semibold">Albums</h2>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					stroke-width="2"
					stroke="currentColor"
					class="w-5 h-5 transition-transform group-hover:translate-x-1"
				>
					<path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
				</svg>
			</a>
			{#if !loadingAlbums && totalAlbumPages > 1}
				<div class="flex items-center gap-2">
					<button 
						class="btn btn-sm btn-circle"
						on:click={() => currentAlbumPage = Math.max(1, currentAlbumPage - 1)}
						disabled={currentAlbumPage === 1}
						aria-label="Previous page"
					>
						«
					</button>
					
					<span class="text-sm">
						{currentAlbumPage} / {totalAlbumPages}
					</span>
					
					<button 
						class="btn btn-sm btn-circle"
						on:click={() => currentAlbumPage = Math.min(totalAlbumPages, currentAlbumPage + 1)}
						disabled={currentAlbumPage === totalAlbumPages}
						aria-label="Next page"
					>
						»
					</button>
				</div>
			{/if}
		</div>

		{#if loadingAlbums}
			<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
				{#each Array(12) as _}
					<AlbumCardSkeleton />
				{/each}
			</div>
		{:else if allAlbums.length > 0}
			<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4" in:fade={{ duration: 300 }}>
				{#each displayedAlbums as album, index (album.foreignAlbumId || `${album.album}-${album.artist}-${index}`)}
					<AlbumCard album={convertToAlbum(album)} />
				{/each}
			</div>
			
			<!-- Bottom Pagination Controls -->
			{#if totalAlbumPages > 1}
				<div class="flex justify-center items-center gap-2 mt-6">
					<button 
						class="btn btn-sm btn-circle"
						on:click={() => currentAlbumPage = Math.max(1, currentAlbumPage - 1)}
						disabled={currentAlbumPage === 1}
						aria-label="Previous page"
					>
						«
					</button>
					
					<span class="text-sm">
						{currentAlbumPage} / {totalAlbumPages}
					</span>
					
					<button 
						class="btn btn-sm btn-circle"
						on:click={() => currentAlbumPage = Math.min(totalAlbumPages, currentAlbumPage + 1)}
						disabled={currentAlbumPage === totalAlbumPages}
						aria-label="Next page"
					>
						»
					</button>
				</div>
			{/if}
		{:else}
			<div class="p-8 bg-base-200 rounded-box text-center text-base-content/50">
				<p>No albums in library</p>
			</div>
		{/if}
	</section>

	<!-- Empty State - only show when all data is loaded and library is empty -->
	{#if !loadingArtists && !loadingAlbums && allArtists.length === 0 && allAlbums.length === 0}
		<div class="flex flex-col items-center justify-center min-h-[200px] text-center mt-8">
			<div class="text-6xl mb-4">📚</div>
			<h2 class="text-2xl font-semibold mb-2">No items in library</h2>
			<p class="text-base-content/70 mb-4">
				Your Lidarr library is empty or hasn't been synced yet.
			</p>
			<button class="btn btn-primary" on:click={syncLibrary} disabled={syncing}>
				{syncing ? 'Syncing...' : 'Sync Now'}
			</button>
		</div>
	{/if}
</div>

<style>
	.scrollbar-hide {
		-ms-overflow-style: none;
		scrollbar-width: none;
	}
	.scrollbar-hide::-webkit-scrollbar {
		display: none;
	}
</style>
