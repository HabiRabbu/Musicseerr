<script lang="ts">
	import { createSettingsForm } from '$lib/utils/settingsForm.svelte';
	import { onDestroy } from 'svelte';
	import type { LidarrConnectionSettings, LidarrVerifyResponse } from '$lib/types';
	import { integrationStore } from '$lib/stores/integration';

	type LidarrSettingsForm = ReturnType<typeof createSettingsForm<LidarrConnectionSettings>> & {
		testResult: LidarrVerifyResponse | { success: false; message: string; valid?: boolean } | null;
	};

	const form = createSettingsForm<LidarrConnectionSettings>({
		loadEndpoint: '/api/v1/settings/lidarr/connection',
		saveEndpoint: '/api/v1/settings/lidarr/connection',
		testEndpoint: '/api/v1/settings/lidarr/verify',
		afterSave: async (data) => {
			if (data.lidarr_url && data.lidarr_api_key) {
				integrationStore.setLidarrConfigured(true);
			}
		}
	}) as LidarrSettingsForm;

	let verifyResult: LidarrVerifyResponse | null = $state(null);
	let showApiKey = $state(false);

	export async function load() {
		verifyResult = null;
		await form.load();
	}

	async function save() {
		await form.save();
	}

	async function verify() {
		if (!form.data) return;

		form.clearMessage();
		verifyResult = null;
		await form.test();
		const result = form.testResult;
		if (!result) return;
		if ('quality_profiles' in result && 'metadata_profiles' in result && 'root_folders' in result) {
			verifyResult = result;
		}
		if (result.success) {
			form.showMessage(result.message, 'success');
			return;
		}
		form.showMessage(
			result.message.toLowerCase().includes('failed')
				? result.message
				: `Connection failed: ${result.message}`,
			'error',
			false
		);
	}

	$effect(() => {
		load();
	});

	onDestroy(() => form.cleanup());
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">Lidarr Connection</h2>
		<p class="text-base-content/70 mb-4">
			Configure your Lidarr server connection for music library management.
		</p>

		{#if form.loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if form.data}
			<div class="space-y-4">
				<div class="form-control w-full">
					<label class="label" for="lidarr-url">
						<span class="label-text">Lidarr URL</span>
					</label>
					<input
						id="lidarr-url"
						type="url"
						bind:value={form.data.lidarr_url}
						class="input input-bordered w-full"
						placeholder="http://lidarr:8686 or http://<host-ip>:8686"
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
							bind:value={form.data.lidarr_api_key}
							class="input input-bordered join-item flex-1"
							placeholder="Your Lidarr API key"
						/>
						<button type="button" class="btn join-item" onclick={() => (showApiKey = !showApiKey)}>
							{showApiKey ? 'Hide' : 'Show'}
						</button>
					</div>
					<label class="label" for="lidarr-api-key">
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
							bind:value={form.data.quality_profile_id}
							class="select select-bordered w-full"
						>
							{#each verifyResult.quality_profiles as profile (profile.id)}
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
							bind:value={form.data.metadata_profile_id}
							class="select select-bordered w-full"
						>
							{#each verifyResult.metadata_profiles as profile (profile.id)}
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
							bind:value={form.data.root_folder_path}
							class="select select-bordered w-full"
						>
							{#each verifyResult.root_folders as folder (folder.path)}
								<option value={folder.path}>{folder.path}</option>
							{/each}
						</select>
					</div>
				{/if}

				{#if form.message}
					<div
						class="alert"
						class:alert-success={form.messageType === 'success'}
						class:alert-error={form.messageType === 'error'}
					>
						<span>{form.message}</span>
					</div>
				{/if}

				<div class="flex justify-end gap-2 pt-2">
					<button
						type="button"
						class="btn btn-ghost"
						onclick={verify}
						disabled={form.testing || !form.data.lidarr_url || !form.data.lidarr_api_key}
					>
						{#if form.testing}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Test Connection
					</button>
					<button type="button" class="btn btn-primary" onclick={save} disabled={form.saving}>
						{#if form.saving}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Save Settings
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>
