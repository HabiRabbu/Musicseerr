<script lang="ts">
	import { goto } from '$app/navigation';
	import { fly } from 'svelte/transition';
	import { API, CACHE_KEYS, CACHE_TTL } from '$lib/constants';
	import type {
		DiscoverQueueItemLight,
		DiscoverQueueEnrichment,
		DiscoverQueueItemFull,
		DiscoverQueueResponse,
		YouTubeSearchResponse
	} from '$lib/types';

	let { open = $bindable(false) }: { open: boolean } = $props();

	let dialogEl: HTMLDialogElement | undefined = $state();
	let queue: DiscoverQueueItemFull[] = $state([]);
	let currentIndex: number = $state(0);
	let loading: boolean = $state(false);
	let queueId: string = $state('');
	let mobileTab: 'video' | 'info' | 'bio' = $state('video');
	let bioExpanded: boolean = $state(false);
	let nextDebounce: ReturnType<typeof setTimeout> | null = $state(null);
	let ytSearching: boolean = $state(false);
	let ytSearchResult: YouTubeSearchResponse | null = $state(null);

	let enrichmentCache = new Map<string, DiscoverQueueEnrichment>();
	let ytSearchCache = new Map<string, YouTubeSearchResponse>();

	let currentItem: DiscoverQueueItemFull | undefined = $derived(queue[currentIndex]);
	let enrichment: DiscoverQueueEnrichment | undefined = $derived(currentItem?.enrichment);
	let enriching: boolean = $derived(currentItem != null && !currentItem.enrichment);
	let isLastItem: boolean = $derived(currentIndex >= queue.length - 1);
	let progressText: string = $derived(
		queue.length > 0 ? `${currentIndex + 1} of ${queue.length}` : ''
	);
	let progressFraction: number = $derived(
		queue.length > 0 ? (currentIndex + 1) / queue.length : 0
	);

	let queueLoaded: boolean = $state(false);

	$effect(() => {
		if (!dialogEl) return;
		if (open) {
			dialogEl.showModal();
			if (!queueLoaded) {
				queueLoaded = true;
				loadQueue();
			}
		} else if (dialogEl.open) {
			dialogEl.close();
			queueLoaded = false;
		}
	});

	function handleClose() {
		open = false;
		saveQueueToStorage();
	}

	function navigateTo(path: string) {
		saveQueueToStorage();
		open = false;
		goto(path);
	}

	// ── Queue Loading ──

	async function loadQueue() {
		const cached = loadQueueFromStorage();
		if (cached) {
			queue = cached.items;
			currentIndex = cached.currentIndex;
			queueId = cached.queueId;
			await validateCachedQueue();
			enrichCurrentAndNext();
			return;
		}
		await fetchNewQueue();
	}

	async function fetchNewQueue() {
		if (loading) return;
		loading = true;
		try {
			const res = await fetch(API.discoverQueue());
			if (!res.ok) throw new Error('Failed to fetch queue');
			const data: DiscoverQueueResponse = await res.json();
			queue = data.items.map((item) => ({ ...item }));
			queueId = data.queue_id;
			currentIndex = 0;
			enrichmentCache.clear();
			saveQueueToStorage();
			enrichCurrentAndNext();
		} catch (e) {
			console.error('Failed to fetch discover queue:', e);
		} finally {
			loading = false;
		}
	}

	async function validateCachedQueue() {
		if (queue.length === 0) return;
		try {
			const mbids = queue.map((i) => i.release_group_mbid);
			const res = await fetch(API.discoverQueueValidate(), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ release_group_mbids: mbids })
			});
			if (res.ok) {
				const data = await res.json();
				const inLibrary = new Set(data.in_library || []);
				if (inLibrary.size > 0) {
					queue = queue.filter((i) => !inLibrary.has(i.release_group_mbid));
					if (currentIndex >= queue.length) currentIndex = Math.max(0, queue.length - 1);
				}
			}
			if (queue.length === 0) {
				await fetchNewQueue();
			}
		} catch {
			/* ignore validation errors */
		}
	}

	// ── Enrichment ──

	async function enrichCurrentAndNext() {
		if (queue.length === 0) return;
		await enrichItem(currentIndex);
		for (let i = 1; i <= 2; i++) {
			if (currentIndex + i < queue.length) {
				enrichItem(currentIndex + i);
			}
		}
	}

	async function enrichItem(index: number) {
		const item = queue[index];
		if (!item || item.enrichment) return;

		const mbid = item.release_group_mbid;
		const cached = enrichmentCache.get(mbid);
		if (cached) {
			queue[index] = { ...item, enrichment: cached };
			return;
		}

		try {
			const res = await fetch(API.discoverQueueEnrich(mbid));
			if (res.ok) {
				const data: DiscoverQueueEnrichment = await res.json();
				enrichmentCache.set(mbid, data);
				if (queue[index]?.release_group_mbid === mbid) {
					queue[index] = { ...queue[index], enrichment: data };
				}
			} else if (queue[index]?.release_group_mbid === mbid && !queue[index]?.enrichment) {
				queue[index] = { ...queue[index], enrichment: {} as DiscoverQueueEnrichment };
			}
		} catch (e) {
			console.error('Failed to enrich item:', e);
			if (queue[index]?.release_group_mbid === mbid && !queue[index]?.enrichment) {
				queue[index] = { ...queue[index], enrichment: {} as DiscoverQueueEnrichment };
			}
		}
	}

	// ── Actions ──

	function handleNext() {
		if (nextDebounce) return;
		nextDebounce = setTimeout(() => {
			nextDebounce = null;
		}, 300);

		if (isLastItem) return;
		currentIndex++;
		bioExpanded = false;
		mobileTab = 'video';
		resetYtSearch();
		enrichCurrentAndNext();
		saveQueueToStorage();
	}

	async function handleIgnore() {
		const item = currentItem;
		if (!item) return;

		try {
			await fetch(API.discoverQueueIgnore(), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					release_group_mbid: item.release_group_mbid,
					artist_mbid: item.artist_mbid,
					release_name: item.album_name,
					artist_name: item.artist_name
				})
			});
		} catch {
			/* continue regardless */
		}

		queue = queue.filter((_, i) => i !== currentIndex);
		if (currentIndex >= queue.length) currentIndex = Math.max(0, queue.length - 1);
		bioExpanded = false;
		resetYtSearch();
		enrichCurrentAndNext();
		saveQueueToStorage();
	}

	function handleGenerateNew() {
		fetchNewQueue();
	}

	// ── localStorage ──

	function saveQueueToStorage() {
		try {
			const data = {
				items: queue.map(({ enrichment, ...rest }) => rest),
				currentIndex,
				queueId,
				timestamp: Date.now()
			};
			localStorage.setItem(CACHE_KEYS.DISCOVER_QUEUE, JSON.stringify(data));
		} catch {
			/* storage full */
		}
	}

	function loadQueueFromStorage(): {
		items: DiscoverQueueItemFull[];
		currentIndex: number;
		queueId: string;
	} | null {
		try {
			const raw = localStorage.getItem(CACHE_KEYS.DISCOVER_QUEUE);
			if (!raw) return null;
			const data = JSON.parse(raw);
			if (Date.now() - data.timestamp > CACHE_TTL.DISCOVER_QUEUE) {
				localStorage.removeItem(CACHE_KEYS.DISCOVER_QUEUE);
				return null;
			}
			return {
				items: data.items,
				currentIndex: data.currentIndex || 0,
				queueId: data.queueId || ''
			};
		} catch {
			return null;
		}
	}

	function countryToFlag(code: string | null): string {
		if (!code || code.length !== 2) return '';
		return String.fromCodePoint(
			...code
				.toUpperCase()
				.split('')
				.map((c) => 0x1f1e6 + c.charCodeAt(0) - 65)
		);
	}

	function truncateText(text: string, maxLen: number): string {
		if (text.length <= maxLen) return text;
		return text.slice(0, maxLen).trimEnd() + '…';
	}

	const PLACEHOLDER = '/placeholder-album.png';

	function handleCoverError() {
		if (currentItem && currentItem.cover_url !== PLACEHOLDER) {
			queue[currentIndex] = { ...queue[currentIndex], cover_url: PLACEHOLDER };
		}
	}

	function resetYtSearch() {
		ytSearching = false;
		ytSearchResult = null;
	}

	async function handleYtSearch() {
		if (!currentItem || ytSearching) return;
		const cacheKey = `${currentItem.artist_name}|${currentItem.album_name}`;
		const cached = ytSearchCache.get(cacheKey);
		if (cached) {
			ytSearchResult = cached;
			return;
		}

		ytSearching = true;
		ytSearchResult = null;
		try {
			const res = await fetch(
				API.discoverQueueYoutubeSearch(currentItem.artist_name, currentItem.album_name)
			);
			if (res.ok) {
				const data: YouTubeSearchResponse = await res.json();
				ytSearchCache.set(cacheKey, data);
				ytSearchResult = data;
			} else {
				ytSearchResult = { video_id: null, embed_url: null, error: 'request_failed' };
			}
		} catch {
			ytSearchResult = { video_id: null, embed_url: null, error: 'request_failed' };
		} finally {
			ytSearching = false;
		}
	}
