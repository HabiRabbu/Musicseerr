<script lang="ts">
	import type { SoularrConnectionSettings } from '$lib/types';

	let connection: SoularrConnectionSettings | null = $state(null);
	let loading = $state(false);
	let saving = $state(false);
	let message = $state('');
	let showApiKey = $state(false);

	export async function load() {
		loading = true;
		message = '';
		try {
			const response = await fetch('/api/settings/soularr');
			if (response.ok) {
				connection = await response.json();
			} else {
				message = 'Failed to load Soularr settings';
			}
		} catch {
			message = 'Failed to load Soularr settings';
		} finally {
			loading = false;
		}
	}

	async function save() {
		saving = true;
		message = '';
		try {
			const response = await fetch('/api/settings/soularr', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(connection)
			});

			if (response.ok) {
				message = 'Soularr settings saved successfully!';
				connection = await response.json();
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
		<h2 class="card-title text-2xl mb-4">Soularr Integration</h2>
		<p class="text-base-content/70 mb-6">
			Configure Soularr for music downloading integration.
		</p>

		{#if loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if connection}
			<div class="space-y-4">
				<label class="form-control">
					<div class="label"><span class="label-text">Soularr URL</span></div>
					<input type="url" bind:value={connection.soularr_url} class="input input-bordered" placeholder="http://localhost:8181" />
				</label>

				<label class="form-control">
					<div class="label"><span class="label-text">API Key</span></div>
					<div class="join w-full">
						<input type={showApiKey ? 'text' : 'password'} bind:value={connection.soularr_api_key} class="input input-bordered join-item flex-1" placeholder="Your Soularr API key" />
						<button class="btn join-item" onclick={() => showApiKey = !showApiKey}>
							{showApiKey ? 'Hide' : 'Show'}
						</button>
					</div>
				</label>

				<div class="form-control">
					<label class="label cursor-pointer justify-start gap-4">
						<input type="checkbox" bind:checked={connection.trigger_soularr} class="checkbox checkbox-primary" />
						<span class="label-text">Trigger Soularr on album requests</span>
					</label>
				</div>

				{#if message}
					<div class="alert" class:alert-success={message.includes('success')} class:alert-error={message.includes('Failed')}>
						<span>{message}</span>
					</div>
				{/if}

				<div class="card-actions justify-end">
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
