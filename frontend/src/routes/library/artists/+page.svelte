<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import ArtistCard from '$lib/components/ArtistCard.svelte';
	import ArtistCardSkeleton from '$lib/components/ArtistCardSkeleton.svelte';
	import { api } from '$lib/api/client';
	import { API } from '$lib/constants';
	import { isAbortError } from '$lib/utils/errorHandling';
	import type { Artist } from '$lib/types';
	import { ChevronLeft, Mic, Search, X } from 'lucide-svelte';

	type LibraryArtist = {
		name: string;
		mbid: string;
		album_count: number;
		date_added: string | null;
	};

	type PaginatedResponse = {
		artists: LibraryArtist[];
		total: number;
		offset: number;
		limit: number;
	};

	const PAGE_SIZE = 48;
	const SEARCH_DEBOUNCE_MS = 300;

	let artists = $state<LibraryArtist[]>([]);
	let total = $state(0);
	let loading = $state(true);
	let loadingMore = $state(false);
	let error = $state<string | null>(null);

	let sortBy = $state('name');
	let sortOrder = $state('asc');
	let searchQuery = $state('');
	let searchTimeout: ReturnType<typeof setTimeout> | null = null;
	let fetchId = 0;
	let abortController: AbortController | null = null;

	onMount(() => {
		fetchArtists(true);
	});

	async function fetchArtists(reset = false) {
		const id = ++fetchId;
		abortController?.abort();
		abortController = new AbortController();

		if (reset) {
			loading = true;
			artists = [];
		} else {
			loadingMore = true;
		}
		error = null;

		try {
			const offset = reset ? 0 : artists.length;
			const q = searchQuery.trim() || undefined;
			const url = API.library.artists(PAGE_SIZE, offset, sortBy, sortOrder, q);
			const data = await api.get<PaginatedResponse>(url, { signal: abortController.signal });
			if (id !== fetchId) return;
			artists = reset ? data.artists : [...artists, ...data.artists];
			total = data.total;
		} catch (e) {
			if (isAbortError(e)) return;
			if (id !== fetchId) return;
			error = "Couldn't load artists";
		} finally {
			if (id === fetchId) {
				loading = false;
				loadingMore = false;
			}
		}
	}

	function handleSearchInput(): void {
		if (searchTimeout) clearTimeout(searchTimeout);
		searchTimeout = setTimeout(() => {
			fetchArtists(true);
		}, SEARCH_DEBOUNCE_MS);
	}

	function clearSearch(): void {
		searchQuery = '';
		if (searchTimeout) clearTimeout(searchTimeout);
		fetchArtists(true);
	}

	function handleSortChange(event: Event): void {
		const value = (event.target as HTMLSelectElement).value;
		const [newSortBy, newSortOrder] = value.split(':');
		sortBy = newSortBy;
		sortOrder = newSortOrder;
		fetchArtists(true);
	}

	function loadMore(): void {
		if (!loadingMore && artists.length < total) {
			fetchArtists(false);
		}
	}

	function convertToArtist(libArtist: LibraryArtist): Artist {
		return {
			title: libArtist.name,
			musicbrainz_id: libArtist.mbid,
			in_library: true
		};
	}

	const hasMore = $derived(artists.length < total);
</script>

<div class="container mx-auto p-4 md:p-6 lg:p-8">
	<div class="flex items-center gap-4 mb-6">
		<button
			class="btn btn-ghost btn-circle"
			onclick={() => goto('/library')}
			aria-label="Back to library"
		>
			<ChevronLeft class="w-6 h-6" />
		</button>
		<div>
			<h1 class="text-3xl font-bold">All Artists</h1>
			<p class="text-base-content/70 text-sm mt-1">
				{total}
				{total === 1 ? 'artist' : 'artists'}
			</p>
		</div>
	</div>

	<div class="flex flex-col sm:flex-row gap-3 mb-6">
		<div class="relative group flex-1">
			<Search
				class="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-base-content/40
				group-focus-within:text-primary transition-colors duration-200 pointer-events-none"
			/>
			<input
				type="text"
				placeholder="Search artists..."
				class="input input-bordered w-full rounded-full pl-11 pr-12"
				bind:value={searchQuery}
				oninput={handleSearchInput}
				aria-label="Search artists"
			/>
			{#if searchQuery}
				<button
					class="absolute right-3 top-1/2 -translate-y-1/2 btn btn-sm btn-ghost btn-circle"
					onclick={clearSearch}
					aria-label="Clear search"
				>
					<X class="h-4 w-4" />
				</button>
			{/if}
		</div>
		<select
			class="select select-bordered rounded-full"
			value="{sortBy}:{sortOrder}"
			onchange={handleSortChange}
			aria-label="Sort artists"
		>
			<option value="name:asc">Name A-Z</option>
			<option value="name:desc">Name Z-A</option>
			<option value="album_count:desc">Most Albums</option>
			<option value="album_count:asc">Fewest Albums</option>
			<option value="date_added:desc">Newest First</option>
			<option value="date_added:asc">Oldest First</option>
		</select>
	</div>

	{#if error}
		<div class="alert alert-error mb-6">
			<span>{error}</span>
			<button class="btn btn-sm btn-ghost" onclick={() => fetchArtists(true)}>Retry</button>
		</div>
	{:else if loading}
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
			{#each Array(12) as _, i (`skeleton-${i}`)}
				<ArtistCardSkeleton />
			{/each}
		</div>
	{:else if artists.length === 0}
		<div class="flex flex-col items-center justify-center min-h-100 text-center">
			<Mic class="h-12 w-12 text-base-content/40 mb-4" strokeWidth={1.5} />
			<h2 class="text-2xl font-semibold mb-2">No artists found</h2>
			<p class="text-base-content/70 mb-4">
				{searchQuery
					? 'Try a different search term.'
					: "Your library doesn't contain any artists yet."}
			</p>
		</div>
	{:else}
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
			{#each artists as artist (artist.mbid)}
				<ArtistCard artist={convertToArtist(artist)} />
			{/each}
		</div>
		{#if hasMore}
			<div class="flex justify-center mt-6">
				<button class="btn btn-primary btn-outline" onclick={loadMore} disabled={loadingMore}>
					{#if loadingMore}
						<span class="loading loading-spinner loading-sm"></span>
					{/if}
					Load More ({artists.length} / {total})
				</button>
			</div>
		{/if}
	{/if}
</div>
