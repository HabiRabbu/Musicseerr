<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import AlbumImage from './AlbumImage.svelte';
	import ArtistImage from './ArtistImage.svelte';
	import { formatListenCount } from '$lib/utils/formatting';
	import { getTimeRangeFallbackPath } from '$lib/utils/timeRangeFallback';
	import type { HomeAlbum, HomeArtist } from '$lib/types';
	import { ChevronLeft, ChevronDown, Check, Search } from 'lucide-svelte';

	type TimeRangeKey = 'this_week' | 'this_month' | 'this_year' | 'all_time';
	type ItemType = 'album' | 'artist';

	interface TimeRangeData {
		featured: HomeAlbum | HomeArtist | null;
		items: (HomeAlbum | HomeArtist)[];
	}

	interface OverviewData {
		this_week: TimeRangeData;
		this_month: TimeRangeData;
		this_year: TimeRangeData;
		all_time: TimeRangeData;
	}

	interface RangeResponse {
		items: (HomeAlbum | HomeArtist)[];
		offset: number;
		limit: number;
		has_more: boolean;
	}

	export let itemType: ItemType;
	export let endpoint: string;
	export let title: string;
	export let subtitle: string;
	export let errorEmoji = '💿';
	export let source: 'listenbrainz' | 'lastfm' | null = null;

	const timeRanges: { key: TimeRangeKey; label: string }[] = [
		{ key: 'this_week', label: 'This Week' },
		{ key: 'this_month', label: 'This Month' },
		{ key: 'this_year', label: 'This Year' },
		{ key: 'all_time', label: 'All Time' }
	];

	let overviewData: OverviewData | null = null;
	let expandedRange: TimeRangeKey | null = null;
	let expandedData: RangeResponse | null = null;
	let loading = true;
	let loadingMore = false;
	let mounted = false;
	let lastSourceKey = '';

	onMount(async () => {
		mounted = true;
		lastSourceKey = source ?? '';
		await loadOverview();
	});

	$: if (mounted && (source ?? '') !== lastSourceKey) {
		lastSourceKey = source ?? '';
		expandedRange = null;
		expandedData = null;
		loadOverview();
	}

	function withSource(url: string): string {
		if (!source) return url;
		const separator = url.includes('?') ? '&' : '?';
		return `${url}${separator}source=${encodeURIComponent(source)}`;
	}

	async function loadOverview() {
		loading = true;
		try {
			const res = await fetch(withSource(`${endpoint}?limit=10`));
			if (res.ok) {
				overviewData = await res.json();
			}
		} catch {
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
			const res = await fetch(withSource(`${endpoint}/${rangeKey}?limit=25&offset=0`));
			if (res.ok) {
				expandedData = await res.json();
			}
		} catch {
		} finally {
			loadingMore = false;
		}
	}

	async function loadMore() {
		if (!expandedRange || !expandedData || loadingMore || !expandedData.has_more) return;

		loadingMore = true;
		try {
			const newOffset = expandedData.offset + expandedData.limit;
			const res = await fetch(withSource(`${endpoint}/${expandedRange}?limit=25&offset=${newOffset}`));
			if (res.ok) {
				const moreData: RangeResponse = await res.json();
				expandedData = {
					...moreData,
					items: [...expandedData.items, ...moreData.items]
				};
			}
		} catch {
		} finally {
			loadingMore = false;
		}
	}

	function handleItemClick(item: HomeAlbum | HomeArtist) {
		if (item.mbid) {
			goto(`/${itemType}/${item.mbid}`);
			return;
		}
		const fallbackPath = getFallbackSearchPath(item);
		if (fallbackPath) {
			goto(fallbackPath);
		}
	}

	function getFallbackSearchPath(item: HomeAlbum | HomeArtist): string | null {
		return getTimeRangeFallbackPath(itemType, item);
	}

	function getItemsForRange(rangeKey: TimeRangeKey): (HomeAlbum | HomeArtist)[] {
		if (!overviewData) return [];
		return overviewData[rangeKey]?.items || [];
	}

	function getFeaturedForRange(rangeKey: TimeRangeKey): HomeAlbum | HomeArtist | null {
		if (!overviewData) return null;
		return overviewData[rangeKey]?.featured || null;
	}

	function isAlbum(item: HomeAlbum | HomeArtist): item is HomeAlbum {
		return itemType === 'album';
	}
</script>

