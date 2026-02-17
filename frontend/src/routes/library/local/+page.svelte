<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { API } from '$lib/constants';
	import AlbumImage from '$lib/components/AlbumImage.svelte';
	import SourceAlbumModal from '$lib/components/SourceAlbumModal.svelte';
	import type { LocalAlbumSummary, LocalPaginatedResponse, LocalStorageStats } from '$lib/types';

	let albums = $state<LocalAlbumSummary[]>([]);
	let recentAlbums = $state<LocalAlbumSummary[]>([]);
	let stats = $state<LocalStorageStats | null>(null);
	let total = $state(0);
	let loading = $state(true);
	let loadingMore = $state(false);
	let fetchError = $state('');

	let sortBy = $state<'name' | 'date_added' | 'year'>('name');
	let searchQuery = $state('');
	let searchTimeout: ReturnType<typeof setTimeout> | null = null;
	let fetchId = 0;

	let detailModalOpen = $state(false);
	let selectedAlbum = $state<LocalAlbumSummary | null>(null);

	const PAGE_SIZE = 48;

	async function fetchAlbums(reset: boolean = false): Promise<void> {
		const id = ++fetchId;
		fetchError = '';
		if (reset) {
			loading = true;
			albums = [];
		} else {
			loadingMore = true;
		}

		try {
			const offset = reset ? 0 : albums.length;
			const url = API.local.albums(
				PAGE_SIZE,
				offset,
				sortBy,
				searchQuery.trim() || undefined
			);
			const res = await fetch(url);
			if (id !== fetchId) return;
			if (res.ok) {
				const data: LocalPaginatedResponse = await res.json();
				albums = reset ? data.items : [...albums, ...data.items];
				total = data.total;
			} else {
				fetchError = 'Failed to load albums';
			}
		} catch {
			if (id === fetchId) fetchError = 'Failed to connect to local files service';
		} finally {
			if (id === fetchId) {
				loading = false;
				loadingMore = false;
			}
		}
	}

	async function fetchSidebar(): Promise<void> {
		const [recentRes, statsRes] = await Promise.allSettled([
			fetch(API.local.recent()),
			fetch(API.local.stats())
		]);

		if (recentRes.status === 'fulfilled' && recentRes.value.ok)
			recentAlbums = await recentRes.value.json();
		if (statsRes.status === 'fulfilled' && statsRes.value.ok)
			stats = await statsRes.value.json();
	}

	function openDetail(album: LocalAlbumSummary): void {
		selectedAlbum = album;
		detailModalOpen = true;
	}

	function handleDetailClose(): void {
		selectedAlbum = null;
	}

	function handleSortChange(e: Event): void {
		sortBy = (e.target as HTMLSelectElement).value as typeof sortBy;
		fetchAlbums(true);
	}

	function handleSearch(): void {
		if (searchTimeout) clearTimeout(searchTimeout);
		searchTimeout = setTimeout(() => {
			fetchAlbums(true);
		}, 300);
	}

	function loadMore(): void {
		if (!loadingMore && albums.length < total) {
			fetchAlbums(false);
		}
	}

	function formatSize(bytes: number): string {
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
		return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
	}

	onMount(() => {
		fetchAlbums(true);
		fetchSidebar();
	});

	onDestroy(() => {
		if (searchTimeout) clearTimeout(searchTimeout);
	});
</script>

