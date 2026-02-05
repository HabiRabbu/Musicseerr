<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		children: Snippet;
		class?: string;
		onNearEnd?: () => void;
	}

	let { children, class: className = '', onNearEnd }: Props = $props();

	let container: HTMLDivElement | undefined = $state();
	let showLeftArrow = $state(false);
	let showRightArrow = $state(true);

	function updateArrows() {
		if (!container) return;
		const { scrollLeft, scrollWidth, clientWidth } = container;
		showLeftArrow = scrollLeft > 10;
		showRightArrow = scrollLeft < scrollWidth - clientWidth - 10;

		if (onNearEnd) {
			const scrollPercentage = (scrollLeft + clientWidth) / scrollWidth;
			if (scrollPercentage > 0.8) onNearEnd();
		}
	}

	function scrollLeft() {
		container?.scrollBy({ left: -container.clientWidth * 0.8, behavior: 'smooth' });
	}

	function scrollRight() {
		container?.scrollBy({ left: container.clientWidth * 0.8, behavior: 'smooth' });
	}

	$effect(() => {
		if (container) setTimeout(updateArrows, 100);
	});
</script>

<div class="relative group/carousel">
	{#if showLeftArrow}
		<button
			class="absolute left-0 top-1/2 -translate-y-1/2 z-10 btn btn-circle btn-sm bg-base-100/90 shadow-lg opacity-0 group-hover/carousel:opacity-100 transition-opacity hidden sm:flex"
			onclick={scrollLeft}
			aria-label="Scroll left"
		>
			<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
				<path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd" />
			</svg>
		</button>
	{/if}

	<div bind:this={container} onscroll={updateArrows} class="flex gap-4 overflow-x-auto scrollbar-hide {className}">
		{@render children()}
	</div>

	{#if showRightArrow}
		<button
			class="absolute right-0 top-1/2 -translate-y-1/2 z-10 btn btn-circle btn-sm bg-base-100/90 shadow-lg opacity-0 group-hover/carousel:opacity-100 transition-opacity hidden sm:flex"
			onclick={scrollRight}
			aria-label="Scroll right"
		>
			<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
				<path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" />
			</svg>
		</button>
	{/if}
</div>

<style>
	.scrollbar-hide {
		-ms-overflow-style: none;
		scrollbar-width: none;
	}
	.scrollbar-hide::-webkit-scrollbar {
		display: none;
	}
</style>
