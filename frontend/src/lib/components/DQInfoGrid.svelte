<script lang="ts">
	import type { DiscoverQueueEnrichment } from '$lib/types';
	import { countryToFlag } from '$lib/utils/formatting';

	interface Props {
		enrichment: DiscoverQueueEnrichment;
		inLibrary?: boolean;
		showTags?: boolean;
	}

	let { enrichment, inLibrary = false, showTags = true }: Props = $props();
</script>

<div class="flex flex-col gap-2">
	{#if enrichment.release_date}
		<div class="flex items-center gap-2 text-xs text-base-content/60">
			<span class="w-5 text-center shrink-0 text-base-content/40">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					stroke-width="2"
					stroke="currentColor"
					class="w-4 h-4"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
					/>
				</svg>
			</span>
			<div class="flex flex-col gap-px">
				<span class="text-[0.6rem] uppercase tracking-wider font-bold text-base-content/35">Released</span>
				<span class="text-sm font-semibold text-base-content/80">{enrichment.release_date}</span>
			</div>
		</div>
	{/if}
	{#if enrichment.country}
		<div class="flex items-center gap-2 text-xs text-base-content/60">
			<span class="w-5 text-center shrink-0 text-base-content/40">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					stroke-width="2"
					stroke="currentColor"
					class="w-4 h-4"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418"
					/>
				</svg>
			</span>
			<div class="flex flex-col gap-px">
				<span class="text-[0.6rem] uppercase tracking-wider font-bold text-base-content/35">Origin</span>
				<span class="text-sm font-semibold text-base-content/80">{countryToFlag(enrichment.country)} {enrichment.country}</span>
			</div>
		</div>
	{/if}
	{#if enrichment.listen_count != null}
		<div class="flex items-center gap-2 text-xs text-base-content/60">
			<span class="w-5 text-center shrink-0 text-base-content/40">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					stroke-width="2"
					stroke="currentColor"
					class="w-4 h-4"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z"
					/>
				</svg>
			</span>
			<div class="flex flex-col gap-px">
				<span class="text-[0.6rem] uppercase tracking-wider font-bold text-base-content/35">Plays</span>
				<span class="text-sm font-semibold text-base-content/80">{enrichment.listen_count.toLocaleString()}</span>
			</div>
		</div>
	{/if}
	{#if inLibrary}
		<div class="flex items-center gap-2 text-xs text-base-content/60">
			<span class="w-5 text-center shrink-0 text-base-content/40">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
					stroke-width="2"
					stroke="currentColor"
					class="w-4 h-4 text-success"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
			</span>
			<div class="flex flex-col gap-px">
				<span class="text-[0.6rem] uppercase tracking-wider font-bold text-base-content/35">Library</span>
				<span class="text-sm font-semibold text-success">In Library</span>
			</div>
		</div>
	{/if}
</div>
{#if showTags && enrichment.tags.length > 0}
	<div class="flex flex-wrap gap-1 mt-2">
		{#each enrichment.tags.slice(0, 6) as tag}
			<span class="dq-tag">{tag}</span>
		{/each}
	</div>
{/if}

<style>
	.dq-tag {
		font-size: 0.75rem;
		padding: 0.2rem 0.6rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--color-base-100) 5%, transparent);
		backdrop-filter: blur(8px);
		color: color-mix(in srgb, var(--color-base-content) 80%, transparent);
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
		font-weight: 400;
		border: 1px solid color-mix(in srgb, var(--color-base-content) 10%, transparent);
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
		transition: all 0.2s ease;
	}

	.dq-tag:hover {
		border-color: color-mix(in srgb, var(--color-base-content) 30%, transparent);
		background: color-mix(in srgb, var(--color-base-100) 10%, transparent);
	}
</style>
