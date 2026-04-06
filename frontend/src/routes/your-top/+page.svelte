<script lang="ts">
	import TimeRangeView from '$lib/components/TimeRangeView.svelte';
	import SourceSwitcher from '$lib/components/SourceSwitcher.svelte';
	import { MusicSource } from '$lib/stores/musicSource.svelte';
	import { Disc3 } from 'lucide-svelte';

	const pageMusicSourceState = new MusicSource(() => 'yourTop');

	let sourceLabel = $derived(
		pageMusicSourceState.current === 'lastfm' ? 'Last.fm' : 'ListenBrainz'
	);
</script>

<svelte:head>
	<title>Your Top Albums - Musicseerr</title>
</svelte:head>

<div class="space-y-4 px-4 sm:px-6 lg:px-8">
	<div class="flex justify-end">
		<SourceSwitcher pageKey="yourTop" />
	</div>
	<TimeRangeView
		itemType="album"
		endpoint="/api/v1/home/your-top/albums"
		title="Your Top Albums"
		subtitle={`Your most listened albums on ${sourceLabel}`}
		source={pageMusicSourceState.current}
		errorIcon={Disc3}
	/>
</div>
