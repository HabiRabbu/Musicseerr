<script lang="ts">
	let { class: className = 'h-6 w-6', style }: { class?: string; style?: string } = $props();
</script>

<!-- Emby logo: outer circle + inner play triangle -->
<svg
	xmlns="http://www.w3.org/2000/svg"
	viewBox="0 0 24 24"
	fill="none"
	class={className}
	{style}
	aria-hidden="true"
>
	<circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.15" />
	<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5" />
	<polygon points="9.5,8 16.5,12 9.5,16" fill="currentColor" />
</svg>
