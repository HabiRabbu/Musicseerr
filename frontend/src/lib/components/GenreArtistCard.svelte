<script lang="ts">
	import { Check } from 'lucide-svelte';
	import ArtistImage from '$lib/components/ArtistImage.svelte';
	import type { HomeArtist } from '$lib/types';

	interface Props {
		artist: HomeArtist;
		showLibraryBadge?: boolean;
		onclick?: () => void;
		href?: string | null;
	}

	let { artist, showLibraryBadge = false, onclick, href = null }: Props = $props();
</script>

<svelte:element
	this={href ? 'a' : 'button'}
	href={href ?? undefined}
	type={href ? undefined : 'button'}
	onclick={href ? undefined : onclick}
	onkeydown={href || !onclick ? undefined : (e: KeyboardEvent) => e.key === 'Enter' && onclick()}
	role={href || !onclick ? undefined : 'button'}
	tabindex={href || !onclick ? undefined : 0}
	class="card bg-base-200/50 hover:bg-base-200 transition-all duration-200 group {href || onclick ? 'cursor-pointer' : 'cursor-default'}"
>
	<figure class="flex justify-center pt-4 relative">
		<ArtistImage mbid={artist.mbid || ''} alt={artist.name} size="md" lazy={false} />
		{#if showLibraryBadge || artist.in_library}
			<div class="absolute top-2 right-2 badge badge-success badge-sm gap-1 opacity-90">
				<Check class="w-3 h-3" />
			</div>
		{/if}
	</figure>
	<div class="card-body p-3 items-center text-center">
		<h3 class="font-semibold text-sm line-clamp-1">{artist.name}</h3>
		{#if artist.listen_count}
			<p class="text-xs text-base-content/50">{artist.listen_count} album{artist.listen_count !== 1 ? 's' : ''}</p>
		{/if}
	</div>
</svelte:element>
