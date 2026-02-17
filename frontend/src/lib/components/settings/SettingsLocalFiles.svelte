<script lang="ts">
	import { API } from '$lib/constants';
	import type { LocalFilesConnectionSettings } from '$lib/types';

	let connection: LocalFilesConnectionSettings | null = $state(null);
	let loading = $state(false);
	let saving = $state(false);
	let testing = $state(false);
	let message = $state('');
	let testResult: { success: boolean; message: string; track_count?: number } | null =
		$state(null);
	let wasAlreadyEnabled = $state(false);

	export async function load() {
		loading = true;
		message = '';
		try {
			const response = await fetch(API.settingsLocalFiles());
			if (response.ok) {
				connection = await response.json();
				wasAlreadyEnabled = connection?.enabled ?? false;
			} else {
				message = 'Failed to load Local Files settings';
			}
		} catch {
			connection = { enabled: false, music_path: '/music', lidarr_root_path: '/music' };
			wasAlreadyEnabled = false;
			message = 'Failed to load settings — showing defaults';
		} finally {
			loading = false;
		}
	}

	async function save() {
		saving = true;
		message = '';
		try {
			const response = await fetch(API.settingsLocalFiles(), {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(connection)
			});

			if (response.ok) {
				message = 'Local Files settings saved successfully!';
				connection = await response.json();
				wasAlreadyEnabled = connection?.enabled ?? false;
				setTimeout(() => {
					message = '';
				}, 5000);
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

	async function test() {
		if (!connection) return;

		testing = true;
		testResult = null;
		try {
			const response = await fetch(API.settingsLocalFilesVerify(), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(connection)
			});

			if (response.ok) {
				testResult = await response.json();
			} else {
				const error = await response.json();
				testResult = { success: false, message: error.detail || 'Verification failed' };
			}
		} catch {
			testResult = { success: false, message: 'Failed to verify path' };
		} finally {
			testing = false;
		}
	}

	function resetVerification(): void {
		testResult = null;
		wasAlreadyEnabled = false;
		if (connection) connection.enabled = false;
	}

	$effect(() => {
		load();
	});
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">Local Files</h2>
		<p class="text-base-content/70 mb-4">
			Play audio files directly from your music library on disk. Requires a Docker volume mount
			pointing to your music folder.
		</p>

		{#if loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if connection}
			<div class="space-y-4">
				<div class="form-control w-full">
					<label class="label" for="local-music-path">
						<span class="label-text">Music Directory Path</span>
					</label>
					<input
						id="local-music-path"
						type="text"
						bind:value={connection.music_path}
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
						bind:value={connection.lidarr_root_path}
						class="input w-full"
						placeholder="/music"
						oninput={resetVerification}
					/>
					<p class="text-xs text-base-content/50 mt-1 ml-1">
						The root folder path as configured in Lidarr. Used to map Lidarr file paths to
						local mount paths.
					</p>
				</div>

				{#if testResult}
					<div
						class="alert"
						class:alert-success={testResult.success}
						class:alert-error={!testResult.success}
					>
						<span>{testResult.message}</span>
					</div>
				{/if}

				<div class="form-control">
					<label class="label cursor-pointer justify-start gap-4">
						<input
							type="checkbox"
							bind:checked={connection.enabled}
							class="toggle toggle-primary"
							disabled={!testResult?.success && !wasAlreadyEnabled}
						/>
						<div>
							<span class="label-text font-medium">Enable Local File Playback</span>
							<p class="text-xs text-base-content/50">
								{#if !testResult?.success && !wasAlreadyEnabled}
									Verify path first to enable
								{:else}
									Play music files directly from your mounted library
								{/if}
							</p>
						</div>
					</label>
				</div>

				{#if message}
					<div
						class="alert"
						class:alert-success={message.includes('success')}
						class:alert-error={message.includes('Failed')}
					>
						<span>{message}</span>
					</div>
				{/if}

				<div class="flex justify-end gap-2 pt-2">
					<button
						type="button"
						class="btn btn-ghost"
						onclick={test}
						disabled={testing || !connection.music_path}
					>
						{#if testing}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Verify Path
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
