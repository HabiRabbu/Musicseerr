<script lang="ts">
	import type { Artist } from '$lib/types';
	import { goto } from '$app/navigation';
	import { formatListenCount } from '$lib/utils/formatting';
	import { Music2 } from 'lucide-svelte';
	import ArtistImage from './ArtistImage.svelte';

	export let artist: Artist;

	function handleClick() {
		goto(`/artist/${artist.musicbrainz_id}`);
	}
</script>

<button
	type="button"
	class="card bg-base-100 w-full shadow-sm flex-shrink-0 cursor-pointer transition-transform hover:scale-105 hover:shadow-lg"
	onclick={handleClick}
>
	<figure class="flex justify-center pt-4">
		<ArtistImage mbid={artist.musicbrainz_id} alt={artist.title} size="lg" />
	</figure>

	<div class="card-body p-3 pt-2 items-center text-center gap-0.5">
		<h2 class="font-semibold text-sm line-clamp-1">{artist.title}</h2>

		<p class="text-xs text-base-content/60 line-clamp-1 min-h-[1rem]">
			{#if artist.disambiguation}{artist.disambiguation}{:else}&nbsp;{/if}
		</p>

		<div class="flex flex-wrap items-center justify-center gap-1 mt-1 min-h-[1.5rem]">
			{#if artist.release_group_count != null}
				<span class="badge badge-sm badge-ghost">
					{artist.release_group_count} release{artist.release_group_count !== 1 ? 's' : ''}
				</span>
			{/if}
			{#if artist.listen_count != null}
				<span class="badge badge-sm badge-primary badge-outline" title="ListenBrainz plays">
					<Music2 class="inline h-3 w-3" /> {formatListenCount(artist.listen_count, true)}
				</span>
			{/if}
		</div>
	</div>
</button>
