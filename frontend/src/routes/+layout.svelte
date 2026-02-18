<script lang="ts">
	import "../app.css";
	import { goto, beforeNavigate } from '$app/navigation';
	import { errorModal } from '$lib/stores/errorModal';
	import { libraryStore } from '$lib/stores/library';
	import { integrationStore } from '$lib/stores/integration';
	import { initCacheTTLs } from '$lib/stores/cacheTtl';
	import { playerStore } from '$lib/stores/player.svelte';
	import { launchYouTubePlayback } from '$lib/player/launchYouTubePlayback';
	import { playbackToast } from '$lib/stores/playbackToast.svelte';
	import Player from '$lib/components/Player.svelte';
	import YouTubeIcon from '$lib/components/YouTubeIcon.svelte';
	import { onMount, onDestroy } from 'svelte';
	import { cancelPendingImages } from '$lib/utils/lazyImage';
	import { fetchActiveRequestCount, type RequestCountChangedDetail } from '$lib/utils/requestsApi';
	import { fromStore } from 'svelte/store';
	
	let query = '';
	let activeRequestCount = $state(0);
	let requestCountInterval: ReturnType<typeof setInterval> | null = null;
	let requestsPageActive = false;
	let modalQuery = '';
	let userDropdown: HTMLDetailsElement;

	beforeNavigate(() => {
		cancelPendingImages();
	});

	function handleClickOutside(event: MouseEvent) {
		if (userDropdown && userDropdown.open && !userDropdown.contains(event.target as Node)) {
			userDropdown.open = false;
		}
	}

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
		document.addEventListener('click', handleClickOutside);
		document.addEventListener('keydown', handleGlobalKeydown);
		window.addEventListener('request-count-changed', handleRequestCountChanged);
		window.addEventListener('requests-page-active', handleRequestsPageActive);
		void restorePlayerSession();
		void pollRequestCount();
		requestCountInterval = setInterval(pollRequestCount, 10_000);
	});

	onDestroy(() => {
		document.removeEventListener('click', handleClickOutside);
		document.removeEventListener('keydown', handleGlobalKeydown);
		window.removeEventListener('request-count-changed', handleRequestCountChanged);
		window.removeEventListener('requests-page-active', handleRequestsPageActive);
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

	function handleSettingsClick() {
		userDropdown.open = false;
		goto('/settings');
	}

	const integrations = fromStore(integrationStore);
	const lidarrConfigured = $derived(integrations.current.lidarr || !integrations.current.loaded);
</script>

<div data-theme="musicseerr">
	<div class="drawer drawer-open">
		<input id="main-drawer" type="checkbox" class="drawer-toggle" />
		
		
		<div class="drawer-content flex flex-col">
			
			<div class="navbar bg-base-100 shadow-sm sticky top-0 z-50">
				<div class="navbar-start">
					<a href="/" class="btn btn-ghost" aria-label="Home">
						<img src="/logo_wide.png" alt="Musicseerr" class="h-8" />
					</a>
				</div>
				<div class="navbar-center">
					{#if lidarrConfigured}
						<form onsubmit={(e) => { e.preventDefault(); handleSearch(); }} class="w-full max-w-2xl">
							<label class="input input-bordered flex items-center gap-2 w-full">
								<svg class="h-[1em] opacity-50" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
									<g stroke-linejoin="round" stroke-linecap="round" stroke-width="2.5" fill="none" stroke="currentColor">
										<circle cx="11" cy="11" r="8"></circle>
										<path d="m21 21-4.3-4.3"></path>
									</g>
								</svg>
								<input
									type="search"
									placeholder="Search..."
									bind:value={query}
									class="grow"
								/>
							</label>
						</form>
					{/if}
				</div>
			<div class="navbar-end">
				<details class="dropdown dropdown-end" bind:this={userDropdown}>
					<summary class="btn btn-ghost btn-circle btn-lg" aria-label="User Profile">
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-6 w-6">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
					</svg>
					</summary>
						<ul class="dropdown-content menu bg-base-200 rounded-box z-[100] w-52 p-2 shadow">
							<li>
								<a href="/settings" onclick={(e: MouseEvent) => { e.preventDefault(); handleSettingsClick(); }}>
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-5 w-5">
									<circle cx="12" cy="12" r="3"></circle>
									<path d="M12 1v6m0 6v6m-9-9h6m6 0h6M4.5 5.5l4 4m6 6l4 4m0-14l-4 4m-6 6l-4 4"></path>
								</svg>
									Settings
								</a>
							</li>
						</ul>
					</details>
				</div>
			</div>
			
			
			<div class="flex-1" class:pb-24={playerStore.isPlayerVisible}>
				<slot />
			</div>
		</div>

		
		<div class="drawer-side is-drawer-close:overflow-visible">
			<label for="main-drawer" aria-label="close sidebar" class="drawer-overlay"></label>
			<div class="is-drawer-close:w-16 is-drawer-open:w-64 bg-base-200 flex flex-col items-start min-h-full">
				
			<ul class="menu w-full grow p-2 [&_li>*]:py-3">
				
				{#if lidarrConfigured}
					<li>
						<button 
							onclick={() => (document.getElementById('search_modal') as HTMLDialogElement)?.showModal()} 
							class="is-drawer-close:tooltip is-drawer-close:tooltip-right" 
							data-tip="Search"
						>
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-6 w-6">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
						</svg>
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
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-6 w-6">
						<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"></path>
						<path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
					</svg>
						<span class="is-drawer-close:hidden">Home</span>
					</a>
				</li>

				<li>
					<a 
						href="/discover" 
						class="is-drawer-close:tooltip is-drawer-close:tooltip-right" 
						data-tip="Discover"
					>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-6 w-6">
						<circle cx="12" cy="12" r="10"></circle>
						<polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon>
					</svg>
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
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-6 w-6">
							<rect x="3" y="3" width="18" height="18" rx="2"></rect>
							<path d="M7 7h10"></path>
							<path d="M7 12h10"></path>
							<path d="M7 17h10"></path>
						</svg>
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
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-6 w-6 text-info">
							<rect x="2" y="7" width="20" height="15" rx="2" ry="2"></rect>
							<polyline points="17 2 12 7 7 2"></polyline>
						</svg>
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
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-6 w-6 text-accent">
							<path d="M3 18v-6a9 9 0 0 1 18 0v6"></path>
							<path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z"></path>
							<path d="M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path>
						</svg>
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
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-6 w-6">
									<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
									<polyline points="7 10 12 15 17 10"></polyline>
									<line x1="12" y1="15" x2="12" y2="3"></line>
								</svg>
								{#if activeRequestCount > 0}
									<span class="absolute -top-2 -right-2 badge badge-info badge-xs w-4 h-4 p-0 text-[10px] font-bold">{activeRequestCount}</span>
								{/if}
							</div>
							<span class="is-drawer-close:hidden">Requests</span>
						</a>
					</li>
				{/if}
			</ul>				
				<div class="m-2 is-drawer-close:tooltip is-drawer-close:tooltip-right" data-tip="Open">
					<label for="main-drawer" class="btn btn-ghost btn-circle drawer-button is-drawer-open:rotate-y-180">
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-5 w-5">
						<path d="M4 4m0 2a2 2 0 0 1 2 -2h12a2 2 0 0 1 2 2v12a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2z"></path>
						<path d="M9 4v16"></path>
						<path d="M14 10l2 2l-2 2"></path>
					</svg>
					</label>
				</div>
			</div>
		</div>
	</div>

	
	<dialog id="search_modal" class="modal">
		<div class="modal-box">
			<form method="dialog">
				<button class="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" aria-label="Close">✕</button>
			</form>
			<h3 class="font-bold text-lg mb-4">Search</h3>
			<form onsubmit={(e) => { e.preventDefault(); handleModalSearch(); }}>
				<input
					type="text"
					placeholder="Search albums or artists..."
					bind:value={modalQuery}
					class="input input-bordered w-full"
					autofocus
				/>
				<div class="modal-action">
					<button type="submit" class="btn btn-primary">Search</button>
				</div>
			</form>
		</div>
		<form method="dialog" class="modal-backdrop">
			<button aria-label="Close modal">close</button>
		</form>
	</dialog>

	
	{#if $errorModal.show}
		<dialog class="modal modal-open">
			<div class="modal-box bg-base-300">
				<h3 class="text-lg font-bold text-primary mb-4 flex items-center">
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon">
						<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
					</svg>
					{$errorModal.title}
				</h3>
				<p class="py-4 text-base-content">{$errorModal.message}</p>
				{#if $errorModal.details}
					<div class="alert bg-primary text-accent-content mb-4">
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon">
							<path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
						<span class="text-sm">{$errorModal.details}</span>
					</div>
				{/if}
				<div class="modal-action">
					<button class="btn btn-accent" onclick={() => errorModal.hide()}>Got it</button>
				</div>
			</div>
			<form method="dialog" class="modal-backdrop" onclick={() => errorModal.hide()}>
				<button>close</button>
			</form>
		</dialog>
	{/if}

	{#if playbackToast.visible}
		<div class="fixed z-50 left-1/2 -translate-x-1/2 transition-all duration-300" style="bottom: {playerStore.isPlayerVisible ? '100px' : '16px'}">
			<div class="alert {playbackToast.type === 'error' ? 'alert-error' : playbackToast.type === 'warning' ? 'alert-warning' : 'alert-info'} shadow-lg px-4 py-2 min-w-64 max-w-md">
				{#if playbackToast.type === 'error'}
					<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
				{:else if playbackToast.type === 'warning'}
					<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
				{/if}
				<span class="text-sm">{playbackToast.message}</span>
				<button class="btn btn-ghost btn-xs btn-circle" onclick={() => playbackToast.dismiss()} aria-label="Dismiss">
					<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
				</button>
			</div>
		</div>
	{/if}

	<Player />
</div>
