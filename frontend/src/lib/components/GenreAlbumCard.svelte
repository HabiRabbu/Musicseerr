<script lang="ts">
	import { Check } from 'lucide-svelte';
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
				<Check class="w-3 h-3" />
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
