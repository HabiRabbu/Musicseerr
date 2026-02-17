<script lang="ts">
	import type { Snippet } from 'svelte';
	import PlayIcon from '$lib/components/PlayIcon.svelte';

	interface Props {
		available: boolean;
		sourceColor: string;
		onclick: () => void;
		ariaLabel: string;
		icon: Snippet;
	}

	let { available, sourceColor, onclick, ariaLabel, icon }: Props = $props();
</script>

{#if available}
	<button
		class="btn btn-sm rounded-lg gap-1.5 flex-shrink-0 border-none"
		style="--btn-color: {sourceColor}; background-color: var(--btn-color); color: oklch(98% 0 0);"
		{onclick}
		aria-label={ariaLabel}
	>
		<PlayIcon />
		{@render icon()}
	</button>
{:else}
	<span
		class="btn btn-sm btn-ghost rounded-lg flex-shrink-0 pointer-events-none opacity-30"
		aria-label="Not available"
	>
		—
	</span>
{/if}
