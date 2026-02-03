<script lang="ts">
	import type { HomeSection, HomeArtist, HomeAlbum, HomeTrack, HomeGenre } from '$lib/types';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { formatListenCount, formatListenedAt } from '$lib/utils/formatting';
	import ArtistImage from './ArtistImage.svelte';
	import AlbumImage from './AlbumImage.svelte';

	export let section: HomeSection;
	export let showConnectCard = true;
	export let headerLink: string | null = null;

	let scrollContainer: HTMLDivElement;
	let showLeftArrow = false;
	let showRightArrow = true;

	function updateArrowVisibility() {
		if (!scrollContainer) return;
		const { scrollLeft, scrollWidth, clientWidth } = scrollContainer;
		showLeftArrow = scrollLeft > 10;
		showRightArrow = scrollLeft < scrollWidth - clientWidth - 10;
	}

	function scrollLeft() {
		if (!scrollContainer) return;
		const scrollAmount = scrollContainer.clientWidth * 0.8;
		scrollContainer.scrollBy({ left: -scrollAmount, behavior: 'smooth' });
	}

	function scrollRight() {
		if (!scrollContainer) return;
		const scrollAmount = scrollContainer.clientWidth * 0.8;
		scrollContainer.scrollBy({ left: scrollAmount, behavior: 'smooth' });
	}

	$: if (browser && scrollContainer) {
		updateArrowVisibility();
	}

	function handleArtistClick(artist: HomeArtist) {
		if (artist.mbid) {
			goto(`/artist/${artist.mbid}`);
		}
	}

	function handleAlbumClick(album: HomeAlbum) {
		if (album.mbid) {
			goto(`/album/${album.mbid}`);
		}
	}

	function handleTrackClick(track: HomeTrack) {
		if (track.artist_mbid) {
			goto(`/artist/${track.artist_mbid}`);
		}
	}

	function handleGenreClick(genre: HomeGenre) {
		goto(`/genre?name=${encodeURIComponent(genre.name)}`);
	}

	function isArtist(item: HomeArtist | HomeAlbum | HomeTrack | HomeGenre): item is HomeArtist {
		return section.type === 'artists';
	}

	function isAlbum(item: HomeArtist | HomeAlbum | HomeTrack | HomeGenre): item is HomeAlbum {
		return section.type === 'albums';
	}

	function isTrack(item: HomeArtist | HomeAlbum | HomeTrack | HomeGenre): item is HomeTrack {
		return section.type === 'tracks';
	}

	function isGenre(item: HomeArtist | HomeAlbum | HomeTrack | HomeGenre): item is HomeGenre {
		return section.type === 'genres';
	}
</script>

