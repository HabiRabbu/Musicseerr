<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';

	export let fallback: string = '/';

	function goBack() {
		if (browser && window.history.length > 1) {
			window.history.back();
		} else {
			goto(fallback);
		}
	}
</script>

<button
	on:click={goBack}
	class="btn btn-circle bg-base-300/50 border-none shadow-lg backdrop-blur-sm hover:bg-base-300/70"
	aria-label="Go back"
>
	<svg
		xmlns="http://www.w3.org/2000/svg"
		class="h-6 w-6"
		fill="none"
		viewBox="0 0 24 24"
		stroke="currentColor"
	>
		<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
	</svg>
</button>
