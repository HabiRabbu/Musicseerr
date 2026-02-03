<script lang="ts">
	let settings: any = $state(null);
	let loading = $state(false);
	let saving = $state(false);
	let message = $state('');

	export async function load() {
		loading = true;
		message = '';
		try {
			const response = await fetch('/api/settings/advanced');
			if (response.ok) {
				settings = await response.json();
			} else {
				message = 'Failed to load advanced settings';
			}
		} catch {
			message = 'Failed to load advanced settings';
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
				message = 'Advanced settings saved successfully!';
				settings = await response.json();
				setTimeout(() => { message = ''; }, 5000);
			} else {
				const error = await response.json();
				message = error.detail || 'Failed to save settings';
			}
		} catch {
			message = 'Failed to save settings';
		} finally {
			saving = false;
		}
	}

	$effect(() => {
		load();
	});
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl mb-4">Advanced Settings</h2>
		<p class="text-base-content/70 mb-6">
			Configure cache TTLs, HTTP timeouts, and batch processing parameters.
		</p>

		{#if loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if settings}
			<div class="mb-8">
				<h3 class="text-xl font-semibold mb-4">Cache Time-To-Live (TTL)</h3>
				<p class="text-sm text-base-content/70 mb-4">How long cached data is considered fresh before re-fetching.</p>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					<label class="form-control">
						<div class="label"><span class="label-text">Library Albums (hours)</span></div>
						<input type="number" bind:value={settings.cache_ttl_album_library} class="input input-bordered" min="1" max="168" />
						<div class="label"><span class="label-text-alt text-base-content/50">Albums in your library (default: 24h)</span></div>
					</label>
					<label class="form-control">
						<div class="label"><span class="label-text">Non-Library Albums (hours)</span></div>
						<input type="number" bind:value={settings.cache_ttl_album_non_library} class="input input-bordered" min="1" max="168" />
						<div class="label"><span class="label-text-alt text-base-content/50">Albums not in your library (default: 6h)</span></div>
					</label>
					<label class="form-control">
						<div class="label"><span class="label-text">Library Artists (hours)</span></div>
						<input type="number" bind:value={settings.cache_ttl_artist_library} class="input input-bordered" min="1" max="168" />
						<div class="label"><span class="label-text-alt text-base-content/50">Artists in your library (default: 6h)</span></div>
					</label>
					<label class="form-control">
						<div class="label"><span class="label-text">Non-Library Artists (hours)</span></div>
						<input type="number" bind:value={settings.cache_ttl_artist_non_library} class="input input-bordered" min="1" max="168" />
						<div class="label"><span class="label-text-alt text-base-content/50">Artists not in your library (default: 6h)</span></div>
					</label>
					<label class="form-control">
						<div class="label"><span class="label-text">Search Results (minutes)</span></div>
						<input type="number" bind:value={settings.cache_ttl_search} class="input input-bordered" min="1" max="1440" />
						<div class="label"><span class="label-text-alt text-base-content/50">Search result freshness (default: 60min)</span></div>
					</label>
				</div>
			</div>

			<div class="mb-8">
				<h3 class="text-xl font-semibold mb-4">HTTP Client Settings</h3>
				<p class="text-sm text-base-content/70 mb-4">Timeout and connection pool settings for external API calls.</p>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					<label class="form-control">
						<div class="label"><span class="label-text">Request Timeout (seconds)</span></div>
						<input type="number" bind:value={settings.http_timeout} class="input input-bordered" min="5" max="60" />
						<div class="label"><span class="label-text-alt text-base-content/50">Max time to wait for response (default: 10s)</span></div>
					</label>
					<label class="form-control">
						<div class="label"><span class="label-text">Connect Timeout (seconds)</span></div>
						<input type="number" bind:value={settings.http_connect_timeout} class="input input-bordered" min="1" max="30" />
						<div class="label"><span class="label-text-alt text-base-content/50">Max time to establish connection (default: 5s)</span></div>
					</label>
					<label class="form-control">
						<div class="label"><span class="label-text">Max Connections</span></div>
						<input type="number" bind:value={settings.http_max_connections} class="input input-bordered" min="50" max="500" step="10" />
						<div class="label"><span class="label-text-alt text-base-content/50">Connection pool size (default: 200)</span></div>
					</label>
				</div>
			</div>

			<div class="mb-8">
				<h3 class="text-xl font-semibold mb-4">Batch Processing</h3>
				<p class="text-sm text-base-content/70 mb-4">Control concurrency and delays during library sync operations.</p>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					<label class="form-control">
						<div class="label"><span class="label-text">Artist Images (concurrent)</span></div>
						<input type="number" bind:value={settings.batch_artist_images} class="input input-bordered" min="1" max="20" />
						<div class="label"><span class="label-text-alt text-base-content/50">Artist image fetch concurrency (default: 5)</span></div>
					</label>
					<label class="form-control">
						<div class="label"><span class="label-text">Albums (concurrent)</span></div>
						<input type="number" bind:value={settings.batch_albums} class="input input-bordered" min="1" max="20" />
						<div class="label"><span class="label-text-alt text-base-content/50">Album data fetch concurrency (default: 3)</span></div>
					</label>
					<label class="form-control">
						<div class="label"><span class="label-text">Artist Delay (seconds)</span></div>
						<input type="number" bind:value={settings.delay_artist} class="input input-bordered" min="0" max="5" step="0.1" />
						<div class="label"><span class="label-text-alt text-base-content/50">Delay between artist batches (default: 0.5s)</span></div>
					</label>
					<label class="form-control">
						<div class="label"><span class="label-text">Album Delay (seconds)</span></div>
						<input type="number" bind:value={settings.delay_albums} class="input input-bordered" min="0" max="5" step="0.1" />
						<div class="label"><span class="label-text-alt text-base-content/50">Delay between album batches (default: 1.0s)</span></div>
					</label>
					<label class="form-control">
						<div class="label"><span class="label-text">MusicBrainz Concurrent Searches</span></div>
						<input type="number" bind:value={settings.musicbrainz_concurrent_searches} class="input input-bordered" min="2" max="5" />
						<div class="label"><span class="label-text-alt text-base-content/50">Parallel API requests during search (default: 3)</span></div>
					</label>
				</div>
			</div>

			<div class="mb-8">
				<h3 class="text-xl font-semibold mb-4">Memory Cache</h3>
				<p class="text-sm text-base-content/70 mb-4">In-memory LRU cache settings for fast data access.</p>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					<label class="form-control">
						<div class="label"><span class="label-text">Max Entries</span></div>
						<input type="number" bind:value={settings.memory_cache_max_entries} class="input input-bordered" min="1000" max="100000" step="1000" />
						<div class="label"><span class="label-text-alt text-base-content/50">Maximum cached items (default: 10000)</span></div>
					</label>
					<label class="form-control">
						<div class="label"><span class="label-text">Cleanup Interval (seconds)</span></div>
						<input type="number" bind:value={settings.memory_cache_cleanup_interval} class="input input-bordered" min="60" max="3600" step="60" />
						<div class="label"><span class="label-text-alt text-base-content/50">How often to purge expired entries (default: 300s)</span></div>
					</label>
				</div>
			</div>

			{#if message}
				<div class="alert mb-6" class:alert-success={message.includes('success')} class:alert-error={message.includes('Failed')}>
					<span>{message}</span>
				</div>
			{/if}

			<div class="card-actions justify-end gap-2">
				<button class="btn btn-ghost" onclick={load} disabled={saving}>Reset</button>
				<button class="btn btn-primary" onclick={save} disabled={saving}>
					{#if saving}
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
