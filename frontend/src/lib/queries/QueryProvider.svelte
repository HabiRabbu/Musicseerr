<script lang="ts">
	import { type Snippet } from 'svelte';
	import { queryClient } from './QueryClient';
	import { QueryClientProvider } from '@tanstack/svelte-query';
	import { SvelteQueryDevtools } from '@tanstack/svelte-query-devtools';

	type Props = {
		children: Snippet;
	};

	const { children }: Props = $props();

	// Uncomment to invalidate queries on manual page reloads, ensuring fresh data after a manual reload
	// onMount(() => {
	// 	const navigationEntry = performance.getEntriesByType(
	// 		'navigation'
	// 	)[0] as PerformanceNavigationTiming;
	// 	if (navigationEntry.type === 'reload') {
	// 		// If the page was reloaded, invalidate all queries
	// 		setTimeout(async () => {
	// 			await queryPersister.restoreQueries(queryClient);
	// 			queryClient.invalidateQueries();
	// 		}, 50); // Slight delay to allow persister to restore queries first
	// 	}
	// });
</script>

<QueryClientProvider client={queryClient}>
	{@render children()}
	<SvelteQueryDevtools client={queryClient} />
</QueryClientProvider>
