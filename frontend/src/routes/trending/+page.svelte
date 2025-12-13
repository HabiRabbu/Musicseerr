<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import ArtistImage from '$lib/components/ArtistImage.svelte';
	import type {
		TrendingArtistsResponse,
		TrendingArtistsRangeResponse,
		HomeArtist
	} from '$lib/types';

	type TimeRangeKey = 'this_week' | 'this_month' | 'this_year' | 'all_time';

	const timeRanges: { key: TimeRangeKey; label: string }[] = [
		{ key: 'this_week', label: 'This Week' },
		{ key: 'this_month', label: 'This Month' },
		{ key: 'this_year', label: 'This Year' },
		{ key: 'all_time', label: 'All Time' }
	];

	let overviewData: TrendingArtistsResponse | null = null;
	let expandedRange: TimeRangeKey | null = null;
	let expandedData: TrendingArtistsRangeResponse | null = null;
	let loading = true;
	let loadingMore = false;

	onMount(async () => {
		await loadOverview();
	});

	async function loadOverview() {
		loading = true;
		try {
			const res = await fetch('/api/home/trending/artists?limit=10');
			if (res.ok) {
				overviewData = await res.json();
			}
		} catch (e) {
			console.error('Failed to load trending artists:', e);
		} finally {
			loading = false;
		}
	}

	async function expandRange(rangeKey: TimeRangeKey) {
		if (expandedRange === rangeKey) {
			expandedRange = null;
			expandedData = null;
			return;
		}

		expandedRange = rangeKey;
		loadingMore = true;
		try {
			const res = await fetch(`/api/home/trending/artists/${rangeKey}?limit=25&offset=0`);
			if (res.ok) {
				expandedData = await res.json();
			}
		} catch (e) {
			console.error('Failed to load expanded range:', e);
		} finally {
			loadingMore = false;
		}
	}

	async function loadMore() {
		if (!expandedRange || !expandedData || loadingMore || !expandedData.has_more) return;

		loadingMore = true;
		try {
			const newOffset = expandedData.offset + expandedData.limit;
			const res = await fetch(
				`/api/home/trending/artists/${expandedRange}?limit=25&offset=${newOffset}`
			);
			if (res.ok) {
				const moreData: TrendingArtistsRangeResponse = await res.json();
				expandedData = {
					...moreData,
					items: [...expandedData.items, ...moreData.items]
				};
			}
		} catch (e) {
			console.error('Failed to load more:', e);
		} finally {
			loadingMore = false;
		}
	}

	function handleArtistClick(artist: HomeArtist) {
		if (artist.mbid) {
			goto(`/artist/${artist.mbid}`);
		}
	}

	function formatListenCount(count: number | null): string {
		if (!count) return '';
		if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
		if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
		return `${count}`;
	}

	function getItemsForRange(rangeKey: TimeRangeKey): HomeArtist[] {
		if (!overviewData) return [];
		return overviewData[rangeKey]?.items || [];
	}

	function getFeaturedForRange(rangeKey: TimeRangeKey): HomeArtist | null {
		if (!overviewData) return null;
		return overviewData[rangeKey]?.featured || null;
	}
</script>

<svelte:head>
	<title>Trending Artists - Musicseerr</title>
</svelte:head>

