<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		label: string;
		icon?: Snippet;
	}

	let { label, icon }: Props = $props();
</script>

<div class="flex items-center gap-3 pt-6 pb-2 sm:pt-8 sm:pb-3">
	{#if icon}
		<span class="text-base-content/30">
			{@render icon()}
		</span>
	{/if}
	<span
		class="text-[11px] font-semibold uppercase tracking-[0.15em] text-base-content/35 whitespace-nowrap select-none"
	>
		{label}
	</span>
	<div class="h-px flex-1 bg-gradient-to-r from-base-content/8 to-transparent"></div>
</div>
