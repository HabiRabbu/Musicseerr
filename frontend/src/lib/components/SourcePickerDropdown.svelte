<script lang="ts">
	import { ChevronDown, Check } from 'lucide-svelte';
	import { getSourceLabel, getSourceColor } from '$lib/utils/sources';
	import JellyfinIcon from '$lib/components/JellyfinIcon.svelte';
	import LocalFilesIcon from '$lib/components/LocalFilesIcon.svelte';
	import YouTubeIcon from '$lib/components/YouTubeIcon.svelte';

	interface Props {
		currentSource: string;
		availableSources: string[];
		onchange: (source: string) => void;
	}

	let { currentSource, availableSources, onchange }: Props = $props();

	let hasMultiple = $derived(availableSources.length > 1);
	let detailsEl = $state<HTMLDetailsElement | null>(null);

	function handleItemClick(source: string, e: MouseEvent) {
		e.stopPropagation();
		onchange(source);
		if (detailsEl) detailsEl.open = false;
	}

	function handleClickOutside(e: MouseEvent) {
		if (detailsEl?.open && !detailsEl.contains(e.target as Node)) {
			detailsEl.open = false;
		}
	}
</script>

<svelte:window onclick={handleClickOutside} />

{#snippet sourceIcon(source: string, cls: string)}
	{#if source === 'jellyfin'}
		<JellyfinIcon class={cls} />
	{:else if source === 'howler'}
		<LocalFilesIcon class={cls} />
	{:else if source === 'youtube'}
		<YouTubeIcon class={cls} />
	{/if}
{/snippet}

{#if hasMultiple}
	<details bind:this={detailsEl} class="dropdown dropdown-end flex-shrink-0">
		<summary
			class="badge badge-sm gap-1.5 cursor-pointer select-none border-base-content/15 hover:border-base-content/30 transition-colors"
			style="color: {getSourceColor(currentSource)};"
			onclick={(e: MouseEvent) => e.stopPropagation()}
		>
			{@render sourceIcon(currentSource, 'h-3 w-3')}
			<span class="text-xs font-medium">{getSourceLabel(currentSource)}</span>
			<ChevronDown class="h-3 w-3 opacity-50" />
		</summary>
		<ul class="dropdown-content menu bg-base-200/95 backdrop-blur-md rounded-box shadow-xl border border-base-300 p-1 min-w-36 z-50 mt-1">
			{#each availableSources as source}
				<li>
					<button
						class="flex items-center gap-2 text-sm"
						style="color: {getSourceColor(source)};"
						onclick={(e) => handleItemClick(source, e)}
					>
						{@render sourceIcon(source, 'h-4 w-4')}
						<span class="flex-1">{getSourceLabel(source)}</span>
						{#if source === currentSource}
							<Check class="h-3.5 w-3.5" />
						{/if}
					</button>
				</li>
			{/each}
		</ul>
	</details>
{:else}
	<span
		class="badge badge-sm gap-1.5 border-base-content/10 flex-shrink-0"
		style="color: {getSourceColor(currentSource)};"
	>
		{@render sourceIcon(currentSource, 'h-3 w-3')}
		<span class="text-xs font-medium">{getSourceLabel(currentSource)}</span>
	</span>
{/if}
