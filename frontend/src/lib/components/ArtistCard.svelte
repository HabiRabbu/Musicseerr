<script lang="ts">
	import type { Artist } from '$lib/types';
	import { goto } from '$app/navigation';
	import ArtistImage from './ArtistImage.svelte';

	export let artist: Artist;

	function handleClick() {
		goto(`/artist/${artist.musicbrainz_id}`);
	}
</script>

<div
	class="card bg-base-100 w-full shadow-sm flex-shrink-0 cursor-pointer transition-transform hover:scale-105 hover:shadow-lg"
	on:click={handleClick}
	on:keydown={(e) => e.key === 'Enter' && handleClick()}
	role="button"
	tabindex="0"
>
	<figure class="aspect-square p-3">
		<ArtistImage mbid={artist.musicbrainz_id} alt={artist.title} size="full" className="w-full h-full" />
	</figure>

	<div class="card-body p-2 pt-0 items-center text-center">
		<h2 class="card-title text-xs line-clamp-1 min-h-[1.25rem]">{artist.title}</h2>
	</div>
</div>
