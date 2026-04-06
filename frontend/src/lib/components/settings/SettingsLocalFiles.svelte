<script lang="ts">
	import { API } from '$lib/constants';
	import { createSettingsForm } from '$lib/utils/settingsForm.svelte';
	import { onDestroy } from 'svelte';
	import type { LocalFilesConnectionSettings } from '$lib/types';

	type LocalFilesTestResult = { success: boolean; message: string; track_count?: number };
	type LocalFilesSettingsForm = ReturnType<
		typeof createSettingsForm<LocalFilesConnectionSettings>
	> & {
		testResult: LocalFilesTestResult | null;
	};

	const form = createSettingsForm<LocalFilesConnectionSettings>({
		loadEndpoint: API.settingsLocalFiles(),
		saveEndpoint: API.settingsLocalFiles(),
		testEndpoint: API.settingsLocalFilesVerify(),
		defaultValue: { enabled: false, music_path: '/music', lidarr_root_path: '/music' },
		enabledField: 'enabled',
		refreshIntegration: true
	}) as LocalFilesSettingsForm;
	let verificationReset = $state(false);

	export async function load() {
		await form.load();
	}

	async function save() {
		await form.save();
	}

	async function test() {
		await form.test();
		verificationReset = false;
	}

	function resetVerification(): void {
		form.testResult = null;
		verificationReset = true;
		if (form.data) form.data.enabled = false;
	}

	$effect(() => {
		form.load();
	});

	onDestroy(() => form.cleanup());
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">Local Files</h2>
		<p class="text-base-content/70 mb-4">
			Play audio files directly from your music library on disk. Requires a Docker volume mount
			pointing to your music folder.
		</p>

		{#if form.loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if form.data}
			<div class="space-y-4">
				<div class="form-control w-full">
					<label class="label" for="local-music-path">
						<span class="label-text">Music Directory Path</span>
					</label>
					<input
						id="local-music-path"
						type="text"
						bind:value={form.data.music_path}
						class="input w-full"
						placeholder="/music"
						oninput={resetVerification}
					/>
					<p class="text-xs text-base-content/50 mt-1 ml-1">
						The path inside the container where music files are mounted (e.g. /music)
					</p>
				</div>

				<div class="form-control w-full">
					<label class="label" for="local-lidarr-root">
						<span class="label-text">Lidarr Root Folder Path</span>
					</label>
					<input
						id="local-lidarr-root"
						type="text"
						bind:value={form.data.lidarr_root_path}
						class="input w-full"
						placeholder="/music"
						oninput={resetVerification}
					/>
					<p class="text-xs text-base-content/50 mt-1 ml-1">
						The root folder path as configured in Lidarr. Used to map Lidarr file paths to local
						mount paths.
					</p>
				</div>

				{#if form.testResult}
					<div
						class="alert"
						class:alert-success={form.testResult.success}
						class:alert-error={!form.testResult.success}
					>
						<span>{form.testResult.message}</span>
					</div>
				{/if}

				<div class="form-control">
					<label class="label cursor-pointer justify-start gap-4">
						<input
							type="checkbox"
							bind:checked={form.data.enabled}
							class="toggle toggle-primary"
							disabled={!form.testResult?.success && (!form.wasAlreadyEnabled || verificationReset)}
						/>
						<div>
							<span class="label-text font-medium">Enable Local File Playback</span>
							<p class="text-xs text-base-content/50">
								{#if !form.testResult?.success && (!form.wasAlreadyEnabled || verificationReset)}
									Verify path first to enable
								{:else}
									Play music files directly from your mounted library
								{/if}
							</p>
						</div>
					</label>
				</div>

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
						onclick={test}
						disabled={form.testing || !form.data.music_path}
					>
						{#if form.testing}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Verify Path
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
