import { CircleCheck, CircleAlert, Clock, Archive, Globe, Maximize2, Database, RotateCcw, Save } from 'lucide-svelte';
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
				{#if messageType === 'success'}
				<CircleCheck class="w-5 h-5 shrink-0" />
			{:else}
				<CircleAlert class="w-5 h-5 shrink-0" />
			{/if}
				<span>{message}</span>
			</div>
		{/if}

		<!-- Section: Frontend Cache TTLs -->
		<div class="collapse collapse-arrow bg-base-200 rounded-box">
			<input type="radio" name="advanced-settings" checked={openSection === 'frontend-cache'} onchange={() => openSection = 'frontend-cache'} />
			<div class="collapse-title">
				<div class="flex items-center gap-3">
					<div class="bg-primary/10 p-2 rounded-lg">
						<Clock class="w-5 h-5 text-primary" />
					</div>
					<div>
						<h3 class="font-semibold text-base">Page Cache Freshness</h3>
						<p class="text-xs text-base-content/50">How long page data stays fresh before checking for updates</p>
					</div>
				</div>
			</div>
			<div class="collapse-content">
				<div class="alert alert-info alert-soft mb-4">
					<span class="text-sm">Frontend TTLs control browser-side cache freshness. Lower values refresh page sections sooner; higher values make return navigation feel faster.</span>
				</div>
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
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Local Files Sidebar</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.frontend_ttl_local_files_sidebar} min="1" max="60" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 2 minutes</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Jellyfin Sidebar</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.frontend_ttl_jellyfin_sidebar} min="1" max="60" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 2 minutes</p>
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
						<Archive class="w-5 h-5 text-secondary" />
					</div>
					<div>
						<h3 class="font-semibold text-base">Server-Side Cache TTL</h3>
						<p class="text-xs text-base-content/50">How long the server keeps metadata before re-fetching from external APIs</p>
					</div>
				</div>
			</div>
			<div class="collapse-content">
				<div class="alert alert-info alert-soft mb-4">
					<span class="text-sm">Server-side TTLs control API/data cache freshness for all clients. Lower values fetch from upstream services more often; higher values reduce backend/API load.</span>
				</div>
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
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Local Recent (Backend)</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.cache_ttl_local_files_recently_added} min="1" max="60" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 2 minutes</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Local Stats (Backend)</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.cache_ttl_local_files_storage_stats} min="1" max="60" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 5 minutes</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Jellyfin Recent (Backend)</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.cache_ttl_jellyfin_recently_played} min="1" max="60" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 5 minutes</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Jellyfin Favorites (Backend)</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.cache_ttl_jellyfin_favorites} min="1" max="60" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 5 minutes</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Jellyfin Genres (Backend)</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.cache_ttl_jellyfin_genres} min="1" max="1440" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 60 minutes</p>
					</fieldset>
					<fieldset class="fieldset">
						<legend class="fieldset-legend">Jellyfin Stats (Backend)</legend>
						<label class="input w-full">
							<input type="number" bind:value={settings.cache_ttl_jellyfin_library_stats} min="1" max="60" class="grow" />
							<span class="label">min</span>
						</label>
						<p class="label text-base-content/50">Default: 10 minutes</p>
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
						<Globe class="w-5 h-5 text-accent" />
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
						<Maximize2 class="w-5 h-5 text-info" />
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
						<Database class="w-5 h-5 text-warning" />
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
				<RotateCcw class="w-4 h-4" />
				Reset
			</button>
			<button class="btn btn-primary" onclick={save} disabled={saving}>
				{#if saving}
					<span class="loading loading-spinner loading-sm"></span>
					Saving…
				{:else}
					<Save class="w-4 h-4" />
					Save Settings
				{/if}
			</button>
		</div>
	{/if}
</div>
