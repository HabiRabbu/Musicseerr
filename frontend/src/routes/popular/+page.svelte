<script lang="ts">
	import TimeRangeView from '$lib/components/TimeRangeView.svelte';
</script>

<svelte:head>
	<title>Popular Albums - Musicseerr</title>
</svelte:head>

<TimeRangeView
	itemType="album"
	endpoint="/api/home/popular/albums"
	title="Popular Right Now"
	subtitle="Most listened albums on ListenBrainz"
	errorEmoji="💿"
/>
