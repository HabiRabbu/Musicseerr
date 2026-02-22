<script lang="ts">
	import type {
		HomeSection as HomeSectionType,
		HomeArtist,
		HomeAlbum,
		HomeTrack,
		HomeGenre
	} from '$lib/types';
	import { ArrowRight, X, Check, Music2, Tv, Sparkles } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { formatListenCount, formatListenedAt } from '$lib/utils/formatting';
	import ArtistImage from './ArtistImage.svelte';
	import AlbumImage from './AlbumImage.svelte';
	import HorizontalCarousel from './HorizontalCarousel.svelte';

	interface Props {
		section: HomeSectionType;
		showConnectCard?: boolean;
		headerLink?: string | null;
	}

	let { section, showConnectCard = true, headerLink = null }: Props = $props();

	function handleArtistClick(artist: HomeArtist) {
		if (artist.mbid) goto(`/artist/${artist.mbid}`);
	}

	function handleAlbumClick(album: HomeAlbum) {
		if (album.mbid) goto(`/album/${album.mbid}`);
	}

	function handleTrackClick(track: HomeTrack) {
		if (track.artist_mbid) goto(`/artist/${track.artist_mbid}`);
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
			<a
				href={headerLink}
				class="text-lg sm:text-xl font-bold hover:text-primary transition-colors flex items-center gap-2 group"
			>
				{section.title}
				<ArrowRight class="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
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
						<Music2 class="h-5 w-5" />
					{:else if section.connect_service === 'jellyfin'}
						<Tv class="h-5 w-5" />
					{:else}
						<Sparkles class="h-5 w-5" />
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
			{#each section.items as item}
				{#if isGenre(item)}
					<button class="btn btn-sm btn-outline" onclick={() => handleGenreClick(item)}>
						{item.name}
						{#if item.listen_count}
							<span class="badge badge-ghost badge-xs ml-1"
								>{formatListenCount(item.listen_count)}</span
							>
						{/if}
					</button>
				{/if}
			{/each}
		</div>
	{:else}
		<HorizontalCarousel class="-mx-4 px-4 sm:mx-0 sm:px-0 pb-2">
			{#each section.items as item}
				{#if isArtist(item)}
					<div class="w-32 sm:w-36 md:w-44 flex-shrink-0">
						<div
							class="card bg-base-100 w-full shadow-sm transition-transform {item.mbid
								? 'cursor-pointer hover:scale-105 active:scale-95 hover:shadow-lg'
								: 'cursor-default opacity-80'}"
							onclick={() => handleArtistClick(item)}
							onkeydown={(e) => e.key === 'Enter' && handleArtistClick(item)}
							role={item.mbid ? 'button' : 'presentation'}
							tabindex={item.mbid ? 0 : -1}
						>
							<figure class="flex justify-center pt-4 relative">
								<ArtistImage mbid={item.mbid ?? ''} alt={item.name} size="md" lazy={true} />
								{#if !item.mbid}
									<div
										class="absolute top-2 left-2 badge badge-ghost badge-sm"
										title="Not linked to MusicBrainz"
									>
										<X class="w-3 h-3" />
									</div>
								{/if}
								{#if item.in_library}
									<div class="absolute top-2 right-2 badge badge-success badge-sm">
										<Check class="w-3 h-3" />
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
							onclick={() => handleAlbumClick(item)}
							onkeydown={(e) => e.key === 'Enter' && handleAlbumClick(item)}
							role="button"
							tabindex={0}
						>
							<figure class="aspect-square overflow-hidden relative">
								<AlbumImage
									mbid={item.mbid || ''}
									alt={item.name}
									size="md"
									rounded="none"
									className="w-full h-full"
									customUrl={item.image_url || null}
								/>
								{#if item.in_library}
									<div class="absolute top-2 right-2 badge badge-success badge-sm">
										<Check class="w-3 h-3" />
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
							onclick={() => handleTrackClick(item)}
							onkeydown={(e) => e.key === 'Enter' && handleTrackClick(item)}
							role="button"
							tabindex={0}
						>
							<figure class="w-16 h-16 flex-shrink-0">
								<div class="w-full h-full flex items-center justify-center text-2xl bg-base-200">
									<Music2 class="h-6 w-6 text-base-content/40" />
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
		</HorizontalCarousel>
	{/if}
</section>
