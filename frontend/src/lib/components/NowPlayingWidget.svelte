<script lang="ts">
	import { Music, Pause } from 'lucide-svelte';
	import AudioQualityBadge from '$lib/components/AudioQualityBadge.svelte';
	import type { NowPlayingSession } from '$lib/types';

	interface Props {
		sessions: NowPlayingSession[];
		coverBuilder?: (session: NowPlayingSession) => string;
	}

	let { sessions, coverBuilder }: Props = $props();

	function formatTime(ms: number): string {
		const totalSeconds = Math.floor(ms / 1000);
		const m = Math.floor(totalSeconds / 60);
		const s = totalSeconds % 60;
		return `${m}:${s.toString().padStart(2, '0')}`;
	}

	function progressPercent(session: NowPlayingSession): number | null {
		if (session.progress_ms == null || session.duration_ms == null || session.duration_ms <= 0)
			return null;
		return Math.min(100, (session.progress_ms / session.duration_ms) * 100);
	}

	function getCoverUrl(session: NowPlayingSession): string {
		if (coverBuilder) return coverBuilder(session);
		return session.cover_url || '';
	}
</script>

{#if sessions.length > 0}
	<section class="space-y-3">
		<div class="flex items-center gap-2 px-1">
			<div class="now-playing-bars">
				<span></span><span></span><span></span>
			</div>
			<h2 class="text-lg font-semibold text-base-content sm:text-xl">Now Playing</h2>
		</div>

		<div class="flex gap-3 overflow-x-auto pb-2">
			{#each sessions as session (session.id)}
				{@const cover = getCoverUrl(session)}
				{@const progress = progressPercent(session)}
				<div
					class="flex min-w-[280px] max-w-[340px] shrink-0 items-center gap-3 rounded-xl bg-base-200/60 p-3 backdrop-blur-sm transition-all"
				>
					{#if cover}
						<div class="relative h-14 w-14 shrink-0 overflow-hidden rounded-lg">
							<img
								src={cover}
								alt={session.album_name}
								class="h-full w-full object-cover"
								loading="lazy"
							/>
							{#if session.is_paused}
								<div class="absolute inset-0 flex items-center justify-center bg-black/40">
									<Pause class="h-5 w-5 text-white" />
								</div>
							{/if}
						</div>
					{:else}
						<div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-base-300">
							<Music class="h-6 w-6 text-base-content/40" />
						</div>
					{/if}

					<div class="min-w-0 flex-1">
						<p class="truncate text-sm font-medium text-base-content">
							{session.track_name}
						</p>
						<p class="truncate text-xs text-base-content/60">
							{session.artist_name}
						</p>
						<div class="mt-0.5 flex items-center gap-1.5 text-[10px] text-base-content/40">
							<span>{session.user_name}</span>
							{#if session.device_name}
								<span>-</span>
								<span>{session.device_name}</span>
							{/if}
							{#if session.audio_codec}
								<span>-</span>
								<AudioQualityBadge codec={session.audio_codec} bitrate={session.bitrate} compact />
							{/if}
						</div>

						{#if progress !== null}
							<div class="mt-1.5 flex items-center gap-1.5">
								<div class="h-1 flex-1 overflow-hidden rounded-full bg-base-300">
									<div
										class="h-full rounded-full bg-primary transition-all duration-1000"
										style="width: {progress}%"
									></div>
								</div>
								{#if session.progress_ms != null && session.duration_ms != null}
									<span class="shrink-0 text-[10px] tabular-nums text-base-content/40">
										{formatTime(session.progress_ms)}/{formatTime(session.duration_ms)}
									</span>
								{/if}
							</div>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	</section>
{/if}
