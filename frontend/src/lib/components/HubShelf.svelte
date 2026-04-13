<script lang="ts">
	import CarouselSkeleton from '$lib/components/CarouselSkeleton.svelte';
	import { ChevronRight } from 'lucide-svelte';
	import type { Snippet } from 'svelte';

	interface Props {
		title: string;
		seeAllHref?: string;
		loading?: boolean;
		children: Snippet;
	}

	let { title, seeAllHref, loading = false, children }: Props = $props();
</script>

<section class="space-y-3">
	<div class="flex items-center justify-between px-1">
		{#if seeAllHref}
			<a
				href={seeAllHref}
				class="group/title flex items-center gap-1 transition-colors hover:text-primary"
			>
				<h2
					class="text-lg font-semibold text-base-content group-hover/title:text-primary sm:text-xl"
				>
					{title}
				</h2>
			</a>
		{:else}
			<h2 class="text-lg font-semibold text-base-content sm:text-xl">{title}</h2>
		{/if}
		{#if seeAllHref}
			<a
				href={seeAllHref}
				class="btn btn-ghost btn-sm gap-1 text-xs font-medium text-base-content/60 hover:text-base-content"
			>
				View all
				<ChevronRight class="h-4 w-4" />
			</a>
		{/if}
	</div>

	<div class="rounded-xl bg-base-100/40 p-4 shadow-sm">
		{#if loading}
			<CarouselSkeleton />
		{:else}
			{@render children()}
		{/if}
	</div>
</section>
