<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import type { AlbumInfo } from '$lib/types';
	import { colors } from '$lib/colors';
	import { errorModal } from '$lib/stores/errorModal';

	export let data: { albumId: string; album: AlbumInfo | null };

	let album: AlbumInfo | null = data.album;
	let error: string | null = null;
	let loading: boolean = true;
	let showToast = false;
	let requesting = false;
	let imageLoaded = false;

	// Fetch album data in the background after component mounts
	onMount(async () => {
		if (!album) {
			try {
				const res = await fetch(`/api/album/${data.albumId}`);
				if (res.ok) {
					album = await res.json();
				} else {
					error = 'Failed to load album';
				}
			} catch (e) {
				error = 'Error loading album';
			} finally {
				loading = false;
			}
		} else {
			loading = false;
		}
	});

	function formatDuration(ms?: number | null): string {
		if (!ms) return '--:--';
		const totalSeconds = Math.floor(ms / 1000);
		const minutes = Math.floor(totalSeconds / 60);
		const seconds = totalSeconds % 60;
		return `${minutes}:${seconds.toString().padStart(2, '0')}`;
	}

	function formatTotalDuration(ms?: number | null): string {
		if (!ms) return '';
		const totalSeconds = Math.floor(ms / 1000);
		const hours = Math.floor(totalSeconds / 3600);
		const minutes = Math.floor((totalSeconds % 3600) / 60);
		
		if (hours > 0) {
			return `${hours} hr ${minutes} min`;
		}
		return `${minutes} min`;
	}

	function handleImageLoad() {
		imageLoaded = true;
	}

	async function handleRequest() {
		if (!album || requesting) return;
		
		requesting = true;
		
		try {
			const res = await fetch('/api/request', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ musicbrainz_id: album.musicbrainz_id })
			});
			
			if (res.ok) {
				if (album) {
					album.in_library = true;
					album = album;
				}
				
				showToast = true;
				setTimeout(() => {
					showToast = false;
				}, 2000);
			} else {
				const errorData = await res.json();
				const errorDetail = errorData.detail || 'Unknown error';
				
				if (errorDetail.includes('Metadata Profile') || errorDetail.includes('Cannot add this')) {
					const albumTypeMatch = errorDetail.match(/Cannot add this (\w+)/);
					const albumType = albumTypeMatch ? albumTypeMatch[1] : 'release';
					
					errorModal.show(
						`Cannot Add ${albumType}`,
						errorDetail,
						'Go to Lidarr → Settings → Profiles → Metadata Profiles, and enable the appropriate release types in your active profile. After enabling, refresh the artist in Lidarr.'
					);
				} else {
					errorModal.show('Request Failed', errorDetail, '');
				}
			}
		} catch (e) {
			errorModal.show('Request Failed', 'Network error occurred', '');
		} finally {
			requesting = false;
		}
	}

	function goBack() {
		if (browser && window.history.length > 1) {
			window.history.back();
		} else {
			goto('/');
		}
	}

	function goToArtist() {
		if (album?.artist_id) {
			goto(`/artist/${album.artist_id}`);
		}
	}

	onDestroy(() => {});
</script>

