<script lang="ts">
	interface Props {
		class?: string;
	}

	let { class: className = 'h-4 w-4' }: Props = $props();
</script>

<svg xmlns="http://www.w3.org/2000/svg" class={className} fill="currentColor" viewBox="0 0 24 24">
	<path d="M8 5v14l11-7z" />
</svg>