<section class="mb-6 sm:mb-8">
	<div class="flex items-center justify-between mb-3 sm:mb-4">
		{#if headerLink}
			<a href={headerLink} class="text-lg sm:text-xl font-bold hover:text-primary transition-colors flex items-center gap-2 group">
				{section.title}
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity">
					<path fill-rule="evenodd" d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z" clip-rule="evenodd" />
				</svg>
			</a>
		{:else}
			<h2 class="text-lg sm:text-xl font-bold">{section.title}</h2>
		{/if}
		{#if section.source}
			<span class="badge badge-ghost badge-xs sm:badge-sm capitalize">{section.source}</span>
		{/if}
	</div>

	{#if section.items.length === 0 && section.fallback_message && showConnectCard}
		<div class="card bg-base-200 border border-dashed border-base-300">
			<div class="card-body items-center text-center py-6 sm:py-8">
				<div class="text-3xl sm:text-4xl mb-2">
					{#if section.connect_service === 'listenbrainz'}
						🎵
					{:else if section.connect_service === 'jellyfin'}
						📺
					{:else}
						✨
					{/if}
				</div>
				<p class="text-base-content/70 text-sm">{section.fallback_message}</p>
				{#if section.connect_service}
					<a href="/settings" class="btn btn-primary btn-sm mt-2">
						Connect {section.connect_service === 'listenbrainz' ? 'ListenBrainz' : 'Jellyfin'}
					</a>
				{/if}
			</div>
		</div>
	{:else if section.type === 'genres'}
		<div class="flex flex-wrap gap-2">
			{#each section.items as item, idx}
				{#if isGenre(item)}
					<button
						class="btn btn-sm btn-outline"
						on:click={() => handleGenreClick(item)}
					>
						{item.name}
						{#if item.listen_count}
							<span class="badge badge-ghost badge-xs ml-1">{formatListenCount(item.listen_count)}</span>
						{/if}
					</button>
				{/if}
			{/each}
		</div>
	{:else}
		<div class="relative group">
			{#if showLeftArrow}
				<button
					class="absolute left-0 top-1/2 -translate-y-1/2 z-10 btn btn-circle btn-sm bg-base-100/90 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity hidden sm:flex"
					on:click={scrollLeft}
					aria-label="Scroll left"
				>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
						<path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd" />
					</svg>
				</button>
			{/if}

			<div 
				bind:this={scrollContainer}
				on:scroll={updateArrowVisibility}
				class="flex gap-3 sm:gap-4 overflow-x-auto pb-2 -mx-4 px-4 sm:mx-0 sm:px-0 scrollbar-hide"
			>
			{#each section.items as item, idx}
				{#if isArtist(item)}
					<div class="w-32 sm:w-36 md:w-44 flex-shrink-0">
						<div 
							class="card bg-base-100 w-full shadow-sm transition-transform {item.mbid ? 'cursor-pointer hover:scale-105 active:scale-95 hover:shadow-lg' : 'cursor-default opacity-80'}"
							on:click={() => handleArtistClick(item)}
							on:keydown={(e) => e.key === 'Enter' && handleArtistClick(item)}
							role={item.mbid ? "button" : "presentation"}
							tabindex={item.mbid ? 0 : -1}
						>
							<figure class="flex justify-center pt-4 relative">
								<ArtistImage mbid={item.mbid ?? ''} alt={item.name} size="md" lazy={true} />
								{#if !item.mbid}
									<div class="absolute top-2 left-2 badge badge-ghost badge-sm" title="Not linked to MusicBrainz">
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-3 h-3">
											<path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
										</svg>
									</div>
								{/if}
								{#if item.in_library}
									<div class="absolute top-2 right-2 badge badge-success badge-sm">
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-3 h-3">
											<path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" />
										</svg>
									</div>
								{/if}
							</figure>
							<div class="card-body p-2 items-center text-center">
								<h3 class="card-title text-xs line-clamp-1">{item.name}</h3>
								{#if item.listen_count}
									<p class="text-xs text-base-content/50">{formatListenCount(item.listen_count)}</p>
								{/if}
							</div>
						</div>
					</div>
				{:else if isAlbum(item)}
					<div class="w-32 sm:w-36 md:w-44 flex-shrink-0">
						<div 
							class="card bg-base-100 w-full shadow-sm cursor-pointer transition-transform hover:scale-105 active:scale-95 hover:shadow-lg"
							on:click={() => handleAlbumClick(item)}
							on:keydown={(e) => e.key === 'Enter' && handleAlbumClick(item)}
							role="button"
							tabindex="0"
						>
							<figure class="aspect-square overflow-hidden relative">
								<AlbumImage mbid={item.mbid || ''} alt={item.name} size="md" rounded="none" className="w-full h-full" customUrl={item.image_url || null} />
								{#if item.in_library}
									<div class="absolute top-2 right-2 badge badge-success badge-sm">
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-3 h-3">
											<path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd" />
										</svg>
									</div>
								{/if}
							</figure>
							<div class="card-body p-2">
								<h3 class="card-title text-xs line-clamp-1">{item.name}</h3>
								{#if item.artist_name}
									<p class="text-xs text-base-content/50 line-clamp-1">{item.artist_name}</p>
								{/if}
							</div>
						</div>
					</div>
				{:else if isTrack(item)}
					<div class="w-56 sm:w-64 md:w-72 flex-shrink-0">
						<div 
							class="card card-side bg-base-100 w-full shadow-sm cursor-pointer hover:shadow-lg active:scale-95 transition-all"
							on:click={() => handleTrackClick(item)}
							on:keydown={(e) => e.key === 'Enter' && handleTrackClick(item)}
							role="button"
							tabindex="0"
						>
							<figure class="w-16 h-16 flex-shrink-0">
								<div class="w-full h-full flex items-center justify-center text-2xl bg-base-200">
									🎵
								</div>
							</figure>
							<div class="card-body p-2 justify-center">
								<h3 class="card-title text-xs line-clamp-1">{item.name}</h3>
								{#if item.artist_name}
									<p class="text-xs text-base-content/50 line-clamp-1">{item.artist_name}</p>
								{/if}
								{#if item.listened_at}
									<p class="text-xs text-base-content/40">{formatListenedAt(item.listened_at)}</p>
								{/if}
							</div>
						</div>
					</div>
				{/if}
			{/each}
			</div>

			{#if showRightArrow}
				<button
					class="absolute right-0 top-1/2 -translate-y-1/2 z-10 btn btn-circle btn-sm bg-base-100/90 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity hidden sm:flex"
					on:click={scrollRight}
					aria-label="Scroll right"
				>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
						<path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" />
					</svg>
				</button>
			{/if}
		</div>
	{/if}
</section>

<style>
	.scrollbar-hide {
		-ms-overflow-style: none;
		scrollbar-width: none;
	}
	.scrollbar-hide::-webkit-scrollbar {
		display: none;
	}
</style>
