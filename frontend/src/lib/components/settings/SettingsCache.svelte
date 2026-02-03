<script lang="ts">
	let cacheStats: any = $state(null);
	let loading = $state(false);
	let clearing = $state(false);
	let message = $state('');

	export async function load() {
		loading = true;
		message = '';
		try {
			const response = await fetch('/api/cache/stats');
			if (response.ok) {
				cacheStats = await response.json();
			} else {
				message = 'Failed to load cache statistics';
			}
		} catch {
			message = 'Failed to load cache statistics';
		} finally {
			loading = false;
		}
	}

	async function clearCache(type: 'all' | 'memory' | 'disk' | 'library' | 'covers') {
		const typeLabel = type === 'library' ? 'library database' : type === 'covers' ? 'cover images' : type === 'all' ? 'entire' : type;
		if (!confirm(`Are you sure you want to clear the ${typeLabel} cache?`)) {
			return;
		}

		clearing = true;
		message = '';
		try {
			const response = await fetch(`/api/cache/clear/${type}`, {
				method: 'POST'
			});

			if (response.ok) {
				const result = await response.json();
				message = result.message;
				await load();
				setTimeout(() => { message = ''; }, 5000);
			} else {
				const error = await response.json();
				message = error.detail || 'Failed to clear cache';
			}
		} catch {
			message = 'Failed to clear cache';
		} finally {
			clearing = false;
		}
	}

	$effect(() => {
		load();
	});
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl mb-4">Cache Management</h2>
		<p class="text-base-content/70 mb-6">
			View cache statistics and clear cached data. Uses 2-tier caching: hot items in RAM (100 max), all data persisted on disk.
		</p>

		{#if loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if cacheStats}
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
					<div class="stat-title">Library</div>
					<div class="stat-value">{(cacheStats.library_db_artist_count ?? 0) + (cacheStats.library_db_album_count ?? 0)}</div>
					<div class="stat-desc">{cacheStats.library_db_artist_count ?? 0} artists, {cacheStats.library_db_album_count ?? 0} albums</div>
				</div>
			</div>

			<div class="space-y-4">
				<h3 class="text-xl font-semibold">Clear Cache</h3>
				<div class="flex flex-wrap gap-2">
					<button class="btn btn-outline btn-sm" onclick={() => clearCache('memory')} disabled={clearing}>
						Clear Memory
					</button>
					<button class="btn btn-outline btn-sm" onclick={() => clearCache('disk')} disabled={clearing}>
						Clear Disk Metadata
					</button>
					<button class="btn btn-outline btn-sm" onclick={() => clearCache('covers')} disabled={clearing}>
						Clear Covers
					</button>
					<button class="btn btn-outline btn-sm" onclick={() => clearCache('library')} disabled={clearing}>
						Clear Library
					</button>
					<button class="btn btn-error btn-sm" onclick={() => clearCache('all')} disabled={clearing}>
						{#if clearing}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Clear All
					</button>
				</div>
			</div>

			{#if message}
				<div class="alert mt-4" class:alert-success={message.includes('success') || message.includes('Cleared')} class:alert-error={message.includes('Failed')}>
					<span>{message}</span>
				</div>
			{/if}
		{/if}
	</div>
</div>
