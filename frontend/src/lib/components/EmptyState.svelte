<script lang="ts">
	import type { ComponentType } from 'svelte';

	interface Props {
		icon: ComponentType;
		title: string;
		description?: string;
		ctaLabel?: string;
		ctaHref?: string;
	}

	let { icon, title, description, ctaLabel, ctaHref }: Props = $props();

	const SvelteComponent = $derived(icon);
</script>

<div class="flex flex-col items-center justify-center py-16 text-center">
	<SvelteComponent class="h-12 w-12 text-base-content/40 mb-4" strokeWidth={1.5} />
	<h3 class="text-xl font-bold mb-1">{title}</h3>
	{#if description}
		<p class="text-sm text-base-content/60 max-w-md">{description}</p>
	{/if}
	{#if ctaLabel && ctaHref}
		<a href={ctaHref} class="btn btn-primary btn-sm mt-4">{ctaLabel}</a>
	{/if}
</div>
