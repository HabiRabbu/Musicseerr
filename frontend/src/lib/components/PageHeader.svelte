<script lang="ts">
	import { RefreshCw } from 'lucide-svelte';
	import type { Snippet } from 'svelte';
	import { formatLastUpdated } from '$lib/utils/formatting';

	interface Props {
		title: Snippet;
		subtitle: string;
		gradientClass?: string;
		loading?: boolean;
		refreshing?: boolean;
		isUpdating?: boolean;
		lastUpdated?: Date | null;
		refreshLabel?: string;
		onRefresh: () => void;
	}

	let {
		title,
		subtitle,
		gradientClass = 'bg-gradient-to-br from-primary/30 via-secondary/20 to-accent/10',
		loading = false,
		refreshing = false,
		isUpdating = false,
		lastUpdated = null,
		refreshLabel = 'Refresh',
		onRefresh
	}: Props = $props();
</script>

<div class="relative mb-6 overflow-hidden {gradientClass}">
	<div class="absolute inset-0 bg-gradient-to-t from-base-100 to-transparent"></div>
	<div class="relative px-4 py-8 sm:px-6 sm:py-12 lg:px-8">
		<div class="flex items-start justify-between">
			<div>
				<h1 class="mb-2 text-3xl font-bold sm:text-4xl lg:text-5xl">
					{@render title()}
				</h1>
				<p class="max-w-xl text-sm text-base-content/70 sm:text-base">
					{subtitle}
				</p>
			</div>
			<div class="flex items-center gap-2">
				{#if isUpdating}
					<span class="badge badge-ghost badge-sm gap-1">
						<span class="loading loading-spinner loading-xs"></span>
						Updating...
					</span>
				{:else if lastUpdated && !loading}
					<span class="hidden text-xs text-base-content/50 sm:inline">
						Updated {formatLastUpdated(lastUpdated)}
					</span>
				{/if}
				<button
					class="btn btn-sm btn-primary gap-1"
					onclick={onRefresh}
					disabled={refreshing || loading}
					title={refreshLabel}
				>
					<RefreshCw class="h-4 w-4 {refreshing ? 'animate-spin' : ''}" />
					<span class="hidden sm:inline">{refreshLabel}</span>
				</button>
			</div>
		</div>
	</div>
</div>
