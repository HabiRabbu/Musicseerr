<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { API, TOAST_DURATION } from '$lib/constants';
	import { toastStore } from '$lib/stores/toast';
	import { launchYouTubePlayback } from '$lib/player/launchYouTubePlayback';
	import YouTubeIcon from '$lib/components/YouTubeIcon.svelte';
	import AlbumImage from '$lib/components/AlbumImage.svelte';
	import type { YouTubeLink } from '$lib/types';

	let links = $state<YouTubeLink[]>([]);
	let loading = $state(true);
	let deleting = $state<string | null>(null);

	async function fetchLinks(): Promise<void> {
		loading = true;
		try {
			const res = await fetch(API.youtube.links());
			if (res.ok) links = await res.json();
		} catch {} finally {
			loading = false;
		}
	}

	async function deleteLink(albumId: string): Promise<void> {
		deleting = albumId;
		try {
			const res = await fetch(API.youtube.deleteLink(albumId), { method: 'DELETE' });
			if (res.ok) {
				links = links.filter((l) => l.album_id !== albumId);
				toastStore.show({ message: 'Link removed', type: 'success', duration: TOAST_DURATION });
			}
		} catch {
			toastStore.show({ message: 'Failed to delete link', type: 'error', duration: TOAST_DURATION });
		} finally {
			deleting = null;
		}
	}

	async function playLink(link: YouTubeLink): Promise<void> {
		try {
			await launchYouTubePlayback(
				{
					albumId: link.album_id,
					albumName: link.album_name,
					artistName: link.artist_name,
					coverUrl: link.cover_url || `/api/covers/release-group/${link.album_id}?size=250`,
					videoId: link.video_id,
					embedUrl: link.embed_url
				},
				{
					onLoadError: () => {
						toastStore.show({ message: 'Failed to load video', type: 'error', duration: TOAST_DURATION });
					}
				}
			);
		} catch {}
	}

	onMount(() => {
		fetchLinks();
	});
</script>

<div class="container mx-auto p-6">
	<div class="flex items-center gap-3 mb-6">
		<YouTubeIcon class="h-8 w-8 text-red-500" />
		<h1 class="text-2xl font-bold">YouTube Links</h1>
		<span class="badge badge-neutral">{links.length}</span>
	</div>

	{#if loading}
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
			{#each Array(12) as _}
				<div class="card bg-base-100 shadow-sm animate-pulse">
					<div class="aspect-square bg-base-300"></div>
					<div class="card-body p-3">
						<div class="h-4 bg-base-300 rounded w-3/4"></div>
						<div class="h-3 bg-base-300 rounded w-1/2 mt-1"></div>
					</div>
				</div>
			{/each}
		</div>
	{:else if links.length === 0}
		<div class="card bg-base-200">
			<div class="card-body items-center text-center">
				<YouTubeIcon class="h-12 w-12 opacity-20" />
				<p class="text-lg opacity-60">No saved YouTube links</p>
				<p class="text-sm opacity-40">Generate links from album pages and they'll appear here.</p>
			</div>
		</div>
	{:else}
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
			{#each links as link (link.album_id)}
				<div
					class="card bg-base-100 w-full shadow-sm group relative cursor-pointer transition-transform hover:scale-105 hover:shadow-lg active:scale-95"
					onclick={() => goto(`/album/${link.album_id}`)}
					onkeydown={(e) => e.key === 'Enter' && goto(`/album/${link.album_id}`)}
					role="button"
					tabindex="0"
				>
					<figure class="aspect-square overflow-hidden relative">
						<AlbumImage
							mbid={link.album_id}
							customUrl={link.cover_url}
							alt={link.album_name}
							size="full"
							rounded="none"
							className="w-full h-full"
						/>
						<!-- Play overlay -->
							<button
								class="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity"
								onclick={(e) => { e.stopPropagation(); void playLink(link); }}
								aria-label="Play {link.album_name}"
							>
							<div class="btn btn-circle btn-accent shadow-lg">
								<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
									<path d="M8 5v14l11-7z" />
								</svg>
							</div>
						</button>
						<!-- YouTube badge -->
						<div class="absolute top-2 left-2">
							<div class="badge badge-sm gap-1" style="background-color: #FF0000; color: white; border: none;">
								<YouTubeIcon class="h-3 w-3" />
							</div>
						</div>
					</figure>

					<div class="card-body p-3">
						<h2 class="card-title text-sm line-clamp-2 min-h-[2.5rem]">{link.album_name}</h2>
						<p class="text-xs opacity-70 line-clamp-1">{link.artist_name}</p>
					</div>

					<!-- Delete button -->
					<button
						class="absolute bottom-2 right-2 btn btn-square btn-sm opacity-0 group-hover:opacity-100 transition-opacity duration-200 btn-error"
						onclick={(e) => { e.stopPropagation(); deleteLink(link.album_id); }}
						disabled={deleting === link.album_id}
						aria-label="Delete link"
					>
						{#if deleting === link.album_id}
							<span class="loading loading-spinner loading-xs"></span>
						{:else}
							<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
								<path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
							</svg>
						{/if}
					</button>
				</div>
			{/each}
		</div>
	{/if}
</div>
