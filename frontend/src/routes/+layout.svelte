<script lang="ts">
	import '../app.css';
	import { browser } from '$app/environment';
	import { goto, beforeNavigate, afterNavigate } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { errorModal } from '$lib/stores/errorModal';
	import { libraryStore } from '$lib/stores/library';
	import { integrationStore } from '$lib/stores/integration';
	import { initCacheTTLs } from '$lib/stores/cacheTtl';
	import { playerStore } from '$lib/stores/player.svelte';
	import { launchYouTubePlayback } from '$lib/player/launchYouTubePlayback';
	import { playbackToast } from '$lib/stores/playbackToast.svelte';
	import { scrobbleManager } from '$lib/stores/scrobble.svelte';
	import Player from '$lib/components/Player.svelte';
	import YouTubeIcon from '$lib/components/YouTubeIcon.svelte';
	import SearchSuggestions from '$lib/components/SearchSuggestions.svelte';
	import type { SuggestResult } from '$lib/types';
	import { onMount, onDestroy } from 'svelte';
	import { cancelPendingImages } from '$lib/utils/lazyImage';
	import { fetchActiveRequestCount, type RequestCountChangedDetail } from '$lib/utils/requestsApi';
	import { createNavigationProgressController } from '$lib/utils/navigationProgress';
	import { fromStore } from 'svelte/store';
	import { Settings, Search, House, Compass, Menu, Tv, Headphones, Download, PanelLeft, TriangleAlert, Info, X } from 'lucide-svelte';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	let query = $state('');
	let activeRequestCount = $state(0);
	let requestCountInterval: ReturnType<typeof setInterval> | null = null;
	let requestsPageActive = false;
	let modalQuery = $state('');
	let showNavigationProgress = $state(false);

	const NAV_PROGRESS_DELAY_MS = 120;
	const NAV_PROGRESS_MIN_VISIBLE_MS = 220;
	const navigationProgress = createNavigationProgressController({
		delayMs: NAV_PROGRESS_DELAY_MS,
		minVisibleMs: NAV_PROGRESS_MIN_VISIBLE_MS,
		onVisibleChange: (visible) => {
			showNavigationProgress = visible;
		}
	});

	beforeNavigate(() => {
		navigationProgress.start();
		cancelPendingImages();
	});

	afterNavigate(() => {
		navigationProgress.finish();
	});



	async function pollRequestCount() {
		try {
			activeRequestCount = await fetchActiveRequestCount();
		} catch {
			// ignore errors silently
		}
	}

	function handleRequestCountChanged(event: Event) {
		const detail = (event as CustomEvent<RequestCountChangedDetail>).detail;
		if (typeof detail?.count === 'number') {
			activeRequestCount = detail.count;
			return;
		}

		void pollRequestCount();
	}

	function handleRequestsPageActive(event: Event) {
		const active = (event as CustomEvent<boolean>).detail;
		requestsPageActive = active;
		if (active) {
			if (requestCountInterval) {
				clearInterval(requestCountInterval);
				requestCountInterval = null;
			}
		} else {
			if (!requestCountInterval) {
				requestCountInterval = setInterval(pollRequestCount, 10_000);
			}
		}
	}

	onMount(() => {
		initCacheTTLs();
		libraryStore.initialize();
		void integrationStore.ensureLoaded();
		document.addEventListener('keydown', handleGlobalKeydown);
		window.addEventListener('request-count-changed', handleRequestCountChanged);
		window.addEventListener('requests-page-active', handleRequestsPageActive);
		void restorePlayerSession();
		void scrobbleManager.init();
		void pollRequestCount();
		requestCountInterval = setInterval(pollRequestCount, 10_000);
	});

	onDestroy(() => {
		navigationProgress.cleanup();
		if (browser) {
			document.removeEventListener('keydown', handleGlobalKeydown);
			window.removeEventListener('request-count-changed', handleRequestCountChanged);
			window.removeEventListener('requests-page-active', handleRequestsPageActive);
		}
		if (requestCountInterval) clearInterval(requestCountInterval);
	});

	function handleGlobalKeydown(e: KeyboardEvent): void {
		const tag = (e.target as HTMLElement)?.tagName;
		if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
		if (!playerStore.isPlayerVisible) return;

		switch (e.key) {
			case ' ':
				e.preventDefault();
				playerStore.togglePlay();
				break;
			case 'ArrowRight':
				e.preventDefault();
				playerStore.seekTo(Math.min(playerStore.progress + 10, playerStore.duration));
				break;
			case 'ArrowLeft':
				e.preventDefault();
				playerStore.seekTo(Math.max(playerStore.progress - 10, 0));
				break;
			case 'ArrowUp':
				e.preventDefault();
				playerStore.setVolume(playerStore.volume + 5);
				break;
			case 'ArrowDown':
				e.preventDefault();
				playerStore.setVolume(playerStore.volume - 5);
				break;
		}
	}

	async function restorePlayerSession(): Promise<void> {
		const session = playerStore.restoreSession();
		if (!session) return;

		try {
			if (session.nowPlaying.sourceType === 'youtube') {
				if (!session.nowPlaying.videoId) return;
				await launchYouTubePlayback({
					albumId: session.nowPlaying.albumId,
					albumName: session.nowPlaying.albumName,
					artistName: session.nowPlaying.artistName,
					coverUrl: session.nowPlaying.coverUrl,
					videoId: session.nowPlaying.videoId,
					embedUrl: session.nowPlaying.embedUrl
				});
			} else {
				playerStore.resumeSession();
			}
		} catch {}
	}

	function handleSearch() {
		if (query.trim()) {
			goto(`/search?q=${encodeURIComponent(query)}`);
		}
	}

	function handleModalSearch() {
		if (modalQuery.trim()) {
			goto(`/search?q=${encodeURIComponent(modalQuery)}`);
			const modal = document.getElementById('search_modal') as HTMLDialogElement;
			if (modal) modal.close();
			modalQuery = '';
		}
	}

	function handleSuggestionSelect(result: SuggestResult) {
		const routeId = result.type === 'artist' ? '/artist/[id]' : '/album/[id]';
		goto(resolve(routeId, { id: result.musicbrainz_id }));
	}

	function handleModalSuggestionSelect(result: SuggestResult) {
		(document.getElementById('search_modal') as HTMLDialogElement)?.close();
		const routeId = result.type === 'artist' ? '/artist/[id]' : '/album/[id]';
		goto(resolve(routeId, { id: result.musicbrainz_id }));
	}

	const integrations = fromStore(integrationStore);
	const lidarrConfigured = $derived(integrations.current.lidarr || !integrations.current.loaded);
