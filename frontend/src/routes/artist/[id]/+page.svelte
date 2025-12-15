<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { invalidate } from '$app/navigation';
	import { goto } from '$app/navigation';
	import { fade } from 'svelte/transition';
	import type { ArtistInfo, ArtistReleases } from '$lib/types';
	import { colors } from '$lib/colors';
	import { errorModal } from '$lib/stores/errorModal';
	import ArtistHeaderSkeleton from '$lib/components/ArtistHeaderSkeleton.svelte';
	import AlbumGridSkeleton from '$lib/components/AlbumGridSkeleton.svelte';
	import ArtistImage from '$lib/components/ArtistImage.svelte';
	import AlbumImage from '$lib/components/AlbumImage.svelte';

	export let data: { artistId: string };

	let artist: ArtistInfo | null = null;
	let loadingBasic = true;
	let loadingExtended = true;
	let error: string | null = null;
	let showToast = false;
	let linksCarousel: HTMLDivElement;
	let requestingAlbums = new Set<string>();
	let descriptionExpanded = false;
	let abortController: AbortController | null = null;
	let descriptionElement: HTMLElement;
	let showViewMore = false;
	let lastFetchTime = 0;
	let albumsCollapsed = false;
	let epsCollapsed = false;
	let singlesCollapsed = false;
	let loadingMoreReleases = false;
	let currentOffset = 50;
	let hasMoreReleases = false;
	let totalReleaseCount = 0;
	let loadedReleaseCount = 0;
	const BATCH_SIZE = 50;
	let fetchMoreTimeoutId: ReturnType<typeof setTimeout> | null = null;
	let heroGradient = 'from-base-300 via-base-200 to-base-100';
	let heroImageLoaded = false;

	async function extractDominantColor(imgUrl: string): Promise<string> {
		return new Promise((resolve) => {
			const img = new Image();
			img.crossOrigin = 'anonymous';
			img.onload = () => {
				try {
					const canvas = document.createElement('canvas');
					const ctx = canvas.getContext('2d');
					if (!ctx) {
						resolve('from-base-300 via-base-200 to-base-100');
						return;
					}
					
					canvas.width = 50;
					canvas.height = 50;
					ctx.drawImage(img, 0, 0, 50, 50);
					
					const imageData = ctx.getImageData(0, 0, 50, 50).data;
					let r = 0, g = 0, b = 0, count = 0;
					
					for (let i = 0; i < imageData.length; i += 16) {
						const pr = imageData[i];
						const pg = imageData[i + 1];
						const pb = imageData[i + 2];
						const pa = imageData[i + 3];
						
						if (pa > 128) {
							r += pr;
							g += pg;
							b += pb;
							count++;
						}
					}
					
					if (count > 0) {
						r = Math.round(r / count);
						g = Math.round(g / count);
						b = Math.round(b / count);
						
						const darkerR = Math.round(r * 0.3);
						const darkerG = Math.round(g * 0.3);
						const darkerB = Math.round(b * 0.3);
						
						heroGradient = `from-[rgb(${darkerR},${darkerG},${darkerB})] via-[rgb(${Math.round(r*0.15)},${Math.round(g*0.15)},${Math.round(b*0.15)})] to-base-100`;
						resolve(heroGradient);
					} else {
						resolve('from-base-300 via-base-200 to-base-100');
					}
				} catch (e) {
					resolve('from-base-300 via-base-200 to-base-100');
				}
			};
			img.onerror = () => resolve('from-base-300 via-base-200 to-base-100');
			img.src = imgUrl;
		});
	}

	function onHeroImageLoad() {
		heroImageLoaded = true;
		if (artist) {
			extractDominantColor(`/api/covers/artist/${artist.musicbrainz_id}?size=250`);
		}
	}

	function checkDescriptionHeight() {
		if (descriptionElement && !descriptionExpanded) {
			const lineHeight = parseFloat(getComputedStyle(descriptionElement).lineHeight);
			const actualHeight = descriptionElement.scrollHeight;
			const fourLines = lineHeight * 4;
			showViewMore = actualHeight > fourLines;
		}
	}
	
	function sortReleasesByYear(releases: any[]) {
		return releases.sort((a, b) => {
			const yearA = a.year;
			const yearB = b.year;
			
			if (yearA === null || yearA === undefined) return 1;
			if (yearB === null || yearB === undefined) return -1;
			
			return yearB - yearA;
		});
	}

	$: validLinks = artist?.external_links.filter(link => link.url && link.url.trim() !== '') || [];

	async function fetchArtist(force = false) {
		loadingBasic = true;
		loadingExtended = true;
		error = null;
		
		if (abortController) {
			abortController.abort();
		}
		abortController = new AbortController();
		
		await fetchBasicInfo(force);
		
		if (artist) {
			fetchExtendedInfo(force); // Don't await - let it load in background
		}
	}
	
	async function fetchBasicInfo(force = false) {
		try {
			const now = Date.now();
			const cacheBuster = force ? `?t=${now}` : '';
			const res = await fetch(`/api/artist/${data.artistId}${cacheBuster}`, {
				signal: abortController?.signal,
				cache: force ? 'no-cache' : 'default'
			});
			
			if (res.ok) {
				artist = await res.json();
				
				if (artist) {
					artist.albums = sortReleasesByYear(artist.albums);
					artist.singles = sortReleasesByYear(artist.singles);
					artist.eps = sortReleasesByYear(artist.eps);
					loadedReleaseCount = artist.albums.length + artist.singles.length + artist.eps.length;
					
					const releaseGroupCount = artist.release_group_count || 0;
					
					if (releaseGroupCount > loadedReleaseCount || 
					    (releaseGroupCount === 0 && loadedReleaseCount >= BATCH_SIZE)) {
						hasMoreReleases = true;
						totalReleaseCount = releaseGroupCount || loadedReleaseCount;
						currentOffset = BATCH_SIZE;
						fetchMoreReleases();
					} else {
						hasMoreReleases = false;
					}
				}
			} else {
				error = 'Failed to load artist';
			}
		} catch (e) {
			if (e instanceof Error && e.name === 'AbortError') {
				return;
			}
			error = 'Error loading artist';
			console.error(e);
		} finally {
			loadingBasic = false;
		}
	}
	
	async function fetchExtendedInfo(force = false) {
		try {
			const now = Date.now();
			const cacheBuster = force ? `?t=${now}` : '';
			const res = await fetch(`/api/artist/${data.artistId}/extended${cacheBuster}`, {
				signal: abortController?.signal,
				cache: force ? 'no-cache' : 'default'
			});
			
			if (res.ok) {
				const extendedInfo = await res.json();
				
				let attempts = 0;
				while (!artist && attempts < 50) {
					await new Promise(resolve => setTimeout(resolve, 100));
					attempts++;
				}
				
				if (artist) {
					artist.description = extendedInfo.description;
					artist.image = extendedInfo.image;
					artist = artist; // Trigger reactivity
					setTimeout(() => checkDescriptionHeight(), 50);
				} else {
					console.warn('Extended info loaded but artist data not available yet');
				}
			}
		} catch (e) {
			if (e instanceof Error && e.name === 'AbortError') {
				return;
			}
			console.error('Error loading extended artist info:', e);
		} finally {
			loadingExtended = false;
		}
	}
	
	async function fetchMoreReleases() {
		if (!artist || loadingMoreReleases || !hasMoreReleases) {
			return;
		}
		
		loadingMoreReleases = true;
		
		try {
			const url = `/api/artist/${data.artistId}/releases?offset=${currentOffset}&limit=${BATCH_SIZE}`;
			const res = await fetch(url, { signal: abortController?.signal });
			
			if (res.ok) {
				const moreReleases: ArtistReleases = await res.json();
				
				if (artist) {
					const newAlbums = moreReleases.albums.filter(
						(a: any) => !artist!.albums.some((existing: any) => existing.id === a.id)
					);
					const newSingles = moreReleases.singles.filter(
						(s: any) => !artist!.singles.some((existing: any) => existing.id === s.id)
					);
					const newEps = moreReleases.eps.filter(
						(e: any) => !artist!.eps.some((existing: any) => existing.id === e.id)
					);
					
					artist.albums = sortReleasesByYear([...artist.albums, ...newAlbums]);
					artist.singles = sortReleasesByYear([...artist.singles, ...newSingles]);
					artist.eps = sortReleasesByYear([...artist.eps, ...newEps]);
					artist = artist;
					
					currentOffset += BATCH_SIZE;
					hasMoreReleases = moreReleases.has_more;
					loadedReleaseCount = artist.albums.length + artist.singles.length + artist.eps.length;
					
					if (hasMoreReleases) {
						if (fetchMoreTimeoutId) clearTimeout(fetchMoreTimeoutId);
						fetchMoreTimeoutId = setTimeout(() => fetchMoreReleases(), 500);
					}
				}
			}
		} catch (e) {
			if (e instanceof Error && e.name === 'AbortError') {
				return;
			}
			console.error('Error loading more releases:', e);
			hasMoreReleases = false;
		} finally {
			loadingMoreReleases = false;
		}
	}

	let currentArtistId: string | null = null;

	$: if (browser && data.artistId && data.artistId !== currentArtistId) {
		currentArtistId = data.artistId;
		resetState();
		fetchArtist();
	}

	function resetState() {
		artist = null;
		loadingBasic = true;
		loadingExtended = true;
		error = null;
		heroImageLoaded = false;
		heroGradient = 'from-base-300 via-base-200 to-base-100';
		currentOffset = 50;
		hasMoreReleases = false;
		loadedReleaseCount = 0;
		if (abortController) {
			abortController.abort();
			abortController = null;
		}
	}

	onMount(() => {
		if (browser) {
			const handleRefresh = () => fetchArtist(true);
			window.addEventListener('artist-refresh', handleRefresh);
			
			return () => {
				window.removeEventListener('artist-refresh', handleRefresh);
			};
		}
	});

	onDestroy(() => {
		if (abortController) {
			abortController.abort();
			abortController = null;
		}
		if (fetchMoreTimeoutId) {
			clearTimeout(fetchMoreTimeoutId);
			fetchMoreTimeoutId = null;
		}
	});

	async function handleRequest(albumId: string, albumTitle?: string) {
		requestingAlbums.add(albumId);
		requestingAlbums = requestingAlbums;
		
		try {
			const res = await fetch('/api/request', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ musicbrainz_id: albumId })
			});
			
			if (res.ok) {
				if (artist) {
					const allReleases = [...artist.albums, ...artist.singles, ...artist.eps];
					const release = allReleases.find(rg => rg.id === albumId);
					if (release) {
						release.in_library = true;
						artist = artist;
					}
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
						'Go to Lidarr -> Settings -> Profiles -> Metadata Profiles, and enable the appropriate release types in your active profile. After enabling, refresh the artist in Lidarr.'
					);
				} else {
					errorModal.show(
						'Request Failed',
						errorDetail,
						''
					);
				}
			}
		} catch (e) {
			errorModal.show('Request Failed', 'Network error occurred', '');
		} finally {
			requestingAlbums.delete(albumId);
			requestingAlbums = requestingAlbums;
		}
	}

	function scrollLinks(direction: 'left' | 'right') {
		if (linksCarousel) {
			const scrollAmount = 400; 
			const newPosition = linksCarousel.scrollLeft + (direction === 'right' ? scrollAmount : -scrollAmount);
			linksCarousel.scrollTo({
				left: newPosition,
				behavior: 'smooth'
			});
		}
	}

	function goToAlbum(albumId: string, event?: Event) {
		if (event) {
			event.stopPropagation();
		}
		goto(`/album/${albumId}`);
	}

	function goBack() {
		if (browser && window.history.length > 1) {
			window.history.back();
		} else {
			goto('/');
		}
	}
