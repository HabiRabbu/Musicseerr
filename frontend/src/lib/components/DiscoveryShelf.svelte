<script lang="ts">
	import CarouselSkeleton from '$lib/components/CarouselSkeleton.svelte';
	import { RefreshCw, Sparkles } from 'lucide-svelte';
	import type { Snippet } from 'svelte';

	interface Props {
		title: string;
		loading?: boolean;
		empty?: boolean;
		emptyMessage?: string;
		onrefresh?: () => void;
		actions?: Snippet;
		children: Snippet;
	}

	let {
		title,
		loading = false,
		empty = false,
		emptyMessage = 'Nothing here yet.',
		onrefresh,
		actions,
		children
	}: Props = $props();
</script>

<section class="space-y-3">
	<div class="flex items-center justify-between px-1">
		<div class="flex items-center gap-2">
			<Sparkles class="h-5 w-5 text-secondary" />
			<h2 class="text-lg font-semibold text-base-content sm:text-xl">{title}</h2>
		</div>
		{#if onrefresh}
			<button
				class="btn btn-ghost btn-sm gap-1 text-xs font-medium text-base-content/60 hover:text-base-content"
				onclick={onrefresh}
				disabled={loading}
			>
				<span class:animate-spin={loading}>
					<RefreshCw class="h-4 w-4" />
				</span>
				Refresh
			</button>
		{/if}
	</div>

	{#if loading}
		<CarouselSkeleton />
	{:else}
		{#if actions}{@render actions()}{/if}
		{#if empty}
			<div class="rounded-lg bg-base-200 p-6 text-center">
				<p class="text-sm text-base-content/50">{emptyMessage}</p>
			</div>
		{:else}
			{@render children()}
		{/if}
	{/if}
</section>
