<script lang="ts">
	import { onMount } from 'svelte';
	import ArtistCard from '$lib/components/ArtistCard.svelte';
	import AlbumCard from '$lib/components/AlbumCard.svelte';
	import CacheSyncIndicator from '$lib/components/CacheSyncIndicator.svelte';
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

	let recentlyAdded: { artists: LibraryArtist[]; albums: LibraryAlbum[] } = {
		artists: [],
		albums: []
	};
	let allArtists: LibraryArtist[] = [];
	let allAlbums: LibraryAlbum[] = [];
	let stats: LibraryStats = {
		artist_count: 0,
		album_count: 0,
		last_sync: null,
		db_size_mb: 0
	};
	let loading = true;
	let artistsCollapsed = true;
	let albumsPerPage = 50;
	let currentAlbumPage = 1;
	let syncing = false;

	onMount(async () => {
		await loadLibrary();
	});

	async function loadLibrary() {
		loading = true;
		try {
			const [recentlyAddedRes, artistsRes, albumsRes, statsRes] = await Promise.all([
				fetch('/api/library/recently-added'),
				fetch('/api/library/artists'),
				fetch('/api/library/albums'),
				fetch('/api/library/stats')
			]);

			if (recentlyAddedRes.ok) {
				recentlyAdded = await recentlyAddedRes.json();
			}
			if (artistsRes.ok) {
				const data = await artistsRes.json();
				allArtists = data.artists;
			}
			if (albumsRes.ok) {
				const data = await albumsRes.json();
				allAlbums = data.albums;
			}
			if (statsRes.ok) {
				stats = await statsRes.json();
			}
		} catch (error) {
			console.error('Failed to load library:', error);
		} finally {
			loading = false;
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

	$: displayedArtists = artistsCollapsed ? allArtists.slice(0, 6) : allArtists;
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
				{stats.artist_count} artists • {stats.album_count} albums • Last sync: {lastSyncText}
			</p>
		</div>
		<button
			class="btn btn-primary"
			class:btn-disabled={syncing || loading}
			on:click={syncLibrary}
			disabled={syncing || loading}
		>
			{#if syncing}
				<span class="loading loading-spinner loading-sm"></span>
			{/if}
			{syncing ? 'Syncing...' : 'Sync Library'}
		</button>
	</div>

	{#if loading}
		<div class="flex justify-center items-center min-h-[400px]">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else}
		<!-- Recently Added Carousel -->
		{#if recentlyAdded.artists.length > 0 || recentlyAdded.albums.length > 0}
			<section class="mb-8">
				<h2 class="text-2xl font-semibold mb-4">Recently Added</h2>

				<div class="carousel carousel-center gap-4 p-4 bg-base-200 rounded-box max-w-full overflow-x-auto">
					{#each recentlyAdded.artists as artist}
						<div class="carousel-item w-48 flex-shrink-0">
							<ArtistCard artist={convertToArtist(artist)} />
						</div>
					{/each}
					{#each recentlyAdded.albums as album}
						<div class="carousel-item w-48 flex-shrink-0">
							<AlbumCard album={convertToAlbum(album)} />
						</div>
					{/each}
				</div>
			</section>
		{/if}

		<!-- Artists Section -->
		{#if allArtists.length > 0}
			<section class="mb-8">
				<div class="flex justify-between items-center mb-4">
					<h2 class="text-2xl font-semibold">Artists</h2>
				</div>

				<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
					{#each displayedArtists as artist}
						<ArtistCard artist={convertToArtist(artist)} />
					{/each}
				</div>
				
				{#if allArtists.length > 6}
					<div class="flex justify-center mt-6">
						<button 
							class="btn btn-circle btn-ghost btn-lg"
							on:click={() => (artistsCollapsed = !artistsCollapsed)}
							aria-label={artistsCollapsed ? 'Show all artists' : 'Show less artists'}
						>
							<svg 
								xmlns="http://www.w3.org/2000/svg" 
								fill="none" 
								viewBox="0 0 24 24" 
								stroke-width="2" 
								stroke="currentColor" 
								class="w-8 h-8 transition-transform duration-300"
								class:rotate-180={!artistsCollapsed}
							>
								<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
							</svg>
						</button>
					</div>
				{/if}
			</section>
		{/if}

		<!-- Albums Section -->
		{#if allAlbums.length > 0}
			<section>
				<div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
					<h2 class="text-2xl font-semibold">
						Albums <span class="text-base-content/60 text-lg font-normal">
							(Page {currentAlbumPage} of {totalAlbumPages})
						</span>
					</h2>
					
					<!-- Top Pagination Controls -->
					{#if totalAlbumPages > 1}
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

				<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
					{#each displayedAlbums as album, index (album.foreignAlbumId || `${album.album}-${album.artist}-${index}`)}
						<AlbumCard album={convertToAlbum(album)} index={(currentAlbumPage - 1) * albumsPerPage + index} />
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
			</section>
		{/if}

		<!-- Empty State -->
		{#if allArtists.length === 0 && allAlbums.length === 0}
			<div class="flex flex-col items-center justify-center min-h-[400px] text-center">
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
	{/if}
</div>
