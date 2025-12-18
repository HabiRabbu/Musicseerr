<script lang="ts">
	import { lazyImage, resetLazyImage } from '$lib/utils/lazyImage';

	export let mbid: string;
	export let alt: string = 'Artist';
	export let size: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'hero' | 'full' = 'md';
	export let lazy: boolean = true;
	export let showPlaceholder: boolean = true;
	export let className: string = '';
	export let rounded: 'none' | 'sm' | 'md' | 'lg' | 'xl' | 'full' = 'full';

	const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

	function isValidMbid(id: string | null | undefined): boolean {
		return !!id && UUID_PATTERN.test(id);
	}

	let imgError = false;
	let imgLoaded = false;
	let imgElement: HTMLImageElement | null = null;
	let currentMbid = '';

	$: validMbid = isValidMbid(mbid);

	const sizeClasses: Record<typeof size, string> = {
		xs: 'w-8 h-8',
		sm: 'w-12 h-12',
		md: 'w-28 h-28 sm:w-36 sm:h-36',
		lg: 'w-36 h-36 sm:w-44 sm:h-44',
		xl: 'w-48 h-48 sm:w-56 sm:h-56',
		hero: 'w-40 h-40 sm:w-52 sm:h-52 lg:w-64 lg:h-64',
		full: ''
	};

	const roundedClasses: Record<typeof rounded, string> = {
		none: '',
		sm: 'rounded-sm',
		md: 'rounded-md',
		lg: 'rounded-lg',
		xl: 'rounded-xl',
		full: 'rounded-full'
	};

	const apiSizes: Record<typeof size, number> = {
		xs: 250,
		sm: 250,
		md: 250,
		lg: 500,
		xl: 500,
		hero: 500,
		full: 500
	};

	$: coverUrl = `/api/covers/artist/${mbid}?size=${apiSizes[size]}`;
	$: sizeClass = sizeClasses[size];
	$: roundedClass = roundedClasses[rounded];

	$: if (mbid && imgElement && mbid !== currentMbid) {
		currentMbid = mbid;
		imgError = false;
		imgLoaded = false;
		resetLazyImage(imgElement, coverUrl);
	}

	function onImgError() {
		imgError = true;
	}

	function onImgLoad(e: Event) {
		imgLoaded = true;
		(e.currentTarget as HTMLImageElement).classList.remove('opacity-0');
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

<div class="relative overflow-hidden flex-shrink-0 {sizeClass} {roundedClass} {className}" style="background-color: #0d120a;">
	<!-- Always show placeholder until image loads -->
	{#if showPlaceholder && (!imgLoaded || imgError || !validMbid)}
		<div class="absolute inset-0 w-full h-full flex items-center justify-center">
			<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" class="w-full h-full">
				<rect fill="#0d120a" width="200" height="200"/>
				<circle cx="100" cy="80" r="30" fill="#1F271B"/>
				<path d="M60 120 Q100 140 140 120 L140 160 Q100 180 60 160 Z" fill="#1F271B"/>
			</svg>
		</div>
	{/if}
	{#if validMbid && !imgError}
		{#if lazy}
			<img
				src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
				data-src={coverUrl}
				{alt}
				class="w-full h-full object-cover opacity-0 transition-opacity duration-300"
				loading="lazy"
				decoding="async"
				use:lazyImage
				use:bindImgElement
				on:error={onImgError}
				on:load={onImgLoad}
			/>
		{:else}
			<img
				src={coverUrl}
				{alt}
				class="w-full h-full object-cover transition-opacity duration-300"
				class:opacity-0={!imgLoaded}
				loading="lazy"
				decoding="async"
				on:error={onImgError}
				on:load={onImgLoad}
			/>
		{/if}
	{/if}
</div>