<div class="container mx-auto p-4 md:p-6 lg:p-8">
	<div class="mb-6 flex items-center gap-4">
		<button class="btn btn-circle btn-ghost" on:click={() => goto('/')} aria-label="Back to home">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
				stroke-width="2"
				stroke="currentColor"
				class="h-6 w-6"
			>
				<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
			</svg>
		</button>
		<div>
			<h1 class="text-3xl font-bold">Trending Artists</h1>
			<p class="mt-1 text-sm text-base-content/70">
				Most listened artists on ListenBrainz
			</p>
		</div>
	</div>

	{#if loading}
		<div class="flex min-h-[400px] items-center justify-center">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else if !overviewData}
		<div class="flex min-h-[400px] flex-col items-center justify-center text-center">
			<div class="mb-4 text-6xl">🎤</div>
			<h2 class="mb-2 text-2xl font-semibold">Unable to load trending artists</h2>
			<p class="mb-4 text-base-content/70">Please try again later.</p>
			<button class="btn btn-primary" on:click={loadOverview}>Retry</button>
		</div>
	{:else}
		<div class="space-y-8">
			{#each timeRanges as range}
				{@const featured = getFeaturedForRange(range.key)}
				{@const items = getItemsForRange(range.key)}
				{@const isExpanded = expandedRange === range.key}

				<section class="rounded-2xl bg-base-200/50 p-4 sm:p-6">
					<button
						class="mb-4 flex w-full items-center justify-between text-left"
						on:click={() => expandRange(range.key)}
					>
						<h2 class="text-xl font-bold sm:text-2xl">{range.label}</h2>
						<div class="flex items-center gap-2">
							<span class="text-sm text-base-content/50">
								{isExpanded ? 'Show less' : 'View all'}
							</span>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 20 20"
								fill="currentColor"
								class="h-5 w-5 transition-transform {isExpanded ? 'rotate-180' : ''}"
							>
								<path
									fill-rule="evenodd"
									d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
									clip-rule="evenodd"
								/>
							</svg>
						</div>
					</button>

					{#if !isExpanded}
						<div class="grid gap-4 lg:grid-cols-3">
							{#if featured}
								<div
									class="card cursor-pointer overflow-hidden bg-base-100 shadow-lg transition-all hover:shadow-xl lg:col-span-1"
									on:click={() => handleArtistClick(featured)}
									on:keydown={(e) => e.key === 'Enter' && handleArtistClick(featured)}
									role="button"
									tabindex="0"
								>
									<figure class="relative aspect-square w-full">
										<ArtistImage 
											mbid={featured.mbid || ''} 
											alt={featured.name} 
											size="full" 
											rounded="none"
											className="w-full h-full"
											lazy={false}
										/>
										<div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent"></div>
										<div class="absolute left-3 top-3 flex items-center gap-2">
											<span class="badge badge-primary badge-lg font-bold">#1</span>
											<span class="badge badge-ghost badge-sm">Most Popular</span>
										</div>
										{#if featured.in_library}
											<div class="badge badge-success absolute right-3 top-3">
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 20 20"
													fill="currentColor"
													class="h-3 w-3"
												>
													<path
														fill-rule="evenodd"
														d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
														clip-rule="evenodd"
													/>
												</svg>
												In Library
											</div>
										{/if}
										<div class="absolute inset-x-0 bottom-0 p-4 text-white">
											<h3 class="line-clamp-2 text-lg font-bold sm:text-xl">{featured.name}</h3>
											{#if featured.listen_count}
												<p class="mt-1 text-sm text-white/60">
													🎧 {formatListenCount(featured.listen_count)} plays
												</p>
											{/if}
										</div>
									</figure>
								</div>
							{/if}

							<div
								class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:col-span-2 lg:grid-cols-4"
							>
								{#each items.slice(0, 8) as artist, idx}
									{@const rank = idx + 2}
									<div
										class="card cursor-pointer bg-base-100 shadow-sm transition-all hover:scale-105 hover:shadow-lg active:scale-95"
										on:click={() => handleArtistClick(artist)}
										on:keydown={(e) => e.key === 'Enter' && handleArtistClick(artist)}
										role="button"
										tabindex="0"
									>
										<figure class="relative flex justify-center pt-4">
											<ArtistImage mbid={artist.mbid || ''} alt={artist.name} size="md" lazy={false} />
											{#if artist.in_library}
												<div class="badge badge-success badge-sm absolute right-1 top-1">
													<svg
														xmlns="http://www.w3.org/2000/svg"
														viewBox="0 0 20 20"
														fill="currentColor"
														class="h-3 w-3"
													>
														<path
															fill-rule="evenodd"
															d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
															clip-rule="evenodd"
														/>
													</svg>
												</div>
											{/if}
											<div class="badge badge-neutral badge-sm absolute bottom-1 left-1 font-bold">
												#{rank}
											</div>
										</figure>
										<div class="card-body p-2">
											<h3 class="card-title line-clamp-1 text-xs">{artist.name}</h3>
											{#if artist.listen_count}
												<p class="text-xs text-base-content/40">
													{formatListenCount(artist.listen_count)} plays
												</p>
											{/if}
										</div>
									</div>
								{/each}
							</div>
						</div>
					{:else}
						{#if loadingMore && !expandedData}
							<div class="flex justify-center py-8">
								<span class="loading loading-spinner loading-lg"></span>
							</div>
						{:else if expandedData}
							<div
								class="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6"
							>
								{#each expandedData.items as artist, idx}
									{@const rank = idx + 1}
									<div
										class="card cursor-pointer bg-base-100 shadow-sm transition-all hover:scale-105 hover:shadow-lg active:scale-95"
										on:click={() => handleArtistClick(artist)}
										on:keydown={(e) => e.key === 'Enter' && handleArtistClick(artist)}
										role="button"
										tabindex="0"
									>
										<figure class="relative aspect-square overflow-hidden">
											<ArtistImage 
												mbid={artist.mbid || ''} 
												alt={artist.name} 
												size="full" 
												rounded="none"
												className="w-full h-full"
											/>
											{#if artist.in_library}
												<div class="badge badge-success badge-sm absolute right-1 top-1">
													<svg
														xmlns="http://www.w3.org/2000/svg"
														viewBox="0 0 20 20"
														fill="currentColor"
														class="h-3 w-3"
													>
														<path
															fill-rule="evenodd"
															d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
															clip-rule="evenodd"
														/>
													</svg>
												</div>
											{/if}
											<div
												class="badge badge-sm absolute bottom-1 left-1 font-bold {rank <= 3
													? 'badge-primary'
													: 'badge-neutral'}"
											>
												#{rank}
											</div>
										</figure>
										<div class="card-body p-2 sm:p-3">
											<h3 class="card-title line-clamp-1 text-xs sm:text-sm">{artist.name}</h3>
											{#if artist.listen_count}
												<p class="text-xs text-base-content/40">
													{formatListenCount(artist.listen_count)} plays
												</p>
											{/if}
										</div>
									</div>
								{/each}
							</div>

							{#if expandedData.has_more}
								<div class="mt-6 flex justify-center">
									<button
										class="btn btn-outline btn-wide"
										on:click={loadMore}
										disabled={loadingMore}
									>
										{#if loadingMore}
											<span class="loading loading-spinner loading-sm"></span>
										{:else}
											Load More
										{/if}
									</button>
								</div>
							{/if}
						{/if}
					{/if}
				</section>
			{/each}
		</div>
	{/if}
</div>
