<script lang="ts">
	import type { Album } from '$lib/types';
	import { colors } from '$lib/colors';
	import { goto } from '$app/navigation';
	import { libraryStore } from '$lib/stores/library';
	import { STATUS_COLORS } from '$lib/constants';
	import { requestAlbum } from '$lib/utils/albumRequest';
	import { formatListenCount } from '$lib/utils/formatting';
	import AlbumImage from './AlbumImage.svelte';

	export let album: Album;
	export let onadded: (() => void) | undefined = undefined;

	let requesting = false;

	$: inLibrary = album.in_library || libraryStore.isInLibrary(album.musicbrainz_id);
	$: isRequested =
		!inLibrary && (album.requested || libraryStore.isRequested(album.musicbrainz_id));

	async function handleRequest(e: Event) {
		e.stopPropagation();
		requesting = true;
		try {
			const result = await requestAlbum(album.musicbrainz_id);
			if (result.success) {
				onadded?.();
			}
		} finally {
			requesting = false;
		}
	}

	function handleClick() {
		goto(`/album/${album.musicbrainz_id}`);
	}

	function getTypeBadgeClass(type: string): string {
		const lower = type.toLowerCase();
		if (lower.includes('ep')) return 'badge-warning';
		if (lower.includes('single')) return 'badge-info';
		if (lower.includes('compilation')) return 'badge-secondary';
		if (lower.includes('live')) return 'badge-error';
		return 'badge-ghost';
	}
</script>

<div
	class="card bg-base-100 w-full shadow-sm flex-shrink-0 group relative cursor-pointer transition-transform hover:scale-105 hover:shadow-lg active:scale-95"
	onclick={handleClick}
	onkeydown={(e) => e.key === 'Enter' && handleClick()}
	role="button"
	tabindex="0"
>
	<figure class="aspect-square overflow-hidden relative">
		<AlbumImage
			mbid={album.musicbrainz_id}
			customUrl={album.cover_url}
			alt={album.title}
			size="full"
			rounded="none"
			className="w-full h-full"
		/>

		{#if album.type_info && album.type_info !== 'Album'}
			<div class="absolute top-2 left-2">
				<span class="badge badge-sm {getTypeBadgeClass(album.type_info)}">{album.type_info}</span>
			</div>
		{/if}
	</figure>

	{#if inLibrary}
		<div
			class="absolute top-2 right-2 rounded-full p-1.5 shadow-lg"
			style="background-color: {colors.accent};"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				class="h-4 w-4"
				fill="none"
				viewBox="0 0 24 24"
				stroke={colors.secondary}
				stroke-width="3"
			>
				<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
			</svg>
		</div>
	{:else if isRequested}
		<div
			class="absolute top-2 right-2 rounded-full p-1.5 shadow-lg"
			style="background-color: {STATUS_COLORS.REQUESTED};"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				class="h-4 w-4"
				fill="none"
				viewBox="0 0 24 24"
				stroke={colors.secondary}
				stroke-width="2"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
		</div>
	{/if}

	<div class="card-body p-3">
		<h2 class="card-title text-sm line-clamp-2 min-h-[2.5rem]">{album.title}</h2>
		<p class="text-xs opacity-70 line-clamp-1">
			{#if album.year}{album.year}{:else}Unknown{/if}
			{#if album.artist}
				<span class="opacity-50 mx-1">•</span>
				{album.artist}
			{/if}
		</p>

		{#if album.listen_count != null}
			<div class="flex items-center gap-1 mt-1">
				<span class="badge badge-sm badge-primary badge-outline" title="ListenBrainz plays">
					♪ {formatListenCount(album.listen_count, true)}
				</span>
			</div>
		{/if}
	</div>

	{#if !inLibrary && !isRequested}
		<button
			class="absolute bottom-2 right-2 btn btn-square btn-md opacity-0 group-hover:opacity-100 transition-opacity duration-200 border-none shadow-lg"
			style="background-color: {colors.accent};"
			onclick={handleRequest}
			disabled={requesting}
			aria-label="Request album"
		>
			{#if requesting}
				<span class="loading loading-spinner loading-sm" style="color: {colors.secondary};"></span>
			{:else}
				<svg
					xmlns="http://www.w3.org/2000/svg"
					class="h-5 w-5"
					fill="none"
					viewBox="0 0 24 24"
					stroke={colors.secondary}
					stroke-width="2.5"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
					/>
				</svg>
			{/if}
		</button>
	{/if}
</div>
