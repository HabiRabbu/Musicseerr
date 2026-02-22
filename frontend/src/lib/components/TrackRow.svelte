<script lang="ts">
	import { goto } from '$app/navigation';
	import { Play, Music2 } from 'lucide-svelte';
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
		<Play class="w-4 h-4 mx-auto fill-current" />
	</span>

	{#if song.release_mbid}
		<div class="w-12 h-12 flex-shrink-0">
			<AlbumImage mbid={song.release_mbid} alt={song.release_name || ''} size="full" className="w-12 h-12 rounded" />
		</div>
	{:else}
		<div class="w-12 h-12 flex-shrink-0 bg-base-300 rounded flex items-center justify-center">
			<Music2 class="w-6 h-6 opacity-50" />
		</div>
	{/if}

	<div class="flex-1 min-w-0 grid grid-cols-2 items-center gap-4">
		<p class="font-medium text-sm truncate min-w-0">{song.title}</p>
		<p class="text-xs text-base-content/60 truncate min-w-0 text-right">{song.release_name || 'Unknown Album'}</p>
	</div>
</div>
