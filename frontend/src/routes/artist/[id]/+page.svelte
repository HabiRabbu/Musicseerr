<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
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

	onMount(async () => {
		abortController = new AbortController();
		
		try {
			const res = await fetch(`/api/artist/${data.artistId}`, {
				signal: abortController.signal
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
			const scrollAmount = 400; // Scroll ~2.5 cards at a time
			const newPosition = linksCarousel.scrollLeft + (direction === 'right' ? scrollAmount : -scrollAmount);
			linksCarousel.scrollTo({
				left: newPosition,
				behavior: 'smooth'
			});
		}
	}
</script>

<style>
	.scrollbar-hide {
		-ms-overflow-style: none;  /* IE and Edge */
		scrollbar-width: none;  /* Firefox */
	}
	.scrollbar-hide::-webkit-scrollbar {
		display: none;  /* Chrome, Safari and Opera */
	}
</style>

<div class="px-4 sm:px-8 py-8 max-w-7xl mx-auto">
	{#if error}
		<div class="flex items-center justify-center min-h-[50vh]">
			<div class="alert alert-error">
				<span>{error}</span>
			</div>
		</div>
	{:else if !artist && loading}
		<!-- Skeleton Loading State -->
		<div class="space-y-8">
			<!-- Artist Hero Skeleton -->
			<div class="card card-side bg-base-200 shadow-xl overflow-hidden min-h-[32rem]">
				<div class="w-96 h-96 sm:w-[28rem] sm:h-[28rem] flex-shrink-0 p-6">
					<div class="skeleton w-full h-full rounded-box"></div>
				</div>
				<div class="card-body flex-1 p-8">
					<div class="flex items-start justify-between gap-4">
						<div class="flex-1 space-y-3">
							<div class="skeleton h-12 w-3/4"></div>
							<div class="skeleton h-4 w-1/4"></div>
						</div>
						<div class="skeleton h-8 w-32"></div>
					</div>
					
					<div class="mt-6 space-y-2">
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

			<!-- Links Skeleton -->
			<div class="px-4 sm:px-8">
				<div class="skeleton h-8 w-24 mb-4"></div>
				<div class="bg-base-200 rounded-box p-4 shadow-md">
					<div class="flex gap-4">
						{#each Array(5) as _}
							<div class="skeleton w-40 h-24 flex-shrink-0 rounded-box"></div>
						{/each}
					</div>
				</div>
			</div>

			<!-- Albums Skeleton -->
			<div class="px-4 sm:px-8">
				<div class="skeleton h-8 w-32 mb-4"></div>
				<div class="bg-base-200 rounded-box shadow-md p-4 space-y-4">
					{#each Array(5) as _}
						<div class="flex items-center gap-4">
							<div class="skeleton w-16 h-16 rounded-box flex-shrink-0"></div>
							<div class="flex-1 space-y-2">
								<div class="skeleton h-5 w-48"></div>
								<div class="skeleton h-4 w-20"></div>
							</div>
							<div class="skeleton w-12 h-12 rounded-full"></div>
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
		<div class="space-y-8">
			<!-- Artist Hero Section -->
			<div class="card card-side bg-base-200 shadow-xl overflow-hidden min-h-[32rem]">
				<figure class="w-96 h-96 sm:w-[28rem] sm:h-[28rem] flex-shrink-0 p-6">
					<img 
						src="/api/covers/artist/{artist.musicbrainz_id}" 
						alt={artist.name}
						class="w-full h-full object-contain rounded-box"
						on:error={(e) => {
							const target = e.currentTarget as HTMLImageElement;
							target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"%3E%3Crect fill="%23444" width="200" height="200"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" fill="%23999" font-size="24" font-family="sans-serif"%3ENo Image%3C/text%3E%3C/svg%3E';
						}}
					/>
				</figure>
				<div class="card-body flex-1 p-8">
					<div class="flex items-start justify-between gap-4">
						<div class="flex-1">
							<h1 class="card-title text-3xl sm:text-5xl font-bold mb-3">{artist.name}</h1>
							{#if artist.disambiguation}
								<p class="text-base-content/60 text-sm mb-3">({artist.disambiguation})</p>
							{/if}
						</div>
						{#if artist.in_library}
							<span class="badge badge-success badge-lg gap-2">
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
									<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
								</svg>
								In Library
							</span>
						{:else}
							<span class="badge badge-ghost badge-lg">Not in Library</span>
						{/if}
					</div>
					
					{#if artist.description}
						<div class="mb-6">
							<h3 class="text-sm font-semibold text-base-content/60 uppercase tracking-wide mb-2">Description</h3>
							<div class="text-base-content/80 leading-relaxed">
								{#if descriptionExpanded}
									<div>
										{@html artist.description.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>')}
									</div>
									<button 
										class="btn btn-ghost btn-sm mt-2"
										on:click={() => descriptionExpanded = false}
									>
										Show less
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
											class="btn btn-ghost btn-sm mt-2"
											on:click={() => {
												descriptionExpanded = true;
											}}
										>
											View more
										</button>
									{/if}
								{/if}
							</div>
						</div>
					{:else}
						<p class="text-base-content/60 italic mb-6">No description available</p>
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
							<div class="badge badge-primary">{tag}</div>
						{/each}
					</div>
				</div>
			</div>

			<!-- External Links Section -->
			{#if validLinks.length > 0}
				<div class="px-4 sm:px-8">
					<h2 class="text-2xl font-bold mb-4">Links</h2>
					<div class="relative">
						<!-- Left Button -->
						<button 
							class="btn btn-circle btn-sm absolute left-0 top-1/2 -translate-y-1/2 z-10 bg-base-300 border-none shadow-lg"
							on:click={() => scrollLinks('left')}
							aria-label="Scroll left"
						>
							❮
						</button>
						
						<!-- Links Container -->
						<div 
							class="overflow-x-auto scrollbar-hide px-12"
							bind:this={linksCarousel}
						>
							<div class="flex gap-4 p-4 bg-base-200 rounded-box shadow-md w-max">
								{#each validLinks as link}
									<a 
										href={link.url} 
										target="_blank" 
										rel="noopener noreferrer"
										class="card card-compact bg-base-100 hover:bg-base-300 shadow-sm hover:shadow-md transition-all w-40 h-24 flex-shrink-0"
									>
										<div class="card-body items-center justify-center text-center">
											<div class="text-2xl mb-1">
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
											<h3 class="text-sm font-semibold line-clamp-2">{link.label}</h3>
										</div>
									</a>
								{/each}
							</div>
						</div>
						
						<!-- Right Button -->
						<button 
							class="btn btn-circle btn-sm absolute right-0 top-1/2 -translate-y-1/2 z-10 bg-base-300 border-none shadow-lg"
							on:click={() => scrollLinks('right')}
							aria-label="Scroll right"
						>
							❯
						</button>
					</div>
				</div>
			{/if}

			<!-- Albums Section -->
			{#if artist.albums.length > 0}
				<div class="px-4 sm:px-8">
					<h2 class="text-2xl font-bold mb-4">Albums ({artist.albums.length})</h2>
					<ul class="list bg-base-200 rounded-box shadow-md">
						{#each artist.albums as rg}
							<li class="list-row group hover:bg-base-300 transition-colors">
								<div class="w-16 h-16 flex-shrink-0 rounded-box overflow-hidden bg-base-100 relative">
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
								<div class="list-col-grow">
									<div class="font-semibold">{rg.title}</div>
									<div class="text-sm text-base-content/60">
										{#if rg.year}{rg.year}{/if}
									</div>
								</div>
								
								{#if rg.in_library}
									<div class="rounded-full p-2 shadow-sm" style="background-color: {colors.accent};">
										<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="3">
											<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
										</svg>
									</div>
								{:else}
									<button
										class="btn btn-square btn-md opacity-0 group-hover:opacity-100 transition-opacity duration-200 border-none"
										style="background-color: {colors.accent};"
										on:click={() => handleRequest(rg.id, rg.title)}
										disabled={requestingAlbums.has(rg.id)}
										aria-label="Request album"
									>
										{#if requestingAlbums.has(rg.id)}
											<span class="loading loading-spinner loading-sm" style="color: {colors.secondary};"></span>
										{:else}
											<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="2.5">
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

			<!-- EPs Section -->
			{#if artist.eps.length > 0}
				<div class="px-4 sm:px-8">
					<h2 class="text-2xl font-bold mb-4">EPs ({artist.eps.length})</h2>
					<ul class="list bg-base-200 rounded-box shadow-md">
						{#each artist.eps as rg}
							<li class="list-row group hover:bg-base-300 transition-colors">
								<div class="w-16 h-16 flex-shrink-0 rounded-box overflow-hidden bg-base-100 relative">
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
								<div class="list-col-grow">
									<div class="font-semibold">{rg.title}</div>
									<div class="text-sm text-base-content/60">
										{#if rg.year}{rg.year}{/if}
									</div>
								</div>
								
								{#if rg.in_library}
									<div class="rounded-full p-2 shadow-sm" style="background-color: {colors.accent};">
										<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="3">
											<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
										</svg>
									</div>
								{:else}
									<button
										class="btn btn-square btn-md opacity-0 group-hover:opacity-100 transition-opacity duration-200 border-none"
										style="background-color: {colors.accent};"
										on:click={() => handleRequest(rg.id, rg.title)}
										disabled={requestingAlbums.has(rg.id)}
										aria-label="Request EP"
									>
										{#if requestingAlbums.has(rg.id)}
											<span class="loading loading-spinner loading-sm" style="color: {colors.secondary};"></span>
										{:else}
											<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="2.5">
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

			<!-- Singles Section -->
			{#if artist.singles.length > 0}
				<div class="px-4 sm:px-8">
					<h2 class="text-2xl font-bold mb-4">Singles ({artist.singles.length})</h2>
					<ul class="list bg-base-200 rounded-box shadow-md">
						{#each artist.singles as rg}
							<li class="list-row group hover:bg-base-300 transition-colors">
								<div class="w-16 h-16 flex-shrink-0 rounded-box overflow-hidden bg-base-100 relative">
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
								<div class="list-col-grow">
									<div class="font-semibold">{rg.title}</div>
									<div class="text-sm text-base-content/60">
										{#if rg.year}{rg.year}{/if}
									</div>
								</div>
								
								{#if rg.in_library}
									<div class="rounded-full p-2 shadow-sm" style="background-color: {colors.accent};">
										<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="3">
											<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
										</svg>
									</div>
								{:else}
									<button
										class="btn btn-square btn-md opacity-0 group-hover:opacity-100 transition-opacity duration-200 border-none"
										style="background-color: {colors.accent};"
										on:click={() => handleRequest(rg.id, rg.title)}
										disabled={requestingAlbums.has(rg.id)}
										aria-label="Request single"
									>
										{#if requestingAlbums.has(rg.id)}
											<span class="loading loading-spinner loading-sm" style="color: {colors.secondary};"></span>
										{:else}
											<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="2.5">
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
