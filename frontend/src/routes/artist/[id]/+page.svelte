<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { invalidate } from '$app/navigation';
	import { goto } from '$app/navigation';
	import type { ArtistInfo } from '$lib/types';
	import { colors } from '$lib/colors';
	import { errorModal } from '$lib/stores/errorModal';

	export let data: { artistId: string };

	let artist: ArtistInfo | null = null;
	let loading = true;
	let error: string | null = null;
	let showToast = false;
	let linksCarousel: HTMLDivElement;
	let requestingAlbums = new Set<string>();
	let descriptionExpanded = false;
	let abortController: AbortController | null = null;
	let descriptionElement: HTMLElement;
	let showViewMore = false;
	let loadedImages = new Set<string>();
	let lastFetchTime = 0;

	function checkDescriptionHeight() {
		if (descriptionElement && !descriptionExpanded) {
			const lineHeight = parseFloat(getComputedStyle(descriptionElement).lineHeight);
			const actualHeight = descriptionElement.scrollHeight;
			const elevenLines = lineHeight * 11;
			showViewMore = actualHeight > elevenLines;
		}
	}
	
	function handleImageLoad(id: string) {
		loadedImages.add(id);
		loadedImages = loadedImages;
	}
	
	$: validLinks = artist?.external_links.filter(link => link.url && link.url.trim() !== '') || [];

	async function fetchArtist(force = false) {
		
		const now = Date.now();
		if (!force && now - lastFetchTime < 1000) {
			return;
		}
		lastFetchTime = now;

		loading = true;
		error = null;
		
		if (abortController) {
			abortController.abort();
		}
		abortController = new AbortController();
		
		try {
			
			const cacheBuster = force ? `?t=${now}` : '';
			const res = await fetch(`/api/artist/${data.artistId}${cacheBuster}`, {
				signal: abortController.signal,
				
				cache: force ? 'no-cache' : 'default'
			});
			if (res.ok) {
				artist = await res.json();
				setTimeout(() => checkDescriptionHeight(), 50);
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
			loading = false;
		}
	}

	onMount(() => {
		fetchArtist();

		
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
						'Go to Lidarr → Settings → Profiles → Metadata Profiles, and enable the appropriate release types in your active profile. After enabling, refresh the artist in Lidarr.'
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
	{#if error}
		<div class="flex items-center justify-center min-h-[50vh]">
			<div class="alert alert-error">
				<span>{error}</span>
			</div>
		</div>
	{:else if !artist && loading}
		
		<div class="space-y-4 sm:space-y-8">
			
			<div class="card bg-base-200 shadow-xl overflow-hidden">
				<div class="flex flex-col lg:flex-row">
					<div class="w-full lg:w-96 xl:w-[28rem] flex-shrink-0 p-4 sm:p-6">
						<div class="skeleton w-full aspect-square max-h-96 lg:h-96 rounded-box"></div>
					</div>
					<div class="card-body flex-1 p-4 sm:p-6 lg:p-8">
						<div class="flex flex-col sm:flex-row items-start justify-between gap-4">
							<div class="flex-1 space-y-3 w-full">
								<div class="skeleton h-8 sm:h-12 w-3/4"></div>
								<div class="skeleton h-4 w-1/4"></div>
							</div>
							<div class="skeleton h-8 w-32 flex-shrink-0"></div>
						</div>
					
					<div class="mt-4 sm:mt-6 space-y-2">
						<div class="skeleton h-4 w-20"></div>
						<div class="skeleton h-4 w-full"></div>
						<div class="skeleton h-4 w-full"></div>
						<div class="skeleton h-4 w-3/4"></div>
					</div>
					
					<div class="flex flex-wrap gap-2 mt-auto">
						<div class="skeleton h-6 w-16"></div>
						<div class="skeleton h-6 w-20"></div>
						<div class="skeleton h-6 w-24"></div>
						<div class="skeleton h-6 w-16"></div>
					</div>
				</div>
			</div>
		</div>

			
			<div>
				<div class="skeleton h-6 sm:h-8 w-20 sm:w-24 mb-3 sm:mb-4"></div>
				<div class="bg-base-200 rounded-box p-3 sm:p-4 shadow-md overflow-x-auto">
					<div class="flex gap-3 sm:gap-4">
						{#each Array(5) as _}
							<div class="skeleton w-32 sm:w-40 h-20 sm:h-24 flex-shrink-0 rounded-box"></div>
						{/each}
					</div>
				</div>
			</div>

			
			<div>
				<div class="skeleton h-6 sm:h-8 w-24 sm:w-32 mb-3 sm:mb-4"></div>
				<div class="bg-base-200 rounded-box shadow-md p-3 sm:p-4 space-y-3 sm:space-y-4">
					{#each Array(5) as _}
						<div class="flex items-center gap-3 sm:gap-4">
							<div class="skeleton w-12 h-12 sm:w-16 sm:h-16 rounded-box flex-shrink-0"></div>
							<div class="flex-1 space-y-2 min-w-0">
								<div class="skeleton h-4 sm:h-5 w-3/4 max-w-48"></div>
								<div class="skeleton h-3 sm:h-4 w-16 sm:w-20"></div>
							</div>
							<div class="skeleton w-10 h-10 sm:w-12 sm:h-12 rounded-full flex-shrink-0"></div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	{:else if error}
		<div class="flex items-center justify-center min-h-[50vh]">
			<div class="alert alert-error">
				<span>{error}</span>
			</div>
		</div>
	{:else if artist}
		<div class="space-y-4 sm:space-y-6 lg:space-y-8">
			
			<div class="card bg-base-200 shadow-xl overflow-hidden">
				
				<div class="flex flex-col lg:flex-row lg:min-h-[32rem]">
				<figure class="w-full lg:w-96 lg:h-96 xl:w-[28rem] xl:h-[28rem] flex-shrink-0 p-4 sm:p-6">
					<img 
						src="/api/covers/artist/{artist.musicbrainz_id}" 
						alt={artist.name}
						class="w-full h-full object-contain rounded-box max-h-80 sm:max-h-96 lg:max-h-none"
						on:error={(e) => {
							const target = e.currentTarget as HTMLImageElement;
							target.src = 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 200%22%3E%3Crect fill=%22%23444%22 width=%22200%22 height=%22200%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 fill=%22%23999%22 font-size=%2224%22 font-family=%22sans-serif%22%3ENo Image%3C/text%3E%3C/svg%3E';
						}}
					/>
				</figure>
					<div class="card-body flex-1 p-4 sm:p-6 lg:p-8">
						<div class="flex flex-col sm:flex-row items-start justify-between gap-3 sm:gap-4">
							<div class="flex-1 min-w-0">
								<h1 class="card-title text-2xl sm:text-3xl lg:text-4xl xl:text-5xl font-bold mb-2 sm:mb-3 break-words">{artist.name}</h1>
								{#if artist.disambiguation}
									<p class="text-base-content/60 text-xs sm:text-sm mb-2 sm:mb-3">({artist.disambiguation})</p>
								{/if}
							</div>
						{#if artist.in_library}
							<span class="badge badge-success badge-lg gap-2 flex-shrink-0">
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
									<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
								</svg>
								In Library
							</span>
							{:else}
								<span class="badge badge-ghost badge-lg flex-shrink-0">Not in Library</span>
							{/if}
						</div>
					
					{#if artist.description}
						<div class="mb-4 sm:mb-6">
							<h3 class="text-xs sm:text-sm font-semibold text-base-content/60 uppercase tracking-wide mb-2">Description</h3>
							<div class="text-sm sm:text-base text-base-content/80 leading-relaxed">
								{#if descriptionExpanded}
									<div>
										{@html artist.description.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>')}
									</div>
									<button 
										class="btn btn-xs sm:btn-sm mt-2 gap-1 sm:gap-2"
										style="background-color: {colors.accent}; color: {colors.secondary};"
										on:click={() => descriptionExpanded = false}
									>
										Show Less
										<svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 sm:h-4 sm:w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
											<path stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7" />
										</svg>
									</button>
								{:else}
									<div 
										bind:this={descriptionElement}
										class="line-clamp-[11] overflow-hidden"
										style="display: -webkit-box; -webkit-box-orient: vertical;"
									>
										{@html artist.description.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>')}
									</div>
									{#if showViewMore}
										<button 
											class="btn btn-xs sm:btn-sm mt-2 gap-1 sm:gap-2"
											style="background-color: {colors.accent}; color: {colors.secondary};"
											on:click={() => {
												descriptionExpanded = true;
											}}
										>
											Expand
											<svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 sm:h-4 sm:w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
												<path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
											</svg>
										</button>
									{/if}
								{/if}
							</div>
						</div>
					{:else}
						<p class="text-base-content/60 italic mb-4 sm:mb-6 text-sm sm:text-base">No description available</p>
					{/if}
					
					<div class="card-actions flex-wrap gap-2 mt-auto">
						{#if artist.type && artist.type !== 'Group' && artist.type !== 'Person'}
							<div class="badge badge-neutral">{artist.type}</div>
						{/if}
						{#if artist.country}
							<div class="badge badge-neutral">{artist.country}</div>
						{/if}
						{#if artist.life_span?.begin}
							<div class="badge badge-neutral">
								{artist.life_span.begin}
								{#if artist.life_span.end} - {artist.life_span.end}{/if}
							</div>
						{/if}
						{#each artist.tags.slice(0, 8) as tag}
							<div class="badge" style="background-color: {colors.primary}; color: {colors.secondary};">{tag}</div>
						{/each}
					</div>
				</div>
			</div>
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

			
			{#if artist.albums.length > 0}
				<div>
					<h2 class="text-xl sm:text-2xl font-bold mb-3 sm:mb-4">Albums ({artist.albums.length})</h2>
					<ul class="list bg-base-200 rounded-box shadow-md">
						{#each artist.albums as rg}
							<li 
								class="list-row group hover:bg-base-300 transition-colors p-2 sm:p-3 cursor-pointer"
								on:click={() => goToAlbum(rg.id)}
								on:keypress={(e) => e.key === 'Enter' && goToAlbum(rg.id)}
								role="button"
								tabindex="0"
							>
								<div class="w-12 h-12 sm:w-16 sm:h-16 flex-shrink-0 rounded-box overflow-hidden bg-base-100 relative">
									{#if !loadedImages.has(rg.id)}
										<div class="skeleton w-full h-full absolute inset-0"></div>
									{/if}
									<img 
										src="/api/covers/release-group/{rg.id}?size=250" 
										alt="{rg.title} cover"
										class="w-full h-full object-cover"
										loading="lazy"
										decoding="async"
										on:load={() => handleImageLoad(rg.id)}
										on:error={(e) => {
											handleImageLoad(rg.id);
											const target = e.currentTarget as HTMLImageElement;
											target.style.display = 'none';
											const parent = target.parentElement;
											if (parent) {
												const skeleton = parent.querySelector('.skeleton');
												if (skeleton) skeleton.remove();
												parent.innerHTML += '<div class="w-full h-full flex items-center justify-center text-2xl">💿</div>';
											}
										}}
									/>
								</div>
								<div class="list-col-grow min-w-0">
									<div class="font-semibold text-sm sm:text-base truncate">{rg.title}</div>
									<div class="text-xs sm:text-sm text-base-content/60">
										{#if rg.year}{rg.year}{/if}
									</div>
								</div>
								
							{#if rg.in_library}
								<div class="rounded-full p-1.5 sm:p-2 shadow-sm flex-shrink-0" style="background-color: {colors.accent};">
									<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="3">
										<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
									</svg>
								</div>
								{:else}
									<button
										class="btn btn-square btn-sm sm:btn-md opacity-100 lg:opacity-0 lg:group-hover:opacity-100 transition-opacity duration-200 border-none flex-shrink-0"
										style="background-color: {colors.accent};"
										on:click={(e) => { e.stopPropagation(); handleRequest(rg.id, rg.title); }}
										disabled={requestingAlbums.has(rg.id)}
										aria-label="Request album"
									>
									{#if requestingAlbums.has(rg.id)}
										<span class="loading loading-spinner loading-xs sm:loading-sm" style="color: {colors.secondary};"></span>
									{:else}
										<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="2.5">
											<path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
										</svg>
									{/if}
									</button>
								{/if}
							</li>
						{/each}
					</ul>
				</div>
			{/if}

			
			{#if artist.eps.length > 0}
				<div>
					<h2 class="text-xl sm:text-2xl font-bold mb-3 sm:mb-4">EPs ({artist.eps.length})</h2>
					<ul class="list bg-base-200 rounded-box shadow-md">
						{#each artist.eps as rg}
							<li 
								class="list-row group hover:bg-base-300 transition-colors p-2 sm:p-3 cursor-pointer"
								on:click={() => goToAlbum(rg.id)}
								on:keypress={(e) => e.key === 'Enter' && goToAlbum(rg.id)}
								role="button"
								tabindex="0"
							>
								<div class="w-12 h-12 sm:w-16 sm:h-16 flex-shrink-0 rounded-box overflow-hidden bg-base-100 relative">
									{#if !loadedImages.has(rg.id)}
										<div class="skeleton w-full h-full absolute inset-0"></div>
									{/if}
									<img 
										src="/api/covers/release-group/{rg.id}?size=250" 
										alt="{rg.title} cover"
										class="w-full h-full object-cover"
										loading="lazy"
										decoding="async"
										on:load={() => handleImageLoad(rg.id)}
										on:error={(e) => {
											handleImageLoad(rg.id);
											const target = e.currentTarget as HTMLImageElement;
											target.style.display = 'none';
											const parent = target.parentElement;
											if (parent) {
												const skeleton = parent.querySelector('.skeleton');
												if (skeleton) skeleton.remove();
												parent.innerHTML += '<div class="w-full h-full flex items-center justify-center text-2xl">💽</div>';
											}
										}}
									/>
								</div>
								<div class="list-col-grow min-w-0">
									<div class="font-semibold text-sm sm:text-base truncate">{rg.title}</div>
									<div class="text-xs sm:text-sm text-base-content/60">
										{#if rg.year}{rg.year}{/if}
									</div>
								</div>
								
							{#if rg.in_library}
								<div class="rounded-full p-1.5 sm:p-2 shadow-sm flex-shrink-0" style="background-color: {colors.accent};">
									<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="3">
										<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
									</svg>
								</div>
								{:else}
									<button
										class="btn btn-square btn-sm sm:btn-md opacity-100 lg:opacity-0 lg:group-hover:opacity-100 transition-opacity duration-200 border-none flex-shrink-0"
										style="background-color: {colors.accent};"
										on:click={(e) => { e.stopPropagation(); handleRequest(rg.id, rg.title); }}
										disabled={requestingAlbums.has(rg.id)}
										aria-label="Request EP"
									>
									{#if requestingAlbums.has(rg.id)}
										<span class="loading loading-spinner loading-xs sm:loading-sm" style="color: {colors.secondary};"></span>
									{:else}
										<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="2.5">
											<path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
										</svg>
									{/if}
									</button>
								{/if}
							</li>
						{/each}
					</ul>
				</div>
			{/if}

			
			{#if artist.singles.length > 0}
				<div>
					<h2 class="text-xl sm:text-2xl font-bold mb-3 sm:mb-4">Singles ({artist.singles.length})</h2>
					<ul class="list bg-base-200 rounded-box shadow-md">
						{#each artist.singles as rg}
							<li 
								class="list-row group hover:bg-base-300 transition-colors p-2 sm:p-3 cursor-pointer"
								on:click={() => goToAlbum(rg.id)}
								on:keypress={(e) => e.key === 'Enter' && goToAlbum(rg.id)}
								role="button"
								tabindex="0"
							>
								<div class="w-12 h-12 sm:w-16 sm:h-16 flex-shrink-0 rounded-box overflow-hidden bg-base-100 relative">
									{#if !loadedImages.has(rg.id)}
										<div class="skeleton w-full h-full absolute inset-0"></div>
									{/if}
									<img 
										src="/api/covers/release-group/{rg.id}?size=250" 
										alt="{rg.title} cover"
										class="w-full h-full object-cover"
										loading="lazy"
										decoding="async"
										on:load={() => handleImageLoad(rg.id)}
										on:error={(e) => {
											handleImageLoad(rg.id);
											const target = e.currentTarget as HTMLImageElement;
											target.style.display = 'none';
											const parent = target.parentElement;
											if (parent) {
												const skeleton = parent.querySelector('.skeleton');
												if (skeleton) skeleton.remove();
												parent.innerHTML += '<div class="w-full h-full flex items-center justify-center text-2xl">🎵</div>';
											}
										}}
									/>
								</div>
								<div class="list-col-grow min-w-0">
									<div class="font-semibold text-sm sm:text-base truncate">{rg.title}</div>
									<div class="text-xs sm:text-sm text-base-content/60">
										{#if rg.year}{rg.year}{/if}
									</div>
								</div>
								
							{#if rg.in_library}
								<div class="rounded-full p-1.5 sm:p-2 shadow-sm flex-shrink-0" style="background-color: {colors.accent};">
									<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="3">
										<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
									</svg>
								</div>
								{:else}
									<button
										class="btn btn-square btn-sm sm:btn-md opacity-100 lg:opacity-0 lg:group-hover:opacity-100 transition-opacity duration-200 border-none flex-shrink-0"
										style="background-color: {colors.accent};"
										on:click={(e) => { e.stopPropagation(); handleRequest(rg.id, rg.title); }}
										disabled={requestingAlbums.has(rg.id)}
										aria-label="Request single"
									>
									{#if requestingAlbums.has(rg.id)}
										<span class="loading loading-spinner loading-xs sm:loading-sm" style="color: {colors.secondary};"></span>
									{:else}
										<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 sm:h-5 sm:w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="2.5">
											<path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
										</svg>
									{/if}
									</button>
								{/if}
							</li>
						{/each}
					</ul>
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
