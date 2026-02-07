<script lang="ts">
	let settings: any = $state(null);
	let loading = $state(false);
	let saving = $state(false);
	let message = $state('');
	let messageType: 'success' | 'error' = $state('success');

	export async function load() {
		loading = true;
		message = '';
		try {
			const response = await fetch('/api/settings/advanced');
			if (response.ok) {
				settings = await response.json();
			} else {
				message = 'Failed to load advanced settings';
				messageType = 'error';
			}
		} catch {
			message = 'Failed to load advanced settings';
			messageType = 'error';
		} finally {
			loading = false;
		}
	}

	async function save() {
		saving = true;
		message = '';
		try {
			const response = await fetch('/api/settings/advanced', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(settings)
			});

			if (response.ok) {
				message = 'Settings saved — some changes take effect after page reload';
				messageType = 'success';
				settings = await response.json();
				setTimeout(() => { message = ''; }, 5000);
			} else {
				const error = await response.json();
				message = error.detail || 'Failed to save settings';
				messageType = 'error';
			}
		} catch {
			message = 'Failed to save settings';
			messageType = 'error';
		} finally {
			saving = false;
		}
	}

	$effect(() => {
		load();
	});

	let openSection: string | null = $state('frontend-cache');
</script>

<div class="space-y-6">
	<div>
		<h2 class="text-2xl font-bold">Advanced Settings</h2>
		<p class="text-base-content/60 mt-1">Fine-tune caching, network, and performance settings.</p>
	</div>

	{#if loading}
		<div class="flex justify-center items-center py-20">
			<span class="loading loading-spinner loading-lg text-primary"></span>
		</div>
	{:else if settings}
		<!-- Toast notification -->
		{#if message}
			<div class="alert {messageType === 'success' ? 'alert-success' : 'alert-error'} alert-soft">
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5 shrink-0">
					{#if messageType === 'success'}
						<path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
					{:else}
						<path d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
					{/if}
				</svg>
				<span>{message}</span>
			</div>
		{/if}

		<!-- Section: Frontend Cache TTLs -->
		<div class="collapse collapse-arrow bg-base-200 rounded-box">
			<input type="radio" name="advanced-settings" checked={openSection === 'frontend-cache'} onchange={() => openSection = 'frontend-cache'} />
			<div class="collapse-title">
				<div class="flex items-center gap-3">
					<div class="bg-primary/10 p-2 rounded-lg">
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5 text-primary">
							<path d="M12 6v6l4 2"></path>
							<circle cx="12" cy="12" r="10"></circle>
						</svg>
					</div>
					<div>
						<h3 class="font-semibold text-base">Page Cache Freshness</h3>
						<p class="text-xs text-base-content/50">How long page data stays fresh before checking for updates</p>
					</div>
				</div>
			</div>
			<div class="collapse-content">
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 pt-2">
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Home Page</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.frontend_ttl_home} min="1" max="60" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 5 minutes</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Discover Page</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.frontend_ttl_discover} min="1" max="1440" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 30 minutes</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Library</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.frontend_ttl_library} min="1" max="60" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 5 minutes</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Recently Added</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.frontend_ttl_recently_added} min="1" max="60" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 5 minutes</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Discover Queue</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.frontend_ttl_discover_queue} min="60" max="10080" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 1440 minutes (24 hours)</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Search & Discovery</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.frontend_ttl_search} min="1" max="60" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 5 minutes</p>
					</fieldset>
				</div>
			</div>
		</div>

		<!-- Section: Backend Cache TTLs -->
		<div class="collapse collapse-arrow bg-base-200 rounded-box">
			<input type="radio" name="advanced-settings" checked={openSection === 'backend-cache'} onchange={() => openSection = 'backend-cache'} />
			<div class="collapse-title">
				<div class="flex items-center gap-3">
					<div class="bg-secondary/10 p-2 rounded-lg">
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5 text-secondary">
							<path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V7"></path>
							<path d="M21 3H3v4h18V3z"></path>
							<path d="M10 12h4"></path>
						</svg>
					</div>
					<div>
						<h3 class="font-semibold text-base">Server-Side Cache TTL</h3>
						<p class="text-xs text-base-content/50">How long the server keeps metadata before re-fetching from external APIs</p>
					</div>
				</div>
			</div>
			<div class="collapse-content">
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 pt-2">
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Library Albums</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.cache_ttl_album_library} min="1" max="168" class="grow" />
							<span class="label">hours</span>
						</label>
						<p class="label text-base-content/50">Default: 24 hours</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Non-Library Albums</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.cache_ttl_album_non_library} min="1" max="24" class="grow" />
							<span class="label">hours</span>
						</label>
						<p class="label text-base-content/50">Default: 6 hours</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Library Artists</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.cache_ttl_artist_library} min="1" max="168" class="grow" />
							<span class="label">hours</span>
						</label>
						<p class="label text-base-content/50">Default: 6 hours</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Non-Library Artists</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.cache_ttl_artist_non_library} min="1" max="168" class="grow" />
							<span class="label">hours</span>
						</label>
						<p class="label text-base-content/50">Default: 6 hours</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Search Results</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.cache_ttl_search} min="1" max="1440" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 60 minutes</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Persistent Metadata</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.persistent_metadata_ttl_hours} min="1" max="168" class="grow" />
							<span class="label">hours</span>
						</label>
						<p class="label text-base-content/50">Covers & enrichment (default: 24h)</p>
					</fieldset>
				</div>
			</div>
		</div>

		<!-- Section: Network -->
		<div class="collapse collapse-arrow bg-base-200 rounded-box">
			<input type="radio" name="advanced-settings" checked={openSection === 'network'} onchange={() => openSection = 'network'} />
			<div class="collapse-title">
				<div class="flex items-center gap-3">
					<div class="bg-accent/10 p-2 rounded-lg">
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5 text-accent">
							<path d="M12 2a10 10 0 100 20 10 10 0 000-20z"></path>
							<path d="M2 12h20"></path>
							<path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"></path>
						</svg>
					</div>
					<div>
						<h3 class="font-semibold text-base">Network & HTTP</h3>
						<p class="text-xs text-base-content/50">Timeouts and connection pool for external API calls</p>
					</div>
				</div>
			</div>
			<div class="collapse-content">
				<div class="grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-4 pt-2">
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Request Timeout</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.http_timeout} min="5" max="60" class="grow" />
							<span class="label">sec</span>
						</label>
						<p class="label text-base-content/50">Default: 10s</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Connect Timeout</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.http_connect_timeout} min="1" max="30" class="grow" />
							<span class="label">sec</span>
						</label>
						<p class="label text-base-content/50">Default: 5s</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Max Connections</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.http_max_connections} min="50" max="500" step="10" class="grow" />
						</label>
						<p class="label text-base-content/50">Pool size (default: 200)</p>
					</fieldset>
				</div>
			</div>
		</div>

		<!-- Section: Batch Processing -->
		<div class="collapse collapse-arrow bg-base-200 rounded-box">
			<input type="radio" name="advanced-settings" checked={openSection === 'batch'} onchange={() => openSection = 'batch'} />
			<div class="collapse-title">
				<div class="flex items-center gap-3">
					<div class="bg-info/10 p-2 rounded-lg">
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5 text-info">
							<path d="M16 3h5v5"></path>
							<path d="M8 3H3v5"></path>
							<path d="M21 3l-7 7"></path>
							<path d="M3 3l7 7"></path>
							<path d="M16 21h5v-5"></path>
							<path d="M8 21H3v-5"></path>
							<path d="M21 21l-7-7"></path>
							<path d="M3 21l7-7"></path>
						</svg>
					</div>
					<div>
						<h3 class="font-semibold text-base">Batch Processing</h3>
						<p class="text-xs text-base-content/50">Concurrency and rate limits during library sync</p>
					</div>
				</div>
			</div>
			<div class="collapse-content">
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 pt-2">
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Artist Image Concurrency</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.batch_artist_images} min="1" max="20" class="grow" />
						</label>
						<p class="label text-base-content/50">Parallel image fetches (default: 5)</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Album Concurrency</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.batch_albums} min="1" max="20" class="grow" />
						</label>
						<p class="label text-base-content/50">Parallel album fetches (default: 3)</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Artist Batch Delay</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.delay_artist} min="0" max="5" step="0.1" class="grow" />
							<span class="label">sec</span>
						</label>
						<p class="label text-base-content/50">Default: 0.5s</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Album Batch Delay</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.delay_albums} min="0" max="5" step="0.1" class="grow" />
							<span class="label">sec</span>
						</label>
						<p class="label text-base-content/50">Default: 1.0s</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">MusicBrainz Searches</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.musicbrainz_concurrent_searches} min="2" max="5" class="grow" />
						</label>
						<p class="label text-base-content/50">Parallel API requests (default: 3)</p>
					</fieldset>
				</div>
			</div>
		</div>

		<!-- Section: Memory & Disk Cache -->
		<div class="collapse collapse-arrow bg-base-200 rounded-box">
			<input type="radio" name="advanced-settings" checked={openSection === 'storage'} onchange={() => openSection = 'storage'} />
			<div class="collapse-title">
				<div class="flex items-center gap-3">
					<div class="bg-warning/10 p-2 rounded-lg">
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5 text-warning">
							<ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
							<path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
							<path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
						</svg>
					</div>
					<div>
						<h3 class="font-semibold text-base">Memory & Disk Storage</h3>
						<p class="text-xs text-base-content/50">LRU cache sizing, cleanup intervals, and disk limits</p>
					</div>
				</div>
			</div>
			<div class="collapse-content">
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 pt-2">
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Memory Cache Max Entries</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.memory_cache_max_entries} min="1000" max="100000" step="1000" class="grow" />
						</label>
						<p class="label text-base-content/50">Default: 10,000</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Memory Cleanup Interval</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.memory_cache_cleanup_interval} min="60" max="3600" step="60" class="grow" />
							<span class="label">sec</span>
						</label>
						<p class="label text-base-content/50">Default: 300s (5 min)</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Disk Cleanup Interval</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.disk_cache_cleanup_interval} min="1" max="60" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 10 minutes</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Metadata Cache Limit</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.recent_metadata_max_size_mb} min="100" max="5000" class="grow" />
							<span class="label">MB</span>
						</label>
						<p class="label text-base-content/50">Default: 500 MB</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Cover Cache Limit</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.recent_covers_max_size_mb} min="100" max="10000" class="grow" />
							<span class="label">MB</span>
						</label>
						<p class="label text-base-content/50">Default: 1024 MB (1 GB)</p>
					</fieldset>
				</div>
			</div>
		</div>

		<!-- Actions -->
		<div class="flex justify-end gap-3 pt-2">
			<button class="btn btn-ghost" onclick={load} disabled={saving}>
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-4 h-4">
					<path d="M1 4v6h6"></path>
					<path d="M3.51 15a9 9 0 102.13-9.36L1 10"></path>
				</svg>
				Reset
			</button>
			<button class="btn btn-primary" onclick={save} disabled={saving}>
				{#if saving}
					<span class="loading loading-spinner loading-sm"></span>
					Saving…
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-4 h-4">
						<path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"></path>
						<polyline points="17 21 17 13 7 13 7 21"></polyline>
						<polyline points="7 3 7 8 15 8"></polyline>
					</svg>
					Save Settings
				{/if}
			</button>
		</div>
	{/if}
</div>
