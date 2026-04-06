<script lang="ts">
	import { ChevronLeft, ChevronRight } from 'lucide-svelte';
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
		if (!container) return;

		const observer = new ResizeObserver(() => {
			updateArrows();
		});
		observer.observe(container);

		updateArrows();

		return () => {
			observer.disconnect();
		};
	});
</script>

<div class="relative group/carousel">
	{#if showLeftArrow}
		<button
			class="absolute left-0 top-1/2 z-10 btn btn-circle btn-sm bg-base-100/90 shadow-lg animate-slide-in-left hidden sm:flex"
			onclick={scrollLeft}
			aria-label="Scroll left"
		>
			<ChevronLeft class="w-5 h-5" />
		</button>
	{/if}

	<div
		bind:this={container}
		onscroll={updateArrows}
		class="flex gap-4 overflow-x-auto overflow-y-hidden pb-8 -mb-8 scrollbar-hide snap-x snap-mandatory scroll-pl-4 [&>*]:snap-start {className}"
	>
		{@render children()}
	</div>

	{#if showRightArrow}
		<button
			class="absolute right-0 top-1/2 z-10 btn btn-circle btn-sm bg-base-100/90 shadow-lg animate-slide-in-right hidden sm:flex"
			onclick={scrollRight}
			aria-label="Scroll right"
		>
			<ChevronRight class="w-5 h-5" />
		</button>
	{/if}
</div>
