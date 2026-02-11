<script lang="ts">
	import { API, TOAST_DURATION } from '$lib/constants';
	import { toastStore } from '$lib/stores/toast';
	import { launchTrackPlayback } from '$lib/player/launchTrackPlayback';
	import YouTubeIcon from '$lib/components/YouTubeIcon.svelte';
	import PlayIcon from '$lib/components/PlayIcon.svelte';
	import { throwOnApiError, getCoverUrl } from '$lib/utils/errorHandling';
	import type { YouTubeTrackLink, YouTubeTrackLinkResponse, YouTubeQuotaStatus } from '$lib/types';

	interface Props {
		trackNumber: number;
		trackName: string;
		trackLink: YouTubeTrackLink | null;
		allTrackLinks: YouTubeTrackLink[];
		albumId: string;
		albumName: string;
		artistName: string;
		coverUrl: string | null;
		artistId?: string;
		onGenerated: (link: YouTubeTrackLink) => void;
		onQuotaUpdate: (quota: YouTubeQuotaStatus) => void;
	}

	let { trackNumber, trackName, trackLink, allTrackLinks, albumId, albumName, artistName, coverUrl, artistId, onGenerated, onQuotaUpdate }: Props = $props();

	let generating = $state(false);

	const hasLink = $derived(trackLink !== null);
	const playerCoverUrl = $derived(getCoverUrl(coverUrl, albumId));

	function play(): void {
		if (!trackLink) return;
		const idx = allTrackLinks.findIndex((tl) => tl.track_number === trackNumber);
		if (idx === -1) return;
		launchTrackPlayback(allTrackLinks, idx, false, { albumId, albumName, artistName, coverUrl: playerCoverUrl, artistId });
	}

	async function generateLink(): Promise<void> {
		generating = true;
		try {
			const res = await fetch(API.youtube.generateTrack(), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					album_id: albumId,
					album_name: albumName,
					artist_name: artistName,
					track_name: trackName,
					track_number: trackNumber
				})
			});
			await throwOnApiError(res, 'Failed to generate');
			const data: YouTubeTrackLinkResponse = await res.json();
			onGenerated(data.track_link);
			onQuotaUpdate(data.quota);
		} catch (e) {
			toastStore.show({
				message: `Failed: ${trackName} — ${e instanceof Error ? e.message : 'Unknown error'}`,
				type: 'error',
				duration: TOAST_DURATION
			});
		} finally {
			generating = false;
		}
	}

	function handleClick(): void {
		if (hasLink) {
			play();
		} else {
			void generateLink();
		}
	}
</script>

{#if generating}
	<button class="btn btn-sm btn-ghost rounded-lg gap-1.5 ml-auto flex-shrink-0" disabled aria-label="Generating link">
		<span class="loading loading-spinner loading-xs"></span>
		<YouTubeIcon class="h-4 w-4" />
	</button>
{:else}
	<button
		class="btn btn-sm rounded-lg gap-1.5 ml-auto flex-shrink-0"
		style={hasLink ? 'background-color: #FF0000; color: white; border: none;' : ''}
		class:btn-ghost={!hasLink}
		onclick={handleClick}
		aria-label={hasLink ? 'Play on YouTube' : 'Generate YouTube link'}
	>
		{#if hasLink}
			<PlayIcon />
		{:else}
			<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
				<path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
			</svg>
		{/if}
		<YouTubeIcon class="h-4 w-4" />
	</button>
{/if}
