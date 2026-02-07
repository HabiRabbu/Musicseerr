<script lang="ts">
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
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 20 20"
						fill="currentColor"
						class="h-4 w-4 {refreshing ? 'animate-spin' : ''}"
					>
						<path
							fill-rule="evenodd"
							d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H3.989a.75.75 0 00-.75.75v4.242a.75.75 0 001.5 0v-2.43l.31.31a7 7 0 0011.712-3.138.75.75 0 00-1.449-.39zm1.23-3.723a.75.75 0 00.219-.53V2.929a.75.75 0 00-1.5 0v2.43l-.31-.31A7 7 0 003.239 8.188a.75.75 0 101.448.389A5.5 5.5 0 0113.89 6.11l.311.31h-2.432a.75.75 0 000 1.5h4.243a.75.75 0 00.53-.219z"
							clip-rule="evenodd"
						/>
					</svg>
					<span class="hidden sm:inline">{refreshLabel}</span>
				</button>
			</div>
		</div>
	</div>
</div>
