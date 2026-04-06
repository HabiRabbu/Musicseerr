<script lang="ts">
	import TimeRangeView from '$lib/components/TimeRangeView.svelte';
	import SourceSwitcher from '$lib/components/SourceSwitcher.svelte';
	import { MusicSource } from '$lib/stores/musicSource.svelte';
	import { Mic } from 'lucide-svelte';

	const pageMusicSourceState = new MusicSource(() => 'trending');

	let sourceLabel = $derived(
		pageMusicSourceState.current === 'lastfm' ? 'Last.fm' : 'ListenBrainz'
	);
</script>

<svelte:head>
	<title>Trending Artists - Musicseerr</title>
</svelte:head>

<div class="space-y-4 px-4 sm:px-6 lg:px-8">
	<div class="flex justify-end">
		<SourceSwitcher pageKey="trending" />
	</div>
	<TimeRangeView
		itemType="artist"
		endpoint="/api/v1/home/trending/artists"
		title="Trending Artists"
		subtitle={`Most listened artists on ${sourceLabel}`}
		source={pageMusicSourceState.current}
		errorIcon={Mic}
	/>
</div>
