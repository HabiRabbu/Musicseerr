<script lang="ts">
	import type { LidarrConnectionSettings, LidarrVerifyResponse } from '$lib/types';

	let connection: LidarrConnectionSettings | null = $state(null);
	let loading = $state(false);
	let saving = $state(false);
	let verifying = $state(false);
	let message = $state('');
	let verifyResult: LidarrVerifyResponse | null = $state(null);
	let showApiKey = $state(false);

	export async function load() {
		loading = true;
		message = '';
		verifyResult = null;
		try {
			const response = await fetch('/api/settings/lidarr/connection');
			if (response.ok) {
				connection = await response.json();
			} else {
				message = 'Failed to load Lidarr connection settings';
			}
		} catch {
			message = 'Failed to load Lidarr connection settings';
		} finally {
			loading = false;
		}
	}

	async function save() {
		saving = true;
		message = '';
		try {
			const response = await fetch('/api/settings/lidarr/connection', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(connection)
			});

			if (response.ok) {
				message = 'Lidarr connection settings saved successfully!';
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

	async function verify() {
		if (!connection) return;

		verifying = true;
		message = '';
		verifyResult = null;
		try {
			const response = await fetch('/api/settings/lidarr/verify', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(connection)
			});

			if (response.ok) {
				const result = await response.json();
				verifyResult = result;
				if (result && result.success) {
					message = result.message;
				} else if (result) {
					message = `Connection failed: ${result.message}`;
				}
			} else {
				const error = await response.json();
				message = error.detail || 'Failed to verify connection';
			}
		} catch {
			message = 'Failed to verify connection';
		} finally {
			verifying = false;
		}
	}

	$effect(() => {
		load();
	});
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl mb-4">Lidarr Connection</h2>
		<p class="text-base-content/70 mb-6">
			Configure your Lidarr server connection for music library management.
		</p>

		{#if loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if connection}
			<div class="space-y-4">
				<label class="form-control">
					<div class="label"><span class="label-text">Lidarr URL</span></div>
					<input type="url" bind:value={connection.lidarr_url} class="input input-bordered" placeholder="http://localhost:8686" />
				</label>

				<label class="form-control">
					<div class="label"><span class="label-text">API Key</span></div>
					<div class="join w-full">
						<input type={showApiKey ? 'text' : 'password'} bind:value={connection.lidarr_api_key} class="input input-bordered join-item flex-1" placeholder="Your Lidarr API key" />
						<button class="btn join-item" onclick={() => showApiKey = !showApiKey}>
							{showApiKey ? 'Hide' : 'Show'}
						</button>
					</div>
				</label>

				{#if verifyResult?.success && verifyResult.quality_profiles}
					<label class="form-control">
						<div class="label"><span class="label-text">Quality Profile</span></div>
						<select bind:value={connection.quality_profile_id} class="select select-bordered">
							{#each verifyResult.quality_profiles as profile}
								<option value={profile.id}>{profile.name}</option>
							{/each}
						</select>
					</label>

					<label class="form-control">
						<div class="label"><span class="label-text">Metadata Profile</span></div>
						<select bind:value={connection.metadata_profile_id} class="select select-bordered">
							{#each verifyResult.metadata_profiles as profile}
								<option value={profile.id}>{profile.name}</option>
							{/each}
						</select>
					</label>

					<label class="form-control">
						<div class="label"><span class="label-text">Root Folder</span></div>
						<select bind:value={connection.root_folder_path} class="select select-bordered">
							{#each verifyResult.root_folders as folder}
								<option value={folder.path}>{folder.path}</option>
							{/each}
						</select>
					</label>
				{/if}

				{#if message}
					<div class="alert" class:alert-success={message.includes('success')} class:alert-error={message.includes('Failed') || message.includes('failed')}>
						<span>{message}</span>
					</div>
				{/if}

				<div class="card-actions justify-end gap-2">
					<button class="btn btn-ghost" onclick={verify} disabled={verifying}>
						{#if verifying}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Test Connection
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
