<script lang="ts">
	import { Disc3 } from 'lucide-svelte';
	import { nowPlayingMerged } from '$lib/stores/nowPlayingMerged.svelte';

	const session = $derived(nowPlayingMerged.primarySession);
	const progressPct = $derived(
		session?.progress_ms && session?.duration_ms
			? Math.min((session.progress_ms / session.duration_ms) * 100, 100)
			: 0
	);

	function formatTime(ms?: number): string {
		if (!ms) return '0:00';
		const totalSeconds = Math.floor(ms / 1000);
		const minutes = Math.floor(totalSeconds / 60);
		const seconds = totalSeconds % 60;
		return `${minutes}:${seconds.toString().padStart(2, '0')}`;
	}

	const sourceLabels: Record<string, string> = {
		jellyfin: 'Jellyfin',
		navidrome: 'Navidrome',
		plex: 'Plex'
	};
</script>

{#if session}
	<section
		class="mb-6 flex items-center gap-5 rounded-2xl border border-base-content/5 bg-base-200/30 p-4 shadow-lg backdrop-blur-md"
		aria-label="Now playing"
	>
		<div
			class="relative h-24 w-24 flex-shrink-0 overflow-hidden rounded-xl shadow-md sm:h-32 sm:w-32"
		>
			{#if session.cover_url}
				<img
					src={session.cover_url}
					alt="{session.album_name} cover"
					class="h-full w-full object-cover"
					loading="lazy"
				/>
			{:else}
				<div class="flex h-full w-full items-center justify-center bg-base-200">
					<Disc3 class="h-10 w-10 text-base-content/20" />
				</div>
			{/if}
		</div>

		<div class="flex min-w-0 flex-1 flex-col gap-1">
			<div class="flex items-center gap-2">
				<div
					class="now-playing-bars now-playing-bars--sm {session.is_paused
						? 'now-playing-bars--paused'
						: ''}"
				>
					<span></span><span></span><span></span>
				</div>
				<span class="text-xs font-medium uppercase tracking-wide text-base-content/50">
					{session.is_paused ? 'Paused' : 'Now Playing'}
					{#if session.source}
						<span class="ml-1 opacity-60">on {sourceLabels[session.source] ?? session.source}</span>
					{/if}
				</span>
			</div>

			<h2 class="truncate text-lg font-bold leading-tight sm:text-xl">{session.track_name}</h2>
			<p class="truncate text-sm text-base-content/70">{session.artist_name}</p>
			{#if session.album_name}
				<p class="truncate text-xs text-base-content/50">{session.album_name}</p>
			{/if}

			{#if session.duration_ms}
				<div class="mt-1 flex items-center gap-2">
					<span class="text-xs tabular-nums text-base-content/50"
						>{formatTime(session.progress_ms)}</span
					>
					<div class="relative h-1 flex-1 overflow-hidden rounded-full bg-base-content/10">
						<div
							class="absolute inset-y-0 left-0 rounded-full bg-primary transition-[width] duration-1000 ease-linear"
							style="width: {progressPct}%"
						></div>
					</div>
					<span class="text-xs tabular-nums text-base-content/50"
						>{formatTime(session.duration_ms)}</span
					>
				</div>
			{/if}

			{#if session.user_name || session.device_name}
				<p class="mt-0.5 truncate text-xs text-base-content/40">
					{[session.user_name, session.device_name].filter(Boolean).join(' - ')}
				</p>
			{/if}
		</div>
	</section>
{/if}
