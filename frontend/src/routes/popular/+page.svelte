<script lang="ts">
	import TimeRangeView from '$lib/components/TimeRangeView.svelte';
	import { type MusicSource } from '$lib/stores/musicSource';
	import { Disc3 } from 'lucide-svelte';
	import type { PageProps } from './$types';
	import { PersistedState } from 'runed';
	import { PAGE_SOURCE_KEYS } from '$lib/constants';
	import SimpleSourceSwitcher from '$lib/components/SimpleSourceSwitcher.svelte';

	const { data }: PageProps = $props();

	// svelte-ignore state_referenced_locally
	let activeSource = new PersistedState<MusicSource>(
		PAGE_SOURCE_KEYS['popular'],
		data.primarySource
	);

	function handleSourceChange(nextSource: MusicSource) {
		activeSource.current = nextSource;
	}

	let sourceLabel = $derived(activeSource.current === 'lastfm' ? 'Last.fm' : 'ListenBrainz');
</script>

<svelte:head>
	<title>Popular Albums - Musicseerr</title>
</svelte:head>

<div class="space-y-4 px-4 sm:px-6 lg:px-8">
	<div class="flex justify-end">
		<SimpleSourceSwitcher
			currentSource={activeSource.current}
			onSourceChange={handleSourceChange}
		/>
	</div>
	<TimeRangeView
		itemType="album"
		endpoint="/api/v1/home/popular/albums"
		title="Popular Right Now"
		subtitle={`Most listened albums on ${sourceLabel}`}
		source={activeSource.current}
		errorIcon={Disc3}
	/>
</div>
