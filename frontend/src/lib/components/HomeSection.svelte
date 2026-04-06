<script lang="ts">
	import type {
		HomeSection as HomeSectionType,
		HomeArtist,
		HomeAlbum,
		HomeTrack,
		HomeGenre
	} from '$lib/types';
	import {
		ArrowRight,
		X,
		Check,
		Music2,
		Tv,
		Sparkles,
		Search,
		Radio,
		Headphones
	} from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { albumHrefOrNull, artistHrefOrNull } from '$lib/utils/entityRoutes';
	import { formatListenCount, formatListenedAt } from '$lib/utils/formatting';
	import ArtistImage from './ArtistImage.svelte';
	import AlbumImage from './AlbumImage.svelte';
	import AlbumCardOverlay from './AlbumCardOverlay.svelte';
	import HorizontalCarousel from './HorizontalCarousel.svelte';

	interface Props {
		section: HomeSectionType;
		showConnectCard?: boolean;
		headerLink?: string | null;
	}

	let { section, showConnectCard = true, headerLink = null }: Props = $props();

	function getGenreHref(genre: HomeGenre): string {
		return `/genre?name=${encodeURIComponent(genre.name)}`;
	}

	function handleAlbumSearch(album: HomeAlbum) {
		const query = [album.artist_name, album.name].filter(Boolean).join(' ').trim();
		if (query) {
			goto(`/search/albums?q=${encodeURIComponent(query)}`);
		}
	}

	function handleTrackAlbumSearch(track: HomeTrack) {
		const query = [track.artist_name, track.album_name || track.name]
			.filter(Boolean)
			.join(' ')
			.trim();
		if (query) {
			goto(`/search/albums?q=${encodeURIComponent(query)}`);
		}
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
		<div class="flex items-center gap-2">
			{#if headerLink}
				<a
					href={headerLink}
					class="text-lg sm:text-xl font-bold hover:text-primary transition-colors"
				>
					{section.title}
				</a>
			{:else}
				<h2 class="text-lg sm:text-xl font-bold">{section.title}</h2>
			{/if}
			{#if section.source === 'lastfm'}
				<span
					class="badge badge-xs sm:badge-sm border-0 gap-1"
					style="background-color: rgb(var(--brand-lastfm) / 0.15); color: rgb(var(--brand-lastfm));"
				>
					<Radio class="w-2.5 h-2.5 sm:w-3 sm:h-3" />
					Last.fm
				</span>
			{:else if section.source === 'listenbrainz'}
				<span
					class="badge badge-xs sm:badge-sm border-0 gap-1"
					style="background-color: rgb(var(--brand-listenbrainz) / 0.15); color: rgb(var(--brand-listenbrainz));"
				>
					<Headphones class="w-2.5 h-2.5 sm:w-3 sm:h-3" />
					ListenBrainz
				</span>
			{:else if section.source}
				<span class="badge badge-ghost badge-xs sm:badge-sm capitalize">{section.source}</span>
			{/if}
		</div>
		{#if headerLink}
			<a
				href={headerLink}
				class="text-sm text-base-content/50 hover:text-primary transition-colors flex items-center gap-1"
			>
				See all
				<ArrowRight class="w-3.5 h-3.5" />
			</a>
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
					{:else if section.connect_service === 'lastfm'}
						<Music2 class="h-5 w-5" />
					{:else}
						<Sparkles class="h-5 w-5" />
					{/if}
				</div>
				<p class="text-base-content/70 text-sm">{section.fallback_message}</p>
				{#if section.connect_service}
					<a href="/settings" class="btn btn-primary btn-sm mt-2">
						Connect {section.connect_service === 'listenbrainz'
							? 'ListenBrainz'
							: section.connect_service === 'lastfm'
								? 'Last.fm'
								: section.connect_service === 'jellyfin'
									? 'Jellyfin'
									: section.connect_service}
					</a>
				{/if}
			</div>
		</div>
	{:else if section.type === 'genres'}
		<div class="flex flex-wrap gap-2">
			{#each section.items as item, i (`${item.name}-${i}`)}
				{#if isGenre(item)}
					<a href={getGenreHref(item)} class="btn btn-sm btn-outline">
						{item.name}
						{#if item.listen_count}
							<span class="badge badge-ghost badge-xs ml-1"
								>{formatListenCount(item.listen_count)}</span
							>
						{/if}
					</a>
				{/if}
			{/each}
		</div>
	{:else}
		<HorizontalCarousel class="-mx-4 px-4 sm:mx-0 sm:px-0 pb-2">
			{#each section.items as item, i (`${item.name}-${i}`)}
				{#if isArtist(item)}
					{@const artistHref = artistHrefOrNull(item.mbid)}
					<div class="w-32 sm:w-36 md:w-44 shrink-0">
						<svelte:element
							this={artistHref ? 'a' : 'div'}
							href={artistHref ?? undefined}
							class="card bg-base-100 w-full shadow-sm transition-all {artistHref
								? 'cursor-pointer hover:scale-105 active:scale-95 hover:shadow-[0_0_20px_rgba(174,213,242,0.15)]'
								: 'cursor-default opacity-80'}"
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
						</svelte:element>
					</div>
				{:else if isAlbum(item)}
					{@const albumHref = albumHrefOrNull(item.mbid)}
					<div class="w-32 sm:w-36 md:w-44 shrink-0">
						<svelte:element
							this={albumHref ? 'a' : 'div'}
							href={albumHref ?? undefined}
							class="card bg-base-100 w-full shadow-sm transition-all group {albumHref
								? 'cursor-pointer hover:scale-105 active:scale-95 hover:shadow-[0_0_20px_rgba(174,213,242,0.15)]'
								: 'cursor-default opacity-90'}"
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
									<div class="absolute top-2 left-2 z-20 badge badge-success badge-sm">
										<Check class="w-3 h-3" />
									</div>
								{/if}
								{#if item.mbid && item.in_library}
									<AlbumCardOverlay
										mbid={item.mbid}
										albumName={item.name}
										artistName={item.artist_name || 'Unknown'}
										coverUrl={item.image_url || null}
										size="sm"
									/>
								{/if}
								{#if !item.mbid}
									<button
										type="button"
										class="btn btn-ghost btn-xs btn-circle absolute bottom-2 right-2"
										title="Search album"
										onclick={(e) => {
											e.stopPropagation();
											handleAlbumSearch(item);
										}}
									>
										<Search class="w-3 h-3" />
									</button>
								{/if}
							</figure>
							<div class="card-body p-2">
								<h3 class="card-title text-xs line-clamp-1">{item.name}</h3>
								{#if item.artist_name}
									<p class="text-xs text-base-content/50 line-clamp-1">{item.artist_name}</p>
								{/if}
							</div>
						</svelte:element>
					</div>
				{:else if isTrack(item)}
					{@const trackArtistHref = artistHrefOrNull(item.artist_mbid)}
					<div class="w-56 sm:w-64 md:w-72 shrink-0">
						<svelte:element
							this={trackArtistHref ? 'a' : 'div'}
							href={trackArtistHref ?? undefined}
							class="card card-side bg-base-100 w-full shadow-sm transition-all {trackArtistHref
								? 'cursor-pointer hover:shadow-[0_0_20px_rgba(174,213,242,0.15)] active:scale-95'
								: 'cursor-default opacity-90'}"
						>
							<figure class="w-16 h-16 shrink-0">
								{#if item.image_url}
									<img
										src={item.image_url}
										alt={item.album_name || item.name}
										class="w-full h-full object-cover"
									/>
								{:else}
									<div class="w-full h-full flex items-center justify-center text-2xl bg-base-200">
										<Music2 class="h-6 w-6 text-base-content/40" />
									</div>
								{/if}
							</figure>
							<div class="card-body p-2 justify-center">
								<h3 class="card-title text-xs line-clamp-1">{item.name}</h3>
								{#if item.artist_name}
									<p class="text-xs text-base-content/50 line-clamp-1">{item.artist_name}</p>
								{/if}
								{#if item.listened_at}
									<p class="text-xs text-base-content/40">{formatListenedAt(item.listened_at)}</p>
								{/if}
								{#if !item.artist_mbid}
									<div class="flex justify-end pt-1">
										<button
											type="button"
											class="btn btn-ghost btn-xs btn-circle"
											title="Search album"
											onclick={(e) => {
												e.stopPropagation();
												handleTrackAlbumSearch(item);
											}}
										>
											<Search class="w-3 h-3" />
										</button>
									</div>
								{/if}
							</div>
						</svelte:element>
					</div>
				{/if}
			{/each}
		</HorizontalCarousel>
	{/if}
</section>
