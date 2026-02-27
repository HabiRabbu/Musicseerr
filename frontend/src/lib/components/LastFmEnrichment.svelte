<script lang="ts">
	import type { LastFmArtistEnrichment } from '$lib/types';
	import LastFmInfoCard from './LastFmInfoCard.svelte';

	interface Props {
		enrichment: LastFmArtistEnrichment | null;
		loading?: boolean;
		enabled?: boolean;
	}

	let { enrichment, loading = false, enabled = true }: Props = $props();
</script>

<LastFmInfoCard
	text={enrichment?.bio}
	tags={enrichment?.tags ?? []}
	listeners={enrichment?.listeners ?? 0}
	playcount={enrichment?.playcount ?? 0}
	url={enrichment?.url}
	{loading}
	{enabled}
/>
