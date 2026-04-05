<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { ChevronLeft } from 'lucide-svelte';

	interface Props {
		fallback?: string;
	}

	let { fallback = '/' }: Props = $props();

	function goBack() {
		if (browser && window.history.length > 1) {
			window.history.back();
		} else {
			goto(fallback);
		}
	}
</script>

<button
	onclick={goBack}
	class="btn btn-circle bg-base-300/50 border-none shadow-lg backdrop-blur-sm hover:bg-base-300/70"
	aria-label="Go back"
>
	<ChevronLeft class="h-6 w-6" />
</button>
