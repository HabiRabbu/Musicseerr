<script lang="ts">
	interface Props {
		elementId?: string;
	}

	let { elementId = 'yt-player-embed' }: Props = $props();
</script>

<div class="rounded-lg shadow-md overflow-hidden" style="width: 120px; height: 68px;">
	<div id={elementId} class="w-full h-full"></div>
</div>
