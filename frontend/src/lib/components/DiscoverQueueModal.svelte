<script lang="ts">
	import { X, Play, Info, ArrowRight, BookOpen } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { fly } from 'svelte/transition';
	import { API } from '$lib/constants';
	import {
		getQueueCachedData,
		setQueueCachedData,
		type QueueCacheData
	} from '$lib/utils/discoverQueueCache';
	import AlbumImage from './AlbumImage.svelte';
	import DQVideoSection from './DQVideoSection.svelte';
	import DQInfoGrid from './DQInfoGrid.svelte';
	import type {
		DiscoverQueueItemLight,
		DiscoverQueueEnrichment,
		DiscoverQueueItemFull,
		DiscoverQueueResponse,
		YouTubeSearchResponse,
		YouTubeQuotaStatus
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
	let ytQuota: YouTubeQuotaStatus | null = $state(null);

	let enrichmentCache = new Map<string, DiscoverQueueEnrichment>();
	let ytSearchCache = new Map<string, YouTubeSearchResponse>();

	let currentItem: DiscoverQueueItemFull | undefined = $derived(queue[currentIndex]);
	let enrichment: DiscoverQueueEnrichment | undefined = $derived(currentItem?.enrichment);
	let enriching: boolean = $derived(currentItem != null && !currentItem.enrichment);
	let isLastItem: boolean = $derived(currentIndex >= queue.length - 1);
	let progressText: string = $derived(
		queue.length > 0 ? `${currentIndex + 1} of ${queue.length}` : ''
	);
	let progressFraction: number = $derived(queue.length > 0 ? (currentIndex + 1) / queue.length : 0);

	let queueLoaded: boolean = $state(false);

	$effect(() => {
		if (!dialogEl) return;
		if (open) {
			dialogEl.showModal();
			fetchQuota();
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
		setQueueCachedData({
			items: queue.map(({ enrichment, ...rest }) => rest),
			currentIndex,
			queueId
		});
	}

	function loadQueueFromStorage(): QueueCacheData | null {
		const cached = getQueueCachedData();
		if (!cached) return null;
		return cached.data;
	}

	function truncateText(text: string, maxLen: number): string {
		if (text.length <= maxLen) return text;
		return text.slice(0, maxLen).trimEnd() + '…';
	}

	function resetYtSearch() {
		ytSearching = false;
		ytSearchResult = null;
	}

	async function fetchQuota() {
		try {
			const res = await fetch(API.discoverQueueYoutubeQuota());
			if (res.ok) {
				ytQuota = await res.json();
			}
		} catch {
			// YouTube not configured or network error — leave null
		}
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
			fetchQuota();
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
				<div in:fly={{ x: 20, duration: 300 }} class="flex flex-col flex-1 min-h-0 w-full">
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
							<button class="btn btn-sm btn-circle btn-ghost" onclick={handleClose}><X class="h-4 w-4" /></button>
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
									<AlbumImage
										mbid={currentItem.release_group_mbid}
										alt={currentItem.album_name}
										size="full"
										lazy={false}
										rounded="none"
										className="dq-cover"
									/>
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
										<DQInfoGrid {enrichment} inLibrary={currentItem.in_library} />
									{/if}
								</div>
							</div>

							<!-- Right: YouTube embed -->
							<div class="dq-col-right">
								<DQVideoSection
									{enriching}
									{enrichment}
									{ytSearching}
									{ytSearchResult}								quota={ytQuota}									onYtSearch={handleYtSearch}
									onNavigate={navigateTo}
								/>
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
							<AlbumImage
								mbid={currentItem.release_group_mbid}
								alt={currentItem.album_name}
								size="full"
								lazy={false}
								rounded="none"
								className="dq-cover-mobile"
							/>
						</button>

						<div role="tablist" class="tabs tabs-boxed tabs-sm mt-3">
							<button
								role="tab"
								class="tab"
								class:tab-active={mobileTab === 'video'}
								onclick={() => (mobileTab = 'video')}
							>
								<Play class="h-3 w-3" /> Video
							</button>
							<button
								role="tab"
								class="tab"
								class:tab-active={mobileTab === 'info'}
								onclick={() => (mobileTab = 'info')}
							>
								<Info class="h-3 w-3" /> Info
							</button>
							<button
								role="tab"
								class="tab"
								class:tab-active={mobileTab === 'bio'}
								onclick={() => (mobileTab = 'bio')}
							>
								<BookOpen class="h-3 w-3" /> Bio
							</button>
						</div>

						<div class="dq-tab-content">
							{#if enriching}
								<div class="skeleton h-40 w-full rounded-lg"></div>
							{:else if mobileTab === 'video'}
								<DQVideoSection
									{enriching}
									{enrichment}
									{ytSearching}
									{ytSearchResult}								quota={ytQuota}									compact={true}
									onYtSearch={handleYtSearch}
									onNavigate={navigateTo}
								/>
							{:else if mobileTab === 'info' && enrichment}
								<DQInfoGrid {enrichment} />
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
							<X class="h-4 w-4" />
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
								<button class="btn btn-primary dq-next-btn" onclick={handleNext}>Next <ArrowRight class="h-4 w-4" /></button>
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
		height: 85vh;
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
		background: linear-gradient(
			90deg,
			var(--color-primary),
			var(--color-secondary),
			var(--color-primary)
		);
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
		transition:
			color 0.2s ease,
			transform 0.2s ease;
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
		transition:
			color 0.2s ease,
			transform 0.2s ease;
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
		flex: 1 1 0;
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
		transition:
			transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1),
			box-shadow 0.3s ease;
	}

	.dq-cover-wrap:hover {
		transform: scale(1.03) translateY(-4px);
		box-shadow:
			0 25px 50px -12px rgba(0, 0, 0, 0.5),
			0 0 60px 10px color-mix(in srgb, var(--color-primary) 25%, transparent);
	}

	:global(.dq-cover) {
		width: 260px;
		height: 260px;
		object-fit: cover;
		display: block;
	}

	:global(.dq-cover-skeleton) {
		width: 260px;
		height: 260px;
		border-radius: 0;
	}

	:global(.dq-cover-mobile) {
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
			height: 100vh;
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
