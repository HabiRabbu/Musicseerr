<script lang="ts">
	import { playerStore } from '$lib/stores/player.svelte';
	import { eqStore } from '$lib/stores/eq.svelte';
	import { scrobbleManager } from '$lib/stores/scrobble.svelte';
	import YouTubePlayer from '$lib/components/YouTubePlayer.svelte';
	import JellyfinIcon from '$lib/components/JellyfinIcon.svelte';
	import NavidromeIcon from '$lib/components/NavidromeIcon.svelte';
	import QueueDrawer from '$lib/components/QueueDrawer.svelte';
	import EqPanel from '$lib/components/EqPanel.svelte';
	import NowPlayingIndicator from '$lib/components/NowPlayingIndicator.svelte';
	import { getCoverUrl } from '$lib/utils/errorHandling';
	import {
		X,
		Music,
		Shuffle,
		SkipBack,
		AlertCircle,
		Pause,
		Play,
		SkipForward,
		Volume2,
		ExternalLink,
		Check,
		CircleX,
		ListMusic,
		SlidersHorizontal
	} from 'lucide-svelte';

	let coverImgError = $state(false);
	let lastCoverKey = '';
	let eqPanelOpen = $state(false);
	let queueDrawerOpen = $state(false);

	function formatTime(seconds: number): string {
		if (!seconds || isNaN(seconds)) return '0:00';
		const mins = Math.floor(seconds / 60);
		const secs = Math.floor(seconds % 60);
		return `${mins}:${secs.toString().padStart(2, '0')}`;
	}

	function handleSeek(e: Event): void {
		const target = e.target as HTMLInputElement;
		playerStore.seekTo(Number(target.value));
	}

	function handleVolume(e: Event): void {
		const target = e.target as HTMLInputElement;
		playerStore.setVolume(Number(target.value));
	}

	const MBID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

	function isAlbumLinkable(id: string | undefined): boolean {
		return !!id && MBID_RE.test(id);
	}

	function openInYouTube(): void {
		const trackSourceId = playerStore.nowPlaying?.trackSourceId;
		if (trackSourceId) {
			window.open(`https://www.youtube.com/watch?v=${trackSourceId}`, '_blank');
		}
	}

	const nowPlayingCoverUrl = $derived.by(() => {
		const np = playerStore.nowPlaying;
		if (!np) return null;
		return getCoverUrl(np.coverUrl, np.albumId);
	});

	$effect(() => {
		const np = playerStore.nowPlaying;
		if (!np) return;
		const key = `${np.albumId}:${np.coverUrl ?? ''}`;
		if (key !== lastCoverKey) {
			lastCoverKey = key;
			coverImgError = false;
		}
	});
</script>

