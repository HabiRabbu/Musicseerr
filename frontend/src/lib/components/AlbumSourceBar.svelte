<script lang="ts">
	import type { Snippet } from 'svelte';
	import PlayIcon from '$lib/components/PlayIcon.svelte';

	interface Props {
		sourceLabel: string;
		sourceColor: string;
		trackCount: number;
		totalTracks: number;
		extraBadge?: string | null;
		onPlayAll: () => void;
		onShuffle: () => void;
		icon: Snippet;
	}

	let {
		sourceLabel,
		sourceColor,
		trackCount,
		totalTracks,
		extraBadge = null,
		onPlayAll,
		onShuffle,
		icon
	}: Props = $props();

	const hasAnyTracks = $derived(trackCount > 0);
</script>

<div class="bg-base-200/80 rounded-box p-4 shadow-md border border-base-content/5">
	<div class="flex items-center gap-3 flex-wrap">
		<div class="flex items-center gap-2 mr-1">
			<span style="color: {sourceColor};">
				{@render icon()}
			</span>
			<span class="text-sm font-bold">{sourceLabel}</span>
			{#if hasAnyTracks}
				<span class="badge badge-sm badge-neutral">{trackCount}/{totalTracks}</span>
			{/if}
			{#if extraBadge}
				<span class="badge badge-sm badge-ghost uppercase">{extraBadge}</span>
			{/if}
		</div>

		<div class="flex gap-2 flex-wrap">
			{#if hasAnyTracks}
				<button class="btn btn-sm btn-accent gap-1.5 shadow-sm" onclick={onPlayAll}>
					<PlayIcon />
					Play All
				</button>

				<button class="btn btn-sm btn-ghost gap-1.5" onclick={onShuffle}>
					<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
						<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12c0-1.232-.046-2.453-.138-3.662a4.006 4.006 0 00-3.7-3.7 48.678 48.678 0 00-7.324 0 4.006 4.006 0 00-3.7 3.7c-.017.22-.032.441-.046.662M19.5 12l3-3m-3 3l-3-3m-12 3c0 1.232.046 2.453.138 3.662a4.006 4.006 0 003.7 3.7 48.656 48.656 0 007.324 0 4.006 4.006 0 003.7-3.7c.017-.22.032-.441.046-.662M4.5 12l3 3m-3-3l-3 3" />
					</svg>
					Shuffle
				</button>
			{/if}
		</div>
	</div>
</div>
