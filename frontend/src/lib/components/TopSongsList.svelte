<script lang="ts">
	import type { TopSong } from '$lib/types';
	import TrackRow from './TrackRow.svelte';

	interface Props {
		songs: TopSong[];
		loading?: boolean;
		configured?: boolean;
	}

	let { songs, loading = false, configured = true }: Props = $props();
</script>

<div class="flex flex-col min-w-0">
	<h3 class="text-lg font-semibold mb-3">Popular Songs</h3>

	{#if loading}
		<div class="space-y-2">
			{#each Array(10) as _, i}
				<div class="flex items-center gap-3 p-2">
					<div class="skeleton w-6 h-4"></div>
					<div class="skeleton w-12 h-12 rounded"></div>
					<div class="flex-1 flex items-center gap-4">
						<div class="skeleton h-4 w-1/2"></div>
						<div class="skeleton h-3 w-1/3 ml-auto"></div>
					</div>
				</div>
			{/each}
		</div>
	{:else if !configured}
		<div class="bg-base-200 rounded-lg p-4 text-center flex-1 flex items-center justify-center">
			<div>
				<p class="text-base-content/70 text-sm">Connect ListenBrainz to see popular songs</p>
				<a href="/settings" class="btn btn-primary btn-xs mt-2">Configure</a>
			</div>
		</div>
	{:else if songs.length === 0}
		<div class="bg-base-200 rounded-lg p-4 text-center flex-1 flex items-center justify-center">
			<p class="text-base-content/70 text-sm">No song data available</p>
		</div>
	{:else}
		<div class="space-y-1">
			{#each songs as song, i}
				<TrackRow {song} position={i + 1} />
			{/each}
		</div>
	{/if}
</div>
