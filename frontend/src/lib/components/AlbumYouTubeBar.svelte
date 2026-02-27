<script lang="ts">
	import { API, TOAST_DURATION } from '$lib/constants';
	import { toastStore } from '$lib/stores/toast';
	import { launchTrackPlayback } from '$lib/player/launchTrackPlayback';
	import { launchYouTubePlayback } from '$lib/player/launchYouTubePlayback';
	import YouTubeIcon from '$lib/components/YouTubeIcon.svelte';
	import { throwOnApiError, getCoverUrl } from '$lib/utils/errorHandling';
	import { Link, Download, Search , Play} from 'lucide-svelte';
	import type { Track, YouTubeLink, YouTubeLinkResponse, YouTubeTrackLink, YouTubeTrackLinkBatchResponse, YouTubeQuotaStatus } from '$lib/types';

	interface Props {
		albumId: string;
		albumName: string;
		artistName: string;
		artistId: string;
		coverUrl: string | null;
		tracks: Track[];
		trackLinks: YouTubeTrackLink[];
		albumLink: YouTubeLink | null;
		onTrackLinksUpdate: (links: YouTubeTrackLink[]) => void;
		onAlbumLinkUpdate: (link: YouTubeLink) => void;
		onQuotaUpdate: (quota: YouTubeQuotaStatus) => void;
	}

	let { albumId, albumName, artistName, artistId, coverUrl, tracks, trackLinks, albumLink, onTrackLinksUpdate, onAlbumLinkUpdate, onQuotaUpdate }: Props = $props();

	let batchGenerating = $state(false);
	let generatingAlbumLink = $state(false);

	const hasAnyTrackLinks = $derived(trackLinks.length > 0);
	const allTracksGenerated = $derived(trackLinks.length === tracks.length);
	const generatedCount = $derived(trackLinks.length);

	const youtubeSearchUrl = $derived(
		`https://www.youtube.com/results?search_query=${encodeURIComponent(`${artistName} ${albumName} full album`)}`
	);

	function playAll(): void {
		if (trackLinks.length === 0) return;
		launchTrackPlayback(trackLinks, 0, false, { albumId, albumName, artistName, coverUrl, artistId });
	}

	async function generateAlbumLink(): Promise<void> {
		if (albumLink) return;
		generatingAlbumLink = true;
		try {
			const res = await fetch(API.youtube.generate(), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					artist_name: artistName,
					album_name: albumName,
					album_id: albumId,
					cover_url: getCoverUrl(coverUrl, albumId)
				})
			});
			await throwOnApiError(res, 'Failed to generate');
			const data: YouTubeLinkResponse = await res.json();
			onAlbumLinkUpdate(data.link);
			onQuotaUpdate(data.quota);
			toastStore.show({ message: 'Album link generated', type: 'success', duration: TOAST_DURATION });
		} catch (e) {
			toastStore.show({
				message: e instanceof Error ? e.message : 'Failed to generate album link',
				type: 'error',
				duration: TOAST_DURATION
			});
		} finally {
			generatingAlbumLink = false;
		}
	}

	async function generateAllTracks(): Promise<void> {
		const ungeneratedTracks = tracks.filter(
			(t) => !trackLinks.some((tl) => tl.track_number === t.position)
		);
		if (ungeneratedTracks.length === 0) return;

		const cost = ungeneratedTracks.length;
		if (!confirm(`This will use ${cost} YouTube API quota unit${cost > 1 ? 's' : ''}. Continue?`)) return;

		batchGenerating = true;
		try {
			const res = await fetch(API.youtube.generateTracks(), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					album_id: albumId,
					album_name: albumName,
					artist_name: artistName,
					tracks: ungeneratedTracks.map((t) => ({
						track_name: t.title,
						track_number: t.position
					}))
				})
			});
			await throwOnApiError(res, 'Batch generation failed');
			const data: YouTubeTrackLinkBatchResponse = await res.json();
			const existing = trackLinks.filter(
				(tl) => !data.track_links.some((nl) => nl.track_number === tl.track_number)
			);
			onTrackLinksUpdate([...existing, ...data.track_links].sort((a, b) => a.track_number - b.track_number));
			onQuotaUpdate(data.quota);

			if (data.failed.length > 0) {
				toastStore.show({
					message: `${data.failed.length} track${data.failed.length > 1 ? 's' : ''} failed`,
					type: 'error',
					duration: TOAST_DURATION
				});
			} else {
				toastStore.show({ message: 'All tracks generated', type: 'success', duration: TOAST_DURATION });
			}
		} catch (e) {
			toastStore.show({
				message: e instanceof Error ? e.message : 'Batch generation failed',
				type: 'error',
				duration: TOAST_DURATION
			});
		} finally {
			batchGenerating = false;
		}
	}

	async function playAlbumLink(): Promise<void> {
		if (!albumLink?.video_id) return;
		try {
			await launchYouTubePlayback(
				{
					albumId: albumLink.album_id,
					albumName: albumLink.album_name,
					artistName: albumLink.artist_name,
					coverUrl: getCoverUrl(albumLink.cover_url || coverUrl, albumId),
					videoId: albumLink.video_id,
					embedUrl: albumLink.embed_url ?? undefined,
					artistId
				},
				{
					onLoadError: () => {
						toastStore.show({ message: 'Failed to load video', type: 'error', duration: TOAST_DURATION });
					}
				}
			);
		} catch {}
	}
</script>

<div class="bg-base-200/80 rounded-box p-4 shadow-md border border-base-content/5">
	<div class="flex items-center gap-3 flex-wrap">
		<div class="flex items-center gap-2 mr-1">
			<YouTubeIcon class="h-5 w-5 text-red-500" />
			<span class="text-sm font-bold">YouTube</span>
			{#if hasAnyTrackLinks}
				<span class="badge badge-sm badge-neutral">{generatedCount}/{tracks.length}</span>
			{/if}
		</div>

		<div class="flex gap-2 flex-wrap">
			{#if hasAnyTrackLinks}
				<button class="btn btn-sm btn-accent gap-1.5 shadow-sm" onclick={playAll}>
					<Play class="h-4 w-4 fill-current" />
					Play All
				</button>
			{/if}

			{#if albumLink}
				<button class="btn btn-sm btn-ghost gap-1.5" onclick={() => void playAlbumLink()}>
					<Play class="h-4 w-4 fill-current" />
					Full Album
				</button>
			{:else}
				<button class="btn btn-sm gap-1.5" onclick={generateAlbumLink} disabled={generatingAlbumLink}>
					{#if generatingAlbumLink}
						<span class="loading loading-spinner loading-sm"></span>
					{:else}
						<Link class="h-4 w-4" />
					{/if}
					Album Link
				</button>
			{/if}

			{#if !allTracksGenerated}
				<button class="btn btn-sm gap-1.5" onclick={generateAllTracks} disabled={batchGenerating}>
					{#if batchGenerating}
						<span class="loading loading-spinner loading-sm"></span>
					{:else}
						<Download class="h-4 w-4" />
					{/if}
					All Tracks
				</button>
			{/if}

			<a
				href={youtubeSearchUrl}
				target="_blank"
				rel="noopener noreferrer"
				class="btn btn-sm btn-ghost gap-1.5"
			>
				<Search class="h-4 w-4" />
				Search
			</a>
		</div>
	</div>
</div>
