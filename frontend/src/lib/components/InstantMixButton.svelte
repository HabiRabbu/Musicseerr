<script lang="ts">
	import { Radio } from 'lucide-svelte';

	interface Props {
		label: string;
		loading?: boolean;
		onclick: () => void;
	}

	let { label, loading = false, onclick }: Props = $props();
</script>

<button class="btn btn-sm btn-outline gap-1.5 whitespace-nowrap" {onclick} disabled={loading}>
	<span class:animate-pulse={loading}>
		<Radio class="h-4 w-4" />
	</span>
	{label}
</button>
