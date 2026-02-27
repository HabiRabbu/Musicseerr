<script lang="ts">
	import { onMount } from 'svelte';
	import TimeRangeView from '$lib/components/TimeRangeView.svelte';
	import SourceSwitcher from '$lib/components/SourceSwitcher.svelte';
	import { musicSourceStore, type MusicSource } from '$lib/stores/musicSource';

	let source: MusicSource | null = null;

	onMount(async () => {
		await musicSourceStore.load();
		source = musicSourceStore.getPageSource('yourTop');
	});

	function handleSourceChange(nextSource: MusicSource) {
		source = nextSource;
	}

	$: sourceLabel = source === 'lastfm' ? 'Last.fm' : 'ListenBrainz';
</script>

<svelte:head>
	<title>Your Top Albums - Musicseerr</title>
</svelte:head>

<div class="space-y-4 px-4 sm:px-6 lg:px-8">
	<div class="flex justify-end">
		<SourceSwitcher pageKey="yourTop" onSourceChange={handleSourceChange} />
	</div>
	<TimeRangeView
		itemType="album"
		endpoint="/api/home/your-top/albums"
		title="Your Top Albums"
		subtitle={`Your most listened albums on ${sourceLabel}`}
		source={source}
		errorEmoji="💿"
	/>
</div>
