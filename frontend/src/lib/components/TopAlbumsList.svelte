<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import type { TopAlbum } from '$lib/types';
	import { colors } from '$lib/colors';
	import { libraryStore } from '$lib/stores/library';
	import { STATUS_COLORS } from '$lib/constants';
	import { requestAlbum } from '$lib/utils/albumRequest';
	import AlbumImage from './AlbumImage.svelte';

	interface Props {
		albums: TopAlbum[];
		loading?: boolean;
		configured?: boolean;
	}

	let { albums, loading = false, configured = true }: Props = $props();
	let requestingIds = $state(new Set<string>());
	
	let libraryMbids = $state(new Set<string>());
	let requestedMbids = $state(new Set<string>());
	
	onMount(() => {
		const unsubscribe = libraryStore.subscribe(state => {
			libraryMbids = new Set(state.mbidSet);
			requestedMbids = new Set(state.requestedSet);
		});
		return unsubscribe;
	});

	function handleClick(mbid: string | null | undefined) {
		if (mbid) goto(`/album/${mbid}`);
	}

	function isInLibrary(album: TopAlbum): boolean {
		const mbid = album.release_group_mbid?.toLowerCase();
		return album.in_library || (mbid ? libraryMbids.has(mbid) : false);
	}

	function isRequested(album: TopAlbum): boolean {
		if (album.requested) return true;
		const mbid = album.release_group_mbid?.toLowerCase();
		if (!mbid) return false;
		return requestedMbids.has(mbid) && !libraryMbids.has(mbid);
	}

	function isRequesting(album: TopAlbum): boolean {
		return album.release_group_mbid ? requestingIds.has(album.release_group_mbid) : false;
	}

	async function handleRequest(album: TopAlbum) {
		if (!album.release_group_mbid) return;
		
		const id = album.release_group_mbid;
		requestingIds = new Set([...requestingIds, id]);
		
		try {
			await requestAlbum(id);
		} finally {
			const newSet = new Set(requestingIds);
			newSet.delete(id);
			requestingIds = newSet;
		}
	}
</script>

<div class="flex flex-col">
	<h3 class="text-lg font-semibold mb-3">Popular Albums</h3>

	{#if loading}
		<div class="space-y-2">
			{#each Array(10) as _}
				<div class="flex items-center gap-3 p-2">
					<div class="skeleton w-12 h-12 rounded"></div>
					<div class="flex-1">
						<div class="skeleton h-4 w-3/4 mb-1"></div>
						<div class="skeleton h-3 w-1/2"></div>
					</div>
				</div>
			{/each}
		</div>
	{:else if !configured}
		<div class="bg-base-200 rounded-lg p-4 text-center flex-1 flex items-center justify-center">
			<div>
				<p class="text-base-content/70 text-sm">Connect ListenBrainz to see popular albums</p>
				<a href="/settings" class="btn btn-primary btn-xs mt-2">Configure</a>
			</div>
		</div>
	{:else if albums.length === 0}
		<div class="bg-base-200 rounded-lg p-4 text-center flex-1 flex items-center justify-center">
			<p class="text-base-content/70 text-sm">No album data available</p>
		</div>
	{:else}
		<div class="space-y-1">
			{#each albums as album}
				<div
					class="flex items-center gap-3 p-2 rounded-lg hover:bg-base-200 cursor-pointer transition-colors group"
					role="button"
					tabindex="0"
					onclick={() => handleClick(album.release_group_mbid)}
					onkeydown={(e) => e.key === 'Enter' && handleClick(album.release_group_mbid)}
				>
					{#if album.release_group_mbid}
						<div class="w-12 h-12 flex-shrink-0 relative">
							<AlbumImage mbid={album.release_group_mbid} alt={album.title} size="full" className="w-12 h-12 rounded" />
							{#if isInLibrary(album)}
								<div 
									class="absolute -bottom-1 -right-1 rounded-full p-0.5"
									style="background-color: {colors.accent};"
								>
									<svg xmlns="http://www.w3.org/2000/svg" class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="3">
										<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
									</svg>
								</div>
							{:else if isRequested(album)}
								<div 
									class="absolute -bottom-1 -right-1 rounded-full p-0.5"
									style="background-color: {STATUS_COLORS.REQUESTED};"
								>
									<svg xmlns="http://www.w3.org/2000/svg" class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="2">
										<path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
									</svg>
								</div>
							{/if}
						</div>
					{:else}
						<div class="w-12 h-12 flex-shrink-0 bg-base-300 rounded flex items-center justify-center">
							<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
							</svg>
						</div>
					{/if}

					<div class="flex-1 min-w-0">
						<p class="font-medium text-sm truncate">{album.title}</p>
						<p class="text-xs text-base-content/50 truncate">
							{#if album.year}{album.year}{/if}
							{#if album.year && album.listen_count}<span class="mx-1">•</span>{/if}
							{#if album.listen_count}
								{album.listen_count.toLocaleString()} plays
							{/if}
						</p>
					</div>

					{#if album.release_group_mbid && !isInLibrary(album) && !isRequested(album)}
						<button
							type="button"
							class="btn btn-circle btn-sm opacity-0 group-hover:opacity-100 transition-all flex-shrink-0 hover:scale-110 hover:brightness-110"
							style="background-color: {colors.accent}; border: none;"
							onclick={(e) => {
								e.stopPropagation();
								e.preventDefault();
								handleRequest(album);
							}}
							disabled={isRequesting(album)}
							aria-label="Request album"
						>
							{#if isRequesting(album)}
								<span class="loading loading-spinner loading-xs" style="color: {colors.secondary};"></span>
							{:else}
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width="2.5">
									<path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
								</svg>
							{/if}
						</button>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>