</script>

<style>
	.scrollbar-hide {
		-ms-overflow-style: none;  
		scrollbar-width: none;  
	}
	.scrollbar-hide::-webkit-scrollbar {
		display: none;  
	}
</style>

<div class="w-full px-2 sm:px-4 lg:px-8 py-4 sm:py-8 max-w-7xl mx-auto">
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
	{:else if loadingBasic && !artist}
		<div class="space-y-4 sm:space-y-8">
			<ArtistHeaderSkeleton />
			<AlbumGridSkeleton title="Albums" count={12} />
		</div>
	{:else if artist}
		<div class="space-y-4 sm:space-y-6 lg:space-y-8">
			
			<div class="relative -mx-2 sm:-mx-4 lg:-mx-8 -mt-4 sm:-mt-8 overflow-hidden">
				<div class="absolute inset-0 bg-gradient-to-b {heroGradient} transition-all duration-1000"></div>
				
				<div class="relative z-10 px-4 sm:px-8 lg:px-12 pt-16 pb-8 sm:pt-20 sm:pb-12">
					<div class="max-w-7xl mx-auto">
						<div class="flex flex-col sm:flex-row items-center sm:items-end gap-6 sm:gap-8">
							<div class="flex-shrink-0">
								<div class="relative">
									<div class="w-40 h-40 sm:w-52 sm:h-52 lg:w-64 lg:h-64 rounded-full overflow-hidden shadow-2xl ring-4 ring-base-100/20" style="background-color: #374151;">
										<!-- Placeholder shown immediately -->
										{#if !heroImageLoaded}
											<div class="absolute inset-0 flex items-center justify-center">
												<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" class="w-full h-full">
													<rect fill="#374151" width="200" height="200"/>
													<circle cx="100" cy="80" r="30" fill="#6B7280"/>
													<path d="M60 120 Q100 140 140 120 L140 160 Q100 180 60 160 Z" fill="#6B7280"/>
												</svg>
											</div>
										{/if}
										<img
											src="/api/covers/artist/{artist.musicbrainz_id}?size=500"
											alt={artist.name}
											class="w-full h-full object-cover transition-opacity duration-300 {heroImageLoaded ? 'opacity-100' : 'opacity-0'}"
											loading="lazy"
											decoding="async"
											on:load={onHeroImageLoad}
											on:error={(e) => {
												const target = e.currentTarget as HTMLImageElement;
												target.style.display = 'none';
											}}
										/>
									</div>
									{#if artist.in_library}
										<div class="absolute -bottom-2 -right-2 badge badge-success badge-lg gap-1 shadow-lg">
											<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
												<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
											</svg>
											In Library
										</div>
									{/if}
								</div>
							</div>
							
							<div class="flex-1 text-center sm:text-left min-w-0">
								{#if artist.type}
									<span class="text-xs sm:text-sm font-medium text-base-content/70 uppercase tracking-wider">
										{artist.type === 'Group' ? 'Band' : artist.type === 'Person' ? 'Artist' : artist.type}
									</span>
								{/if}
								<h1 class="text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-bold text-base-content mt-1 mb-2 break-words">
									{artist.name}
								</h1>
								{#if artist.disambiguation}
									<p class="text-base-content/60 text-sm sm:text-base mb-3">({artist.disambiguation})</p>
								{/if}
								
								<div class="flex flex-wrap justify-center sm:justify-start gap-2 mt-3">
									{#if artist.country}
										<div class="badge badge-lg badge-ghost gap-1">
											<span class="text-sm">🌍</span>
											{artist.country}
										</div>
									{/if}
									{#if artist.life_span?.begin}
										<div class="badge badge-lg badge-ghost gap-1">
											<span class="text-sm">📅</span>
											{artist.life_span.begin}{#if artist.life_span.end} - {artist.life_span.end}{/if}
										</div>
									{/if}
									{#if artist.albums.length + artist.eps.length + artist.singles.length > 0}
										<div class="badge badge-lg badge-ghost gap-1">
											<span class="text-sm">💿</span>
											{artist.albums.length + artist.eps.length + artist.singles.length} releases
										</div>
									{/if}
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>

			{#if artist.tags.length > 0}
				<div class="flex flex-wrap gap-2 justify-center sm:justify-start">
					{#each artist.tags.slice(0, 10) as tag}
						<span class="badge badge-lg" style="background-color: {colors.primary}; color: {colors.secondary};">{tag}</span>
					{/each}
				</div>
			{/if}

			<div class="bg-base-200/50 rounded-box p-4 sm:p-6">
				{#if loadingExtended}
					<div class="space-y-2">
						<div class="skeleton h-4 w-full"></div>
						<div class="skeleton h-4 w-full"></div>
						<div class="skeleton h-4 w-3/4"></div>
					</div>
				{:else if artist.description}
					<div class="text-sm sm:text-base text-base-content/80 leading-relaxed">
						{#if descriptionExpanded}
							<div>
								{@html artist.description.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>')}
							</div>
							<button 
								class="btn btn-sm mt-3 gap-2"
								style="background-color: {colors.accent}; color: {colors.secondary};"
								on:click={() => descriptionExpanded = false}
							>
								Show Less
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
									<path stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7" />
								</svg>
							</button>
						{:else}
							<div 
								bind:this={descriptionElement}
								class="line-clamp-4 overflow-hidden"
								style="display: -webkit-box; -webkit-box-orient: vertical;"
							>
								{@html artist.description.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>')}
							</div>
							{#if showViewMore}
								<button 
									class="btn btn-sm mt-3 gap-2"
									style="background-color: {colors.accent}; color: {colors.secondary};"
									on:click={() => descriptionExpanded = true}
								>
									Read More
									<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
										<path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
									</svg>
								</button>
							{/if}
						{/if}
					</div>
				{:else}
					<p class="text-base-content/50 italic text-sm">No biography available</p>
				{/if}
			</div>

			
			{#if validLinks.length > 0}
				<div>
					<h2 class="text-xl sm:text-2xl font-bold mb-3 sm:mb-4">Links</h2>
					<div class="relative">
						
						<button 
							class="btn btn-circle btn-sm absolute left-0 top-1/2 -translate-y-1/2 z-10 bg-base-300 border-none shadow-lg hidden sm:flex"
							on:click={() => scrollLinks('left')}
							aria-label="Scroll left"
						>
							❮
						</button>
						
						
						<div 
							class="overflow-x-auto scrollbar-hide sm:px-12"
							bind:this={linksCarousel}
						>
							<div class="flex gap-3 sm:gap-4 p-3 sm:p-4 bg-base-200 rounded-box shadow-md w-max">
								{#each validLinks as link}
									<a 
										href={link.url} 
										target="_blank" 
										rel="noopener noreferrer"
										class="card card-compact bg-base-100 hover:bg-base-300 shadow-sm hover:shadow-md transition-all w-32 h-20 sm:w-40 sm:h-24 flex-shrink-0"
									>
										<div class="card-body items-center justify-center text-center p-2">
											<div class="text-xl sm:text-2xl mb-0.5 sm:mb-1">
												{#if link.label === 'Spotify'}
													🎵
												{:else if link.label === 'YouTube'}
													▶️
												{:else if link.label === 'Instagram'}
													📷
												{:else if link.label === 'Twitter'}
													🐦
												{:else if link.label === 'Facebook'}
													👥
												{:else if link.label === 'Bandcamp'}
													🎹
												{:else if link.label === 'SoundCloud'}
													☁️
												{:else if link.label === 'Official Website'}
													🌐
												{:else if link.label === 'Wikipedia'}
													📖
												{:else if link.label === 'Discogs'}
													💿
												{:else if link.label === 'AllMusic'}
													🎼
												{:else if link.label === 'Last.fm'}
													📻
												{:else if link.label === 'Apple Music'}
													🍎
												{:else if link.label === 'Deezer'}
													🎧
												{:else}
													🔗
												{/if}
											</div>
											<h3 class="text-xs sm:text-sm font-semibold line-clamp-2">{link.label}</h3>
										</div>
									</a>
								{/each}
							</div>
						</div>
						
						
						<button 
							class="btn btn-circle btn-sm absolute right-0 top-1/2 -translate-y-1/2 z-10 bg-base-300 border-none shadow-lg hidden sm:flex"
							on:click={() => scrollLinks('right')}
							aria-label="Scroll right"
						>
							❯
						</button>
					</div>
				</div>
			{/if}

			{#if hasMoreReleases || loadingMoreReleases}
				<div class="flex items-center justify-center gap-3 p-4 bg-base-300 rounded-box mb-6" style="border: 2px solid {colors.accent};">
					<span class="loading loading-spinner loading-md" style="color: {colors.accent};"></span>
					<div class="flex flex-col items-start">
						<span class="font-semibold text-base" style="color: {colors.accent};">Loading all releases...</span>
						<span class="text-sm text-base-content/70">Loaded {loadedReleaseCount} of {totalReleaseCount} releases</span>
					</div>
				</div>
			{/if}
			
			{#if artist.albums.length > 0}
				<div>
					<button 
						class="w-full flex items-center justify-between text-xl sm:text-2xl font-bold mb-3 sm:mb-4 hover:opacity-80 transition-opacity"
						on:click={() => albumsCollapsed = !albumsCollapsed}
					>
						<span>Albums ({artist.albums.length})</span>
						<svg 
							xmlns="http://www.w3.org/2000/svg" 
							class="h-6 w-6 transition-transform duration-200 {albumsCollapsed ? '' : 'rotate-180'}" 
							fill="none" 
							viewBox="0 0 24 24" 
							stroke="currentColor"
						>
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
						</svg>
					</button>
					{#if !albumsCollapsed}
						<div class="list bg-base-200 rounded-box shadow-md" role="list">
							{#each artist.albums as rg}
								<div class="list-row group hover:bg-base-300 transition-colors p-0" role="listitem">
									<button
										class="flex items-center gap-2 sm:gap-3 flex-1 p-2 sm:p-3 cursor-pointer text-left min-w-0"
										on:click={() => goToAlbum(rg.id)}
									>
										<AlbumImage
											mbid={rg.id}
											alt="{rg.title} cover"
											size="sm"
											rounded="lg"
											className="w-12 h-12 sm:w-16 sm:h-16"
										/>
										<div class="list-col-grow min-w-0">
											<div class="font-semibold text-sm sm:text-base truncate">{rg.title}</div>
											<div class="text-xs sm:text-sm text-base-content/60">
												{#if rg.year}{rg.year}{/if}
											</div>
										</div>
									</button>
									<div class="flex items-center flex-shrink-0 ml-auto mr-3 sm:mr-4">
										{#if rg.in_library}
											<div class="w-8 h-8 sm:w-10 sm:h-10 rounded-full shadow-sm flex items-center justify-center" style="background-color: {colors.accent};">
												<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="3">
													<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
												</svg>
											</div>
										{:else}
											<button
												class="w-8 h-8 sm:w-10 sm:h-10 rounded-full opacity-100 lg:opacity-0 lg:group-hover:opacity-100 transition-opacity duration-200 border-none flex items-center justify-center shadow-sm"
												style="background-color: {colors.accent};"
												on:click={(e) => { e.stopPropagation(); handleRequest(rg.id, rg.title); }}
												disabled={requestingAlbums.has(rg.id)}
												aria-label="Request album"
											>
												{#if requestingAlbums.has(rg.id)}
													<span class="loading loading-spinner loading-xs" style="color: {colors.secondary};"></span>
												{:else}
													<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="2.5">
														<path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
													</svg>
												{/if}
											</button>
										{/if}
									</div>
								</div>
							{/each}
						</div>
						{#if hasMoreReleases || loadingMoreReleases}
							<div class="flex items-center justify-center gap-2 p-3 mt-2">
								<span class="loading loading-spinner loading-sm" style="color: {colors.accent};"></span>
							</div>
						{/if}
					{/if}
				</div>
			{/if}

			
			{#if artist.eps.length > 0}
				<div>
					<button 
						class="w-full flex items-center justify-between text-xl sm:text-2xl font-bold mb-3 sm:mb-4 hover:opacity-80 transition-opacity"
						on:click={() => epsCollapsed = !epsCollapsed}
					>
						<span>EPs ({artist.eps.length})</span>
						<svg 
							xmlns="http://www.w3.org/2000/svg" 
							class="h-6 w-6 transition-transform duration-200 {epsCollapsed ? '' : 'rotate-180'}" 
							fill="none" 
							viewBox="0 0 24 24" 
							stroke="currentColor"
						>
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
						</svg>
					</button>
					{#if !epsCollapsed}
						<div class="list bg-base-200 rounded-box shadow-md" role="list">
							{#each artist.eps as rg}
								<div class="list-row group hover:bg-base-300 transition-colors p-0" role="listitem">
									<button
										class="flex items-center gap-2 sm:gap-3 flex-1 p-2 sm:p-3 cursor-pointer text-left min-w-0"
										on:click={() => goToAlbum(rg.id)}
									>
										<AlbumImage
											mbid={rg.id}
											alt="{rg.title} cover"
											size="sm"
											rounded="lg"
											className="w-12 h-12 sm:w-16 sm:h-16"
										/>
										<div class="list-col-grow min-w-0">
											<div class="font-semibold text-sm sm:text-base truncate">{rg.title}</div>
											<div class="text-xs sm:text-sm text-base-content/60">
												{#if rg.year}{rg.year}{/if}
											</div>
										</div>
									</button>
									<div class="flex items-center flex-shrink-0 ml-auto mr-3 sm:mr-4">
										{#if rg.in_library}
											<div class="w-8 h-8 sm:w-10 sm:h-10 rounded-full shadow-sm flex items-center justify-center" style="background-color: {colors.accent};">
												<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="3">
													<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
												</svg>
											</div>
										{:else}
											<button
												class="w-8 h-8 sm:w-10 sm:h-10 rounded-full opacity-100 lg:opacity-0 lg:group-hover:opacity-100 transition-opacity duration-200 border-none flex items-center justify-center shadow-sm"
												style="background-color: {colors.accent};"
												on:click={(e) => { e.stopPropagation(); handleRequest(rg.id, rg.title); }}
												disabled={requestingAlbums.has(rg.id)}
												aria-label="Request EP"
											>
												{#if requestingAlbums.has(rg.id)}
													<span class="loading loading-spinner loading-xs" style="color: {colors.secondary};"></span>
												{:else}
													<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="2.5">
														<path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
													</svg>
												{/if}
											</button>
										{/if}
									</div>
								</div>
							{/each}
						</div>
						{#if hasMoreReleases || loadingMoreReleases}
							<div class="flex items-center justify-center gap-2 p-3 mt-2">
								<span class="loading loading-spinner loading-sm" style="color: {colors.accent};"></span>
							</div>
						{/if}
					{/if}
				</div>
			{/if}

			
			{#if artist.singles.length > 0}
				<div>
					<button 
						class="w-full flex items-center justify-between text-xl sm:text-2xl font-bold mb-3 sm:mb-4 hover:opacity-80 transition-opacity"
						on:click={() => singlesCollapsed = !singlesCollapsed}
					>
						<span>Singles ({artist.singles.length})</span>
						<svg 
							xmlns="http://www.w3.org/2000/svg" 
							class="h-6 w-6 transition-transform duration-200 {singlesCollapsed ? '' : 'rotate-180'}" 
							fill="none" 
							viewBox="0 0 24 24" 
							stroke="currentColor"
						>
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
						</svg>
					</button>
					{#if !singlesCollapsed}
						<div class="list bg-base-200 rounded-box shadow-md" role="list">
							{#each artist.singles as rg}
								<div class="list-row group hover:bg-base-300 transition-colors p-0" role="listitem">
									<button
										class="flex items-center gap-2 sm:gap-3 flex-1 p-2 sm:p-3 cursor-pointer text-left min-w-0"
										on:click={() => goToAlbum(rg.id)}
									>
										<AlbumImage
											mbid={rg.id}
											alt="{rg.title} cover"
											size="sm"
											rounded="lg"
											className="w-12 h-12 sm:w-16 sm:h-16"
										/>
										<div class="list-col-grow min-w-0">
											<div class="font-semibold text-sm sm:text-base truncate">{rg.title}</div>
											<div class="text-xs sm:text-sm text-base-content/60">
												{#if rg.year}{rg.year}{/if}
											</div>
										</div>
									</button>
									<div class="flex items-center flex-shrink-0 ml-auto mr-3 sm:mr-4">
										{#if rg.in_library}
											<div class="w-8 h-8 sm:w-10 sm:h-10 rounded-full shadow-sm flex items-center justify-center" style="background-color: {colors.accent};">
												<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="3">
													<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
												</svg>
											</div>
										{:else}
											<button
												class="w-8 h-8 sm:w-10 sm:h-10 rounded-full opacity-100 lg:opacity-0 lg:group-hover:opacity-100 transition-opacity duration-200 border-none flex items-center justify-center shadow-sm"
												style="background-color: {colors.accent};"
												on:click={(e) => { e.stopPropagation(); handleRequest(rg.id, rg.title); }}
												disabled={requestingAlbums.has(rg.id)}
												aria-label="Request single"
											>
												{#if requestingAlbums.has(rg.id)}
													<span class="loading loading-spinner loading-xs" style="color: {colors.secondary};"></span>
												{:else}
													<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="2.5">
														<path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
													</svg>
												{/if}
											</button>
										{/if}
									</div>
								</div>
							{/each}
						</div>
						{#if hasMoreReleases || loadingMoreReleases}
							<div class="flex items-center justify-center gap-2 p-3 mt-2">
								<span class="loading loading-spinner loading-sm" style="color: {colors.accent};"></span>
							</div>
						{/if}
					{/if}
				</div>
			{/if}
		</div>
	{:else}
		<div class="flex items-center justify-center min-h-[50vh]">
			<p class="text-base-content/60">Artist not found</p>
		</div>
	{/if}
</div>


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
