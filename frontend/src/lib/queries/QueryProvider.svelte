<script lang="ts">
	import { type Snippet } from 'svelte';
	import { queryClient } from './QueryClient';
	import { QueryClientProvider } from '@tanstack/svelte-query';
	import { SvelteQueryDevtools } from '@tanstack/svelte-query-devtools';
	import { dev } from '$app/environment';

	type Props = {
		children: Snippet;
	};

	const { children }: Props = $props();
</script>

<QueryClientProvider client={queryClient}>
	{@render children()}
	{#if dev}
		<SvelteQueryDevtools client={queryClient} />
	{/if}
</QueryClientProvider>
