<script lang="ts">
	import type { Snippet } from 'svelte';
	import { Shuffle , Play} from 'lucide-svelte';

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
					<Play class="h-4 w-4 fill-current" />
					Play All
				</button>

				<button class="btn btn-sm btn-ghost gap-1.5" onclick={onShuffle}>
					<Shuffle class="h-4 w-4" />
					Shuffle
				</button>
			{/if}
		</div>
	</div>
</div>
