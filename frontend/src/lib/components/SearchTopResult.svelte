<script lang="ts">
	import type { Artist, Album } from '$lib/types';
	import { artistHref, albumHref } from '$lib/utils/entityRoutes';
	import HeroBackdrop from './HeroBackdrop.svelte';
	import ArtistImage from './ArtistImage.svelte';
	import { ArrowRight, Disc3 } from 'lucide-svelte';

	interface Props {
		artist?: Artist | null;
		album?: Album | null;
	}

	let { artist = null, album = null }: Props = $props();

	let imageUrl = $derived.by(() => {
		if (artist) {
			return artist.banner_url || artist.fanart_url || artist.thumb_url || null;
		}
		if (album) {
			return album.cover_url || album.album_thumb_url || null;
		}
		return null;
	});

	let href = $derived.by(() => {
		if (artist) return artistHref(artist.musicbrainz_id);
		if (album) return albumHref(album.musicbrainz_id);
		return '#';
	});

	let title = $derived(artist?.title ?? album?.title ?? '');
	let subtitle = $derived.by(() => {
		if (artist) {
			return artist.disambiguation || artist.type_info || 'Artist';
		}
		if (album) {
			const parts: string[] = [];
			if (album.artist) parts.push(album.artist);
			if (album.year) parts.push(String(album.year));
			return parts.join(' · ') || 'Album';
		}
		return '';
	});

	let resultType = $derived(artist ? 'artist' : 'album');
</script>

<a
	{href}
	class="group relative flex items-end gap-4 overflow-hidden rounded-box p-4 sm:p-6 min-h-30 sm:min-h-35 transition-shadow hover:shadow-lg"
	style="--hero-glow-color: var(--brand-hero);"
>
	<div class="absolute inset-0 bg-base-200"></div>
	<HeroBackdrop
		{imageUrl}
		opacity={0.18}
		hoverOpacity={0.25}
		blur={2}
		hoverBlur={1}
		position="full"
	/>
	<div
		class="absolute inset-0 bg-linear-to-r from-base-100/80 via-base-100/40 to-transparent pointer-events-none"
	></div>

	<div class="relative z-10 flex items-center gap-4 sm:gap-5 w-full">
		{#if resultType === 'artist' && artist}
			<div class="shrink-0">
				<ArtistImage
					mbid={artist.musicbrainz_id}
					alt={artist.title}
					size="lg"
					remoteUrl={artist.thumb_url ?? null}
				/>
			</div>
		{:else if album}
			<div class="shrink-0 w-16 h-16 sm:w-20 sm:h-20 rounded-lg overflow-hidden shadow-md">
				{#if album.cover_url}
					<img src={album.cover_url} alt={album.title} class="w-full h-full object-cover" />
				{:else}
					<div class="w-full h-full bg-base-200 flex items-center justify-center">
						<Disc3 class="h-8 w-8 text-base-content/20" />
					</div>
				{/if}
			</div>
		{/if}

		<div class="flex-1 min-w-0">
			<span
				class="text-[10px] font-semibold uppercase tracking-widest text-primary/70 mb-0.5 block"
			>
				Top {resultType}
			</span>
			<h3 class="text-lg sm:text-xl font-bold line-clamp-1">{title}</h3>
			{#if subtitle}
				<p class="text-sm text-base-content/60 line-clamp-1">{subtitle}</p>
			{/if}
		</div>

		<div class="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
			<ArrowRight class="h-5 w-5 text-base-content/40" />
		</div>
	</div>
</a>
