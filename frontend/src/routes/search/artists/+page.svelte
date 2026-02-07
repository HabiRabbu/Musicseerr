<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import SearchArtistCard from '$lib/components/SearchArtistCard.svelte';
	import ArtistCardSkeleton from '$lib/components/ArtistCardSkeleton.svelte';
	import type { Artist } from '$lib/types';
	import { colors } from '$lib/colors';
	import { searchStore } from '$lib/stores/search';
	import { fetchEnrichmentBatch, applyArtistEnrichment } from '$lib/utils/enrichment';

	export let data: { query: string };

	let artists: Artist[] = [];
	let loading = false;
	let hasMore = true;
	let offset = 0;
	const limit = 24;
	let sentinel: HTMLElement;
	let abortController: AbortController | null = null;
	let enrichmentController: AbortController | null = null;
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

	async function fetchEnrichment(artistMbids: string[]) {
		if (artistMbids.length === 0) return;

		if (enrichmentController) {
			enrichmentController.abort();
		}
		enrichmentController = new AbortController();

		try {
			const enrichment = await fetchEnrichmentBatch(artistMbids, [], enrichmentController.signal);
			if (!enrichment) return;

			artists = applyArtistEnrichment(artists, enrichment);
		} catch (error) {
			if (error instanceof Error && error.name === 'AbortError') {
				return;
			}
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
				const newArtists: Artist[] = responseData.results || [];
				if (newArtists.length < limit) {
					hasMore = false;
				}

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
				searchStore.updateArtists(artists);

				const needsEnrichment = artists
					.filter((a) => a.release_group_count == null)
					.map((a) => a.musicbrainz_id);
				if (needsEnrichment.length > 0) {
					fetchEnrichment(needsEnrichment);
				}
			} else {
				hasMore = false;
			}
		} catch (error) {
			if (error instanceof Error && error.name === 'AbortError') {
				return;
			}
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
		if (enrichmentController) {
			enrichmentController.abort();
			enrichmentController = null;
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
		if (enrichmentController) {
			enrichmentController.abort();
			enrichmentController = null;
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
		<button
			class="badge badge-lg cursor-pointer"
			style="background-color: {colors.primary}; color: {colors.secondary};"
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

<section class="px-8 py-4">
	{#if !data.query}
		<p class="text-center mt-32 text-gray-400">Enter a search query to get started.</p>
	{:else if loading && artists.length === 0}
		<div class="bg-base-200 rounded-box p-4">
			<div
				class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
			>
				{#each Array(12) as _, i}
					<ArtistCardSkeleton variant="detailed" />
				{/each}
			</div>
		</div>
	{:else if artists.length === 0 && !loading}
		<div class="p-8 bg-base-200 rounded-box text-center text-gray-500">No artists found</div>
	{:else}
		<div class="bg-base-200 rounded-box p-4">
			<div
				class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
			>
				{#each artists as artist (artist.musicbrainz_id)}
					<SearchArtistCard {artist} />
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
