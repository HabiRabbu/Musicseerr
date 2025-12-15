<script lang="ts">
	import { page } from '$app/stores';
	import { onMount, onDestroy } from 'svelte';
	import { goto, beforeNavigate } from '$app/navigation';
	import ArtistImage from '$lib/components/ArtistImage.svelte';
	import AlbumImage from '$lib/components/AlbumImage.svelte';
	import type { HomeArtist, HomeAlbum, GenreDetailResponse } from '$lib/types';

	let genreName = '';
	let genreData: GenreDetailResponse | null = null;
	let loading = true;
	let error = '';
	let heroArtistMbid: string | null = null;
	let heroImageLoaded = false;
	let abortController: AbortController | null = null;
	let lastLoadedGenre = '';

	let artistOffset = 0;
	let albumOffset = 0;
	let loadingMoreArtists = false;
	let loadingMoreAlbums = false;
	const PAGE_SIZE = 50;

	let activeTab: 'artists' | 'albums' = 'artists';

	$: genreName = $page.url.searchParams.get('name') || '';

	async function loadHeroArtist() {
		if (!genreName) return;
		heroArtistMbid = null;
		heroImageLoaded = false;
		try {
			const response = await fetch(`/api/home/genre-artist/${encodeURIComponent(genreName)}`, {
				signal: abortController?.signal
			});
			if (response.ok) {
				const data = await response.json();
				heroArtistMbid = data.artist_mbid;
			}
		} catch (e) {
			if (e instanceof Error && e.name === 'AbortError') return;
		}
	}

	async function loadGenreData() {
		if (!genreName) {
			error = 'No genre specified';
			loading = false;
			return;
		}

		loading = true;
		error = '';
		artistOffset = 0;
		albumOffset = 0;

		try {
			const response = await fetch(
				`/api/home/genre/${encodeURIComponent(genreName)}?limit=${PAGE_SIZE}`,
				{ signal: abortController?.signal }
			);
			if (response.ok) {
				genreData = await response.json();
			} else {
				error = 'Failed to load genre data';
			}
		} catch (e) {
			if (e instanceof Error && e.name === 'AbortError') return;
			console.error('Failed to load genre data:', e);
			error = 'Failed to load genre data';
		} finally {
			loading = false;
		}
	}

	async function loadMoreArtists() {
		if (!genreData || loadingMoreArtists || !genreData.popular?.has_more_artists) return;

		loadingMoreArtists = true;
		artistOffset += PAGE_SIZE;

		try {
			const response = await fetch(
				`/api/home/genre/${encodeURIComponent(genreName)}?limit=${PAGE_SIZE}&artist_offset=${artistOffset}`
			);
			if (response.ok) {
				const data: GenreDetailResponse = await response.json();
				if (genreData.popular && data.popular) {
					genreData.popular.artists = [...genreData.popular.artists, ...data.popular.artists];
					genreData.popular.has_more_artists = data.popular.has_more_artists;
				}
			}
		} catch (e) {
			console.error('Failed to load more artists:', e);
		} finally {
			loadingMoreArtists = false;
		}
	}

	async function loadMoreAlbums() {
		if (!genreData || loadingMoreAlbums || !genreData.popular?.has_more_albums) return;

		loadingMoreAlbums = true;
		albumOffset += PAGE_SIZE;

		try {
			const response = await fetch(
				`/api/home/genre/${encodeURIComponent(genreName)}?limit=${PAGE_SIZE}&album_offset=${albumOffset}`
			);
			if (response.ok) {
				const data: GenreDetailResponse = await response.json();
				if (genreData.popular && data.popular) {
					genreData.popular.albums = [...genreData.popular.albums, ...data.popular.albums];
					genreData.popular.has_more_albums = data.popular.has_more_albums;
				}
			}
		} catch (e) {
			console.error('Failed to load more albums:', e);
		} finally {
			loadingMoreAlbums = false;
		}
	}

	function loadData() {
		if (abortController) {
			abortController.abort();
		}
		abortController = new AbortController();
		lastLoadedGenre = genreName;
		loadGenreData();
		loadHeroArtist();
	}

	function cleanup() {
		if (abortController) {
			abortController.abort();
			abortController = null;
		}
	}

	onMount(() => {
		if (genreName) {
			loadData();
		}
	});

	onDestroy(cleanup);
	beforeNavigate(cleanup);

	$: if (genreName && genreName !== lastLoadedGenre) {
		loadData();
	}

	function handleArtistClick(mbid: string) {
		goto(`/artist/${mbid}`);
	}

	function handleAlbumClick(mbid: string) {
		goto(`/album/${mbid}`);
	}

	$: hasLibraryContent =
		(genreData?.library?.artists?.length ?? 0) > 0 ||
		(genreData?.library?.albums?.length ?? 0) > 0;
