<script lang="ts">
	import { goto } from '$app/navigation';
	import type { TopSong } from '$lib/types';
	import AlbumImage from './AlbumImage.svelte';

	interface Props {
		song: TopSong;
		position: number;
	}

	let { song, position }: Props = $props();

	function handleClick() {
		if (song.release_mbid) {
			goto(`/album/${song.release_mbid}`);
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') handleClick();
	}
</script>

<div
	class="flex items-center gap-3 p-2 rounded-lg hover:bg-base-200 cursor-pointer transition-colors group"
	role="button"
	tabindex="0"
	onclick={handleClick}
	onkeydown={handleKeydown}
>
	<span class="w-6 text-center text-sm text-base-content/50 group-hover:hidden">{position}</span>
	<span class="w-6 text-center hidden group-hover:block">
		<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-4 h-4 mx-auto">
			<path fill-rule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" clip-rule="evenodd" />
		</svg>
	</span>

	{#if song.release_mbid}
		<div class="w-12 h-12 flex-shrink-0">
			<AlbumImage mbid={song.release_mbid} alt={song.release_name || ''} size="full" className="w-12 h-12 rounded" />
		</div>
	{:else}
		<div class="w-12 h-12 flex-shrink-0 bg-base-300 rounded flex items-center justify-center">
			<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
			</svg>
		</div>
	{/if}

	<div class="flex-1 min-w-0">
		<p class="font-medium text-sm truncate">{song.title}</p>
		<p class="text-xs text-base-content/60 truncate">{song.release_name || 'Unknown Album'}</p>
	</div>
</div>
