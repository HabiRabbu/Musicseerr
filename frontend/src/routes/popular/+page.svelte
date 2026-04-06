<script lang="ts">
	import { onMount } from 'svelte';
	import TimeRangeView from '$lib/components/TimeRangeView.svelte';
	import SourceSwitcher from '$lib/components/SourceSwitcher.svelte';
	import { musicSourceStore, type MusicSource } from '$lib/stores/musicSource';
	import { Disc3 } from 'lucide-svelte';

	let source: MusicSource | null = $state(null);

	onMount(async () => {
		await musicSourceStore.load();
		source = musicSourceStore.getPageSource('popular');
	});

	function handleSourceChange(nextSource: MusicSource) {
		source = nextSource;
	}

	let sourceLabel = $derived(source === 'lastfm' ? 'Last.fm' : 'ListenBrainz');
</script>

<svelte:head>
	<title>Popular Albums - Musicseerr</title>
</svelte:head>

<div class="space-y-4 px-4 sm:px-6 lg:px-8">
	<div class="flex justify-end">
		<SourceSwitcher pageKey="popular" onSourceChange={handleSourceChange} />
	</div>
	<TimeRangeView
		itemType="album"
		endpoint="/api/v1/home/popular/albums"
		title="Popular Right Now"
		subtitle={`Most listened albums on ${sourceLabel}`}
		{source}
		errorIcon={Disc3}
	/>
</div>
