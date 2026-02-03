<script lang="ts">
	import ArtistImage from '$lib/components/ArtistImage.svelte';
	import type { HomeArtist } from '$lib/types';

	interface Props {
		artist: HomeArtist;
		showLibraryBadge?: boolean;
		onclick?: () => void;
	}

	let { artist, showLibraryBadge = false, onclick }: Props = $props();
</script>

<button
	type="button"
	class="card bg-base-200/50 hover:bg-base-200 transition-all duration-200 cursor-pointer group"
	{onclick}
>
	<figure class="flex justify-center pt-4 relative">
		<ArtistImage mbid={artist.mbid || ''} alt={artist.name} size="md" lazy={false} />
		{#if showLibraryBadge || artist.in_library}
			<div class="absolute top-2 right-2 badge badge-success badge-sm gap-1 opacity-90">
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3 h-3">
					<path fill-rule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clip-rule="evenodd" />
				</svg>
			</div>
		{/if}
	</figure>
	<div class="card-body p-3 items-center text-center">
		<h3 class="font-semibold text-sm line-clamp-1">{artist.name}</h3>
		{#if artist.listen_count}
			<p class="text-xs text-base-content/50">{artist.listen_count} album{artist.listen_count !== 1 ? 's' : ''}</p>
		{/if}
	</div>
</button>
