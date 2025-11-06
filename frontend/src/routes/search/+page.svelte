<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import AlbumCard from '$lib/components/AlbumCard.svelte';
	import ArtistCard from '$lib/components/ArtistCard.svelte';
	import ViewMoreAlbumCard from '$lib/components/ViewMoreAlbumCard.svelte';
	import ViewMoreArtistCard from '$lib/components/ViewMoreArtistCard.svelte';
	import type { Artist, Album } from '$lib/types';
	import { colors } from '$lib/colors';

	export let data: { query: string };
	
	let artists: Artist[] = [];
	let albums: Album[] = [];
	let loadingArtists = false;
	let loadingAlbums = false;
	let hasSearched = false;
	let showToast = false;
	let abortController: AbortController | null = null;

	$: isSearching = loadingArtists || loadingAlbums;
	$: hasResults = artists.length > 0 || albums.length > 0;

	function navigateToBucket(bucket: 'artists' | 'albums') {
		if (data.query) {
			goto(`/search/${bucket}?q=${encodeURIComponent(data.query)}`);
		}
	}

	function handleAlbumAdded() {
		showToast = true;
		setTimeout(() => {
			showToast = false;
		}, 3000);
	}

	async function performSearch(q: string) {
		if (abortController) {
			abortController.abort();
		}

		if (!q.trim()) {
			artists = [];
			albums = [];
			hasSearched = false;
			return;
		}

		abortController = new AbortController();
		hasSearched = true;
		loadingArtists = true;
		loadingAlbums = true;

		try {
			const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit_artists=6&limit_albums=24`, {
				signal: abortController.signal
			});
			
			if (res.ok) {
				const data = await res.json();
				artists = data.artists || [];
				albums = data.albums || [];
			} else {
				artists = [];
				albums = [];
			}
		} catch (error) {
			if (error instanceof Error && error.name === 'AbortError') {
				return;
			}
			console.error('Search failed:', error);
			artists = [];
			albums = [];
		} finally {
			loadingArtists = false;
			loadingAlbums = false;
		}
	}

	let lastQuery = '';
	
	$: if (browser && data.query && data.query !== lastQuery) {
		lastQuery = data.query;
		performSearch(data.query);
	} else if (browser && !data.query) {
		artists = [];
		albums = [];
		hasSearched = false;
		lastQuery = '';
	}

	onMount(() => {
		if (browser) {
			const handleRefresh = () => {
				if (data.query) {
					performSearch(data.query);
				}
			};
			window.addEventListener('search-refresh', handleRefresh);
			
			return () => {
				window.removeEventListener('search-refresh', handleRefresh);
			};
		}
	});

	onDestroy(() => {
		if (abortController) {
			abortController.abort();
			abortController = null;
		}
	});
</script>


{#if hasSearched || isSearching}
	<div class="px-8 pt-4 pb-2">
		<div class="flex gap-2">
			<button class="badge badge-lg cursor-pointer" style="background-color: {colors.primary}; color: {colors.secondary};">
				All
			</button>
			<button 
				class="badge badge-lg cursor-pointer transition-colors"
				style="background-color: {colors.secondary}; color: {colors.primary};"
				on:click={() => navigateToBucket('artists')}
			>
				Artists
			</button>
			<button 
				class="badge badge-lg cursor-pointer transition-colors"
				style="background-color: {colors.secondary}; color: {colors.primary};"
				on:click={() => navigateToBucket('albums')}
			>
				Albums
			</button>
		</div>
	</div>
{/if}

{#if isSearching && !hasResults}
	<section class="px-8 py-4 space-y-8">
		<div>
			<h2 class="text-xl font-bold mb-4">Artists</h2>
			<div class="bg-base-200 rounded-box p-4">
				<div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
					<div class="card bg-base-100 w-full shadow-sm">
						<div class="skeleton aspect-square w-full"></div>
					</div>
					{#each Array(6) as _, i}
						<div class="card bg-base-100 w-full shadow-sm">
							<div class="skeleton aspect-square w-full"></div>
							<div class="card-body p-3 space-y-2">
								<div class="skeleton h-4 w-full"></div>
								<div class="skeleton h-3 w-2/3"></div>
								<div class="skeleton h-8 w-full"></div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>

		<div>
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-xl font-bold">Albums</h2>
			</div>
			<div class="bg-base-200 rounded-box p-4">
				<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
					<div class="card bg-base-100 w-full shadow-sm">
						<div class="skeleton aspect-square w-full"></div>
					</div>
					{#each Array(24) as _, i}
						<div class="card bg-base-100 w-full shadow-sm">
							<div class="skeleton aspect-square w-full"></div>
							<div class="card-body p-3 space-y-2">
								<div class="skeleton h-4 w-full"></div>
								<div class="skeleton h-3 w-2/3"></div>
								<div class="skeleton h-8 w-full"></div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	</section>
{:else if hasSearched}
	<section class="px-8 py-4 space-y-8">
		<div>
			<h2 class="text-xl font-bold mb-4">Artists</h2>
			{#if loadingArtists}
				<div class="bg-base-200 rounded-box p-4">
					<div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
						{#each Array(7) as _, i}
							<div class="card bg-base-100 w-full shadow-sm">
								<div class="skeleton aspect-square w-full"></div>
								<div class="card-body p-2">
									<div class="skeleton h-4 w-full"></div>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{:else if artists.length > 0}
				<div class="bg-base-200 rounded-box p-4">
					<div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
						<ViewMoreArtistCard />
						{#each artists as artist, index}
							<ArtistCard {artist} {index} />
						{/each}
					</div>
				</div>
			{:else}
				<div class="p-8 bg-base-200 rounded-box text-center text-gray-500">
					No artists found
				</div>
			{/if}
		</div>

		<div>
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-xl font-bold">Albums</h2>
				{#if albums.length > 0}
					<a
						href={`/search/albums?q=${encodeURIComponent(data.query)}`}
						class="text-sm text-primary hover:underline"
					>
						View more →
					</a>
				{/if}
			</div>
			{#if loadingAlbums}
				<div class="bg-base-200 rounded-box p-4">
					<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
						{#each Array(8) as _, i}
							<div class="card bg-base-100 w-full shadow-sm">
								<div class="skeleton aspect-square w-full"></div>
								<div class="card-body p-3">
									<div class="skeleton h-4 w-full mb-2"></div>
									<div class="skeleton h-3 w-3/4"></div>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{:else if albums.length > 0}
				<div class="bg-base-200 rounded-box p-4">
					<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
						<ViewMoreAlbumCard />
						{#each albums as album, index}
							<AlbumCard {album} {index} onadded={handleAlbumAdded} />
						{/each}
					</div>
				</div>
			{:else}
				<div class="p-8 bg-base-200 rounded-box text-center text-gray-500">
					No albums found
				</div>
			{/if}
		</div>
	</section>
{:else}
	<p class="text-center mt-32 text-gray-400">Enter a search query to get started.</p>
{/if}


{#if showToast}
	<div class="toast toast-end toast-bottom">
		<div class="alert alert-success">
			<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
				<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
			</svg>
			<span>Added to Library</span>
		</div>
	</div>
{/if}
