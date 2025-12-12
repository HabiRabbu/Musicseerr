<script lang="ts">
	import type { Artist } from '$lib/types';
	import { goto } from '$app/navigation';
	import { lazyImage, resetLazyImage } from '$lib/utils/lazyImage';

	export let artist: Artist;

	let coverUrl = `/api/covers/artist/${artist.musicbrainz_id}?size=250`;
	let imgError = false;
	let imgLoaded = false;
	let imgElement: HTMLImageElement | null = null;

	function onImgError() {
		imgError = true;
	}

	function onImgLoad(e: Event) {
		imgLoaded = true;
		(e.currentTarget as HTMLImageElement).classList.remove('opacity-0');
	}

	function handleClick() {
		goto(`/artist/${artist.musicbrainz_id}`);
	}

	$: coverUrl = `/api/covers/artist/${artist.musicbrainz_id}?size=250`;

	$: if (artist && imgElement) {
		imgError = false;
		imgLoaded = false;
		resetLazyImage(imgElement, coverUrl);
	}

	function bindImgElement(img: HTMLImageElement) {
		imgElement = img;
		return {
			destroy() {
				if (imgElement === img) {
					imgElement = null;
				}
			}
		};
	}
</script>

<div
	class="card bg-base-100 w-full shadow-sm flex-shrink-0 cursor-pointer transition-transform hover:scale-105 hover:shadow-lg"
	on:click={handleClick}
	on:keydown={(e) => e.key === 'Enter' && handleClick()}
	role="button"
	tabindex="0"
>
	<figure class="aspect-square overflow-hidden relative">
		{#if imgError}
			<div class="w-full h-full flex items-center justify-center text-6xl opacity-50 bg-base-200">
				🎤
			</div>
		{:else}
			{#if !imgLoaded}
				<div class="skeleton w-full h-full absolute inset-0"></div>
			{/if}
			<img
				src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
				data-src={coverUrl}
				alt={artist.title}
				class="w-full h-full object-cover opacity-0 transition-opacity duration-300"
				decoding="async"
				use:lazyImage
				use:bindImgElement
				on:error={onImgError}
				on:load={onImgLoad}
			/>
		{/if}
	</figure>

	<div class="card-body p-2">
		<h2 class="card-title text-xs line-clamp-1 min-h-[1.25rem]">{artist.title}</h2>
	</div>
</div>
