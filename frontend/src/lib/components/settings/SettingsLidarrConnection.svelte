<script lang="ts">
	import type { LidarrConnectionSettings, LidarrVerifyResponse } from '$lib/types';
	import { integrationStore } from '$lib/stores/integration';

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
				if (connection?.lidarr_url && connection?.lidarr_api_key) {
					integrationStore.setLidarrConfigured(true);
				}
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
		<h2 class="card-title text-2xl">Lidarr Connection</h2>
		<p class="text-base-content/70 mb-4">
			Configure your Lidarr server connection for music library management.
		</p>

		{#if loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if connection}
			<div class="space-y-4">
				<div class="form-control w-full">
					<label class="label" for="lidarr-url">
						<span class="label-text">Lidarr URL</span>
					</label>
					<input
						id="lidarr-url"
						type="url"
						bind:value={connection.lidarr_url}
						class="input input-bordered w-full"
						placeholder="http://localhost:8686"
					/>
				</div>

				<div class="form-control w-full">
					<label class="label" for="lidarr-api-key">
						<span class="label-text">API Key</span>
					</label>
					<div class="join w-full">
						<input
							id="lidarr-api-key"
							type={showApiKey ? 'text' : 'password'}
							bind:value={connection.lidarr_api_key}
							class="input input-bordered join-item flex-1"
							placeholder="Your Lidarr API key"
						/>
						<button type="button" class="btn join-item" onclick={() => showApiKey = !showApiKey}>
							{showApiKey ? 'Hide' : 'Show'}
						</button>
					</div>
					<label class="label">
						<span class="label-text-alt text-base-content/50">Settings → General → API Key</span>
					</label>
				</div>

				{#if verifyResult?.success && verifyResult.quality_profiles}
					<div class="form-control w-full">
						<label class="label" for="quality-profile">
							<span class="label-text">Quality Profile</span>
						</label>
						<select
							id="quality-profile"
							bind:value={connection.quality_profile_id}
							class="select select-bordered w-full"
						>
							{#each verifyResult.quality_profiles as profile}
								<option value={profile.id}>{profile.name}</option>
							{/each}
						</select>
					</div>

					<div class="form-control w-full">
						<label class="label" for="metadata-profile">
							<span class="label-text">Metadata Profile</span>
						</label>
						<select
							id="metadata-profile"
							bind:value={connection.metadata_profile_id}
							class="select select-bordered w-full"
						>
							{#each verifyResult.metadata_profiles as profile}
								<option value={profile.id}>{profile.name}</option>
							{/each}
						</select>
					</div>

					<div class="form-control w-full">
						<label class="label" for="root-folder">
							<span class="label-text">Root Folder</span>
						</label>
						<select
							id="root-folder"
							bind:value={connection.root_folder_path}
							class="select select-bordered w-full"
						>
							{#each verifyResult.root_folders as folder}
								<option value={folder.path}>{folder.path}</option>
							{/each}
						</select>
					</div>
				{/if}

				{#if message}
					<div class="alert" class:alert-success={message.includes('success')} class:alert-error={message.includes('Failed') || message.includes('failed')}>
						<span>{message}</span>
					</div>
				{/if}

				<div class="flex justify-end gap-2 pt-2">
					<button type="button" class="btn btn-ghost" onclick={verify} disabled={verifying || !connection.lidarr_url || !connection.lidarr_api_key}>
						{#if verifying}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Test Connection
					</button>
					<button type="button" class="btn btn-primary" onclick={save} disabled={saving}>
						{#if saving}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Save Settings
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>
