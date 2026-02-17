<script lang="ts">
	import { YOUTUBE_PLAYER_ELEMENT_ID } from '$lib/constants';

	interface Props {
		elementId?: string;
	}

	let { elementId = YOUTUBE_PLAYER_ELEMENT_ID }: Props = $props();
</script>

<div class="rounded-lg shadow-md overflow-hidden" style="width: 120px; height: 68px;">
	<div id={elementId} class="w-full h-full"></div>
</div>
