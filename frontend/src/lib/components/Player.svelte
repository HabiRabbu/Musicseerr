<script lang="ts">
	import { playerStore } from '$lib/stores/player.svelte';
	import YouTubePlayer from '$lib/components/YouTubePlayer.svelte';
	import JellyfinIcon from '$lib/components/JellyfinIcon.svelte';
	import { X, Music, Shuffle, SkipBack, AlertCircle, Pause, Play, SkipForward, Volume2, ExternalLink } from 'lucide-svelte';

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
		const videoId = playerStore.nowPlaying?.videoId;
		if (videoId) {
			window.open(`https://www.youtube.com/watch?v=${videoId}`, '_blank');
		}
	}
</script>

{#if playerStore.isPlayerVisible && playerStore.nowPlaying}
	<div
		class="fixed bottom-0 left-0 right-0 z-50 bg-base-300/95 backdrop-blur-md shadow-[0_-4px_20px_rgba(0,0,0,0.3)] transition-transform duration-300"
		style="height: 90px;"
	>
		<!-- Close button -->
		<button
			class="btn btn-ghost btn-xs btn-circle absolute top-1 right-1 opacity-60 hover:opacity-100"
			onclick={() => playerStore.stop()}
			aria-label="Close player"
		>
			<X class="h-3.5 w-3.5" />
		</button>

		<div class="flex items-center h-full px-4 gap-4 max-w-screen-2xl mx-auto">
			<!-- Left: Cover Art + Info -->
			<div class="flex items-center gap-3 min-w-0 w-1/4">
				{#if playerStore.nowPlaying.coverUrl}
					<img
						src={playerStore.nowPlaying.coverUrl}
						alt={playerStore.nowPlaying.albumName}
						class="w-[60px] h-[60px] rounded-lg shadow-lg ring-1 ring-base-content/10 object-cover flex-shrink-0"
					/>
				{:else}
					<div class="w-[60px] h-[60px] rounded-lg shadow-lg bg-base-200 flex items-center justify-center flex-shrink-0">
						<Music class="h-6 w-6 opacity-40" />
					</div>
				{/if}
				<div class="min-w-0">
					{#if playerStore.nowPlaying.trackName}
						<p class="text-sm font-semibold truncate">{playerStore.nowPlaying.trackName}</p>
						<p class="text-xs opacity-60 truncate">
							{#if isAlbumLinkable(playerStore.nowPlaying.albumId)}
								<a href="/album/{playerStore.nowPlaying.albumId}" class="hover:underline">{playerStore.nowPlaying.albumName}</a>
							{:else}
								{playerStore.nowPlaying.albumName}
							{/if}
							{' — '}
							{#if playerStore.nowPlaying.artistId}
								<a href="/artist/{playerStore.nowPlaying.artistId}" class="hover:underline">{playerStore.nowPlaying.artistName}</a>
							{:else}
								{playerStore.nowPlaying.artistName}
							{/if}
						</p>
					{:else}
						<p class="text-sm font-semibold truncate">
							{#if isAlbumLinkable(playerStore.nowPlaying.albumId)}
								<a href="/album/{playerStore.nowPlaying.albumId}" class="hover:underline">{playerStore.nowPlaying.albumName}</a>
							{:else}
								{playerStore.nowPlaying.albumName}
							{/if}
						</p>
						<p class="text-xs opacity-60 truncate">
							{#if playerStore.nowPlaying.artistId}
								<a href="/artist/{playerStore.nowPlaying.artistId}" class="hover:underline">{playerStore.nowPlaying.artistName}</a>
							{:else}
								{playerStore.nowPlaying.artistName}
							{/if}
						</p>
					{/if}
					{#if playerStore.hasQueue}
						<p class="text-xs opacity-40 truncate">Track {playerStore.currentTrackNumber} of {playerStore.queueLength}</p>
					{/if}
					{#if playerStore.playbackState === 'error'}
						<p class="text-xs text-error truncate">Track unavailable</p>
					{/if}
				</div>
			</div>

			<!-- Center: Controls + Progress -->
			<div class="flex flex-col items-center justify-center flex-1 gap-1">
				<!-- Transport Controls -->
				<div class="flex items-center gap-3">
					<!-- Shuffle -->
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

					<!-- Previous -->
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

					<!-- Play/Pause -->
					<button
						class="btn btn-circle btn-accent shadow-md w-10 h-10"
						onclick={() => playerStore.playbackState === 'error' ? playerStore.stop() : playerStore.togglePlay()}
						aria-label={playerStore.playbackState === 'error' ? 'Close' : playerStore.isPlaying ? 'Pause' : 'Play'}
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

					<!-- Next -->
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

				<!-- Progress Bar -->
				<div class="flex items-center gap-2 w-full max-w-lg">
					<span class="text-xs opacity-60 w-10 text-right tabular-nums">{formatTime(playerStore.progress)}</span>
					<input
						type="range"
						class="range range-xs range-accent flex-1"
						min="0"
						max={playerStore.duration || 1}
						value={playerStore.progress}
						oninput={handleSeek}
					/>
					<span class="text-xs opacity-60 w-10 tabular-nums">{formatTime(playerStore.duration)}</span>
				</div>
			</div>

			<!-- Right: Volume + YouTube + Open Link -->
			<div class="flex items-center gap-3 w-1/4 justify-end">
				<!-- Volume -->
				<div class="hidden sm:flex items-center gap-1.5">
					<Volume2 class="h-4 w-4 opacity-60 flex-shrink-0" />
					<input
						type="range"
						class="range range-xs w-20"
						min="0"
						max="100"
						value={playerStore.volume}
						oninput={handleVolume}
					/>
				</div>

				<!-- YouTube mini player -->
				{#if playerStore.nowPlaying.sourceType === 'youtube'}
					<div class="hidden md:block">
						<YouTubePlayer />
					</div>

					<!-- Open in YouTube -->
					<div class="tooltip tooltip-left" data-tip="Open in YouTube">
						<button class="btn btn-ghost btn-sm btn-circle" onclick={openInYouTube} aria-label="Open in YouTube">
							<ExternalLink class="h-4 w-4" />
						</button>
					</div>
				{:else if playerStore.nowPlaying.sourceType === 'jellyfin'}
					<div class="hidden sm:flex items-center gap-2" style="color: rgb(var(--brand-jellyfin))">
						<JellyfinIcon class="h-5 w-5" />
						<span class="text-sm font-medium">Jellyfin</span>
					</div>
				{:else if playerStore.nowPlaying.sourceType === 'howler'}
					<div class="hidden sm:flex items-center gap-2" style="color: rgb(var(--brand-localfiles))">
						<Music class="h-5 w-5" />
						<span class="text-sm font-medium">Local{#if playerStore.currentQueueItem?.format}<span class="badge badge-xs badge-ghost ml-1 uppercase">{playerStore.currentQueueItem.format}</span>{/if}</span>
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