<div class="container mx-auto p-4 md:p-6 lg:p-8">
	<div class="mb-6 flex items-center gap-4">
		<button class="btn btn-circle btn-ghost" on:click={() => goto('/')} aria-label="Back to home">
			<ChevronLeft class="h-6 w-6" />
		</button>
		<div>
			<h1 class="text-3xl font-bold">{title}</h1>
			<p class="mt-1 text-sm text-base-content/70">{subtitle}</p>
		</div>
	</div>

	{#if loading}
		<div class="flex min-h-[400px] items-center justify-center">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else if !overviewData}
		<div class="flex min-h-[400px] flex-col items-center justify-center text-center">
			<div class="mb-4 text-6xl">{errorEmoji}</div>
			<h2 class="mb-2 text-2xl font-semibold">Unable to load {itemType}s</h2>
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
						aria-label="{isExpanded ? 'Collapse' : 'Expand'} {range.label}"
					>
						<h2 class="text-xl font-bold sm:text-2xl">{range.label}</h2>
						<div class="flex items-center gap-2">
							<span class="text-sm text-base-content/50">
								{isExpanded ? 'Show less' : 'View all'}
							</span>
							<ChevronDown class="h-5 w-5 transition-transform {isExpanded ? 'rotate-180' : ''}" />
						</div>
					</button>

					{#if !isExpanded}
						<div class="grid gap-4 lg:grid-cols-3">
							{#if featured}
								<div
									class="card cursor-pointer overflow-hidden bg-base-100 shadow-lg transition-all hover:shadow-xl lg:col-span-1"
									on:click={() => handleItemClick(featured)}
									on:keydown={(e) => e.key === 'Enter' && handleItemClick(featured)}
									role="button"
									tabindex="0"
								>
									<figure class="relative aspect-square w-full">
										{#if itemType === 'album'}
											<AlbumImage
												mbid={featured.mbid || ''}
												alt={featured.name}
												size="xl"
												rounded="none"
												className="w-full h-full"
												customUrl={(featured as HomeAlbum).image_url || null}
											/>
										{:else}
											<ArtistImage
												mbid={featured.mbid || ''}
												alt={featured.name}
												size="full"
												rounded="none"
												className="w-full h-full"
												lazy={false}
											/>
										{/if}
										<div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent"></div>
										<div class="absolute left-3 top-3 flex items-center gap-2">
											<span class="badge badge-primary badge-lg font-bold">#1</span>
											<span class="badge badge-ghost badge-sm">Most Popular</span>
										</div>
										{#if featured.in_library}
											<div class="badge badge-success absolute right-3 top-3">
												<Check class="h-3 w-3" />
												In Library
											</div>
										{/if}
										<div class="absolute inset-x-0 bottom-0 p-4 text-white">
											<h3 class="line-clamp-2 text-lg font-bold sm:text-xl">{featured.name}</h3>
											{#if isAlbum(featured) && featured.artist_name}
												<p class="line-clamp-1 text-sm text-white/80">{featured.artist_name}</p>
											{/if}
											{#if featured.listen_count !== null && featured.listen_count !== undefined}
												<p class="mt-1 text-sm text-white/60">🎧 {formatListenCount(featured.listen_count)}</p>
											{/if}
										</div>
										{#if !featured.mbid}
											<button
												type="button"
												class="btn btn-ghost btn-xs btn-circle absolute bottom-3 right-3 text-white"
												title={itemType === 'album' ? 'Search album' : 'Search artist'}
												on:click={(e) => {
													e.stopPropagation();
													handleItemClick(featured);
												}}
											>
												<Search class="h-3 w-3" />
											</button>
										{/if}
									</figure>
								</div>
							{/if}

							<div class="grid-cards-overview lg:col-span-2">
								{#each items.slice(0, 8) as item, idx}
									{@const rank = idx + 2}
									<div
										class="card cursor-pointer bg-base-100 shadow-sm transition-all hover:scale-105 hover:shadow-lg active:scale-95"
										on:click={() => handleItemClick(item)}
										on:keydown={(e) => e.key === 'Enter' && handleItemClick(item)}
										role="button"
										tabindex="0"
									>
										{#if itemType === 'album'}
											<figure class="relative aspect-square overflow-hidden">
												<AlbumImage
													mbid={item.mbid || ''}
													alt={item.name}
													size="md"
													rounded="none"
													className="w-full h-full"
													customUrl={(item as HomeAlbum).image_url || null}
												/>
												{#if item.in_library}
													<div class="badge badge-success badge-sm absolute right-1 top-1">
														<Check class="h-3 w-3" />
													</div>
												{/if}
												<div class="badge badge-neutral badge-sm absolute bottom-1 left-1 font-bold">#{rank}</div>
													{#if !item.mbid}
														<button
															type="button"
															class="btn btn-ghost btn-xs btn-circle absolute bottom-1 right-1"
															title="Search artist"
															on:click={(e) => {
																e.stopPropagation();
																handleItemClick(item);
															}}
														>
															<Search class="h-3 w-3" />
														</button>
													{/if}
											</figure>
										{:else}
											<figure class="relative flex justify-center pt-4">
												<ArtistImage mbid={item.mbid || ''} alt={item.name} size="md" lazy={false} />
												{#if item.in_library}
													<div class="badge badge-success badge-sm absolute right-1 top-1">
														<Check class="h-3 w-3" />
													</div>
												{/if}
												<div class="badge badge-neutral badge-sm absolute bottom-1 left-1 font-bold">#{rank}</div>
												{#if !item.mbid}
													<button
														type="button"
														class="btn btn-ghost btn-xs btn-circle absolute bottom-1 right-1"
														title="Search artist"
														on:click={(e) => {
															e.stopPropagation();
															handleItemClick(item);
														}}
													>
														<Search class="h-3 w-3" />
													</button>
												{/if}
											</figure>
										{/if}
										<div class="card-body p-2">
											<h3 class="card-title line-clamp-1 text-xs">{item.name}</h3>
											{#if isAlbum(item) && item.artist_name}
												<p class="line-clamp-1 text-xs text-base-content/50">{item.artist_name}</p>
											{/if}
											{#if item.listen_count !== null && item.listen_count !== undefined}
												<p class="text-xs text-base-content/40">{formatListenCount(item.listen_count)}</p>
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
							<div class="grid-cards">
								{#each expandedData.items as item, idx}
									{@const rank = idx + 1}
									<div
										class="card cursor-pointer bg-base-100 shadow-sm transition-all hover:scale-105 hover:shadow-lg active:scale-95"
										on:click={() => handleItemClick(item)}
										on:keydown={(e) => e.key === 'Enter' && handleItemClick(item)}
										role="button"
										tabindex="0"
									>
										{#if itemType === 'album'}
											<figure class="relative aspect-square overflow-hidden">
												<AlbumImage
													mbid={item.mbid || ''}
													alt={item.name}
													size="md"
													rounded="none"
													className="w-full h-full"
													customUrl={(item as HomeAlbum).image_url || null}
												/>
												{#if item.in_library}
													<div class="badge badge-success badge-sm absolute right-1 top-1">
														<Check class="h-3 w-3" />
													</div>
												{/if}
												<div class="badge badge-sm absolute bottom-1 left-1 font-bold {rank <= 3 ? 'badge-primary' : 'badge-neutral'}">#{rank}</div>
													{#if !item.mbid}
														<button
															type="button"
															class="btn btn-ghost btn-xs btn-circle absolute bottom-1 right-1"
															title="Search album"
															on:click={(e) => {
																e.stopPropagation();
																handleItemClick(item);
															}}
														>
															<Search class="h-3 w-3" />
														</button>
													{/if}
											</figure>
										{:else}
											<figure class="relative aspect-square overflow-hidden">
												<ArtistImage
													mbid={item.mbid || ''}
													alt={item.name}
													size="full"
													rounded="none"
													className="w-full h-full"
												/>
												{#if item.in_library}
													<div class="badge badge-success badge-sm absolute right-1 top-1">
														<Check class="h-3 w-3" />
													</div>
												{/if}
												<div class="badge badge-sm absolute bottom-1 left-1 font-bold {rank <= 3 ? 'badge-primary' : 'badge-neutral'}">#{rank}</div>
												{#if !item.mbid}
													<button
														type="button"
														class="btn btn-ghost btn-xs btn-circle absolute bottom-1 right-1"
														title="Search artist"
														on:click={(e) => {
															e.stopPropagation();
															handleItemClick(item);
														}}
													>
														<Search class="h-3 w-3" />
													</button>
												{/if}
											</figure>
										{/if}
										<div class="card-body p-2 sm:p-3">
											<h3 class="card-title line-clamp-1 text-xs sm:text-sm">{item.name}</h3>
											{#if isAlbum(item) && item.artist_name}
												<p class="line-clamp-1 text-xs text-base-content/50">{item.artist_name}</p>
											{/if}
											{#if item.listen_count !== null && item.listen_count !== undefined}
												<p class="text-xs text-base-content/40">{formatListenCount(item.listen_count)}</p>
											{/if}
										</div>
									</div>
								{/each}
							</div>

							{#if expandedData.has_more}
								<div class="mt-6 flex justify-center">
									<button class="btn btn-outline btn-wide" on:click={loadMore} disabled={loadingMore}>
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
