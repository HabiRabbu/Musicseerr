<script lang="ts">
	import { onDestroy } from 'svelte';
	import { lazyImage, resetLazyImage } from '$lib/utils/lazyImage';
	import { PLACEHOLDER_COLORS, API_SIZES } from '$lib/constants';
	import { isValidMbid } from '$lib/utils/formatting';
	import { imageSettingsStore } from '$lib/stores/imageSettings';
	import { appendAudioDBSizeSuffix } from '$lib/utils/imageSuffix';
	import { getApiUrl } from '$lib/utils/api';

	export let mbid: string;
	export let alt: string = 'Image';
	export let size: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'hero' | 'full' = 'md';
	export let lazy: boolean = true;
	export let showPlaceholder: boolean = true;
	export let className: string = '';
	export let rounded: 'none' | 'sm' | 'md' | 'lg' | 'xl' | 'full' = 'lg';
	export let customUrl: string | null = null;
	export let remoteUrl: string | null = null;
	export let imageType: 'album' | 'artist' = 'album';

	const MAX_RETRIES = 3;
	const RETRY_DELAYS = [2000, 4000, 8000];

	let imgError = false;
	let imgLoaded = false;
	let remoteError = false;
	let imgElement: HTMLImageElement | null = null;
	let currentSource = '';
	let retryCount = 0;
	let retryTimer: ReturnType<typeof setTimeout> | null = null;
	let retrySourceKey = '';

	const albumSizeClasses: Record<typeof size, string> = {
		xs: 'w-8 h-8',
		sm: 'w-12 h-12',
		md: 'w-16 h-16',
		lg: 'w-24 h-24 sm:w-32 sm:h-32',
		xl: 'w-36 h-36 sm:w-44 sm:h-44',
		hero: 'w-48 h-48 sm:w-64 sm:h-64 lg:w-80 lg:h-80',
		full: ''
	};

	const artistSizeClasses: Record<typeof size, string> = {
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
		xs: API_SIZES.XS,
		sm: API_SIZES.SM,
		md: API_SIZES.MD,
		lg: API_SIZES.LG,
		xl: API_SIZES.XL,
		hero: API_SIZES.HERO,
		full: API_SIZES.FULL
	};

	$: useRemoteUrl = remoteUrl && $imageSettingsStore.directRemoteImagesEnabled;
	$: resolvedRemoteUrl = remoteUrl ? appendAudioDBSizeSuffix(remoteUrl, size) : null;

	$: canonicalAlbumCoverUrl =
		imageType === 'album' && isValidMbid(mbid)
			? getApiUrl(`/api/v1/covers/release-group/${mbid}?size=${apiSizes[size]}`)
			: null;
	$: validMbid = imageType === 'artist' ? isValidMbid(mbid) : true;
	$: hasSource =
		(useRemoteUrl && resolvedRemoteUrl) ||
		(imageType === 'album' ? canonicalAlbumCoverUrl || customUrl || mbid : validMbid);
	$: apiEndpoint = imageType === 'album' ? 'release-group' : 'artist';
	$: fallbackCoverUrl = getApiUrl(`/api/v1/covers/${apiEndpoint}/${mbid}?size=${apiSizes[size]}`);
	$: coverUrl =
		imageType === 'album'
			? (canonicalAlbumCoverUrl ?? customUrl ?? fallbackCoverUrl)
			: fallbackCoverUrl;
	$: retryCoverUrl =
		retryCount > 0
			? coverUrl + (coverUrl.includes('?') ? '&' : '?') + `_r=${retryCount}`
			: coverUrl;
	$: sizeClasses = imageType === 'album' ? albumSizeClasses : artistSizeClasses;
	$: sizeClass = sizeClasses[size];
	$: roundedClass = roundedClasses[rounded];

	$: {
		const newKey = coverUrl;
		if (newKey !== retrySourceKey) {
			retrySourceKey = newKey;
			if (retryTimer) {
				clearTimeout(retryTimer);
				retryTimer = null;
			}
			retryCount = 0;
			if (imgError) {
				imgError = false;
				imgLoaded = false;
			}
		}
	}

	$: {
		const source = imageType === 'album' ? (canonicalAlbumCoverUrl ?? customUrl ?? mbid) : mbid;
		if (source && imgElement && source !== currentSource) {
			currentSource = source;
			imgError = false;
			imgLoaded = false;
			resetLazyImage(imgElement, retryCoverUrl);
		}
	}

	$: {
		remoteError = false;
		if (remoteUrl) imgLoaded = false;
	}

	function onRemoteError() {
		remoteError = true;
		imgLoaded = false;
	}

	function onImgError() {
		if (retryCount < MAX_RETRIES) {
			imgError = true;
			const delay = RETRY_DELAYS[retryCount] + Math.random() * 1000 - 500;
			retryTimer = setTimeout(() => {
				retryTimer = null;
				retryCount++;
				imgError = false;
				imgLoaded = false;
			}, delay);
		} else {
			imgError = true;
		}
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

	onDestroy(() => {
		if (retryTimer) clearTimeout(retryTimer);
	});
</script>

<div
	class="relative overflow-hidden flex-shrink-0 {sizeClass} {roundedClass} {className}"
	style="background-color: {PLACEHOLDER_COLORS.DARK};"
>
	{#if showPlaceholder && (!imgLoaded || imgError || !hasSource)}
		<div class="absolute inset-0 w-full h-full flex items-center justify-center">
			{#if imageType === 'album'}
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" class="w-full h-full">
					<rect fill={PLACEHOLDER_COLORS.DARK} width="200" height="200" />
					<circle
						cx="100"
						cy="100"
						r="70"
						fill={PLACEHOLDER_COLORS.MEDIUM}
						stroke={PLACEHOLDER_COLORS.LIGHT}
						stroke-width="2"
					/>
					<circle
						cx="100"
						cy="100"
						r="50"
						fill="none"
						stroke={PLACEHOLDER_COLORS.LIGHT}
						stroke-width="1"
					/>
					<circle
						cx="100"
						cy="100"
						r="30"
						fill="none"
						stroke={PLACEHOLDER_COLORS.LIGHT}
						stroke-width="1"
					/>
					<circle cx="100" cy="100" r="12" fill={PLACEHOLDER_COLORS.LIGHT} />
					<circle cx="100" cy="100" r="4" fill={PLACEHOLDER_COLORS.DARK} />
				</svg>
			{:else}
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" class="w-full h-full">
					<rect fill={PLACEHOLDER_COLORS.DARK} width="200" height="200" />
					<circle cx="100" cy="80" r="30" fill={PLACEHOLDER_COLORS.LIGHT} />
					<path
						d="M60 120 Q100 140 140 120 L140 160 Q100 180 60 160 Z"
						fill={PLACEHOLDER_COLORS.LIGHT}
					/>
				</svg>
			{/if}
		</div>
	{/if}
	{#if useRemoteUrl && resolvedRemoteUrl && !remoteError}
		<img
			src={resolvedRemoteUrl}
			{alt}
			class="w-full h-full object-cover transition-opacity duration-300"
			class:opacity-0={!imgLoaded}
			referrerpolicy="no-referrer"
			loading={lazy ? 'lazy' : 'eager'}
			decoding="async"
			on:error={onRemoteError}
			on:load={onImgLoad}
		/>
	{:else if hasSource && !imgError}
		{#if lazy}
			<img
				src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
				data-src={retryCoverUrl}
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
				src={retryCoverUrl}
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