<div class="container mx-auto p-6">
	<div class="flex items-center gap-3 mb-2">
		<svg
			xmlns="http://www.w3.org/2000/svg"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
			class="h-8 w-8 text-accent"
		>
			<path d="M3 18v-6a9 9 0 0 1 18 0v6"></path>
			<path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z"></path>
			<path d="M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path>
		</svg>
		<h1 class="text-2xl font-bold">Local Files</h1>
		{#if stats}
			<span class="badge badge-neutral">{stats.total_albums} albums</span>
		{/if}
	</div>

	{#if stats}
		<div class="flex flex-wrap gap-3 mb-6">
			<div class="stat bg-base-200 rounded-box p-3 min-w-0">
				<div class="stat-title text-xs">Tracks</div>
				<div class="stat-value text-lg">{stats.total_tracks.toLocaleString()}</div>
			</div>
			<div class="stat bg-base-200 rounded-box p-3 min-w-0">
				<div class="stat-title text-xs">Artists</div>
				<div class="stat-value text-lg">{stats.total_artists}</div>
			</div>
			<div class="stat bg-base-200 rounded-box p-3 min-w-0">
				<div class="stat-title text-xs">Total Size</div>
				<div class="stat-value text-lg">{stats.total_size_human}</div>
			</div>
			<div class="stat bg-base-200 rounded-box p-3 min-w-0">
				<div class="stat-title text-xs">Disk Free</div>
				<div class="stat-value text-lg">{stats.disk_free_human}</div>
			</div>
			{#if Object.keys(stats.format_breakdown).length > 0}
				<div class="stat bg-base-200 rounded-box p-3 min-w-0">
					<div class="stat-title text-xs">Formats</div>
					<div class="flex gap-1 mt-1 flex-wrap">
						{#each Object.entries(stats.format_breakdown) as [fmt, info]}
							<span class="badge badge-xs badge-ghost">{fmt}: {info.count}</span>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}

	{#if recentAlbums.length > 0}
		<div class="mb-8">
			<h2 class="text-lg font-semibold mb-3 opacity-80">Recently Added</h2>
			<div class="flex gap-3 overflow-x-auto pb-2">
				{#each recentAlbums as album (album.lidarr_album_id)}
					<button
						class="flex-shrink-0 w-36 group cursor-pointer transition-transform hover:scale-105 active:scale-95"
						onclick={() => openDetail(album)}
					>
						<div class="aspect-square rounded-lg overflow-hidden shadow-sm relative">
							<AlbumImage
								mbid={album.musicbrainz_id ?? String(album.lidarr_album_id)}
								customUrl={album.cover_url}
								alt={album.name}
								size="full"
								rounded="none"
								className="w-full h-full"
							/>
							{#if album.primary_format}
								<div class="absolute bottom-1 right-1">
									<span class="badge badge-xs badge-ghost">{album.primary_format}</span>
								</div>
							{/if}
						</div>
						<p class="text-sm font-medium mt-1 line-clamp-1">{album.name}</p>
						<p class="text-xs opacity-60 line-clamp-1">{album.artist_name}</p>
					</button>
				{/each}
			</div>
		</div>
	{/if}

	<div class="mb-6">
		<h2 class="text-lg font-semibold mb-3 opacity-80">All Albums</h2>
		<div class="flex flex-wrap items-center gap-3 mb-4">
			<input
				type="text"
				placeholder="Search albums..."
				class="input input-sm w-48"
				bind:value={searchQuery}
				oninput={handleSearch}
				aria-label="Search albums"
			/>
			<select class="select select-sm" onchange={handleSortChange}>
				<option value="name" selected={sortBy === 'name'}>Name</option>
				<option value="date_added" selected={sortBy === 'date_added'}>Date Added</option>
				<option value="year" selected={sortBy === 'year'}>Year</option>
			</select>
			{#if !loading}
				<span class="text-sm opacity-50">{total} results</span>
			{/if}
		</div>
	</div>

	{#if fetchError}
		<div role="alert" class="alert alert-error alert-soft mb-4">
			<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
			</svg>
			<span>{fetchError}</span>
			<button class="btn btn-sm btn-ghost" onclick={() => fetchAlbums(true)}>Retry</button>
		</div>
	{/if}

	{#if loading}
		<div
			class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
		>
			{#each Array(12) as _}
				<div class="card bg-base-100 shadow-sm animate-pulse">
					<div class="aspect-square bg-base-300"></div>
					<div class="card-body p-3">
						<div class="h-4 bg-base-300 rounded w-3/4"></div>
						<div class="h-3 bg-base-300 rounded w-1/2 mt-1"></div>
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<div
			class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
		>
			{#each albums as album (album.lidarr_album_id)}
				<div
					class="card bg-base-100 w-full shadow-sm group relative cursor-pointer transition-transform hover:scale-105 hover:shadow-lg active:scale-95"
					onclick={() => openDetail(album)}
					onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), openDetail(album))}
					role="button"
					tabindex="0"
				>
					<figure class="aspect-square overflow-hidden relative">
						<AlbumImage
							mbid={album.musicbrainz_id ?? String(album.lidarr_album_id)}
							customUrl={album.cover_url}
							alt={album.name}
							size="full"
							rounded="none"
							className="w-full h-full"
						/>
						<div class="absolute top-2 left-2">
							<div
								class="badge badge-sm gap-1 badge-accent"
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="2"
									class="h-3 w-3"
								>
									<path d="M3 18v-6a9 9 0 0 1 18 0v6"></path>
								</svg>
							</div>
						</div>
						{#if album.primary_format}
							<div class="absolute top-2 right-2">
								<div class="badge badge-sm badge-ghost">{album.primary_format}</div>
							</div>
						{/if}
						{#if album.year}
							<div class="absolute bottom-2 right-2">
								<div class="badge badge-sm badge-ghost">{album.year}</div>
							</div>
						{/if}
					</figure>

					<div class="card-body p-3">
						<h2 class="card-title text-sm line-clamp-2 min-h-[2.5rem]">{album.name}</h2>
						<div class="flex items-center justify-between">
							<p class="text-xs opacity-70 line-clamp-1 flex-1">{album.artist_name}</p>
							{#if album.total_size_bytes > 0}
								<span class="text-xs opacity-40 flex-shrink-0 ml-1"
									>{formatSize(album.total_size_bytes)}</span
								>
							{/if}
						</div>
					</div>
				</div>
			{/each}
		</div>

		{#if albums.length === 0}
			<div class="card bg-base-200 mt-4">
				<div class="card-body items-center text-center">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						class="h-12 w-12 opacity-20"
					>
						<path d="M3 18v-6a9 9 0 0 1 18 0v6"></path>
						<path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z"></path>
						<path d="M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path>
					</svg>
					<p class="text-lg opacity-60">No local files found</p>
					<p class="text-sm opacity-40">
						Make sure your music directory is mounted and configured in Settings.
					</p>
				</div>
			</div>
		{/if}

		{#if albums.length < total}
			<div class="flex justify-center mt-6">
				<button class="btn btn-ghost" onclick={loadMore} disabled={loadingMore}>
					{#if loadingMore}
						<span class="loading loading-spinner loading-sm"></span>
					{/if}
					Load More
				</button>
			</div>
		{/if}
	{/if}
</div>

<SourceAlbumModal
	bind:open={detailModalOpen}
	sourceType="local"
	album={selectedAlbum}
	onclose={handleDetailClose}
/>
