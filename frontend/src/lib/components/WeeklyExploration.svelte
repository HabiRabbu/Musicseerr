<script lang="ts">
	import type {
		WeeklyExplorationSection as SectionType,
		YouTubeQuotaStatus,
		TrackCacheCheckItem
	} from '$lib/types';
	import { Sparkles, ExternalLink } from 'lucide-svelte';
	import { onMount } from 'svelte';
	import { API } from '$lib/constants';
	import { api } from '$lib/api/client';
	import HorizontalCarousel from './HorizontalCarousel.svelte';
	import WeeklyExplorationCard from './WeeklyExplorationCard.svelte';
	import { SvelteMap } from 'svelte/reactivity';

	interface Props {
		section: SectionType;
		ytConfigured?: boolean;
	}

	let { section, ytConfigured = false }: Props = $props();

	let activeQuotaIndex = $state<number | null>(null);
	let quotaInfo = $state<YouTubeQuotaStatus | null>(null);
	let cacheMap = new SvelteMap<string, boolean>();

	function cacheKey(artist: string, track: string): string {
		return `${artist.toLowerCase()}|${track.toLowerCase()}`;
	}

	onMount(async () => {
		if (!ytConfigured || section.tracks.length === 0) return;
		try {
			const data = await api.global.post<{ items: TrackCacheCheckItem[] }>(
				API.discoverQueueYoutubeCacheCheck(),
				{
					items: section.tracks.map((t) => ({ artist: t.artist_name, track: t.title }))
				}
			);
			for (const item of data.items) {
				cacheMap.set(cacheKey(item.artist, item.track), item.cached);
			}
		} catch {
			// cache check is best-effort
		}
	});

	function formatPlaylistDate(dateStr: string): string {
		try {
			const d = new Date(dateStr);
			return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
		} catch {
			return '';
		}
	}

	const formattedDate = $derived(formatPlaylistDate(section.playlist_date));
</script>

<section class="my-10">
	<div class="mb-4 flex items-center gap-3">
		<div class="flex items-center gap-2">
			<Sparkles class="h-5 w-5 text-warning" />
			<h2 class="text-lg font-bold text-base-content">Weekly Exploration</h2>
		</div>

		{#if formattedDate}
			<span class="badge badge-ghost badge-sm text-base-content/50">
				{formattedDate}
			</span>
		{/if}

		{#if section.source_url}
			<a
				href={section.source_url}
				target="_blank"
				rel="noopener noreferrer"
				class="ml-auto flex items-center gap-1 text-xs text-base-content/40
					hover:text-primary transition-colors"
				title="View on ListenBrainz"
			>
				ListenBrainz
				<ExternalLink class="h-3 w-3" />
			</a>
		{/if}
	</div>

	<HorizontalCarousel>
		{#each section.tracks as track, i (track.artist_name + track.title)}
			<WeeklyExplorationCard
				{track}
				index={i}
				{ytConfigured}
				initialCached={cacheMap.get(cacheKey(track.artist_name, track.title)) ?? null}
				showQuota={activeQuotaIndex === i}
				{quotaInfo}
			/>
		{/each}
	</HorizontalCarousel>
</section>
