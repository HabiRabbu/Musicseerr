<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { preferencesStore } from '$lib/stores/preferences';
	import type { UserPreferences, ReleaseTypeOption } from '$lib/types';

	let activeTab = 'settings';
	let preferences: UserPreferences = {
		primary_types: [],
		secondary_types: [],
		release_statuses: []
	};
	let saving = false;
	let saveMessage = '';
	
	// Cache state
	let cacheStats: any = null;
	let loadingCache = false;
	let clearingCache = false;
	let cacheMessage = '';

	
	const primaryTypes: ReleaseTypeOption[] = [
		{ id: 'album', title: 'Album', description: 'Full-length studio albums' },
		{ id: 'ep', title: 'EP', description: 'Extended Play releases (shorter than albums)' },
		{ id: 'single', title: 'Single', description: 'Individual track releases' },
		{ id: 'broadcast', title: 'Broadcast', description: 'Radio or TV broadcast recordings' },
		{ id: 'other', title: 'Other', description: 'Miscellaneous release types' }
	];

	
	const secondaryTypes: ReleaseTypeOption[] = [
		{ id: 'studio', title: 'Studio', description: 'Original studio recordings' },
		{ id: 'compilation', title: 'Compilation', description: 'Greatest hits and collections' },
		{ id: 'soundtrack', title: 'Soundtrack', description: 'Music from movies, games, or TV' },
		{ id: 'spokenword', title: 'Spoken Word', description: 'Audiobooks and spoken content' },
		{ id: 'interview', title: 'Interview', description: 'Interview recordings' },
		{ id: 'audiobook', title: 'Audio Drama', description: 'Dramatic audio productions' },
		{ id: 'live', title: 'Live', description: 'Live concert recordings' },
		{ id: 'remix', title: 'Remix', description: 'Remix albums' },
		{ id: 'dj-mix', title: 'DJ-mix', description: 'DJ mixed compilations' },
		{ id: 'mixtape/street', title: 'Mixtape/Street', description: 'Unofficial mixtapes' },
		{ id: 'demo', title: 'Demo', description: 'Demo recordings' }
	];

	
	const releaseStatuses: ReleaseTypeOption[] = [
		{ id: 'official', title: 'Official', description: 'Officially released by the artist or label' },
		{ id: 'promotion', title: 'Promotion', description: 'Promotional releases' },
		{ id: 'bootleg', title: 'Bootleg', description: 'Unofficial bootleg recordings' },
		{ id: 'pseudo-release', title: 'Pseudo-Release', description: 'Placeholder or meta releases' }
	];

	function toggleType(category: 'primary_types' | 'secondary_types' | 'release_statuses', id: string) {
		const index = preferences[category].indexOf(id);
		if (index > -1) {
			preferences[category] = preferences[category].filter((t) => t !== id);
		} else {
			preferences[category] = [...preferences[category], id];
		}
	}
	
	async function loadCacheStats() {
		loadingCache = true;
		cacheMessage = '';
		try {
			const response = await fetch('/api/cache/stats');
			if (response.ok) {
				cacheStats = await response.json();
			} else {
				cacheMessage = 'Failed to load cache statistics';
			}
		} catch (error) {
			console.error('Failed to load cache stats:', error);
			cacheMessage = 'Failed to load cache statistics';
		} finally {
			loadingCache = false;
		}
	}
	
	async function clearCache(type: 'all' | 'memory' | 'disk') {
		if (!confirm(`Are you sure you want to clear the ${type === 'all' ? 'entire' : type} cache?`)) {
			return;
		}
		
		clearingCache = true;
		cacheMessage = '';
		try {
			const response = await fetch(`/api/cache/clear/${type}`, {
				method: 'POST'
			});
			
			if (response.ok) {
				const result = await response.json();
				cacheMessage = result.message;
				await loadCacheStats();
				
				setTimeout(() => {
					cacheMessage = '';
				}, 5000);
			} else {
				const error = await response.json();
				cacheMessage = error.detail || 'Failed to clear cache';
			}
		} catch (error) {
			console.error('Failed to clear cache:', error);
			cacheMessage = 'Failed to clear cache';
		} finally {
			clearingCache = false;
		}
	}

	async function handleSave() {
		saving = true;
		saveMessage = '';

		const success = await preferencesStore.save(preferences);

		if (success) {
			saveMessage = 'Settings saved successfully! Artist pages and search results will refresh automatically.';
			
			
			if (browser) {
				window.dispatchEvent(new CustomEvent('artist-refresh'));
				window.dispatchEvent(new CustomEvent('search-refresh'));
			}
			
			setTimeout(() => {
				saveMessage = '';
			}, 5000);
		} else {
			saveMessage = 'Failed to save settings. Please try again.';
		}

		saving = false;
	}
	
	function switchTab(tab: string) {
		activeTab = tab;
		if (tab === 'cache' && !cacheStats) {
			loadCacheStats();
		}
	}

	onMount(async () => {
		await preferencesStore.load();
		preferencesStore.subscribe((prefs) => {
			preferences = { ...prefs };
		});
	});
