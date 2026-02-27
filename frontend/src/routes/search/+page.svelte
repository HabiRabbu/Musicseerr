<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import AlbumCard from '$lib/components/AlbumCard.svelte';
	import SearchArtistCard from '$lib/components/SearchArtistCard.svelte';
	import ViewMoreAlbumCard from '$lib/components/ViewMoreAlbumCard.svelte';
	import ViewMoreArtistCard from '$lib/components/ViewMoreArtistCard.svelte';
	import ArtistCardSkeleton from '$lib/components/ArtistCardSkeleton.svelte';
	import AlbumCardSkeleton from '$lib/components/AlbumCardSkeleton.svelte';
	import type { Artist, Album, EnrichmentSource } from '$lib/types';
	import { colors } from '$lib/colors';
	import { searchStore } from '$lib/stores/search';
	import {
		fetchEnrichmentBatch,
		applyArtistEnrichment,
		applyAlbumEnrichment
	} from '$lib/utils/enrichment';
	import { Check, ArrowRight } from 'lucide-svelte';

	export let data: { query: string };

	let artists: Artist[] = [];
	let albums: Album[] = [];
	let loadingArtists = false;
	let loadingAlbums = false;
	let hasSearched = false;
	let showToast = false;
	let abortController: AbortController | null = null;
	let enrichmentController: AbortController | null = null;
	let enrichmentSource: EnrichmentSource = 'none';

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

	async function fetchEnrichment() {
		if (artists.length === 0 && albums.length === 0) return;

		if (enrichmentController) {
			enrichmentController.abort();
		}
		enrichmentController = new AbortController();

		const artistRequests = artists.map((a) => ({
			musicbrainz_id: a.musicbrainz_id,
			name: a.title
		}));
		const albumRequests = albums.map((a) => ({
			musicbrainz_id: a.musicbrainz_id,
			artist_name: a.artist || '',
			album_name: a.title
		}));

		try {
			const enrichment = await fetchEnrichmentBatch(
				artistRequests,
				albumRequests,
				enrichmentController.signal
			);
			if (!enrichment) return;

			enrichmentSource = enrichment.source;
			artists = applyArtistEnrichment(artists, enrichment);
			albums = applyAlbumEnrichment(albums, enrichment);
		} catch (error) {
			if (error instanceof Error && error.name === 'AbortError') {
				return;
			}
		}
	}

	async function performSearch(q: string) {
		if (abortController) {
			abortController.abort();
		}
		if (enrichmentController) {
			enrichmentController.abort();
		}

		if (!q.trim()) {
			artists = [];
			albums = [];
			hasSearched = false;
			searchStore.clear();
			return;
		}

		abortController = new AbortController();
		hasSearched = true;
		artists = [];
		albums = [];
		loadingArtists = true;
		loadingAlbums = true;

		const fetchArtists = fetch(
			`/api/search?q=${encodeURIComponent(q)}&limit_artists=6&limit_albums=0&buckets=artists`,
			{
				signal: abortController.signal
			}
		)
			.then(async (res) => {
				if (res.ok) {
					const responseData = await res.json();
					artists = responseData.artists || [];
				} else {
					artists = [];
				}
				loadingArtists = false;
			})
			.catch((error) => {
				if (error instanceof Error && error.name === 'AbortError') {
					return;
				}
				artists = [];
				loadingArtists = false;
			});

		const fetchAlbums = fetch(
			`/api/search?q=${encodeURIComponent(q)}&limit_artists=0&limit_albums=24&buckets=albums`,
			{
				signal: abortController.signal
			}
		)
			.then(async (res) => {
				if (res.ok) {
					const responseData = await res.json();
					albums = responseData.albums || [];
				} else {
					albums = [];
				}
				loadingAlbums = false;
			})
			.catch((error) => {
				if (error instanceof Error && error.name === 'AbortError') {
					return;
				}
				albums = [];
				loadingAlbums = false;
			});

		await Promise.allSettled([fetchArtists, fetchAlbums]);

		searchStore.setResults(q, artists, albums);

		fetchEnrichment();
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
		searchStore.clear();
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
		if (enrichmentController) {
			enrichmentController.abort();
			enrichmentController = null;
		}
	});
</script>

{#if hasSearched || isSearching}
	<div class="px-8 pt-4 pb-2">
		<div class="flex gap-2">
			<button
				class="badge badge-lg cursor-pointer"
				style="background-color: {colors.primary}; color: {colors.secondary};"
			>
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
				<div
					class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
				>
					{#each Array(6) as _, i}
						<ArtistCardSkeleton variant="detailed" />
					{/each}
				</div>
			</div>
		</div>

		<div>
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-xl font-bold">Albums</h2>
			</div>
			<div class="bg-base-200 rounded-box p-4">
				<div
					class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
				>
					{#each Array(6) as _, i}
						<AlbumCardSkeleton />
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
					<div
						class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
					>
						{#each Array(6) as _, i}
							<ArtistCardSkeleton variant="detailed" />
						{/each}
					</div>
				</div>
			{:else if artists.length > 0}
				<div class="bg-base-200 rounded-box p-4 overflow-hidden">
					<div
						class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
					>
						<ViewMoreArtistCard />
						{#each artists.slice(0, 5) as artist (artist.musicbrainz_id)}
							<SearchArtistCard {artist} {enrichmentSource} />
						{/each}
					</div>
				</div>
			{:else}
				<div class="p-8 bg-base-200 rounded-box text-center text-gray-500">No artists found</div>
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
						View more <ArrowRight class="h-4 w-4 inline align-middle" />
					</a>
				{/if}
			</div>
			{#if loadingAlbums}
				<div class="bg-base-200 rounded-box p-4">
					<div
						class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
					>
						{#each Array(6) as _, i}
							<AlbumCardSkeleton />
						{/each}
					</div>
				</div>
			{:else if albums.length > 0}
				<div class="bg-base-200 rounded-box p-4">
					<div
						class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
					>
						<ViewMoreAlbumCard />
						{#each albums as album (album.musicbrainz_id)}
							<AlbumCard {album} {enrichmentSource} onadded={handleAlbumAdded} />
						{/each}
					</div>
				</div>
			{:else}
				<div class="p-8 bg-base-200 rounded-box text-center text-gray-500">No albums found</div>
			{/if}
		</div>
	</section>
{:else}
	<p class="text-center mt-32 text-gray-400">Enter a search query to get started.</p>
{/if}

{#if showToast}
	<div class="toast toast-end toast-bottom">
		<div class="alert alert-success">
			<Check class="h-6 w-6" />
			<span>Added to Library</span>
		</div>
	</div>
{/if}
