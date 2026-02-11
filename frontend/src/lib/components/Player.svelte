<script lang="ts">
	import { playerStore } from '$lib/stores/player.svelte';
	import YouTubePlayer from '$lib/components/YouTubePlayer.svelte';

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
			<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
				<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
			</svg>
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
						<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
						</svg>
					</div>
				{/if}
				<div class="min-w-0">
					{#if playerStore.nowPlaying.trackName}
						<p class="text-sm font-semibold truncate">{playerStore.nowPlaying.trackName}</p>
						<p class="text-xs opacity-60 truncate">
							<a href="/album/{playerStore.nowPlaying.albumId}" class="hover:underline">{playerStore.nowPlaying.albumName}</a>
							{' — '}
							{#if playerStore.nowPlaying.artistId}
								<a href="/artist/{playerStore.nowPlaying.artistId}" class="hover:underline">{playerStore.nowPlaying.artistName}</a>
							{:else}
								{playerStore.nowPlaying.artistName}
							{/if}
						</p>
					{:else}
						<p class="text-sm font-semibold truncate">
							<a href="/album/{playerStore.nowPlaying.albumId}" class="hover:underline">{playerStore.nowPlaying.albumName}</a>
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
						<p class="text-xs text-error truncate">Video unavailable</p>
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
							<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
								<path stroke-linecap="round" stroke-linejoin="round" d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5" />
							</svg>
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
						<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
							<path d="M6 6h2v12H6zm3.5 6l8.5 6V6z" />
						</svg>
					</button>

					<!-- Play/Pause -->
					<button
						class="btn btn-circle btn-accent shadow-md w-10 h-10"
						onclick={() => playerStore.playbackState === 'error' ? playerStore.stop() : playerStore.togglePlay()}
						aria-label={playerStore.playbackState === 'error' ? 'Close' : playerStore.isPlaying ? 'Pause' : 'Play'}
					>
						{#if playerStore.playbackState === 'error'}
							<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
								<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M12 3a9 9 0 100 18 9 9 0 000-18z" />
							</svg>
						{:else if playerStore.isBuffering}
							<span class="loading loading-spinner loading-sm"></span>
						{:else if playerStore.isPlaying}
							<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
								<path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
							</svg>
						{:else}
							<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
								<path d="M8 5v14l11-7z" />
							</svg>
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
						<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
							<path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
						</svg>
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
					<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 opacity-60 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
						<path stroke-linecap="round" stroke-linejoin="round" d="M15.536 8.464a5 5 0 010 7.072M12 6.253v11.494m0-11.494A5.978 5.978 0 007.582 8.83L4 12l3.582 3.17A5.978 5.978 0 0012 17.747" />
					</svg>
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
							<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
								<path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
							</svg>
						</button>
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
