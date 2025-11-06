<script lang="ts">
	import type { Artist } from '$lib/types';
	import { goto } from '$app/navigation';
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';

	export let artist: Artist;
	export let index: number = 0;
	
	let coverUrl = `/api/covers/artist/${artist.musicbrainz_id}?size=250`;
	let imgError = false;
	let imgLoaded = false;
	let imageObserver: IntersectionObserver | null = null;

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

	function setupImageObserver(img: HTMLImageElement) {
		if (!img) return;
		
		if (imageObserver) {
			imageObserver.observe(img);
		} else {
			const checkObserver = setInterval(() => {
				if (imageObserver) {
					imageObserver.observe(img);
					clearInterval(checkObserver);
				}
			}, 50);
			
			setTimeout(() => clearInterval(checkObserver), 1000);
		}
		
		return {
			destroy() {
				if (imageObserver && img) {
					imageObserver.unobserve(img);
				}
			}
		};
	}

	onMount(() => {
		if (browser) {
			imageObserver = new IntersectionObserver(
				(entries) => {
					entries.forEach((entry) => {
						if (entry.isIntersecting) {
							const img = entry.target as HTMLImageElement;
							const src = img.dataset.src;
							if (src && img.src !== src) {
								console.log('Loading artist image:', src);
								img.src = src;
								imageObserver?.unobserve(img);
							}
						}
					});
				},
				{
					rootMargin: '200px',
					threshold: 0.01
				}
			);
		}
	});

	onDestroy(() => {
		if (imageObserver) {
			imageObserver.disconnect();
			imageObserver = null;
		}
	});
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
				src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
				data-src={coverUrl}
				alt={artist.title}
				class="w-full h-full object-cover opacity-0 transition-opacity duration-300"
				decoding="async"
				use:setupImageObserver
				on:error={onImgError}
				on:load={onImgLoad}
			/>
		{/if}
	</figure>

	<div class="card-body p-2">
		<h2 class="card-title text-xs line-clamp-1 min-h-[1.25rem]">{artist.title}</h2>
	</div>
</div>
