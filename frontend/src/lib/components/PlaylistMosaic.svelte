<script lang="ts">
	import { Music } from 'lucide-svelte';

	interface Props {
		coverUrls?: string[];
		customCoverUrl?: string | null;
		size?: string;
		rounded?: string;
	}

	let {
		coverUrls = [],
		customCoverUrl = null,
		size = 'w-32 h-32',
		rounded = 'rounded-box'
	}: Props = $props();

	let imageErrors = $state<Record<number, boolean>>({});

	function handleImageError(index: number) {
		imageErrors[index] = true;
	}

	let urls = $derived(coverUrls.slice(0, 4));
</script>

{#snippet gridFallback()}
	<div
		class="bg-linear-to-br from-base-300 to-base-200 w-full h-full flex items-center justify-center"
	>
		<Music class="w-1/3 h-1/3 text-base-content/30" />
	</div>
{/snippet}

<div class="overflow-hidden {rounded} {size}">
	{#if customCoverUrl}
		<img
			src={customCoverUrl}
			alt="Playlist cover"
			class="object-cover w-full h-full"
			loading="lazy"
		/>
	{:else if urls.length >= 4}
		<div class="grid grid-cols-2 grid-rows-2 w-full h-full gap-0">
			{#each urls as url, i (`${url}-${i}`)}
				{#if imageErrors[i]}
					{@render gridFallback()}
				{:else}
					<img
						src={url}
						alt=""
						class="object-cover w-full h-full"
						loading="lazy"
						onerror={() => handleImageError(i)}
					/>
				{/if}
			{/each}
		</div>
	{:else if urls.length === 3}
		<div class="grid grid-cols-2 grid-rows-2 w-full h-full gap-0">
			{#each urls as url, i (`${url}-${i}`)}
				{#if imageErrors[i]}
					{@render gridFallback()}
				{:else}
					<img
						src={url}
						alt=""
						class="object-cover w-full h-full"
						loading="lazy"
						onerror={() => handleImageError(i)}
					/>
				{/if}
			{/each}
			{@render gridFallback()}
		</div>
	{:else if urls.length === 2}
		<div class="grid grid-cols-2 w-full h-full gap-0">
			{#each urls as url, i (`${url}-${i}`)}
				{#if imageErrors[i]}
					{@render gridFallback()}
				{:else}
					<img
						src={url}
						alt=""
						class="object-cover w-full h-full"
						loading="lazy"
						onerror={() => handleImageError(i)}
					/>
				{/if}
			{/each}
		</div>
	{:else if urls.length === 1}
		{#if imageErrors[0]}
			<div
				class="bg-linear-to-br from-base-300 to-base-200 w-full h-full flex items-center justify-center"
			>
				<Music class="w-1/3 h-1/3 text-base-content/30" />
			</div>
		{:else}
			<img
				src={urls[0]}
				alt="Playlist cover"
				class="object-cover w-full h-full"
				loading="lazy"
				onerror={() => handleImageError(0)}
			/>
		{/if}
	{:else}
		<div
			class="bg-linear-to-br from-base-300 to-base-200 w-full h-full flex items-center justify-center"
		>
			<Music class="w-1/3 h-1/3 text-base-content/30" />
		</div>
	{/if}
</div>
