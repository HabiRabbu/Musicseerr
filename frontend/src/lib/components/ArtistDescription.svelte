<script lang="ts">
	import { colors } from '$lib/colors';
	import { onMount } from 'svelte';

	export let description: string | null | undefined;
	export let loading = false;

	let descriptionExpanded = false;
	let descriptionElement: HTMLElement;
	let showViewMore = false;

	function checkDescriptionHeight() {
		if (descriptionElement && !descriptionExpanded) {
			const lineHeight = parseFloat(getComputedStyle(descriptionElement).lineHeight);
			const actualHeight = descriptionElement.scrollHeight;
			const fourLines = lineHeight * 4;
			showViewMore = actualHeight > fourLines;
		}
	}

	onMount(() => {
		setTimeout(() => checkDescriptionHeight(), 50);
	});

	$: if (description && !loading) {
		setTimeout(() => checkDescriptionHeight(), 50);
	}
</script>

<div class="bg-base-200/50 rounded-box p-4 sm:p-6">
	{#if loading}
		<div class="space-y-2">
			<div class="skeleton h-4 w-full"></div>
			<div class="skeleton h-4 w-full"></div>
			<div class="skeleton h-4 w-3/4"></div>
		</div>
	{:else if description}
		<div class="text-sm sm:text-base text-base-content/80 leading-relaxed">
			{#if descriptionExpanded}
				<div>
					{@html description.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>')}
				</div>
				<button
					class="btn btn-sm mt-3 gap-2"
					style="background-color: {colors.accent}; color: {colors.secondary};"
					on:click={() => (descriptionExpanded = false)}
				>
					Show Less
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="h-4 w-4"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						stroke-width="2"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7" />
					</svg>
				</button>
			{:else}
				<div
					bind:this={descriptionElement}
					class="line-clamp-4 overflow-hidden"
					style="display: -webkit-box; -webkit-box-orient: vertical;"
				>
					{@html description.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>')}
				</div>
				{#if showViewMore}
					<button
						class="btn btn-sm mt-3 gap-2"
						style="background-color: {colors.accent}; color: {colors.secondary};"
						on:click={() => (descriptionExpanded = true)}
					>
						Read More
						<svg
							xmlns="http://www.w3.org/2000/svg"
							class="h-4 w-4"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
							stroke-width="2"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
						</svg>
					</button>
				{/if}
			{/if}
		</div>
	{:else}
		<p class="text-base-content/50 italic text-sm">No biography available</p>
	{/if}
</div>