</script>

<div class="min-h-screen bg-base-100">
	<div class="container mx-auto p-4 max-w-7xl">
		
		<div class="mb-6">
			<h1 class="text-3xl font-bold">Settings</h1>
			<p class="text-base-content/70 mt-2">
				Manage your preferences and application settings
			</p>
		</div>

		<div class="flex flex-col lg:flex-row gap-6">
			
			<aside class="w-full lg:w-80">
				<ul class="menu bg-base-200 rounded-box p-2">
					<li>
						<button
							class="text-base justify-start"
							class:btn-active={activeTab === 'settings'}
							on:click={() => switchTab('settings')}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								class="w-5 h-5"
							>
								<circle cx="12" cy="12" r="3"></circle>
								<path
									d="M12 1v6m0 6v6m-9-9h6m6 0h6M4.5 5.5l4 4m6 6l4 4m0-14l-4 4m-6 6l-4 4"
								></path>
							</svg>
							<span>Release Preferences</span>
						</button>
					</li>
					<li>
						<button
							class="text-base justify-start"
							class:btn-active={activeTab === 'cache'}
							on:click={() => switchTab('cache')}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								class="w-5 h-5"
							>
								<path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7"></path>
								<path d="M21 3H3v4h18V3z"></path>
								<path d="M10 12h4"></path>
							</svg>
							<span>Cache</span>
						</button>
					</li>
				</ul>
			</aside>

			
			<main class="flex-1">
				{#if activeTab === 'settings'}
					<div class="card bg-base-200">
						<div class="card-body">
							<h2 class="card-title text-2xl mb-4">Included Releases</h2>
							<p class="text-base-content/70 mb-6">
								Choose which types of releases to show in artist pages and search results.
							</p>

							
							<div class="mb-8">
								<h3 class="text-xl font-semibold mb-4">Primary Types</h3>
								<div class="overflow-x-auto">
									<table class="table">
										<tbody>
											{#each primaryTypes as type}
												<tr>
													<td class="w-12">
														<input
															type="checkbox"
															class="checkbox checkbox-primary"
															checked={preferences.primary_types.includes(type.id)}
															on:change={() => toggleType('primary_types', type.id)}
														/>
													</td>
													<td class="font-medium">{type.title}</td>
													<td class="text-base-content/70">{type.description}</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</div>

							
							<div class="mb-8">
								<h3 class="text-xl font-semibold mb-4">Secondary Types</h3>
								<div class="overflow-x-auto">
									<table class="table">
										<tbody>
											{#each secondaryTypes as type}
												<tr>
													<td class="w-12">
														<input
															type="checkbox"
															class="checkbox checkbox-primary"
															checked={preferences.secondary_types.includes(type.id)}
															on:change={() => toggleType('secondary_types', type.id)}
														/>
													</td>
													<td class="font-medium">{type.title}</td>
													<td class="text-base-content/70">{type.description}</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</div>

							
							<div class="mb-8">
								<h3 class="text-xl font-semibold mb-4">Release Statuses</h3>
								<div class="overflow-x-auto">
									<table class="table">
										<tbody>
											{#each releaseStatuses as status}
												<tr>
													<td class="w-12">
														<input
															type="checkbox"
															class="checkbox checkbox-primary"
															checked={preferences.release_statuses.includes(status.id)}
															on:change={() => toggleType('release_statuses', status.id)}
														/>
													</td>
													<td class="font-medium">{status.title}</td>
													<td class="text-base-content/70">{status.description}</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</div>

							
							<div class="card-actions justify-end items-center gap-4">
								{#if saveMessage}
									<div
										class="alert flex-1"
										class:alert-success={saveMessage.includes('success')}
										class:alert-error={saveMessage.includes('Failed')}
									>
										{#if saveMessage.includes('success')}
											<svg
												xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
												class="h-6 w-6 shrink-0 stroke-current"
												fill="none"
												viewBox="0 0 24 24"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													stroke-width="2"
													d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
												/>
											</svg>
										{:else}
											<svg
												xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
												class="h-6 w-6 shrink-0 stroke-current"
												fill="none"
												viewBox="0 0 24 24"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													stroke-width="2"
													d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
												/>
											</svg>
										{/if}
										<span>{saveMessage}</span>
									</div>
								{/if}
								<button class="btn btn-primary" on:click={handleSave} disabled={saving}>
									{#if saving}
										<span class="loading loading-spinner loading-sm"></span>
										Saving...
									{:else}
										Save Settings
									{/if}
								</button>
							</div>
						</div>
					</div>
				{:else if activeTab === 'cache'}
					<div class="card bg-base-200">
						<div class="card-body">
							<h2 class="card-title text-2xl mb-4">Cache Management</h2>
							<p class="text-base-content/70 mb-6">
								View cache statistics and clear cached data. The cache stores metadata in memory and cover images on disk.
							</p>

							{#if loadingCache}
								<div class="flex justify-center items-center py-12">
									<span class="loading loading-spinner loading-lg"></span>
								</div>
							{:else if cacheStats}
								<!-- Cache Statistics -->
								<div class="stats stats-vertical lg:stats-horizontal shadow mb-6">
									<div class="stat">
										<div class="stat-title">Memory Entries</div>
										<div class="stat-value text-primary">{cacheStats.memory_entries}</div>
										<div class="stat-desc">{cacheStats.memory_size_mb} MB</div>
									</div>
									
									<div class="stat">
										<div class="stat-title">Cover Images</div>
										<div class="stat-value text-secondary">{cacheStats.disk_cover_count}</div>
										<div class="stat-desc">{cacheStats.disk_cover_size_mb} MB</div>
									</div>
									
									<div class="stat">
										<div class="stat-title">Total Cache</div>
										<div class="stat-value text-accent">{cacheStats.total_size_mb} MB</div>
										<div class="stat-desc">Memory + Disk</div>
									</div>
								</div>

								<!-- Cache Details -->
								<div class="overflow-x-auto mb-6">
									<table class="table">
										<thead>
											<tr>
												<th>Cache Type</th>
												<th>Description</th>
												<th>Size</th>
											</tr>
										</thead>
										<tbody>
											<tr>
												<td class="font-medium">Memory Cache</td>
												<td class="text-base-content/70">
													Artist & album metadata, search results, MusicBrainz data
												</td>
												<td>{cacheStats.memory_size_mb} MB ({cacheStats.memory_entries} entries)</td>
											</tr>
											<tr>
												<td class="font-medium">Disk Cache</td>
												<td class="text-base-content/70">
													Cover art images stored at /app/cache/covers
												</td>
												<td>{cacheStats.disk_cover_size_mb} MB ({cacheStats.disk_cover_count} files)</td>
											</tr>
										</tbody>
									</table>
								</div>

								<!-- Clear Cache Actions -->
								<div class="divider">Clear Cache</div>
								
								<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
									<div class="card bg-base-100">
										<div class="card-body">
											<h3 class="card-title text-lg">Memory Cache</h3>
											<p class="text-sm text-base-content/70">
												Clear metadata cache. Pages will reload data from sources.
											</p>
											<div class="card-actions justify-end">
												<button 
													class="btn btn-warning btn-sm" 
													on:click={() => clearCache('memory')}
													disabled={clearingCache}
												>
													Clear Memory
												</button>
											</div>
										</div>
									</div>
									
									<div class="card bg-base-100">
										<div class="card-body">
											<h3 class="card-title text-lg">Disk Cache</h3>
											<p class="text-sm text-base-content/70">
												Clear cover images. Images will be re-downloaded as needed.
											</p>
											<div class="card-actions justify-end">
												<button 
													class="btn btn-warning btn-sm" 
													on:click={() => clearCache('disk')}
													disabled={clearingCache}
												>
													Clear Disk
												</button>
											</div>
										</div>
									</div>
									
									<div class="card bg-base-100">
										<div class="card-body">
											<h3 class="card-title text-lg">All Cache</h3>
											<p class="text-sm text-base-content/70">
												Clear everything. Complete fresh start.
											</p>
											<div class="card-actions justify-end">
												<button 
													class="btn btn-error btn-sm" 
													on:click={() => clearCache('all')}
													disabled={clearingCache}
												>
													Clear All
												</button>
											</div>
										</div>
									</div>
								</div>

								{#if cacheMessage}
									<div class="alert alert-success">
										<svg
											xmlns="http://www.w3.org/2000/svg"
											class="h-6 w-6 shrink-0 stroke-current"
											fill="none"
											viewBox="0 0 24 24"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												stroke-width="2"
												d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
											/>
										</svg>
										<span>{cacheMessage}</span>
									</div>
								{/if}

								<!-- Refresh Button -->
								<div class="card-actions justify-end mt-4">
									<button 
										class="btn btn-primary" 
										on:click={loadCacheStats}
										disabled={loadingCache}
									>
										{#if loadingCache}
											<span class="loading loading-spinner loading-sm"></span>
											Loading...
										{:else}
											Refresh Stats
										{/if}
									</button>
								</div>
							{/if}
						</div>
					</div>
				{/if}
			</main>
		</div>
	</div>
</div>