{#if playerStore.isPlayerVisible && playerStore.nowPlaying}
	<div
		class="fixed bottom-0 left-0 right-0 z-50 bg-base-300/95 backdrop-blur-md shadow-[0_-4px_20px_rgba(0,0,0,0.3)] transition-transform duration-300"
		style="height: 90px;"
	>
		<button
			class="btn btn-ghost btn-xs btn-circle absolute top-1 right-1 opacity-60 hover:opacity-100"
			onclick={() => playerStore.stop()}
			aria-label="Close player"
		>
			<X class="h-3.5 w-3.5" />
		</button>

		<div class="flex items-center h-full px-4 gap-4 max-w-screen-2xl mx-auto">
			<div class="flex items-center gap-3 min-w-0 w-1/4">
				{#if nowPlayingCoverUrl && !coverImgError}
					<img
						src={nowPlayingCoverUrl}
						alt={playerStore.nowPlaying.albumName}
						class="w-15 h-15 rounded-lg shadow-lg ring-1 ring-base-content/10 object-cover shrink-0"
						onerror={() => {
							coverImgError = true;
						}}
					/>
				{:else}
					<div
						class="w-15 h-15 rounded-lg shadow-lg bg-base-200 flex items-center justify-center shrink-0"
					>
						<Music class="h-6 w-6 opacity-40" />
					</div>
				{/if}
				{#if playerStore.isPlaying}
					<NowPlayingIndicator size="md" />
				{/if}
				<div class="min-w-0">
					{#if playerStore.nowPlaying.trackName}
						<p class="text-sm font-semibold truncate">{playerStore.nowPlaying.trackName}</p>
						<p class="text-xs opacity-60 truncate">
							{#if isAlbumLinkable(playerStore.nowPlaying.albumId)}
								<a href="/album/{playerStore.nowPlaying.albumId}" class="hover:underline"
									>{playerStore.nowPlaying.albumName}</a
								>
							{:else}
								{playerStore.nowPlaying.albumName}
							{/if}
							—
							{#if playerStore.nowPlaying.artistId}
								<a href="/artist/{playerStore.nowPlaying.artistId}" class="hover:underline"
									>{playerStore.nowPlaying.artistName}</a
								>
							{:else}
								{playerStore.nowPlaying.artistName}
							{/if}
						</p>
					{:else}
						<p class="text-sm font-semibold truncate">
							{#if isAlbumLinkable(playerStore.nowPlaying.albumId)}
								<a href="/album/{playerStore.nowPlaying.albumId}" class="hover:underline"
									>{playerStore.nowPlaying.albumName}</a
								>
							{:else}
								{playerStore.nowPlaying.albumName}
							{/if}
						</p>
						<p class="text-xs opacity-60 truncate">
							{#if playerStore.nowPlaying.artistId}
								<a href="/artist/{playerStore.nowPlaying.artistId}" class="hover:underline"
									>{playerStore.nowPlaying.artistName}</a
								>
							{:else}
								{playerStore.nowPlaying.artistName}
							{/if}
						</p>
					{/if}
					{#if playerStore.hasQueue}
						<p class="text-xs opacity-40 truncate">
							Track {playerStore.currentTrackNumber} of {playerStore.queueLength}
						</p>
					{/if}
					{#if playerStore.playbackState === 'error'}
						<p class="text-xs text-error truncate">Track unavailable</p>
					{/if}
				</div>
			</div>

			<div class="flex flex-col items-center justify-center flex-1 gap-1">
				<div class="flex items-center gap-3">
					{#if playerStore.hasQueue}
						<button
							class="btn btn-ghost btn-sm btn-circle"
							class:text-accent={playerStore.shuffleEnabled}
							class:opacity-50={!playerStore.shuffleEnabled}
							onclick={() => playerStore.toggleShuffle()}
							aria-label="Toggle shuffle"
						>
							<Shuffle class="h-4 w-4" />
						</button>
					{/if}

					<button
						class="btn btn-ghost btn-sm btn-circle"
						class:opacity-30={!playerStore.hasPrevious}
						class:cursor-not-allowed={!playerStore.hasPrevious}
						disabled={!playerStore.hasPrevious}
						onclick={() => playerStore.previousTrack()}
						aria-label="Previous"
					>
						<SkipBack class="h-4 w-4 fill-current" />
					</button>

					<button
						class="btn btn-circle btn-accent shadow-md w-10 h-10"
						onclick={() =>
							playerStore.playbackState === 'error' ? playerStore.stop() : playerStore.togglePlay()}
						aria-label={playerStore.playbackState === 'error'
							? 'Close'
							: playerStore.isPlaying
								? 'Pause'
								: 'Play'}
					>
						{#if playerStore.playbackState === 'error'}
							<AlertCircle class="h-5 w-5" />
						{:else if playerStore.isBuffering}
							<span class="loading loading-spinner loading-sm"></span>
						{:else if playerStore.isPlaying}
							<Pause class="h-5 w-5 fill-current" />
						{:else}
							<Play class="h-5 w-5 ml-0.5 fill-current" />
						{/if}
					</button>

					<button
						class="btn btn-ghost btn-sm btn-circle"
						class:opacity-30={!playerStore.hasNext}
						class:cursor-not-allowed={!playerStore.hasNext}
						disabled={!playerStore.hasNext}
						onclick={() => playerStore.nextTrack()}
						aria-label="Next"
					>
						<SkipForward class="h-4 w-4 fill-current" />
					</button>
				</div>

				<div class="flex items-center gap-2 w-full max-w-lg">
					<span class="text-xs opacity-60 w-10 text-right tabular-nums"
						>{formatTime(playerStore.progress)}</span
					>
					<input
						type="range"
						class="range range-xs range-accent flex-1"
						class:opacity-50={!playerStore.isSeekable}
						class:cursor-not-allowed={!playerStore.isSeekable}
						min="0"
						max={playerStore.duration || 1}
						value={playerStore.progress}
						disabled={!playerStore.isSeekable}
						oninput={handleSeek}
					/>
					<span class="text-xs opacity-60 w-10 tabular-nums"
						>{formatTime(playerStore.duration)}</span
					>
				</div>
				{#if !playerStore.isSeekable}
					<p class="text-[10px] text-base-content/60">Seeking unavailable for this stream format</p>
				{/if}
			</div>

			<div class="flex items-center gap-3 lg:gap-7 w-1/4 justify-end">
				<div class="tooltip tooltip-left" data-tip="Queue">
					<button
						class="btn btn-ghost btn-sm btn-circle relative"
						class:text-accent={queueDrawerOpen}
						onclick={() => (queueDrawerOpen = !queueDrawerOpen)}
						aria-label="Toggle queue"
					>
						<ListMusic class="h-4 w-4" />
						{#if playerStore.upcomingQueueLength > 0}
							<span class="badge badge-xs badge-accent absolute -top-1 -right-1"
								>{playerStore.upcomingQueueLength}</span
							>
						{/if}
					</button>
				</div>

				<div
					class="tooltip tooltip-left"
					data-tip={playerStore.nowPlaying?.sourceType === 'youtube'
						? 'EQ unavailable for YouTube'
						: 'Equalizer'}
				>
					<button
						class="btn btn-ghost btn-sm btn-circle"
						class:text-accent={eqStore.enabled && playerStore.nowPlaying?.sourceType !== 'youtube'}
						class:opacity-30={playerStore.nowPlaying?.sourceType === 'youtube'}
						onclick={() => (eqPanelOpen = !eqPanelOpen)}
						aria-label="Toggle equalizer"
					>
						<SlidersHorizontal class="h-4 w-4" />
					</button>
				</div>

				<div class="hidden sm:flex items-center gap-1.5">
					<Volume2 class="h-4 w-4 opacity-60 shrink-0" />
					<input
						type="range"
						class="range range-xs w-20"
						min="0"
						max="100"
						value={playerStore.volume}
						oninput={handleVolume}
					/>
				</div>

				{#if scrobbleManager.enabled && scrobbleManager.status !== 'idle'}
					<div class="tooltip tooltip-left" data-tip={scrobbleManager.tooltip}>
						{#if scrobbleManager.status === 'scrobbled'}
							<Check class="h-4 w-4 text-success" />
						{:else if scrobbleManager.status === 'error'}
							<CircleX class="h-4 w-4 text-error" />
						{:else}
							<span class="badge badge-info badge-sm gap-1 font-semibold">
								<span class="status status-md status-info"></span>
								Tracking
							</span>
						{/if}
					</div>
				{/if}

				{#if playerStore.nowPlaying.sourceType === 'youtube'}
					<div class="hidden md:block">
						<YouTubePlayer />
					</div>

					<div class="tooltip tooltip-left" data-tip="Open in YouTube">
						<button
							class="btn btn-ghost btn-sm btn-circle"
							onclick={openInYouTube}
							aria-label="Open in YouTube"
						>
							<ExternalLink class="h-4 w-4" />
						</button>
					</div>
				{:else if playerStore.nowPlaying.sourceType === 'jellyfin'}
					<div class="hidden sm:flex items-center gap-2" style="color: rgb(var(--brand-jellyfin))">
						<JellyfinIcon class="h-5 w-5" />
						<span class="text-sm font-medium">Jellyfin</span>
					</div>
				{:else if playerStore.nowPlaying.sourceType === 'navidrome'}
					<div class="hidden sm:flex items-center gap-2" style="color: rgb(var(--brand-navidrome))">
						<NavidromeIcon class="h-5 w-5" />
						<span class="text-sm font-medium">Navidrome</span>
					</div>
				{:else if playerStore.nowPlaying.sourceType === 'local'}
					<div
						class="hidden sm:flex items-center gap-2"
						style="color: rgb(var(--brand-localfiles))"
					>
						<Music class="h-5 w-5" />
						<span class="text-sm font-medium"
							>Local{#if playerStore.currentQueueItem?.format}<span
									class="badge badge-xs badge-ghost ml-1 uppercase"
									>{playerStore.currentQueueItem.format}</span
								>{/if}</span
						>
					</div>
				{/if}
			</div>
		</div>
	</div>

	<QueueDrawer bind:open={queueDrawerOpen} onclose={() => (queueDrawerOpen = false)} />
	<EqPanel bind:open={eqPanelOpen} onclose={() => (eqPanelOpen = false)} />
{/if}
