<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		title: string;
		loading?: boolean;
		configured?: boolean;
		hasData?: boolean;
		emptyMessage?: string;
		configureMessage?: string;
		children: Snippet;
		skeletonCount?: number;
	}

	let {
		title,
		loading = false,
		configured = true,
		hasData = true,
		emptyMessage = 'No data available',
		configureMessage = 'Connect ListenBrainz in Settings to see recommendations',
		children,
		skeletonCount = 5
	}: Props = $props();
</script>

<section class="mb-8">
	<h2 class="text-xl font-bold mb-4">{title}</h2>

	{#if loading}
		<div class="flex gap-4 overflow-hidden">
			{#each Array(skeletonCount) as _}
				<div class="w-32 flex-shrink-0">
					<div class="skeleton aspect-square rounded-lg"></div>
					<div class="skeleton h-4 w-3/4 mt-2"></div>
				</div>
			{/each}
		</div>
	{:else if !configured}
		<div class="bg-base-200 rounded-lg p-6 text-center">
			<p class="text-base-content/70">{configureMessage}</p>
			<a href="/settings" class="btn btn-primary btn-sm mt-3">Configure</a>
		</div>
	{:else if !hasData}
		<div class="bg-base-200 rounded-lg p-6 text-center">
			<p class="text-base-content/70">{emptyMessage}</p>
		</div>
	{:else}
		{@render children()}
	{/if}
</section>
