<script lang="ts">
	import { API, TOAST_DURATION } from '$lib/constants';
	import { toastStore } from '$lib/stores/toast';
	import { launchYouTubePlayback } from '$lib/player/launchYouTubePlayback';
	import YouTubeIcon from '$lib/components/YouTubeIcon.svelte';
	import type { YouTubeLink, YouTubeLinkResponse, YouTubeQuotaStatus } from '$lib/types';

	interface Props {
		artistName: string;
		albumName: string;
		albumId: string;
		coverUrl?: string | null;
	}

	let { artistName, albumName, albumId, coverUrl = null }: Props = $props();

	const playerCoverUrl = coverUrl || `/api/covers/release-group/${albumId}?size=250`;

	let savedLink = $state<YouTubeLink | null>(null);
	let loading = $state(false);
	let quota = $state<YouTubeQuotaStatus | null>(null);
	let showQuota = $state(false);
	let fetchSavedLinkRequestId = 0;

	const youtubeSearchUrl = $derived(
		`https://www.youtube.com/results?search_query=${encodeURIComponent(`${artistName} ${albumName} full album`)}`
	);

	async function fetchSavedLink(targetAlbumId: string): Promise<void> {
		const requestId = ++fetchSavedLinkRequestId;
		savedLink = null;
		try {
			const res = await fetch(API.youtube.link(targetAlbumId));
			if (requestId !== fetchSavedLinkRequestId) return;

			if (res.status === 200) {
				savedLink = await res.json();
			} else {
				savedLink = null;
			}
		} catch {
			if (requestId === fetchSavedLinkRequestId) {
				savedLink = null;
			}
		}
	}

	async function generateLink(): Promise<void> {
		loading = true;
		try {
			const res = await fetch(API.youtube.generate(), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					artist_name: artistName,
					album_name: albumName,
					album_id: albumId,
					cover_url: playerCoverUrl
				})
			});
			if (!res.ok) {
				const err = await res.json().catch(() => null);
				throw new Error(err?.detail?.message || err?.detail || 'Failed to generate link');
			}
			const data: YouTubeLinkResponse = await res.json();
			savedLink = data.link;
			quota = data.quota;
			showQuota = true;
			void launchPlayer(data.link);
		} catch (e) {
			toastStore.show({
				message: e instanceof Error ? e.message : 'Failed to generate link',
				type: 'error',
				duration: TOAST_DURATION
			});
		} finally {
			loading = false;
		}
	}

	async function launchPlayer(link: YouTubeLink): Promise<void> {
		closeDropdown();
		try {
			await launchYouTubePlayback(
				{
					albumId: link.album_id,
					albumName: link.album_name,
					artistName: link.artist_name,
					coverUrl: link.cover_url || playerCoverUrl,
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

	function closeDropdown(): void {
		const el = document.activeElement as HTMLElement;
		el?.blur();
	}

	$effect(() => {
		const id = albumId;
		showQuota = false;
		quota = null;
		void fetchSavedLink(id);
	});
</script>

<div class="dropdown dropdown-end">
	<button
		class="btn btn-sm gap-1.5"
		style="background-color: #FF0000; color: white; border: none;"
		tabindex="0"
	>
		<YouTubeIcon class="h-4 w-4" />
		Play
		<svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
			<path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
		</svg>
	</button>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<ul tabindex="0" class="dropdown-content menu bg-base-200 rounded-box shadow-lg w-52 z-50 p-2">
		{#if savedLink}
			<li>
				<button onclick={() => void launchPlayer(savedLink!)}>
					<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
						<path d="M8 5v14l11-7z" />
					</svg>
					Play in Player
				</button>
			</li>
		{:else}
			<li>
				<button onclick={generateLink} disabled={loading}>
					{#if loading}
						<span class="loading loading-spinner loading-xs"></span>
						Generating...
					{:else}
						<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
						</svg>
						Generate Link
					{/if}
				</button>
			</li>
		{/if}
		<li>
			<a href={youtubeSearchUrl} target="_blank" rel="noopener noreferrer">
				<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
					<path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
				</svg>
				Search on YouTube
			</a>
		</li>
	</ul>
</div>

{#if showQuota && quota}
	<div class="flex items-center gap-2 mt-1">
		<progress class="progress progress-accent w-20 h-1.5" value={quota.used} max={quota.limit}></progress>
		<span class="text-xs opacity-60">{quota.remaining} / {quota.limit} remaining</span>
	</div>
{/if}
