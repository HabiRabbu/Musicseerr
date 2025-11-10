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
	
	let cacheStats: any = null;
	let loadingCache = false;
	let clearingCache = false;
	let cacheMessage = '';
	
	let lidarrSettings: any = null;
	let loadingLidarr = false;
	let savingLidarr = false;
	let syncingLibrary = false;
	let lidarrMessage = '';
	
	let advancedSettings: any = null;
	let loadingAdvanced = false;
	let savingAdvanced = false;
	let advancedMessage = '';

	
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
	
	async function clearCache(type: 'all' | 'memory' | 'disk' | 'library') {
		const typeLabel = type === 'library' ? 'library database' : type === 'all' ? 'entire' : type;
		if (!confirm(`Are you sure you want to clear the ${typeLabel} cache?`)) {
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
		if (tab === 'lidarr' && !lidarrSettings) {
			loadLidarrSettings();
		}
		if (tab === 'advanced' && !advancedSettings) {
			loadAdvancedSettings();
		}
	}
	
	async function loadLidarrSettings() {
		loadingLidarr = true;
		lidarrMessage = '';
		try {
			const response = await fetch('/api/settings/lidarr');
			if (response.ok) {
				lidarrSettings = await response.json();
			} else {
				lidarrMessage = 'Failed to load Lidarr settings';
			}
		} catch (error) {
			console.error('Failed to load Lidarr settings:', error);
			lidarrMessage = 'Failed to load Lidarr settings';
		} finally {
			loadingLidarr = false;
		}
	}
	
	async function saveLidarrSettings() {
		savingLidarr = true;
		lidarrMessage = '';
		try {
			const response = await fetch('/api/settings/lidarr', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(lidarrSettings)
			});
			
			if (response.ok) {
				const result = await response.json();
				lidarrMessage = 'Settings saved successfully!';
				lidarrSettings = result;
				
				setTimeout(() => {
					lidarrMessage = '';
				}, 5000);
			} else {
				const error = await response.json();
				lidarrMessage = error.detail || 'Failed to save settings';
			}
		} catch (error) {
			console.error('Failed to save Lidarr settings:', error);
			lidarrMessage = 'Failed to save settings';
		} finally {
			savingLidarr = false;
		}
	}
	
	async function syncLibraryNow() {
		syncingLibrary = true;
		lidarrMessage = '';
		try {
			const response = await fetch('/api/library/sync', {
				method: 'POST'
			});
			
			if (response.ok) {
				lidarrMessage = 'Library sync started successfully!';
				// Reload settings to get updated last_sync timestamp
				await loadLidarrSettings();
				
				setTimeout(() => {
					lidarrMessage = '';
				}, 5000);
			} else {
				const error = await response.json();
				lidarrMessage = error.detail || 'Failed to start sync';
			}
		} catch (error) {
			console.error('Failed to sync library:', error);
			lidarrMessage = 'Failed to sync library';
		} finally {
			syncingLibrary = false;
		}
	}
	
	async function loadAdvancedSettings() {
		loadingAdvanced = true;
		advancedMessage = '';
		try {
			const response = await fetch('/api/settings/advanced');
			if (response.ok) {
				advancedSettings = await response.json();
			} else {
				advancedMessage = 'Failed to load advanced settings';
			}
		} catch (error) {
			console.error('Failed to load advanced settings:', error);
			advancedMessage = 'Failed to load advanced settings';
		} finally {
			loadingAdvanced = false;
		}
	}
	
	async function saveAdvancedSettings() {
		savingAdvanced = true;
		advancedMessage = '';
		try {
			const response = await fetch('/api/settings/advanced', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(advancedSettings)
			});
			
			if (response.ok) {
				advancedMessage = 'Advanced settings saved successfully!';
				advancedSettings = await response.json();
				
				setTimeout(() => {
					advancedMessage = '';
				}, 5000);
			} else {
				const error = await response.json();
				advancedMessage = error.detail || 'Failed to save settings';
			}
		} catch (error) {
			console.error('Failed to save advanced settings:', error);
			advancedMessage = 'Failed to save settings';
		} finally {
			savingAdvanced = false;
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
							class:btn-active={activeTab === 'lidarr'}
							on:click={() => switchTab('lidarr')}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								class="w-5 h-5"
							>
								<path d="M9 18V5l12-2v13"></path>
								<circle cx="6" cy="18" r="3"></circle>
								<circle cx="18" cy="16" r="3"></circle>
							</svg>
							<span>Library Sync</span>
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
					<li>
						<button
							class="text-base justify-start"
							class:btn-active={activeTab === 'advanced'}
							on:click={() => switchTab('advanced')}
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
								<path d="M12 1v6m0 6v6"></path>
								<path d="M1 12h6m6 0h6"></path>
								<path d="M4.2 4.2l4.3 4.3m7 7l4.3 4.3"></path>
								<path d="M19.8 4.2l-4.3 4.3m-7 7l-4.3 4.3"></path>
							</svg>
							<span>Advanced</span>
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
								View cache statistics and clear cached data. Uses 2-tier caching: hot items in RAM (100 max), all data persisted on disk.
							</p>

							{#if loadingCache}
								<div class="flex justify-center items-center py-12">
									<span class="loading loading-spinner loading-lg"></span>
								</div>
							{:else if cacheStats}
								<!-- Cache Statistics -->
								<div class="stats stats-vertical lg:stats-horizontal shadow mb-6">
									<div class="stat">
										<div class="stat-title">Memory Cache</div>
										<div class="stat-value text-primary">{cacheStats.memory_entries}</div>
										<div class="stat-desc">{cacheStats.memory_size_mb} MB (hot items)</div>
									</div>
									
									<div class="stat">
										<div class="stat-title">Disk Metadata</div>
										<div class="stat-value text-secondary">{cacheStats.disk_metadata_count}</div>
										<div class="stat-desc">{cacheStats.disk_metadata_albums} albums, {cacheStats.disk_metadata_artists} artists</div>
									</div>
									
									<div class="stat">
										<div class="stat-title">Cover Images</div>
										<div class="stat-value text-accent">{cacheStats.disk_cover_count}</div>
										<div class="stat-desc">{cacheStats.disk_cover_size_mb} MB</div>
									</div>
									
									<div class="stat">
										<div class="stat-title">Total Cache</div>
										<div class="stat-value">{cacheStats.total_size_mb} MB</div>
										<div class="stat-desc">All types</div>
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
												<td class="font-medium">Memory Cache (RAM)</td>
												<td class="text-base-content/70">
													Hot metadata cache - most recently accessed items only
												</td>
												<td>{cacheStats.memory_size_mb} MB ({cacheStats.memory_entries} entries, max 100)</td>
											</tr>
											<tr>
												<td class="font-medium">Disk Metadata Cache</td>
												<td class="text-base-content/70">
													Persistent album/artist metadata at /app/cache/metadata (JSON files)
												</td>
												<td>{cacheStats.disk_metadata_count} entries ({cacheStats.disk_metadata_albums} albums, {cacheStats.disk_metadata_artists} artists)</td>
											</tr>
											<tr>
												<td class="font-medium">Disk Cover Cache</td>
												<td class="text-base-content/70">
													Cover art images stored at /app/cache/covers
												</td>
												<td>{cacheStats.disk_cover_size_mb} MB ({cacheStats.disk_cover_count} files)</td>
											</tr>
											<tr>
												<td class="font-medium">Library Database</td>
												<td class="text-base-content/70">
													Persistent SQLite cache of Lidarr library at /app/cache/library.db
												</td>
												<td>{cacheStats.library_db_size_mb} MB ({cacheStats.library_db_artist_count} artists, {cacheStats.library_db_album_count} albums)</td>
											</tr>
										</tbody>
									</table>
								</div>

								<!-- Clear Cache Actions -->
								<div class="divider">Clear Cache</div>
								
								<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
									<div class="card bg-base-100">
										<div class="card-body">
											<h3 class="card-title text-lg">Memory Cache</h3>
											<p class="text-sm text-base-content/70">
												Clear RAM cache. Data will reload from disk or APIs.
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
											<h3 class="card-title text-lg">Disk Metadata</h3>
											<p class="text-sm text-base-content/70">
												Clear album/artist JSON files. Data will re-fetch from APIs.
											</p>
											<div class="card-actions justify-end">
												<button 
													class="btn btn-warning btn-sm" 
													on:click={() => clearCache('disk')}
													disabled={clearingCache}
												>
													Clear Metadata
												</button>
											</div>
										</div>
									</div>
									
									<div class="card bg-base-100">
										<div class="card-body">
											<h3 class="card-title text-lg">Library Database</h3>
											<p class="text-sm text-base-content/70">
												Clear library cache. Will re-sync from Lidarr on next visit.
											</p>
											<div class="card-actions justify-end">
												<button 
													class="btn btn-warning btn-sm" 
													on:click={() => clearCache('library')}
													disabled={clearingCache}
												>
													Clear Library
												</button>
											</div>
										</div>
									</div>
									
									<div class="card bg-base-100">
										<div class="card-body">
											<h3 class="card-title text-lg">All Caches</h3>
											<p class="text-sm text-base-content/70">
												Clear everything except library DB. Complete reset.
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
				{:else if activeTab === 'lidarr'}
					<div class="card bg-base-200">
						<div class="card-body">
							<h2 class="card-title text-2xl mb-4">Library Sync Settings</h2>
							<p class="text-base-content/70 mb-6">
								Configure automatic synchronization of your Lidarr library. The library cache is persistent and survives restarts.
							</p>

							{#if loadingLidarr}
								<div class="flex justify-center items-center py-12">
									<span class="loading loading-spinner loading-lg"></span>
								</div>
							{:else if lidarrSettings}
								<!-- Sync Frequency Setting -->
								<div class="form-control mb-6">
									<label class="label">
										<span class="label-text font-semibold">Sync Frequency</span>
									</label>
									<select 
										class="select select-bordered w-full max-w-xs"
										bind:value={lidarrSettings.sync_frequency}
									>
										<option value="manual">Manual Only</option>
										<option value="5min">Every 5 Minutes</option>
										<option value="10min">Every 10 Minutes</option>
										<option value="30min">Every 30 Minutes</option>
										<option value="1hr">Every Hour</option>
									</select>
									<label class="label">
										<span class="label-text-alt text-base-content/70">
											How often to automatically sync your library from Lidarr. Manual sync is always available.
										</span>
									</label>
								</div>

								<!-- Last Sync Display -->
								<div class="mb-6">
									<div class="stats shadow">
										<div class="stat">
											<div class="stat-title">Last Sync</div>
											<div class="stat-value text-lg">
												{#if lidarrSettings.last_sync}
													{new Date(lidarrSettings.last_sync * 1000).toLocaleString()}
												{:else}
													Never
												{/if}
											</div>
											<div class="stat-desc">
												{#if lidarrSettings.sync_frequency === 'manual'}
													Automatic sync disabled
												{:else}
													Syncs {lidarrSettings.sync_frequency === '5min' ? 'every 5 minutes' : 
													        lidarrSettings.sync_frequency === '10min' ? 'every 10 minutes' : 
													        lidarrSettings.sync_frequency === '30min' ? 'every 30 minutes' : 'every hour'}
												{/if}
											</div>
										</div>
									</div>
								</div>

								<!-- Manual Sync Button -->
								<div class="mb-6">
									<button 
										class="btn btn-secondary" 
										on:click={syncLibraryNow}
										disabled={syncingLibrary}
									>
										{#if syncingLibrary}
											<span class="loading loading-spinner loading-sm"></span>
											Syncing...
										{:else}
											Sync Library Now
										{/if}
									</button>
									<p class="text-sm text-base-content/70 mt-2">
										Manually trigger a library sync from Lidarr.
									</p>
								</div>

								{#if lidarrMessage}
									<div 
										class="alert mb-6"
										class:alert-success={lidarrMessage.includes('success')}
										class:alert-error={lidarrMessage.includes('Failed')}
									>
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
												d={lidarrMessage.includes('success') 
													? "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" 
													: "M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"}
											/>
										</svg>
										<span>{lidarrMessage}</span>
									</div>
								{/if}

								<!-- Save Button -->
								<div class="card-actions justify-end">
									<button 
										class="btn btn-primary" 
										on:click={saveLidarrSettings}
										disabled={savingLidarr}
									>
										{#if savingLidarr}
											<span class="loading loading-spinner loading-sm"></span>
											Saving...
										{:else}
											Save Settings
										{/if}
									</button>
								</div>
							{/if}
						</div>
					</div>
				{:else if activeTab === 'advanced'}
					<div class="card bg-base-200">
						<div class="card-body">
							<h2 class="card-title text-2xl mb-4">Advanced Settings</h2>
							<p class="text-base-content/70 mb-6">
								Configure cache TTLs, HTTP timeouts, and batch processing parameters.
							</p>

							{#if loadingAdvanced}
								<div class="flex justify-center items-center py-12">
									<span class="loading loading-spinner loading-lg"></span>
								</div>
							{:else}
								<!-- Cache TTL Settings -->
								<div class="mb-8">
									<h3 class="text-xl font-semibold mb-4">Cache Time-To-Live (TTL)</h3>
									<p class="text-sm text-base-content/70 mb-4">
										How long cached data is considered fresh before re-fetching.
									</p>
									
									<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
										<label class="form-control">
											<div class="label">
												<span class="label-text">Library Albums (hours)</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.cache_ttl_album_library}
												class="input input-bordered"
												min="1"
												max="168"
												step="1"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Albums in your library (default: 24h)
												</span>
											</div>
										</label>

										<label class="form-control">
											<div class="label">
												<span class="label-text">Non-Library Albums (hours)</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.cache_ttl_album_non_library}
												class="input input-bordered"
												min="1"
												max="168"
												step="1"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Albums not in your library (default: 6h)
												</span>
											</div>
										</label>

										<label class="form-control">
											<div class="label">
												<span class="label-text">Library Artists (hours)</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.cache_ttl_artist_library}
												class="input input-bordered"
												min="1"
												max="168"
												step="1"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Artists in your library (default: 6h)
												</span>
											</div>
										</label>

										<label class="form-control">
											<div class="label">
												<span class="label-text">Non-Library Artists (hours)</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.cache_ttl_artist_non_library}
												class="input input-bordered"
												min="1"
												max="168"
												step="1"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Artists not in your library (default: 6h)
												</span>
											</div>
										</label>

										<label class="form-control">
											<div class="label">
												<span class="label-text">Search Results (minutes)</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.cache_ttl_search}
												class="input input-bordered"
												min="1"
												max="1440"
												step="1"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Search result freshness (default: 60min)
												</span>
											</div>
										</label>
									</div>
								</div>

								<!-- HTTP Settings -->
								<div class="mb-8">
									<h3 class="text-xl font-semibold mb-4">HTTP Client Settings</h3>
									<p class="text-sm text-base-content/70 mb-4">
										Timeout and connection pool settings for external API calls.
									</p>
									
									<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
										<label class="form-control">
											<div class="label">
												<span class="label-text">Request Timeout (seconds)</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.http_timeout}
												class="input input-bordered"
												min="5"
												max="60"
												step="1"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Max time to wait for response (default: 10s)
												</span>
											</div>
										</label>

										<label class="form-control">
											<div class="label">
												<span class="label-text">Connect Timeout (seconds)</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.http_connect_timeout}
												class="input input-bordered"
												min="1"
												max="30"
												step="1"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Max time to establish connection (default: 5s)
												</span>
											</div>
										</label>

										<label class="form-control">
											<div class="label">
												<span class="label-text">Max Connections</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.http_max_connections}
												class="input input-bordered"
												min="50"
												max="500"
												step="10"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Connection pool size (default: 200)
												</span>
											</div>
										</label>
									</div>
								</div>

								<!-- Batch Processing Settings -->
								<div class="mb-8">
									<h3 class="text-xl font-semibold mb-4">Batch Processing</h3>
									<p class="text-sm text-base-content/70 mb-4">
										Control concurrency and delays during library sync operations.
									</p>
									
									<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
										<label class="form-control">
											<div class="label">
												<span class="label-text">Artist Images (concurrent)</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.batch_artist_images}
												class="input input-bordered"
												min="1"
												max="20"
												step="1"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Artist image fetch concurrency (default: 5)
												</span>
											</div>
										</label>

										<label class="form-control">
											<div class="label">
												<span class="label-text">Albums (concurrent)</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.batch_albums}
												class="input input-bordered"
												min="1"
												max="20"
												step="1"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Album data fetch concurrency (default: 3)
												</span>
											</div>
										</label>

										<label class="form-control">
											<div class="label">
												<span class="label-text">Artist Delay (seconds)</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.delay_artist}
												class="input input-bordered"
												min="0"
												max="5"
												step="0.1"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Delay between artist batches (default: 0.5s)
												</span>
											</div>
										</label>

										<label class="form-control">
											<div class="label">
												<span class="label-text">Album Delay (seconds)</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.delay_albums}
												class="input input-bordered"
												min="0"
												max="5"
												step="0.1"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Delay between album batches (default: 1.0s)
												</span>
											</div>
										</label>
									</div>
								</div>

								<!-- Memory Cache Settings -->
								<div class="mb-8">
									<h3 class="text-xl font-semibold mb-4">Memory Cache</h3>
									<p class="text-sm text-base-content/70 mb-4">
										In-memory LRU cache settings for fast data access.
									</p>
									
									<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
										<label class="form-control">
											<div class="label">
												<span class="label-text">Max Entries</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.memory_cache_max_entries}
												class="input input-bordered"
												min="1000"
												max="100000"
												step="1000"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													Maximum cached items (default: 10000)
												</span>
											</div>
										</label>

										<label class="form-control">
											<div class="label">
												<span class="label-text">Cleanup Interval (seconds)</span>
											</div>
											<input 
												type="number" 
												bind:value={advancedSettings.memory_cache_cleanup_interval}
												class="input input-bordered"
												min="60"
												max="3600"
												step="60"
											/>
											<div class="label">
												<span class="label-text-alt text-base-content/50">
													How often to purge expired entries (default: 300s)
												</span>
											</div>
										</label>
									</div>
								</div>

								{#if advancedMessage}
									<div 
										class="alert mb-6"
										class:alert-success={advancedMessage.includes('success')}
										class:alert-error={advancedMessage.includes('Failed')}
									>
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
												d={advancedMessage.includes('success') 
													? "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" 
													: "M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"}
											/>
										</svg>
										<span>{advancedMessage}</span>
									</div>
								{/if}

								<!-- Action Buttons -->
								<div class="card-actions justify-end gap-2">
									<button 
										class="btn btn-ghost" 
										on:click={loadAdvancedSettings}
										disabled={savingAdvanced}
									>
										Reset
									</button>
									<button 
										class="btn btn-primary" 
										on:click={saveAdvancedSettings}
										disabled={savingAdvanced}
									>
										{#if savingAdvanced}
											<span class="loading loading-spinner loading-sm"></span>
											Saving...
										{:else}
											Save Settings
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
