<script lang="ts">
	import { Check, X } from 'lucide-svelte';
	let settings: any = $state(null);
	let loading = $state(false);
	let saving = $state(false);
	let syncing = $state(false);
	let message = $state('');

	export async function load() {
		loading = true;
		message = '';
		try {
			const response = await fetch('/api/settings/lidarr');
			if (response.ok) {
				settings = await response.json();
			} else {
				message = 'Failed to load Lidarr settings';
			}
		} catch {
			message = 'Failed to load Lidarr settings';
		} finally {
			loading = false;
		}
	}

	async function save() {
		saving = true;
		message = '';
		try {
			const response = await fetch('/api/settings/lidarr', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(settings)
			});

			if (response.ok) {
				message = 'Settings saved successfully!';
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

	async function syncNow() {
		syncing = true;
		message = '';
		try {
			const response = await fetch('/api/library/sync', { method: 'POST' });

			if (response.ok) {
				message = 'Library sync started successfully!';
				await load();
				setTimeout(() => { message = ''; }, 5000);
			} else {
				const error = await response.json();
				message = error.detail || 'Failed to start sync';
			}
		} catch {
			message = 'Failed to sync library';
		} finally {
			syncing = false;
		}
	}

	function formatLastSync(timestamp: number | null): string {
		if (!timestamp) return 'Never';
		const date = new Date(timestamp * 1000);
		return date.toLocaleString();
	}

	$effect(() => {
		load();
	});
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl mb-4">Library Sync</h2>
		<p class="text-base-content/70 mb-6">
			Configure how often MusicSeer syncs with your Lidarr library.
		</p>

		{#if loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if settings}
			<div class="space-y-6">
				<div class="stats shadow">
					<div class="stat">
						<div class="stat-title">Last Sync</div>
						<div class="stat-value text-lg">{formatLastSync(settings.last_sync)}</div>
						<div class="stat-desc">
							{#if settings.last_sync_success === true}
							<span class="text-success inline-flex items-center gap-0.5"><Check class="h-3 w-3" /> Successful</span>
						{:else if settings.last_sync_success === false}
							<span class="text-error inline-flex items-center gap-0.5"><X class="h-3 w-3" /> Failed</span>
							{/if}
						</div>
					</div>
				</div>

				<label class="form-control">
					<div class="label"><span class="label-text">Sync Frequency</span></div>
					<select bind:value={settings.sync_frequency} class="select select-bordered">
						<option value="manual">Manual only</option>
						<option value="5min">Every 5 minutes</option>
						<option value="10min">Every 10 minutes</option>
						<option value="30min">Every 30 minutes</option>
						<option value="1hr">Every hour</option>
					</select>
				</label>

				{#if message}
					<div class="alert" class:alert-success={message.includes('success')} class:alert-error={message.includes('Failed')}>
						<span>{message}</span>
					</div>
				{/if}

				<div class="card-actions justify-end gap-2">
					<button class="btn btn-ghost" onclick={syncNow} disabled={syncing}>
						{#if syncing}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Sync Now
					</button>
					<button class="btn btn-primary" onclick={save} disabled={saving}>
						{#if saving}
							<span class="loading loading-spinner loading-sm"></span>
							Saving...
						{:else}
							Save Settings
						{/if}
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>
