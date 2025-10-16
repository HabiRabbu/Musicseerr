<script lang="ts">
	import type { Artist } from '$lib/types';

	export let artist: Artist;
	export let index: number = 0;
	
	let coverUrl = `/api/covers/artist/${artist.musicbrainz_id}`;
	let imgError = false;
	let imgLoaded = false;

	function onImgError() {
		imgError = true;
	}

	function onImgLoad(e: Event) {
		imgLoaded = true;
		(e.currentTarget as HTMLImageElement).classList.remove('opacity-0');
	}
</script>

<div class="card bg-base-100 w-full shadow-sm flex-shrink-0">
	<figure class="aspect-square overflow-hidden relative">
		{#if imgError}
			<div
				class="w-full h-full flex items-center justify-center text-6xl opacity-50 bg-base-200"
			>
				🎤
			</div>
		{:else}
			{#if !imgLoaded}
				<div class="skeleton w-full h-full absolute inset-0"></div>
			{/if}
			<img
				src={coverUrl}
				alt={artist.title}
				class="w-full h-full object-cover opacity-0 transition-opacity duration-300"
				loading="lazy"
				decoding="async"
				fetchpriority={index < 6 ? 'high' : 'auto'}
				on:error={onImgError}
				on:load={onImgLoad}
			/>
		{/if}
	</figure>

	<div class="card-body p-3">
		<h2 class="card-title text-sm line-clamp-2 min-h-[2.5rem]">{artist.title}</h2>
		<p class="text-xs opacity-70 line-clamp-1">Artist</p>
	</div>
</div>
