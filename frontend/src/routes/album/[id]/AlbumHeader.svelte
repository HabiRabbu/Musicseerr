<script lang="ts">
	import type { AlbumBasicInfo, AlbumTracksInfo } from '$lib/types';
	import { getApiUrl } from '$lib/utils/api';
	import { colors } from '$lib/colors';
	import AlbumImage from '$lib/components/AlbumImage.svelte';
	import HeroBackdrop from '$lib/components/HeroBackdrop.svelte';
	import { formatTotalDuration } from '$lib/utils/formatting';
	import { Check, Trash2, Clock, Plus } from 'lucide-svelte';

	interface Props {
		album: AlbumBasicInfo;
		tracksInfo: AlbumTracksInfo | null;
		loadingTracks: boolean;
		inLibrary: boolean;
		isRequested: boolean;
		requesting: boolean;
		lidarrConfigured: boolean;
		onrequest: () => void;
		ondelete: () => void;
		onartistclick: () => void;
	}

	let {
		album,
		tracksInfo,
		loadingTracks,
		inLibrary,
		isRequested,
		requesting,
		lidarrConfigured,
		onrequest,
		ondelete,
		onartistclick
	}: Props = $props();

	let backdropUrl = $derived(
		album.cover_url ||
			album.album_thumb_url ||
			(album.musicbrainz_id
				? getApiUrl(`/api/v1/covers/release-group/${album.musicbrainz_id}?size=250`)
				: null)
	);
</script>

<div class="album-hero group relative overflow-hidden rounded-2xl transition-all duration-500">
	<HeroBackdrop
		imageUrl={backdropUrl}
		opacity={0.1}
		hoverOpacity={0.15}
		blur={3}
		hoverBlur={2}
		position="full"
	/>

	<div class="relative z-10 flex flex-col lg:flex-row gap-6 lg:gap-8 p-4 sm:p-6 lg:p-8">
		<div class="w-full lg:w-64 xl:w-80 flex-shrink-0">
			<AlbumImage
				mbid={album.musicbrainz_id}
				customUrl={album.cover_url}
				remoteUrl={album.album_thumb_url ?? null}
				alt={album.title}
				size="hero"
				lazy={false}
				rounded="xl"
				className="w-full aspect-square shadow-2xl"
			/>
		</div>

		<div class="flex-1 flex flex-col lg:justify-end space-y-4">
			<div class="text-xs sm:text-sm font-semibold uppercase tracking-wider opacity-70">
				{album.type || 'Album'}
			</div>

			<h1 class="text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-bold leading-tight">
				{album.title}
			</h1>

			{#if album.disambiguation}
				<p class="text-sm opacity-60 italic">({album.disambiguation})</p>
			{/if}

			<div class="flex flex-wrap items-center gap-2 text-sm">
				<button onclick={onartistclick} class="font-semibold hover:underline cursor-pointer">
					{album.artist_name}
				</button>

				{#if album.year}
					<span class="opacity-50">•</span>
					<span>{album.year}</span>
				{/if}

				{#if tracksInfo && tracksInfo.total_tracks > 0}
					<span class="opacity-50">•</span>
					<span>{tracksInfo.total_tracks} {tracksInfo.total_tracks === 1 ? 'track' : 'tracks'}</span
					>
				{:else if loadingTracks}
					<span class="opacity-50">•</span>
					<span class="skeleton w-16 h-4 inline-block"></span>
				{/if}

				{#if tracksInfo?.total_length}
					<span class="opacity-50">•</span>
					<span>{formatTotalDuration(tracksInfo.total_length)}</span>
				{/if}
			</div>

			<div class="flex flex-wrap gap-x-4 gap-y-2 text-xs sm:text-sm opacity-70">
				{#if tracksInfo?.label}
					<div>
						<span class="font-semibold">Label:</span>
						{tracksInfo.label}
					</div>
				{/if}
				{#if tracksInfo?.country}
					<div>
						<span class="font-semibold">Country:</span>
						{tracksInfo.country}
					</div>
				{/if}
				{#if tracksInfo?.barcode}
					<div>
						<span class="font-semibold">Barcode:</span>
						{tracksInfo.barcode}
					</div>
				{/if}
			</div>

			{#if lidarrConfigured}
				<div class="pt-4 flex flex-wrap items-start gap-3">
					{#if inLibrary}
						<div
							class="badge badge-lg gap-2"
							style="background-color: {colors.accent}; color: {colors.secondary};"
						>
							<Check class="h-4 w-4" />
							In Library
						</div>
						<button class="btn btn-sm btn-error btn-outline gap-1" onclick={ondelete}>
							<Trash2 class="h-4 w-4" />
							Remove
						</button>
					{:else if isRequested}
						<div class="badge badge-lg badge-warning gap-2">
							<Clock class="h-4 w-4" />
							Requested
						</div>
						<button class="btn btn-sm btn-error btn-outline gap-1" onclick={ondelete}>
							<Trash2 class="h-4 w-4" />
							Remove
						</button>
					{:else}
						<button
							class="btn btn-lg gap-2"
							style="background-color: {colors.accent}; color: {colors.secondary}; border: none;"
							onclick={onrequest}
							disabled={requesting}
						>
							{#if requesting}
								<span class="loading loading-spinner loading-sm"></span>
								Requesting...
							{:else}
								<Plus class="h-5 w-5" />
								Add to Library
							{/if}
						</button>
					{/if}
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	.album-hero {
		--hero-glow-color: var(--brand-hero);
		border: 1px solid rgb(var(--brand-hero) / 0.06);
		animation: hero-glow 4s ease-in-out infinite;
	}
	.album-hero:hover {
		border-color: rgb(var(--brand-hero) / 0.15);
	}
	@media (prefers-reduced-motion: reduce) {
		.album-hero {
			animation: none;
		}
	}
</style>
