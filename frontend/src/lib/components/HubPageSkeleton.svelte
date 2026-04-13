<script lang="ts">
	import CarouselSkeleton from '$lib/components/CarouselSkeleton.svelte';
</script>

<div class="space-y-8 animate-pulse" role="status" aria-busy="true">
	<span class="sr-only">Loading hub...</span>

	<div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
		{#each Array(3) as _, i (i)}
			<div class="skeleton skeleton-shimmer h-28 rounded-xl"></div>
		{/each}
	</div>

	{#each ['Recently Added', 'Favorites', 'Browse Albums'] as title (title)}
		<section class="space-y-3">
			<div class="skeleton skeleton-shimmer h-6 w-40 rounded"></div>
			<div class="rounded-xl bg-base-100/40 p-4 shadow-sm">
				<CarouselSkeleton />
			</div>
		</section>
	{/each}
</div>
