<script lang="ts">
	interface Props {
		variant?: 'compact' | 'detailed';
	}

	let { variant = 'compact' }: Props = $props();
</script>

{#if variant === 'detailed'}
	<div class="card bg-base-100 w-full shadow-sm shrink-0">
		<figure class="flex justify-center pt-4">
			<div
				class="skeleton skeleton-shimmer w-28 h-28 sm:w-32 sm:h-32 md:w-36 md:h-36 rounded-full"
			></div>
		</figure>
		<div class="card-body items-center text-center p-3 gap-1">
			<div class="skeleton skeleton-shimmer h-4 w-3/4"></div>
			<div class="skeleton skeleton-shimmer h-3 w-1/2"></div>
			<div class="skeleton skeleton-shimmer h-5 w-2/3 mt-1"></div>
		</div>
	</div>
{:else}
	<div class="card bg-base-100 w-full shadow-sm shrink-0">
		<figure class="flex justify-center pt-4">
			<div class="skeleton skeleton-shimmer w-24 h-24 sm:w-32 sm:h-32 rounded-full"></div>
		</figure>
		<div class="card-body items-center text-center p-2">
			<div class="skeleton skeleton-shimmer h-4 w-3/4"></div>
		</div>
	</div>
{/if}
