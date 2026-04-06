<script lang="ts">
	import { Check, X } from 'lucide-svelte';
	import { api } from '$lib/api/client';
	import { createSettingsForm } from '$lib/utils/settingsForm.svelte';
	import { syncStatus } from '$lib/stores/syncStatus.svelte';
	import { onDestroy } from 'svelte';

	interface LibrarySyncSettings {
		sync_frequency:
			| 'manual'
			| '5min'
			| '10min'
			| '30min'
			| '1hr'
			| '6hr'
			| '12hr'
			| '24hr'
			| '3d'
			| '7d';
		last_sync: number | null;
		last_sync_success: boolean;
	}

	const form = createSettingsForm<LibrarySyncSettings>({
		loadEndpoint: '/api/v1/settings/lidarr',
		saveEndpoint: '/api/v1/settings/lidarr'
	});

	let syncing = $state(false);

	export async function load() {
		await form.load();
	}

	async function save() {
		await form.save();
	}

	async function syncNow() {
		syncing = true;
		form.clearMessage();
		try {
			await api.global.post('/api/v1/library/sync');
			form.showMessage('Library sync started');
			syncStatus.checkStatus();
			await load();
		} catch {
			form.showMessage("Couldn't sync the library", 'error', false);
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

	onDestroy(() => form.cleanup());
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl mb-4">Library Sync</h2>
		<p class="text-base-content/70 mb-6">
			Choose how often MusicSeerr syncs with your Lidarr library.
		</p>

		{#if form.loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if form.data}
			<div class="space-y-6">
				<div class="stats shadow">
					<div class="stat">
						<div class="stat-title">Last Sync</div>
						<div class="stat-value text-lg">{formatLastSync(form.data.last_sync)}</div>
						<div class="stat-desc">
							{#if form.data.last_sync_success === true}
								<span class="text-success inline-flex items-center gap-0.5"
									><Check class="h-3 w-3" /> Successful</span
								>
							{:else if form.data.last_sync_success === false}
								<span class="text-error inline-flex items-center gap-0.5"
									><X class="h-3 w-3" /> Failed</span
								>
							{/if}
						</div>
					</div>
				</div>

				<label class="form-control">
					<div class="label"><span class="label-text">Sync Frequency</span></div>
					<select bind:value={form.data.sync_frequency} class="select select-bordered">
						<option value="manual">Manual only</option>
						{#if form.data.sync_frequency === '5min'}
							<option value="5min">Every 5 minutes (legacy)</option>
						{/if}
						{#if form.data.sync_frequency === '10min'}
							<option value="10min">Every 10 minutes (legacy)</option>
						{/if}
						<option value="30min">Every 30 minutes</option>
						<option value="1hr">Every hour</option>
						<option value="6hr">Every 6 hours</option>
						<option value="12hr">Every 12 hours</option>
						<option value="24hr">Every 24 hours</option>
						<option value="3d">Every 3 days</option>
						<option value="7d">Every 7 days</option>
					</select>
				</label>

				{#if form.message}
					<div
						class="alert"
						class:alert-success={form.messageType === 'success'}
						class:alert-error={form.messageType === 'error'}
					>
						<span>{form.message}</span>
					</div>
				{/if}

				<div class="card-actions justify-end gap-2">
					{#if syncStatus.isActive}
						<button class="btn btn-error" onclick={() => syncStatus.cancelSync()}>
							Stop Sync
						</button>
					{:else}
						<button class="btn btn-ghost" onclick={syncNow} disabled={syncing}>
							{#if syncing}
								<span class="loading loading-spinner loading-sm"></span>
							{/if}
							Sync Now
						</button>
					{/if}
					<button class="btn btn-primary" onclick={save} disabled={form.saving}>
						{#if form.saving}
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