</script>

<svelte:head>
	<title>{genreName ? `${genreName}` : 'Genre'} - Musicseerr</title>
</svelte:head>

<div class="min-h-screen bg-base-100 relative overflow-hidden">
	<!-- Hero Background Image -->
	{#if heroArtistMbid}
		<div class="absolute inset-x-0 top-0 h-80 overflow-hidden pointer-events-none" style="z-index: 0;">
			<img
				src="/api/covers/artist/{heroArtistMbid}?size=500"
				alt=""
				class="w-full object-contain object-top transition-opacity duration-500 {heroImageLoaded ? 'opacity-20' : 'opacity-0'}"
				on:load={() => heroImageLoaded = true}
			/>
			<div class="absolute inset-0 bg-gradient-to-b from-transparent via-base-100/70 to-base-100"></div>
		</div>
	{/if}

	<div class="container mx-auto p-4 max-w-7xl relative" style="z-index: 1;">
		<!-- Header -->
		<div class="mb-8">
			<a href="/" class="btn btn-ghost btn-sm gap-2 mb-4 -ml-2">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-4 h-4"
				>
					<path
						fill-rule="evenodd"
						d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
						clip-rule="evenodd"
					/>
				</svg>
				Back
			</a>
			<div class="flex items-center gap-4">
				<div
					class="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/30 to-secondary/30 flex items-center justify-center text-4xl"
				>
					🎵
				</div>
				<div>
					<h1 class="text-4xl font-bold capitalize">{genreName || 'Genre'}</h1>
					{#if genreData}
						<p class="text-base-content/60 mt-1">
							{#if hasLibraryContent}
								{genreData.library?.artist_count ?? 0} artists · {genreData.library?.album_count ??
									0} albums in library
							{:else}
								Explore popular {genreName} music
							{/if}
						</p>
					{/if}
				</div>
			</div>
		</div>

		{#if loading}
			<!-- Skeleton Loading -->
			<!-- Library Section Skeleton -->
			<section class="mb-12">
				<div class="flex items-center gap-3 mb-6">
					<div class="skeleton w-10 h-10 rounded-xl"></div>
					<div>
						<div class="skeleton h-6 w-48 mb-2"></div>
						<div class="skeleton h-4 w-32"></div>
					</div>
				</div>
				<div class="skeleton h-5 w-20 mb-4"></div>
				<div
					class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
				>
					{#each Array(6) as _}
						<div class="card bg-base-200/50">
							<div class="skeleton aspect-square rounded-t-2xl"></div>
							<div class="p-3">
								<div class="skeleton h-4 w-3/4 mb-2"></div>
								<div class="skeleton h-3 w-1/2"></div>
							</div>
						</div>
					{/each}
				</div>
			</section>

			<div class="divider my-8"></div>

			<!-- Popular Section Skeleton -->
			<section>
				<div class="flex items-center gap-3 mb-6">
					<div class="skeleton w-10 h-10 rounded-xl"></div>
					<div>
						<div class="skeleton h-6 w-56 mb-2"></div>
						<div class="skeleton h-4 w-40"></div>
					</div>
				</div>
				<div class="skeleton h-10 w-64 rounded-lg mb-6"></div>
				<div
					class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
				>
					{#each Array(12) as _}
						<div class="card bg-base-200/50">
							<div class="skeleton aspect-square rounded-t-2xl"></div>
							<div class="p-3">
								<div class="skeleton h-4 w-3/4"></div>
							</div>
						</div>
					{/each}
				</div>
			</section>
		{:else if error}
			<div class="flex flex-col items-center justify-center py-24">
				<div class="text-6xl mb-4">😕</div>
				<p class="text-base-content/70 text-lg">{error}</p>
				<button class="btn btn-primary mt-6" on:click={loadGenreData}>Try Again</button>
			</div>
		{:else if genreData}
			<!-- Library Section (if we have items) -->
			{#if hasLibraryContent}
				<section class="mb-12">
					<div class="flex items-center gap-3 mb-6">
						<div
							class="w-10 h-10 rounded-xl bg-success/20 flex items-center justify-center text-success"
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 20 20"
								fill="currentColor"
								class="w-5 h-5"
							>
								<path
									d="M10.75 16.82A7.462 7.462 0 0115 15.5c.71 0 1.396.098 2.046.282A.75.75 0 0018 15.06v-11a.75.75 0 00-.546-.721A9.006 9.006 0 0015 3a8.963 8.963 0 00-4.25 1.065V16.82zM9.25 4.065A8.963 8.963 0 005 3c-.85 0-1.673.118-2.454.339A.75.75 0 002 4.06v11a.75.75 0 00.954.721A7.506 7.506 0 015 15.5c1.579 0 3.042.487 4.25 1.32V4.065z"
								/>
							</svg>
						</div>
						<div>
							<h2 class="text-2xl font-bold">From Your Library</h2>
							<p class="text-sm text-base-content/60">
								{genreData.library?.artist_count ?? 0} artists · {genreData.library?.album_count ??
									0} albums
							</p>
						</div>
					</div>

					<!-- Library Artists -->
					{#if (genreData.library?.artists?.length ?? 0) > 0}
						<h3 class="text-lg font-semibold mb-4 text-base-content/80">Artists</h3>
						<div
							class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 mb-8"
						>
							{#each genreData.library?.artists ?? [] as artist (artist.mbid || artist.name)}
								<button
									type="button"
									class="card bg-base-200/50 hover:bg-base-200 transition-all duration-200 cursor-pointer group"
									on:click={() => artist.mbid && handleArtistClick(artist.mbid)}
								>
									<figure class="flex justify-center pt-4 relative">
										<ArtistImage mbid={artist.mbid || ''} alt={artist.name} size="md" lazy={false} />
										<div
											class="absolute top-2 right-2 badge badge-success badge-sm gap-1 opacity-90"
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 16 16"
												fill="currentColor"
												class="w-3 h-3"
											>
												<path
													fill-rule="evenodd"
													d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z"
													clip-rule="evenodd"
												/>
											</svg>
										</div>
									</figure>
									<div class="card-body p-3 items-center text-center">
										<h3 class="font-semibold text-sm line-clamp-1">{artist.name}</h3>
										{#if artist.listen_count}
											<p class="text-xs text-base-content/50">
												{artist.listen_count} album{artist.listen_count !== 1 ? 's' : ''}
											</p>
										{/if}
									</div>
								</button>
							{/each}
						</div>
					{/if}

					<!-- Library Albums -->
					{#if (genreData.library?.albums?.length ?? 0) > 0}
						<h3 class="text-lg font-semibold mb-4 text-base-content/80">Albums</h3>
						<div
							class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
						>
							{#each genreData.library?.albums ?? [] as album (album.mbid || album.name)}
								<button
									type="button"
									class="card bg-base-200/50 hover:bg-base-200 transition-all duration-200 cursor-pointer group"
									on:click={() => album.mbid && handleAlbumClick(album.mbid)}
								>
								<figure class="aspect-square overflow-hidden relative rounded-t-2xl">
									<AlbumImage 
										mbid={album.mbid || ''} 
										alt={album.name} 
										size="md" 
										rounded="none" 
										className="w-full h-full" 
										customUrl={album.image_url || null} 
									/>
									<div
											class="absolute top-2 right-2 badge badge-success badge-sm gap-1 opacity-90"
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 16 16"
												fill="currentColor"
												class="w-3 h-3"
											>
												<path
													fill-rule="evenodd"
													d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z"
													clip-rule="evenodd"
												/>
											</svg>
										</div>
									</figure>
									<div class="card-body p-3">
										<h3 class="font-semibold text-sm line-clamp-1">{album.name}</h3>
										<p class="text-xs text-base-content/50 line-clamp-1">
											{album.artist_name || 'Unknown Artist'}
											{#if album.release_date}
												· {album.release_date}
											{/if}
										</p>
									</div>
								</button>
							{/each}
						</div>
					{/if}
				</section>

				<div class="divider my-8"></div>
			{/if}

			<!-- Popular Section -->
			<section>
				<div class="flex items-center gap-3 mb-6">
					<div
						class="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center text-primary"
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 20 20"
							fill="currentColor"
							class="w-5 h-5"
						>
							<path
								fill-rule="evenodd"
								d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401Z"
								clip-rule="evenodd"
							/>
						</svg>
					</div>
					<div>
						<h2 class="text-2xl font-bold">Popular in {genreName}</h2>
						<p class="text-sm text-base-content/60">Discover the best {genreName} music</p>
					</div>
				</div>

				<!-- Tabs -->
				<div class="tabs tabs-box mb-6">
					<button
						class="tab {activeTab === 'artists' ? 'tab-active' : ''}"
						on:click={() => (activeTab = 'artists')}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 20 20"
							fill="currentColor"
							class="w-4 h-4 mr-2"
						>
							<path
								d="M10 8a3 3 0 100-6 3 3 0 000 6zM3.465 14.493a1.23 1.23 0 00.41 1.412A9.957 9.957 0 0010 18c2.31 0 4.438-.784 6.131-2.1.43-.333.604-.903.408-1.41a7.002 7.002 0 00-13.074.003z"
							/>
						</svg>
						Artists
						{#if genreData.popular?.artists?.length}
							<span class="badge badge-sm ml-2">{genreData.popular.artists.length}</span>
						{/if}
					</button>
					<button
						class="tab {activeTab === 'albums' ? 'tab-active' : ''}"
						on:click={() => (activeTab = 'albums')}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 20 20"
							fill="currentColor"
							class="w-4 h-4 mr-2"
						>
							<path
								fill-rule="evenodd"
								d="M10 18a8 8 0 100-16 8 8 0 000 16zM10 5a1 1 0 100 2 1 1 0 000-2zm-3 4a1 1 0 100-2 1 1 0 000 2zm8 0a1 1 0 100-2 1 1 0 000 2zm-5 7a4 4 0 100-8 4 4 0 000 8zm0-2a2 2 0 100-4 2 2 0 000 4z"
								clip-rule="evenodd"
							/>
						</svg>
						Albums
						{#if genreData.popular?.albums?.length}
							<span class="badge badge-sm ml-2">{genreData.popular.albums.length}</span>
						{/if}
					</button>
				</div>

				<!-- Artists Grid -->
				{#if activeTab === 'artists'}
					{#if (genreData.popular?.artists?.length ?? 0) === 0}
						<div class="flex flex-col items-center justify-center py-16">
							<div class="text-5xl mb-4 opacity-30">🎤</div>
							<p class="text-base-content/50">No artists found for this genre</p>
						</div>
					{:else}
						<div
							class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
						>
							{#each genreData.popular?.artists ?? [] as artist (artist.mbid || artist.name)}
								<button
									type="button"
									class="card bg-base-200/50 hover:bg-base-200 transition-all duration-200 cursor-pointer group"
									on:click={() => artist.mbid && handleArtistClick(artist.mbid)}
								>
									<figure class="flex justify-center pt-4 relative">
										<ArtistImage mbid={artist.mbid || ''} alt={artist.name} size="md" lazy={false} />
										{#if artist.in_library}
											<div
												class="absolute top-2 right-2 badge badge-success badge-sm gap-1 opacity-90"
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 16 16"
													fill="currentColor"
													class="w-3 h-3"
												>
													<path
														fill-rule="evenodd"
														d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z"
														clip-rule="evenodd"
													/>
												</svg>
											</div>
										{/if}
									</figure>
									<div class="card-body p-3 items-center text-center">
										<h3 class="font-semibold text-sm line-clamp-1">{artist.name}</h3>
									</div>
								</button>
							{/each}
						</div>

						<!-- Load More Artists -->
						{#if genreData.popular?.has_more_artists}
							<div class="flex justify-center mt-8">
								<button
									class="btn btn-outline btn-wide gap-2"
									on:click={loadMoreArtists}
									disabled={loadingMoreArtists}
								>
									{#if loadingMoreArtists}
										<span class="loading loading-spinner loading-sm"></span>
									{:else}
										<svg
											xmlns="http://www.w3.org/2000/svg"
											viewBox="0 0 20 20"
											fill="currentColor"
											class="w-5 h-5"
										>
											<path
												d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z"
											/>
										</svg>
									{/if}
									Load More Artists
								</button>
							</div>
						{/if}
					{/if}
				{/if}

				<!-- Albums Grid -->
				{#if activeTab === 'albums'}
					{#if (genreData.popular?.albums?.length ?? 0) === 0}
						<div class="flex flex-col items-center justify-center py-16">
							<div class="text-5xl mb-4 opacity-30">💿</div>
							<p class="text-base-content/50">No albums found for this genre</p>
						</div>
					{:else}
						<div
							class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4"
						>
							{#each genreData.popular?.albums ?? [] as album (album.mbid || album.name)}
								<button
									type="button"
									class="card bg-base-200/50 hover:bg-base-200 transition-all duration-200 cursor-pointer group"
									on:click={() => album.mbid && handleAlbumClick(album.mbid)}
								>
								<figure class="aspect-square overflow-hidden relative rounded-t-2xl">
									<AlbumImage 
										mbid={album.mbid || ''} 
										alt={album.name} 
										size="md" 
										rounded="none" 
										className="w-full h-full" 
										customUrl={album.image_url || null} 
									/>
									{#if album.in_library}
											<div
												class="absolute top-2 right-2 badge badge-success badge-sm gap-1 opacity-90"
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 16 16"
													fill="currentColor"
													class="w-3 h-3"
												>
													<path
														fill-rule="evenodd"
														d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z"
														clip-rule="evenodd"
													/>
												</svg>
											</div>
										{/if}
									</figure>
									<div class="card-body p-3">
										<h3 class="font-semibold text-sm line-clamp-1">{album.name}</h3>
										<p class="text-xs text-base-content/50 line-clamp-1">
											{album.artist_name || 'Unknown Artist'}
											{#if album.release_date}
												· {album.release_date}
											{/if}
										</p>
									</div>
								</button>
							{/each}
						</div>

						<!-- Load More Albums -->
						{#if genreData.popular?.has_more_albums}
							<div class="flex justify-center mt-8">
								<button
									class="btn btn-outline btn-wide gap-2"
									on:click={loadMoreAlbums}
									disabled={loadingMoreAlbums}
								>
									{#if loadingMoreAlbums}
										<span class="loading loading-spinner loading-sm"></span>
									{:else}
										<svg
											xmlns="http://www.w3.org/2000/svg"
											viewBox="0 0 20 20"
											fill="currentColor"
											class="w-5 h-5"
										>
											<path
												d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z"
											/>
										</svg>
									{/if}
									Load More Albums
								</button>
							</div>
						{/if}
					{/if}
				{/if}
			</section>
		{/if}
	</div>
</div>
