<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import AlbumCard from '$lib/components/AlbumCard.svelte';
	import AlbumCardSkeleton from '$lib/components/AlbumCardSkeleton.svelte';
	import type { Album } from '$lib/types';
	import { colors } from '$lib/colors';
	import { searchStore } from '$lib/stores/search';
	import { fetchEnrichmentBatch, applyAlbumEnrichment } from '$lib/utils/enrichment';

	export let data: { query: string };

	let albums: Album[] = [];
	let loading = false;
	let hasMore = true;
	let offset = 0;
	const limit = 24;
	let sentinel: HTMLElement;
	let showToast = false;
	let abortController: AbortController | null = null;
	let enrichmentController: AbortController | null = null;
	let observer: IntersectionObserver | null = null;
	let initializedFromCache = false;

	function navigateBack() {
		if (data.query) {
			goto(`/search?q=${encodeURIComponent(data.query)}`);
		}
	}

	function navigateToBucket(bucket: 'artists') {
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

	async function fetchEnrichment(albumMbids: string[]) {
		if (albumMbids.length === 0) return;

		if (enrichmentController) {
			enrichmentController.abort();
		}
		enrichmentController = new AbortController();

		try {
			const enrichment = await fetchEnrichmentBatch([], albumMbids, enrichmentController.signal);
			if (!enrichment) return;

			albums = applyAlbumEnrichment(albums, enrichment);
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
				`/api/search/albums?q=${encodeURIComponent(data.query)}&limit=${limit}&offset=${offset}`,
				{ signal: abortController.signal }
			);

			if (res.ok) {
				const responseData = await res.json();
				const newAlbums: Album[] = responseData.results || [];
				if (newAlbums.length < limit) {
					hasMore = false;
				}

				const newMbids: string[] = [];
				if (offset === 0 && albums.length > 0) {
					const existingIds = new Set(albums.map((a) => a.musicbrainz_id));
					const uniqueNewAlbums = newAlbums.filter(
						(a: Album) => !existingIds.has(a.musicbrainz_id)
					);
					albums = [...albums, ...uniqueNewAlbums];
					offset = albums.length;
					uniqueNewAlbums.forEach((a) => newMbids.push(a.musicbrainz_id));
				} else {
					albums = [...albums, ...newAlbums];
					offset += newAlbums.length;
					newAlbums.forEach((a) => newMbids.push(a.musicbrainz_id));
				}
				searchStore.updateAlbums(albums);

				if (newMbids.length > 0) {
					fetchEnrichment(newMbids);
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
		if (cache && cache.albums.length > 0) {
			albums = cache.albums;
			offset = 0;
			hasMore = true;
			initializedFromCache = true;
			loadMore();
		} else {
			albums = [];
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
			class="badge badge-lg cursor-pointer transition-colors"
			style="background-color: {colors.secondary}; color: {colors.primary};"
			on:click={() => navigateToBucket('artists')}
		>
			Artists
		</button>
		<button
			class="badge badge-lg cursor-pointer"
			style="background-color: {colors.primary}; color: {colors.secondary};"
		>
			Albums
		</button>
	</div>
</div>

<section class="px-8 py-4">
	{#if !data.query}
		<p class="text-center mt-32 text-gray-400">Enter a search query to get started.</p>
	{:else if loading && albums.length === 0}
		<div class="bg-base-200 rounded-box p-4">
			<div
				class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
			>
				{#each Array(12) as _, i}
					<AlbumCardSkeleton />
				{/each}
			</div>
		</div>
	{:else if albums.length === 0 && !loading}
		<div class="p-8 bg-base-200 rounded-box text-center text-gray-500">No albums found</div>
	{:else}
		<div class="bg-base-200 rounded-box p-4">
			<div
				class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
			>
				{#each albums as album (album.musicbrainz_id)}
					<AlbumCard {album} onadded={handleAlbumAdded} />
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

{#if showToast}
	<div class="toast toast-end toast-bottom">
		<div class="alert alert-success">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				class="h-6 w-6"
				fill="none"
				viewBox="0 0 24 24"
				stroke="currentColor"
				stroke-width="2"
			>
				<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
			</svg>
			<span>Added to Library</span>
		</div>
	</div>
{/if}
