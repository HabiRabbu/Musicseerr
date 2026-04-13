<script lang="ts">
	import { Clock } from 'lucide-svelte';

	interface TrackRow {
		id: string;
		title: string;
		artist_name: string;
		album_name: string;
		duration_seconds: number;
		codec?: string | null;
		bitrate?: number | null;
	}

	interface Props {
		tracks: TrackRow[];
	}

	let { tracks }: Props = $props();

	function formatDuration(seconds: number): string {
		const m = Math.floor(seconds / 60);
		const s = Math.floor(seconds % 60);
		return `${m}:${s.toString().padStart(2, '0')}`;
	}
</script>

<div class="overflow-x-auto">
	<table class="table table-sm w-full">
		<thead>
			<tr class="text-base-content/60">
				<th scope="col" class="w-12">#</th>
				<th scope="col">Title</th>
				<th scope="col" class="hidden md:table-cell">Artist</th>
				<th scope="col" class="hidden lg:table-cell">Album</th>
				<th scope="col" class="hidden sm:table-cell">
					<span class="flex items-center gap-1">
						<Clock class="h-3.5 w-3.5" />
					</span>
				</th>
				<th scope="col" class="hidden xl:table-cell">Quality</th>
			</tr>
		</thead>
		<tbody>
			{#each tracks as track, i (track.id)}
				<tr class="hover:bg-base-200/50 transition-colors">
					<td class="text-base-content/40 tabular-nums">{i + 1}</td>
					<td>
						<div class="font-medium line-clamp-1">{track.title}</div>
						<div class="text-xs text-base-content/50 md:hidden line-clamp-1">
							{track.artist_name}
						</div>
					</td>
					<td class="hidden md:table-cell text-base-content/70 line-clamp-1">
						{track.artist_name}
					</td>
					<td class="hidden lg:table-cell text-base-content/70 line-clamp-1">
						{track.album_name}
					</td>
					<td class="hidden sm:table-cell text-base-content/50 tabular-nums">
						{formatDuration(track.duration_seconds)}
					</td>
					<td class="hidden xl:table-cell text-base-content/50 text-xs">
						{#if track.codec}
							{track.codec.toUpperCase()}
							{#if track.bitrate}
								- {Math.round(track.bitrate / 1000)} kbps
							{/if}
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