<div class="w-full px-2 sm:px-4 lg:px-8 py-4 sm:py-8 max-w-7xl mx-auto">
	<!-- Back Button -->
	<button 
		on:click={goBack}
		class="btn btn-ghost btn-circle mb-4"
		aria-label="Go back"
	>
		<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
		</svg>
	</button>

	{#if error}
		<div class="flex items-center justify-center min-h-[50vh]">
			<div class="alert alert-error">
				<span>{error}</span>
			</div>
		</div>
	{:else if loading || !album}
		<!-- Skeleton Loading State -->
		<div class="space-y-6 sm:space-y-8">
			<div class="flex flex-col lg:flex-row gap-6 lg:gap-8">
				<!-- Skeleton Cover -->
				<div class="skeleton w-full lg:w-64 xl:w-80 aspect-square rounded-box flex-shrink-0"></div>
				
				<!-- Skeleton Info -->
				<div class="flex-1 flex flex-col justify-end space-y-4">
					<div class="skeleton h-4 w-20"></div>
					<div class="skeleton h-12 w-3/4"></div>
					<div class="skeleton h-6 w-1/2"></div>
					<div class="flex gap-4 mt-6">
						<div class="skeleton h-12 w-32"></div>
						<div class="skeleton h-12 w-32"></div>
					</div>
				</div>
			</div>
			
			<!-- Skeleton Tracklist -->
			<div class="space-y-2">
				<div class="skeleton h-8 w-32 mb-4"></div>
				{#each Array(8) as _, i}
					<div class="skeleton h-12 w-full"></div>
				{/each}
			</div>
		</div>
	{:else if album}
		<div class="space-y-6 sm:space-y-8">
			<!-- Album Header -->
			<div class="flex flex-col lg:flex-row gap-6 lg:gap-8">
				<div class="w-full lg:w-64 xl:w-80 flex-shrink-0 relative">
					{#if !imageLoaded}
						<div class="skeleton w-full aspect-square rounded-box absolute inset-0"></div>
					{/if}
					<img 
						src="/api/covers/release-group/{album.musicbrainz_id}" 
						alt={album.title}
						class="w-full aspect-square object-cover rounded-box shadow-2xl transition-opacity duration-300"
						class:opacity-0={!imageLoaded}
						on:load={handleImageLoad}
						on:error={(e) => {
							const target = e.currentTarget as HTMLImageElement;
							target.src = 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 200%22%3E%3Crect fill=%22%23444%22 width=%22200%22 height=%22200%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 fill=%22%23999%22 font-size=%2224%22 font-family=%22sans-serif%22%3ENo Image%3C/text%3E%3C/svg%3E';
							imageLoaded = true;
						}}
					/>
				</div>

				<!-- Album Info -->
				<div class="flex-1 flex flex-col justify-end space-y-4">
					<div class="text-xs sm:text-sm font-semibold uppercase tracking-wider opacity-70">
						{album.type || 'Album'}
					</div>
					
					<h1 class="text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-bold leading-tight">
						{album.title}
					</h1>
					
					{#if album.disambiguation}
						<p class="text-sm opacity-60 italic">({album.disambiguation})</p>
					{/if}
					
					<div class="flex flex-wrap items-center gap-2 text-sm">
						<!-- Artist Link -->
						<button 
							on:click={goToArtist}
							class="font-semibold hover:underline cursor-pointer"
						>
							{album.artist_name}
						</button>
						
						{#if album.year}
							<span class="opacity-50">•</span>
							<span>{album.year}</span>
						{/if}
						
						{#if album.total_tracks > 0}
							<span class="opacity-50">•</span>
							<span>{album.total_tracks} {album.total_tracks === 1 ? 'track' : 'tracks'}</span>
						{/if}
						
						{#if album.total_length}
							<span class="opacity-50">•</span>
							<span>{formatTotalDuration(album.total_length)}</span>
						{/if}
					</div>

					<!-- Additional Info -->
					<div class="flex flex-wrap gap-x-4 gap-y-2 text-xs sm:text-sm opacity-70">
						{#if album.label}
							<div>
								<span class="font-semibold">Label:</span> {album.label}
							</div>
						{/if}
						{#if album.country}
							<div>
								<span class="font-semibold">Country:</span> {album.country}
							</div>
						{/if}
						{#if album.barcode}
							<div>
								<span class="font-semibold">Barcode:</span> {album.barcode}
							</div>
						{/if}
					</div>
					
					<!-- Action Button -->
					<div class="pt-4">
						{#if album.in_library}
							<div class="badge badge-lg gap-2" style="background-color: {colors.accent}; color: {colors.secondary};">
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
									<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
								</svg>
								In Library
							</div>
						{:else}
							<button
								class="btn btn-lg gap-2"
								style="background-color: {colors.accent}; color: {colors.secondary}; border: none;"
								on:click={handleRequest}
								disabled={requesting}
							>
								{#if requesting}
									<span class="loading loading-spinner loading-sm"></span>
									Requesting...
								{:else}
									<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
										<path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
									</svg>
									Add to Library
								{/if}
							</button>
						{/if}
					</div>
				</div>
			</div>

			<!-- Tracks List -->
			{#if album.tracks.length > 0}
				<div class="space-y-3">
					<h2 class="text-xl sm:text-2xl font-bold">Tracks</h2>
					
					<div class="bg-base-200 rounded-box overflow-hidden">
						<ul class="list">
							{#each album.tracks as track, index}
								<li class="list-row hover:bg-base-300/50 transition-colors p-3 sm:p-4">
									<div class="flex items-center gap-4 w-full">
										<!-- Track Number -->
										<div class="text-base-content/60 font-medium w-8 text-center flex-shrink-0">
											{track.position}
										</div>
										
										<!-- Track Title -->
										<div class="flex-1 min-w-0">
											<div class="font-medium truncate">
												{track.title}
											</div>
										</div>
										
										<!-- Track Duration -->
										<div class="text-base-content/60 text-sm flex-shrink-0">
											{formatDuration(track.length)}
										</div>
									</div>
								</li>
							{/each}
						</ul>
					</div>
				</div>
			{/if}

			<!-- Release Date -->
			{#if album.release_date}
				<div class="text-xs opacity-60">
					<span class="font-semibold">Release Date:</span> {album.release_date}
				</div>
			{/if}
		</div>
	{:else}
		<div class="flex items-center justify-center min-h-[50vh]">
			<p class="text-base-content/60">Album not found</p>
		</div>
	{/if}
</div>

<!-- Toast Notification -->
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