</script>

<dialog bind:this={dialogEl} class="modal" onclose={handleClose}>
	<div class="modal-box dq-modal">
		<!-- Loading state -->
		{#if loading}
			<div class="dq-loading">
				<span class="loading loading-spinner loading-lg text-primary"></span>
				<p class="mt-4 text-base-content/60">Building your discovery queue…</p>
			</div>
		{:else if queue.length === 0}
			<div class="dq-loading">
				<p class="text-base-content/60">No albums to discover right now.</p>
				<button class="btn btn-primary mt-4" onclick={handleGenerateNew}>Try Again</button>
			</div>
		{:else if currentItem}
			{#key currentItem.release_group_mbid}
				<div in:fly={{ x: 20, duration: 300 }} class="flex flex-col h-full w-full">
					<!-- Header -->
			<div class="dq-header">
				<div class="dq-header-left">
					{#if currentItem.recommendation_reason}
						<span class="dq-reason-eyebrow">{currentItem.recommendation_reason}</span>
					{/if}
					<div class="dq-title-row">
						<button
							class="dq-album-title"
							onclick={() => navigateTo(`/album/${currentItem.release_group_mbid}`)}
						>
							{currentItem.album_name}
						</button>
						{#if currentItem.is_wildcard}
							<span class="badge badge-sm badge-warning">✨</span>
						{/if}
					</div>
					{#if currentItem.artist_mbid}
						<button
							class="dq-artist-name"
							onclick={() => navigateTo(`/artist/${currentItem.artist_mbid}`)}
						>
							{currentItem.artist_name}
						</button>
					{:else}
						<span class="dq-artist-name-static">{currentItem.artist_name}</span>
					{/if}
				</div>
				<div class="dq-header-right">
					<div class="dq-progress-bar-wrap">
						<div class="dq-progress-bar-fill" style="width: {progressFraction * 100}%"></div>
					</div>
					<span class="dq-progress">{progressText}</span>
					<button class="btn btn-sm btn-circle btn-ghost" onclick={handleClose}>✕</button>
				</div>
			</div>

			<!-- Desktop: 2-column layout -->
			<div class="dq-body dq-desktop">
				<div class="dq-grid">
					<!-- Left: Album cover + info card -->
					<div class="dq-col-left">
						<button
							class="dq-cover-wrap"
							onclick={() => navigateTo(`/album/${currentItem.release_group_mbid}`)}
						>
							{#if enriching}
								<div class="dq-cover-skeleton skeleton"></div>
							{:else}
								<img
									src={currentItem.cover_url || PLACEHOLDER}
									alt={currentItem.album_name}
									class="dq-cover"
									onerror={handleCoverError}
								/>
							{/if}
						</button>

						<!-- Info card below cover -->
						<div class="dq-info-card">
							{#if enriching}
								<div class="flex flex-col gap-2">
									<div class="skeleton h-4 w-3/4 rounded"></div>
									<div class="skeleton h-4 w-1/2 rounded"></div>
									<div class="skeleton h-3 w-2/3 rounded"></div>
								</div>
							{:else if enrichment}
								<div class="dq-info-grid">
									{#if enrichment.release_date}
										<div class="dq-info-row">
											<span class="dq-info-icon">
												<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
													<path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
												</svg>
											</span>
											<div class="dq-info-content">
												<span class="dq-info-label">Released</span>
												<span class="dq-info-value">{enrichment.release_date}</span>
											</div>
										</div>
									{/if}
									{#if enrichment.country}
										<div class="dq-info-row">
											<span class="dq-info-icon">
												<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
													<path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
												</svg>
											</span>
											<div class="dq-info-content">
												<span class="dq-info-label">Origin</span>
												<span class="dq-info-value">{countryToFlag(enrichment.country)} {enrichment.country}</span>
											</div>
										</div>
									{/if}
									{#if enrichment.listen_count != null}
										<div class="dq-info-row">
											<span class="dq-info-icon">
												<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
													<path stroke-linecap="round" stroke-linejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" />
												</svg>
											</span>
											<div class="dq-info-content">
												<span class="dq-info-label">Plays</span>
												<span class="dq-info-value">{enrichment.listen_count.toLocaleString()}</span>
											</div>
										</div>
									{/if}
									{#if currentItem.in_library}
										<div class="dq-info-row">
											<span class="dq-info-icon">
												<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-success">
													<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
												</svg>
											</span>
											<div class="dq-info-content">
												<span class="dq-info-label">Library</span>
												<span class="dq-info-value text-success">In Library</span>
											</div>
										</div>
									{/if}
								</div>
								{#if enrichment.tags.length > 0}
									<div class="dq-tags">
										{#each enrichment.tags.slice(0, 6) as tag}
											<span class="dq-tag">{tag}</span>
										{/each}
									</div>
								{/if}
							{/if}
						</div>
					</div>

					<!-- Right: YouTube embed -->
					<div class="dq-col-right">
						{#if enriching}
							<div class="skeleton dq-video-skeleton"></div>
						{:else if enrichment?.youtube_url}
							<div class="dq-video-wrap">
								<iframe
									src={enrichment.youtube_url}
									title="Album preview"
									frameborder="0"
									allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
									allowfullscreen
									loading="lazy"
									class="dq-video"
								></iframe>
							</div>
						{:else if ytSearchResult?.embed_url}
							<div class="dq-video-wrap">
								<iframe
									src={ytSearchResult.embed_url}
									title="Album preview"
									frameborder="0"
									allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
									allowfullscreen
									loading="lazy"
									class="dq-video"
								></iframe>
							</div>
						{:else if ytSearching}
							<div class="dq-no-video">
								<span class="loading loading-spinner loading-lg text-primary"></span>
								<p class="mt-2">Searching for video preview…</p>
							</div>
						{:else if ytSearchResult?.error === 'quota_exceeded'}
							<div class="dq-no-video">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="dq-yt-icon">
									<path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814z"/>
									<path d="M9.545 15.568V8.432L15.818 12l-6.273 3.568z" fill="white"/>
								</svg>
								<p>YouTube limit reached for today</p>
								{#if enrichment}
									<a href={enrichment.youtube_search_url} target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm mt-2">
										Search on YouTube
									</a>
								{/if}
							</div>
						{:else if ytSearchResult?.error === 'not_found' || ytSearchResult?.error === 'request_failed'}
							<div class="dq-no-video">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="dq-yt-icon">
									<path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814z"/>
									<path d="M9.545 15.568V8.432L15.818 12l-6.273 3.568z" fill="white"/>
								</svg>
								<p>No video found</p>
								{#if enrichment}
									<a href={enrichment.youtube_search_url} target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm mt-2">
										Search on YouTube
									</a>
								{/if}
							</div>
						{:else if enrichment?.youtube_search_available}
							<div class="dq-no-video">
								<button class="btn btn-lg gap-2 dq-yt-btn" onclick={handleYtSearch}>
									<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="h-6 w-6">
										<path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814z"/>
										<path d="M9.545 15.568V8.432L15.818 12l-6.273 3.568z" fill="white"/>
									</svg>
									Find Video Preview
								</button>
								<p class="mt-2 text-xs text-base-content/30">Uses YouTube Data API</p>
							</div>
						{:else if enrichment}
							<div class="dq-no-video">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="dq-yt-icon-color">
									<path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814z"/>
									<path d="M9.545 15.568V8.432L15.818 12l-6.273 3.568z" fill="white"/>
								</svg>
								<p>No video preview available</p>
								<button class="btn btn-sm btn-primary gap-1 mt-2" onclick={(e) => { e.preventDefault(); navigateTo('/settings?tab=youtube'); }}>
									<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4">
										<path fill-rule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clip-rule="evenodd"/>
									</svg>
									Add YouTube API Key
								</button>
								<a href={enrichment.youtube_search_url} target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm mt-2">
									Search on YouTube
								</a>
							</div>
						{/if}
					</div>
				</div>

				<!-- Bio — full width below grid -->
				{#if enriching}
					<div class="skeleton h-12 w-full rounded-lg mt-4"></div>
				{:else if enrichment?.artist_description}
					<div class="dq-bio">
						<p>
							{#if bioExpanded}
								{enrichment.artist_description}
							{:else}
								{truncateText(enrichment.artist_description, 300)}
							{/if}
						</p>
						{#if enrichment.artist_description.length > 300}
							<button class="dq-bio-toggle" onclick={() => (bioExpanded = !bioExpanded)}>
								{bioExpanded ? 'Show less' : 'Read more'}
							</button>
						{/if}
					</div>
				{/if}
			</div>

			<!-- Mobile: Tabbed layout -->
			<div class="dq-body dq-mobile">
				<button
					class="dq-cover-wrap-mobile"
					onclick={() => navigateTo(`/album/${currentItem.release_group_mbid}`)}
				>
					<img
						src={currentItem.cover_url || PLACEHOLDER}
						alt={currentItem.album_name}
						class="dq-cover-mobile"
						onerror={handleCoverError}
					/>
				</button>

				<div role="tablist" class="tabs tabs-boxed tabs-sm mt-3">
					<button
						role="tab"
						class="tab"
						class:tab-active={mobileTab === 'video'}
						onclick={() => (mobileTab = 'video')}
					>
						▶ Video
					</button>
					<button
						role="tab"
						class="tab"
						class:tab-active={mobileTab === 'info'}
						onclick={() => (mobileTab = 'info')}
					>
						ℹ Info
					</button>
					<button
						role="tab"
						class="tab"
						class:tab-active={mobileTab === 'bio'}
						onclick={() => (mobileTab = 'bio')}
					>
						📖 Bio
					</button>
				</div>

				<div class="dq-tab-content">
					{#if enriching}
						<div class="skeleton h-40 w-full rounded-lg"></div>
					{:else if mobileTab === 'video'}
						{#if enrichment?.youtube_url}
							<div class="dq-video-wrap">
								<iframe
									src={enrichment.youtube_url}
									title="Album preview"
									frameborder="0"
									allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
									allowfullscreen
									loading="lazy"
									class="dq-video"
								></iframe>
							</div>
						{:else if ytSearchResult?.embed_url}
							<div class="dq-video-wrap">
								<iframe
									src={ytSearchResult.embed_url}
									title="Album preview"
									frameborder="0"
									allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
									allowfullscreen
									loading="lazy"
									class="dq-video"
								></iframe>
							</div>
						{:else if ytSearching}
							<div class="dq-no-video">
								<span class="loading loading-spinner loading-lg text-primary"></span>
								<p class="mt-2">Searching…</p>
							</div>
						{:else if ytSearchResult?.error === 'quota_exceeded'}
							<div class="dq-no-video">
								<p>YouTube limit reached</p>
								{#if enrichment}
									<a href={enrichment.youtube_search_url} target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm mt-2">Search on YouTube</a>
								{/if}
							</div>
						{:else if ytSearchResult?.error}
							<div class="dq-no-video">
								<p>No video found</p>
								{#if enrichment}
									<a href={enrichment.youtube_search_url} target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm mt-2">Search on YouTube</a>
								{/if}
							</div>
						{:else if enrichment?.youtube_search_available}
							<div class="dq-no-video">
								<button class="btn btn-lg gap-2 dq-yt-btn" onclick={handleYtSearch}>
									<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="h-6 w-6">
										<path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814z"/>
										<path d="M9.545 15.568V8.432L15.818 12l-6.273 3.568z" fill="white"/>
									</svg>
									Find Video
								</button>
							</div>
						{:else if enrichment}
							<div class="dq-no-video">
								<p>No preview available</p>
								<a href={enrichment.youtube_search_url} target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm mt-2">Search on YouTube</a>
							</div>
						{/if}
					{:else if mobileTab === 'info' && enrichment}
						<div class="dq-info-grid">
							{#if enrichment.release_date}
								<div class="dq-info-row">
									<span class="dq-info-icon">
										<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
											<path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
										</svg>
									</span>
									<div class="dq-info-content">
										<span class="dq-info-label">Released</span>
										<span class="dq-info-value">{enrichment.release_date}</span>
									</div>
								</div>
							{/if}
							{#if enrichment.country}
								<div class="dq-info-row">
									<span class="dq-info-icon">
										<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
											<path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
										</svg>
									</span>
									<div class="dq-info-content">
										<span class="dq-info-label">Origin</span>
										<span class="dq-info-value">{countryToFlag(enrichment.country)} {enrichment.country}</span>
									</div>
								</div>
							{/if}
							{#if enrichment.listen_count != null}
								<div class="dq-info-row">
									<span class="dq-info-icon">
										<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
											<path stroke-linecap="round" stroke-linejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" />
										</svg>
									</span>
									<div class="dq-info-content">
										<span class="dq-info-label">Plays</span>
										<span class="dq-info-value">{enrichment.listen_count.toLocaleString()}</span>
									</div>
								</div>
							{/if}
							{#if enrichment.tags.length > 0}
								<div class="dq-tags mt-2">
									{#each enrichment.tags.slice(0, 6) as tag}
										<span class="dq-tag">{tag}</span>
									{/each}
								</div>
							{/if}
						</div>
					{:else if mobileTab === 'bio'}
						{#if enrichment?.artist_description}
							<p class="text-sm text-base-content/70">{enrichment.artist_description}</p>
						{:else}
							<p class="text-sm text-base-content/50">No biography available.</p>
						{/if}
					{/if}
				</div>
			</div>

			<!-- Footer -->
			<div class="dq-footer">
				<button class="btn btn-sm dq-ignore-btn" onclick={handleIgnore}>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 20 20"
						fill="currentColor"
						class="h-4 w-4"
					>
						<path
							d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
						/>
					</svg>
					Not for me
				</button>
				<div class="dq-footer-actions">
					<button
						class="btn btn-sm dq-view-album-btn"
						onclick={() => navigateTo(`/album/${currentItem.release_group_mbid}`)}
					>
						View Album
					</button>
					{#if isLastItem}
						<button class="btn btn-primary" onclick={handleGenerateNew}> New Queue </button>
					{:else}
						<button class="btn btn-primary dq-next-btn" onclick={handleNext}> Next → </button>
					{/if}
				</div>
			</div>
			</div>
			{/key}
		{/if}
	</div>
	<form method="dialog" class="modal-backdrop">
		<button>close</button>
	</form>
</dialog>

<style>
	:global(dialog.modal::backdrop) {
		background: rgba(0, 0, 0, 0.85) !important;
	}

	:global(.modal-backdrop) {
		background: rgba(0, 0, 0, 0.85) !important;
	}

	.dq-modal {
		width: 92vw;
		max-width: 64rem;
		max-height: 85vh;
		display: flex;
		flex-direction: column;
		padding: 0 !important;
		overflow: hidden;
		border-radius: 1.25rem;
		background-color: var(--color-base-100);
		box-shadow:
			0 25px 50px -12px rgba(0, 0, 0, 0.4),
			0 0 0 1px color-mix(in srgb, var(--color-base-content) 6%, transparent),
			inset 0 1px 0 0 color-mix(in srgb, var(--color-base-content) 6%, transparent);
		position: relative;
	}

	.dq-modal::before {
		content: '';
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 2px;
		background: linear-gradient(90deg, var(--color-primary), var(--color-secondary), var(--color-primary));
		z-index: 10;
		border-radius: 1.25rem 1.25rem 0 0;
	}

	.dq-loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 4rem 2rem;
	}

	/* ── Header ── */
	.dq-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		padding: 1.25rem 1.5rem 0;
		flex-shrink: 0;
	}

	.dq-header-left {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
		min-width: 0;
	}

	.dq-header-right {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.dq-title-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.dq-album-title {
		font-size: 1.5rem;
		font-weight: 800;
		color: var(--color-base-content);
		text-align: left;
		background: none;
		border: none;
		padding: 0;
		cursor: pointer;
		line-height: 1.1;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 100%;
		letter-spacing: -0.02em;
		text-shadow: 0 2px 8px color-mix(in srgb, var(--color-base-content) 15%, transparent);
		transition: color 0.2s ease, transform 0.2s ease;
		transform-origin: left center;
	}

	.dq-album-title:hover {
		color: var(--color-primary);
		transform: scale(1.02);
	}

	.dq-artist-name {
		font-size: 0.85rem;
		color: color-mix(in srgb, var(--color-base-content) 60%, transparent);
		text-align: left;
		background: none;
		border: none;
		padding: 0;
		cursor: pointer;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		font-weight: 600;
		transition: color 0.2s ease, transform 0.2s ease;
		transform-origin: left center;
	}

	.dq-artist-name:hover {
		color: var(--color-primary);
		transform: scale(1.02);
	}

	.dq-artist-name-static {
		font-size: 0.85rem;
		color: color-mix(in srgb, var(--color-base-content) 60%, transparent);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		font-weight: 600;
	}

	.dq-reason-eyebrow {
		font-size: 0.65rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: color-mix(in srgb, var(--color-primary) 70%, transparent);
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
		margin-bottom: 0.25rem;
	}

	.dq-progress {
		font-size: 0.7rem;
		color: color-mix(in srgb, var(--color-base-content) 45%, transparent);
		white-space: nowrap;
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--color-base-content) 4%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-base-content) 6%, transparent);
	}

	.dq-progress-bar-wrap {
		width: 4.5rem;
		height: 5px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--color-base-content) 20%, transparent);
		overflow: hidden;
		border: 1px solid color-mix(in srgb, var(--color-base-content) 8%, transparent);
	}

	.dq-progress-bar-fill {
		height: 100%;
		border-radius: 999px;
		background: linear-gradient(90deg, var(--color-primary), var(--color-secondary));
		transition: width 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
	}

	/* ── Body ── */
	.dq-body {
		overflow-y: auto;
		min-height: 0;
		padding: 1rem 1.5rem;
	}

	.dq-desktop {
		display: none;
	}

	.dq-mobile {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		align-items: center;
	}

	@media (min-width: 1024px) {
		.dq-desktop {
			display: block;
		}

		.dq-grid {
			display: grid;
			grid-template-columns: 260px 1fr;
			gap: 1.5rem;
			align-items: start;
		}

		.dq-mobile {
			display: none;
		}
	}

	/* ── Left column ── */
	.dq-col-left {
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.dq-cover-wrap,
	.dq-cover-wrap-mobile {
		background: none;
		border: none;
		padding: 0;
		cursor: pointer;
		border-radius: 0.75rem;
		overflow: hidden;
		box-shadow:
			0 20px 40px -10px rgba(0, 0, 0, 0.5),
			0 0 60px 10px color-mix(in srgb, var(--color-primary) 15%, transparent);
		transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease;
	}

	.dq-cover-wrap:hover {
		transform: scale(1.03) translateY(-4px);
		box-shadow:
			0 25px 50px -12px rgba(0, 0, 0, 0.5),
			0 0 60px 10px color-mix(in srgb, var(--color-primary) 25%, transparent);
	}

	.dq-cover {
		width: 260px;
		height: 260px;
		object-fit: cover;
		display: block;
	}

	.dq-cover-skeleton {
		width: 260px;
		height: 260px;
		border-radius: 0;
	}

	.dq-cover-mobile {
		width: 100%;
		max-width: 220px;
		aspect-ratio: 1;
		object-fit: cover;
		display: block;
	}

	/* ── Info card ── */
	.dq-info-card {
		margin-top: 0.75rem;
		padding: 0.75rem;
		background: color-mix(in srgb, var(--color-base-100) 30%, transparent);
		backdrop-filter: blur(12px);
		border-radius: 0.75rem;
		border: 1px solid color-mix(in srgb, var(--color-base-content) 5%, transparent);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
	}

	.dq-info-grid {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.dq-info-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.7rem;
		color: color-mix(in srgb, var(--color-base-content) 60%, transparent);
	}

	.dq-info-icon {
		width: 1.25rem;
		text-align: center;
		flex-shrink: 0;
		color: color-mix(in srgb, var(--color-base-content) 40%, transparent);
	}

	.dq-info-content {
		display: flex;
		flex-direction: column;
		gap: 0.05rem;
	}

	.dq-info-label {
		font-size: 0.6rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		font-weight: 700;
		color: color-mix(in srgb, var(--color-base-content) 35%, transparent);
	}

	.dq-info-value {
		font-size: 0.8rem;
		font-weight: 600;
		color: color-mix(in srgb, var(--color-base-content) 80%, transparent);
	}

	.dq-tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		margin-top: 0.5rem;
	}

	.dq-tag {
		font-size: 0.75rem;
		padding: 0.2rem 0.6rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--color-base-100) 5%, transparent);
		backdrop-filter: blur(8px);
		color: color-mix(in srgb, var(--color-base-content) 80%, transparent);
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
		font-weight: 400;
		border: 1px solid color-mix(in srgb, var(--color-base-content) 10%, transparent);
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
		transition: all 0.2s ease;
	}

	.dq-tag:hover {
		border-color: color-mix(in srgb, var(--color-base-content) 30%, transparent);
		background: color-mix(in srgb, var(--color-base-100) 10%, transparent);
	}

	/* ── Bio ── */
	.dq-bio {
		margin-top: 0.75rem;
	}

	.dq-bio p {
		font-size: 0.8rem;
		line-height: 1.5;
		color: color-mix(in srgb, var(--color-base-content) 55%, transparent);
	}

	.dq-bio-toggle {
		font-size: 0.75rem;
		color: var(--color-primary);
		background: none;
		border: none;
		padding: 0;
		margin-top: 0.25rem;
		cursor: pointer;
	}

	.dq-bio-toggle:hover {
		text-decoration: underline;
	}

	/* ── Right column ── */
	.dq-col-right {
		display: flex;
		flex-direction: column;
	}

	.dq-video-wrap {
		position: relative;
		width: 100%;
		padding-bottom: 56.25%;
		border-radius: 0.75rem;
		overflow: hidden;
		background: var(--color-base-200);
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
	}

	.dq-video {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
	}

	.dq-video-skeleton {
		width: 100%;
		padding-bottom: 56.25%;
		border-radius: 0.75rem;
	}

	.dq-no-video {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 3rem 2rem;
		background: linear-gradient(135deg, color-mix(in srgb, var(--color-base-content) 3%, transparent), color-mix(in srgb, var(--color-base-content) 1%, transparent));
		border: none;
		border-radius: 0.75rem;
		color: color-mix(in srgb, var(--color-base-content) 40%, transparent);
		font-size: 0.85rem;
	}

	.dq-yt-icon {
		width: 2.5rem;
		height: 2.5rem;
		color: #ff0000;
		opacity: 0.7;
		margin-bottom: 0.75rem;
		animation: pulse-icon 3s cubic-bezier(0.4, 0, 0.6, 1) infinite;
	}

	@keyframes pulse-icon {
		0%,
		100% {
			opacity: 0.7;
			transform: scale(1);
		}
		50% {
			opacity: 0.4;
			transform: scale(0.95);
		}
	}

	.dq-yt-icon-color {
		width: 3rem;
		height: 3rem;
		color: #ff0000;
		margin-bottom: 0.75rem;
		filter: drop-shadow(0 2px 4px rgba(255, 0, 0, 0.2));
	}

	.dq-yt-btn {
		background: #ff0000;
		border: none;
		color: #fff;
		font-weight: 600;
	}

	.dq-yt-btn:hover {
		background: #cc0000;
		color: #fff;
	}

	/* ── Mobile tabs ── */
	.dq-tab-content {
		min-height: 120px;
		width: 100%;
	}

	/* ── Footer ── */
	.dq-footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-shrink: 0;
		padding: 0.75rem 1.5rem;
		border-top: 1px solid color-mix(in srgb, var(--color-base-content) 6%, transparent);
		background: color-mix(in srgb, var(--color-base-content) 2%, transparent);
	}

	.dq-ignore-btn {
		background: color-mix(in srgb, var(--color-error) 15%, transparent) !important;
		border: 1px solid color-mix(in srgb, var(--color-error) 25%, transparent) !important;
		color: var(--color-error) !important;
		font-size: 0.8rem;
		font-weight: 500;
		transition: all 0.2s ease;
	}

	.dq-ignore-btn:hover {
		background: color-mix(in srgb, var(--color-error) 25%, transparent) !important;
		border-color: color-mix(in srgb, var(--color-error) 40%, transparent) !important;
		color: var(--color-error) !important;
	}

	.dq-view-album-btn {
		background: rgba(255, 255, 255, 0.03) !important;
		backdrop-filter: blur(10px);
		border: 1px solid color-mix(in srgb, var(--color-base-content) 15%, transparent) !important;
		color: color-mix(in srgb, var(--color-base-content) 80%, transparent) !important;
		font-weight: 500;
	}

	.dq-view-album-btn:hover {
		background: color-mix(in srgb, var(--color-base-content) 10%, transparent) !important;
		color: var(--color-base-content) !important;
		border-color: color-mix(in srgb, var(--color-base-content) 30%, transparent) !important;
	}

	.dq-next-btn {
		background: var(--color-primary) !important;
		border: none !important;
		box-shadow: 0 0 20px -5px color-mix(in srgb, var(--color-primary) 50%, transparent);
		color: var(--color-primary-content) !important;
		transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
	}

	.dq-next-btn:hover {
		background: color-mix(in srgb, var(--color-primary) 85%, transparent) !important;
		box-shadow: 0 0 30px -5px color-mix(in srgb, var(--color-primary) 70%, transparent);
		transform: scale(1.05);
	}

	.dq-footer-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	@media (max-width: 640px) {
		.dq-modal {
			width: 100vw;
			max-height: 100vh;
			max-width: 100vw;
			border-radius: 0;
		}

		.dq-header {
			padding: 1rem 1rem 0;
		}

		.dq-body {
			padding: 0.75rem 1rem;
		}

		.dq-footer {
			padding: 0.75rem 1rem;
			flex-direction: column;
			gap: 0.5rem;
		}

		.dq-footer-actions {
			width: 100%;
			justify-content: center;
		}
	}
</style>
