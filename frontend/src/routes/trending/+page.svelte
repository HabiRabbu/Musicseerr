<script lang="ts">
	import TimeRangeView from '$lib/components/TimeRangeView.svelte';
</script>

<svelte:head>
	<title>Trending Artists - Musicseerr</title>
</svelte:head>

<TimeRangeView
	itemType="artist"
	endpoint="/api/home/trending/artists"
	title="Trending Artists"
	subtitle="Most listened artists on ListenBrainz"
	errorEmoji="🎤"
/>
