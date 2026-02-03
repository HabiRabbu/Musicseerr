<script lang="ts">
	import "../app.css";
	import { goto, beforeNavigate } from '$app/navigation';
	import { errorModal } from '$lib/stores/errorModal';
	import { libraryStore } from '$lib/stores/library';
	import { integrationStore } from '$lib/stores/integration';
	import { onMount } from 'svelte';
	import { cancelPendingImages } from '$lib/utils/lazyImage';
	
	let query = '';
	let modalQuery = '';

	beforeNavigate(() => {
		cancelPendingImages();
	});

	onMount(() => {
		libraryStore.initialize();
	});

	function handleSearch(e: Event) {
		e.preventDefault();
		if (query.trim()) {
			goto(`/search?q=${encodeURIComponent(query)}`);
		}
	}

	function handleModalSearch(e: Event) {
		e.preventDefault();
		if (modalQuery.trim()) {
			goto(`/search?q=${encodeURIComponent(modalQuery)}`);
			const modal = document.getElementById('search_modal') as HTMLDialogElement;
			if (modal) modal.close();
			modalQuery = '';
		}
	}

	function handleSettingsClick(e: Event) {
		e.preventDefault();
		const dropdown = document.querySelector('.dropdown') as HTMLDetailsElement;
		if (dropdown) {
			dropdown.open = false;
		}
		goto('/settings');
	}

	$: lidarrConfigured = $integrationStore.lidarr || !$integrationStore.loaded;
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
						<form on:submit|preventDefault={handleSearch} class="w-full max-w-2xl">
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
				<details class="dropdown dropdown-end">
					<summary class="btn btn-ghost btn-circle btn-lg" aria-label="User Profile">
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-6 w-6">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
					</svg>
					</summary>
						<ul class="dropdown-content menu bg-base-200 rounded-box z-50 w-52 p-2 shadow">
							<li>
								<a href="/settings" on:click={handleSettingsClick}>
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
			
			
			<slot />
		</div>

		
		<div class="drawer-side is-drawer-close:overflow-visible">
			<label for="main-drawer" aria-label="close sidebar" class="drawer-overlay"></label>
			<div class="is-drawer-close:w-16 is-drawer-open:w-64 bg-base-200 flex flex-col items-start min-h-full">
				
			<ul class="menu w-full grow p-2 [&_li>*]:py-3">
				
				{#if lidarrConfigured}
					<li>
						<button 
							on:click={() => (document.getElementById('search_modal') as HTMLDialogElement)?.showModal()} 
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
			<form on:submit|preventDefault={handleModalSearch}>
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
					<button class="btn btn-accent" on:click={() => errorModal.hide()}>Got it</button>
				</div>
			</div>
			<form method="dialog" class="modal-backdrop" on:click={() => errorModal.hide()}>
				<button>close</button>
			</form>
		</dialog>
	{/if}
</div>
