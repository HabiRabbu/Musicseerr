<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import ArtistCard from '$lib/components/ArtistCard.svelte';
	import type { Artist } from '$lib/types';
	import { colors } from '$lib/colors';
	import { searchStore } from '$lib/stores/search';

	export let data: { query: string };

	let artists: Artist[] = [];
	let loading = false;
	let hasMore = true;
	let offset = 0;
	const limit = 24;
	let sentinel: HTMLElement;
	let abortController: AbortController | null = null;
	let observer: IntersectionObserver | null = null;
	let initializedFromCache = false;

	function navigateBack() {
		if (data.query) {
			goto(`/search?q=${encodeURIComponent(data.query)}`);
		}
	}

	function navigateToBucket(bucket: 'albums') {
		if (data.query) {
			goto(`/search/${bucket}?q=${encodeURIComponent(data.query)}`);
		}
	}

	async function loadMore() {
		if (loading || !hasMore || !data.query) return;

		loading = true;

		if (abortController) {
			abortController.abort();
		}
		abortController = new AbortController();

		try {
			const res = await fetch(
				`/api/search/artists?q=${encodeURIComponent(data.query)}&limit=${limit}&offset=${offset}`,
				{ signal: abortController.signal }
			);

			if (res.ok) {
				const responseData = await res.json();
				const newArtists = responseData.results || [];
				if (newArtists.length < limit) {
					hasMore = false;
				}
				// If we had cached results displayed, merge new results avoiding duplicates
				if (offset === 0 && artists.length > 0) {
					const existingIds = new Set(artists.map((a) => a.musicbrainz_id));
					const uniqueNewArtists = newArtists.filter(
						(a: Artist) => !existingIds.has(a.musicbrainz_id)
					);
					artists = [...artists, ...uniqueNewArtists];
					offset = artists.length;
				} else {
					artists = [...artists, ...newArtists];
					offset += newArtists.length;
				}
				// Update cache with full results
				searchStore.updateArtists(artists);
			} else {
				hasMore = false;
			}
		} catch (error) {
			if (error instanceof Error && error.name === 'AbortError') {
				return;
			}
			console.error('Failed to load artists:', error);
			hasMore = false;
		} finally {
			loading = false;
		}
	}

	function resetAndLoad() {
		if (abortController) {
			abortController.abort();
			abortController = null;
		}

		if (observer) {
			observer.disconnect();
			observer = null;
		}

		const cache = searchStore.getCache(data.query);
		if (cache && cache.artists.length > 0) {
			artists = cache.artists;
			offset = 0;
			hasMore = true;
			initializedFromCache = true;
			loadMore();
		} else {
			artists = [];
			offset = 0;
			hasMore = true;
			initializedFromCache = false;
			loadMore();
		}
	}

	$: if (browser && data.query) {
		resetAndLoad();
	}

	$: if (browser && sentinel && !observer) {
		observer = new IntersectionObserver(
			(entries) => {
				if (entries[0].isIntersecting && hasMore && !loading) {
					loadMore();
				}
			},
			{ threshold: 0.1 }
		);

		observer.observe(sentinel);
	}

	onMount(() => {
		if (browser) {
			const handleRefresh = () => resetAndLoad();
			window.addEventListener('search-refresh', handleRefresh);
			
			return () => {
				window.removeEventListener('search-refresh', handleRefresh);
			};
		}
	});

	onDestroy(() => {
		if (observer) {
			observer.disconnect();
			observer = null;
		}
		if (abortController) {
			abortController.abort();
			abortController = null;
		}
	});
</script>


<div class="px-8 pt-4 pb-2">
	<div class="flex gap-2">
		<button 
			class="badge badge-lg cursor-pointer transition-colors"
			style="background-color: {colors.secondary}; color: {colors.primary};"
			on:click={navigateBack}
		>
			All
		</button>
		<button class="badge badge-lg cursor-pointer" style="background-color: {colors.primary}; color: {colors.secondary};">
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

<section class="px-8 py-4">
	{#if !data.query}
		<p class="text-center mt-32 text-gray-400">Enter a search query to get started.</p>
	{:else if loading && artists.length === 0}
		<div class="bg-base-200 rounded-box p-4">
			<div class="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
				{#each Array(20) as _, i}
					<div class="card bg-base-100 w-full shadow-sm">
						<div class="skeleton aspect-square w-full"></div>
						<div class="card-body p-2">
							<div class="skeleton h-4 w-full"></div>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{:else if artists.length === 0 && !loading}
		<div class="p-8 bg-base-200 rounded-box text-center text-gray-500">
			No artists found
		</div>
	{:else}
		<div class="bg-base-200 rounded-box p-4">
			<div class="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
				{#each artists as artist}
					<ArtistCard {artist} />
				{/each}
			</div>
		</div>

		<div bind:this={sentinel} class="h-20 flex items-center justify-center">
			{#if loading}
				<span class="loading loading-spinner loading-md text-primary"></span>
			{:else if !hasMore}
				<p class="text-gray-400 text-sm">No more results</p>
			{/if}
		</div>
	{/if}
</section>
