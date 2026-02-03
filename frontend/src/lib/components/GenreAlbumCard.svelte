<script lang="ts">
	import AlbumImage from '$lib/components/AlbumImage.svelte';
	import type { HomeAlbum } from '$lib/types';

	interface Props {
		album: HomeAlbum;
		showLibraryBadge?: boolean;
		onclick?: () => void;
	}

	let { album, showLibraryBadge = false, onclick }: Props = $props();
</script>

<button
	type="button"
	class="card bg-base-200/50 hover:bg-base-200 transition-all duration-200 cursor-pointer group"
	{onclick}
>
	<figure class="aspect-square overflow-hidden relative rounded-t-2xl">
		<AlbumImage
			mbid={album.mbid || ''}
			alt={album.name}
			size="md"
			rounded="none"
			className="w-full h-full"
			customUrl={album.image_url || null}
		/>
		{#if showLibraryBadge || album.in_library}
			<div class="absolute top-2 right-2 badge badge-success badge-sm gap-1 opacity-90">
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3 h-3">
					<path fill-rule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clip-rule="evenodd" />
				</svg>
			</div>
		{/if}
	</figure>
	<div class="card-body p-3">
		<h3 class="font-semibold text-sm line-clamp-1">{album.name}</h3>
		<p class="text-xs text-base-content/50 line-clamp-1">
			{album.artist_name || 'Unknown Artist'}
			{#if album.release_date}
				· {album.release_date}
			{/if}
		</p>
	</div>
</button>
