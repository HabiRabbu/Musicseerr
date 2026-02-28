<script lang="ts">
	import type { Artist } from '$lib/types';
	import { artistHref } from '$lib/utils/entityRoutes';
	import ArtistImage from './ArtistImage.svelte';

	export let artist: Artist;
</script>

<a
	href={artistHref(artist.musicbrainz_id)}
	class="card bg-base-100 w-full shadow-sm flex-shrink-0 transition-transform hover:scale-105 hover:shadow-lg"
	aria-label="Open {artist.title}"
>
	<figure class="aspect-square p-3">
		<ArtistImage mbid={artist.musicbrainz_id} alt={artist.title} size="full" className="w-full h-full" />
	</figure>

	<div class="card-body p-2 pt-0 items-center text-center">
		<h2 class="card-title text-xs line-clamp-1 min-h-[1.25rem]">{artist.title}</h2>
	</div>
</a>