</script>

<div data-theme="musicseerr">
	{#if showNavigationProgress}
		<div class="fixed top-0 left-0 right-0 z-[120] pointer-events-none">
			<progress class="progress progress-primary w-full h-1"></progress>
		</div>
	{/if}

	<div class="drawer drawer-open">
		<input id="main-drawer" type="checkbox" class="drawer-toggle" />

		<div class="drawer-content flex flex-col">
			<div class="navbar bg-base-100 shadow-sm sticky top-0 z-50">
				<div class="navbar-start w-auto">
					<a href="/" class="btn btn-ghost" aria-label="Home">
						<img src="/logo_wide.png" alt="Musicseerr" class="h-8" />
					</a>
				</div>
			<div class="navbar-center grow px-4 justify-center">
					{#if lidarrConfigured}
						<div class="w-full max-w-2xl">
							<SearchSuggestions
								bind:query
								onSearch={handleSearch}
								onSelect={handleSuggestionSelect}
								id="navbar-suggest"
							/>
						</div>
					{/if}
				</div>
				<div class="navbar-end w-auto">
				</div>
			</div>

			<div class="flex-1" class:pb-24={playerStore.isPlayerVisible}>
				{@render children()}
			</div>
		</div>

		<div class="drawer-side is-drawer-close:overflow-visible">
			<label for="main-drawer" aria-label="close sidebar" class="drawer-overlay"></label>
			<div
				class="is-drawer-close:w-16 is-drawer-open:w-64 bg-base-200 flex flex-col items-start min-h-full"
			>
				<ul class="menu w-full grow p-2 [&_li>*]:py-3">
					{#if lidarrConfigured}
						<li>
							<button
								onclick={() =>
									(document.getElementById('search_modal') as HTMLDialogElement)?.showModal()}
								class="is-drawer-close:tooltip is-drawer-close:tooltip-right"
								data-tip="Search"
							>
								<Search class="h-6 w-6" />
								<span class="is-drawer-close:hidden">Search</span>
							</button>
						</li>

						<div class="divider my-0"></div>
					{/if}

					<li>
						<a
							href="/"
							class="is-drawer-close:tooltip is-drawer-close:tooltip-right"
							data-tip="Home"
						>
							<House class="h-6 w-6" />
							<span class="is-drawer-close:hidden">Home</span>
						</a>
					</li>

					<li>
						<a
							href="/discover"
							class="is-drawer-close:tooltip is-drawer-close:tooltip-right"
							data-tip="Discover"
						>
							<Compass class="h-6 w-6" />
							<span class="is-drawer-close:hidden">Discover</span>
						</a>
					</li>

					{#if lidarrConfigured}
						<li>
							<a
								href="/library"
								class="is-drawer-close:tooltip is-drawer-close:tooltip-right"
								data-tip="Library"
							>
								<Menu class="h-6 w-6" />
								<span class="is-drawer-close:hidden">Library</span>
							</a>
						</li>
					{/if}

					{#if integrations.current.youtube || integrations.current.jellyfin || integrations.current.localfiles}
						<div class="divider my-0"></div>
					{/if}

					{#if integrations.current.youtube}
						<li>
							<a
								href="/library/youtube"
								class="is-drawer-close:tooltip is-drawer-close:tooltip-right"
								data-tip="YouTube"
							>
								<YouTubeIcon class="h-6 w-6 text-error" />
								<span class="is-drawer-close:hidden">YouTube</span>
							</a>
						</li>
					{/if}

					{#if integrations.current.jellyfin}
						<li>
							<a
								href="/library/jellyfin"
								class="is-drawer-close:tooltip is-drawer-close:tooltip-right"
								data-tip="Jellyfin"
							>
								<Tv class="h-6 w-6 text-info" />
								<span class="is-drawer-close:hidden">Jellyfin</span>
							</a>
						</li>
					{/if}

					{#if integrations.current.localfiles}
						<li>
							<a
								href="/library/local"
								class="is-drawer-close:tooltip is-drawer-close:tooltip-right"
								data-tip="Local Files"
							>
								<Headphones class="h-6 w-6 text-accent" />
								<span class="is-drawer-close:hidden">Local Files</span>
							</a>
						</li>
					{/if}

					{#if lidarrConfigured}
						<div class="divider my-0"></div>
						<li>
							<a
								href="/requests"
								class="is-drawer-close:tooltip is-drawer-close:tooltip-right"
								data-tip="Requests"
							>
								<div class="relative">
									<Download class="h-6 w-6" />
									{#if activeRequestCount > 0}
										<span
											class="absolute -top-2 -right-2 badge badge-info badge-xs w-4 h-4 p-0 text-[10px] font-bold"
											>{activeRequestCount}</span
										>
									{/if}
								</div>
								<span class="is-drawer-close:hidden">Requests</span>
							</a>
						</li>
					{/if}
				</ul>
				<div class="w-full p-2 flex flex-col gap-1">
					<div class="is-drawer-close:tooltip is-drawer-close:tooltip-right" data-tip="Settings">
						<a
							href="/settings"
							class="btn btn-ghost btn-circle"
							aria-label="Settings"
						>
							<Settings class="h-5 w-5" />
						</a>
					</div>
					<div class="is-drawer-close:tooltip is-drawer-close:tooltip-right" data-tip="Open">
						<label
							for="main-drawer"
							class="btn btn-ghost btn-circle drawer-button is-drawer-open:rotate-y-180"
						>
							<PanelLeft class="h-5 w-5" />
						</label>
					</div>
				</div>
			</div>
		</div>
	</div>

	<dialog id="search_modal" class="modal">
		<div class="modal-box overflow-visible">
			<form method="dialog">
				<button class="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" aria-label="Close"
					><X class="h-4 w-4" /></button
				>
			</form>
			<h3 class="font-bold text-lg mb-4">Search</h3>
			<SearchSuggestions
				bind:query={modalQuery}
				onSearch={handleModalSearch}
				onSelect={handleModalSuggestionSelect}
				placeholder="Search albums or artists..."
				autofocus={true}
				id="modal-suggest"
			/>
		</div>
		<form method="dialog" class="modal-backdrop">
			<button aria-label="Close modal">close</button>
		</form>
	</dialog>

	{#if $errorModal.show}
		<dialog class="modal modal-open">
			<div class="modal-box bg-base-200 border border-base-300 shadow-xl max-w-md">
				<button
					class="btn btn-sm btn-circle btn-ghost absolute right-3 top-3 opacity-60 hover:opacity-100"
					onclick={() => errorModal.hide()}
					aria-label="Close"
				>
					<X class="h-4 w-4" />
				</button>

				<div class="flex flex-col items-center text-center pt-2 pb-1">
					<div class="bg-error/10 rounded-full p-3 mb-4">
						<TriangleAlert class="h-8 w-8 text-error" />
					</div>

					<h3 class="text-lg font-bold text-base-content mb-2">
						{$errorModal.title}
					</h3>

					<p class="text-sm text-base-content/70 leading-relaxed">
						{$errorModal.message}
					</p>
				</div>

				{#if $errorModal.details}
					<div class="mt-4 rounded-box bg-base-300/60 border border-base-300 p-4">
						<div class="flex gap-3 items-start">
							<Info class="h-5 w-5 text-info flex-shrink-0 mt-0.5" />
							<p class="text-sm text-base-content/80 leading-relaxed text-left">
								{$errorModal.details}
							</p>
						</div>
					</div>
				{/if}

				<div class="modal-action justify-center mt-5">
					<button class="btn btn-accent btn-sm px-6" onclick={() => errorModal.hide()}>
						Dismiss
					</button>
				</div>
			</div>
			<form method="dialog" class="modal-backdrop" onclick={() => errorModal.hide()}>
				<button>close</button>
			</form>
		</dialog>
	{/if}

	{#if playbackToast.visible}
		<div
			class="fixed z-50 left-1/2 -translate-x-1/2 transition-all duration-300"
			style="bottom: {playerStore.isPlayerVisible ? '100px' : '16px'}"
		>
			<div
				class="alert {playbackToast.type === 'error'
					? 'alert-error'
					: playbackToast.type === 'warning'
						? 'alert-warning'
						: 'alert-info'} shadow-lg px-4 py-2 min-w-64 max-w-md"
			>
				{#if playbackToast.type === 'error'}
					<X class="h-5 w-5 flex-shrink-0" />
				{:else if playbackToast.type === 'warning'}
					<TriangleAlert class="h-5 w-5 flex-shrink-0" />
				{:else}
					<Info class="h-5 w-5 flex-shrink-0" />
				{/if}
				<span class="text-sm">{playbackToast.message}</span>
				<button
					class="btn btn-ghost btn-xs btn-circle"
					onclick={() => playbackToast.dismiss()}
					aria-label="Dismiss"
				>
					<X class="h-3.5 w-3.5" />
				</button>
			</div>
		</div>
	{/if}

	<Player />
</div>
