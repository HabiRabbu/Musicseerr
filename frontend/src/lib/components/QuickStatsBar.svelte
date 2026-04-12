<script lang="ts">
	import type { HubStat } from '$lib/types';
	import { ChevronRight } from 'lucide-svelte';

	interface Props {
		stats: HubStat[];
	}

	let { stats }: Props = $props();

	function formatNumber(value: number): string {
		if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
		if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
		return value.toLocaleString();
	}
</script>

<div class="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-4">
	{#each stats as stat (stat.label)}
		{@const Tag = stat.href ? 'a' : 'div'}
		<svelte:element
			this={Tag}
			href={stat.href || undefined}
			class="group relative rounded-xl border border-base-content/5 bg-base-200/30 px-4 py-3 text-center shadow-lg backdrop-blur-md transition-all duration-200 {stat.href ? 'cursor-pointer hover:-translate-y-0.5 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-base-100' : ''}"
		>
			{#if stat.value !== null}
				<div class="text-xl font-bold tabular-nums text-base-content sm:text-2xl">
					{formatNumber(stat.value)}
				</div>
			{:else}
				<div class="skeleton skeleton-shimmer mx-auto h-7 w-16 rounded-md sm:h-8"></div>
			{/if}
			<div class="mt-1 text-xs font-medium uppercase tracking-wider text-base-content/50">
				{stat.label}
			</div>
			{#if stat.href}
				<ChevronRight
					class="absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-base-content/0 transition-all duration-200 group-hover:text-base-content/40"
				/>
			{/if}
		</svelte:element>
	{/each}
</div>
