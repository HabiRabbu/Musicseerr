<script lang="ts">
	import type { JellyfinConnectionSettings } from '$lib/types';

	type JellyfinUser = { id: string; name: string };

	let connection: JellyfinConnectionSettings | null = $state(null);
	let loading = $state(false);
	let saving = $state(false);
	let testing = $state(false);
	let message = $state('');
	let testResult: { success: boolean; message: string; users?: JellyfinUser[] } | null = $state(null);
	let showApiKey = $state(false);
	let wasAlreadyEnabled = $state(false);
	let availableUsers: JellyfinUser[] = $state([]);

	export async function load() {
		loading = true;
		message = '';
		try {
			const response = await fetch('/api/settings/jellyfin');
			if (response.ok) {
				connection = await response.json();
				wasAlreadyEnabled = connection?.enabled ?? false;
			} else {
				message = 'Failed to load Jellyfin settings';
			}
		} catch {
			message = 'Failed to load Jellyfin settings';
		} finally {
			loading = false;
		}
	}

	async function save() {
		saving = true;
		message = '';
		try {
			const response = await fetch('/api/settings/jellyfin', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(connection)
			});

			if (response.ok) {
				message = 'Jellyfin settings saved successfully!';
				connection = await response.json();
				wasAlreadyEnabled = connection?.enabled ?? false;
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

	async function test() {
		if (!connection) return;

		testing = true;
		testResult = null;
		availableUsers = [];
		try {
			const response = await fetch('/api/settings/jellyfin/verify', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(connection)
			});

			if (response.ok) {
				const result = await response.json();
				testResult = result;
				if (result.success && result.users) {
					availableUsers = result.users;
					if (!connection.user_id && availableUsers.length > 0) {
						connection.user_id = availableUsers[0].id;
					}
				}
			} else {
				const error = await response.json();
				testResult = { success: false, message: error.detail || 'Connection failed' };
			}
		} catch {
			testResult = { success: false, message: 'Failed to test connection' };
		} finally {
			testing = false;
		}
	}

	$effect(() => {
		load();
	});
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">Jellyfin Connection</h2>
		<p class="text-base-content/70 mb-4">
			Connect your Jellyfin server for recently played tracks and favorites.
		</p>

		{#if loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if connection}
			<div class="space-y-4">
				<div class="form-control w-full">
					<label class="label" for="jellyfin-url">
						<span class="label-text">Jellyfin URL</span>
					</label>
					<input
						id="jellyfin-url"
						type="url"
						bind:value={connection.jellyfin_url}
						class="input input-bordered w-full"
						placeholder="http://localhost:8096"
					/>
				</div>

				<div class="form-control w-full">
					<label class="label" for="jellyfin-api-key">
						<span class="label-text">API Key</span>
					</label>
					<div class="join w-full">
						<input
							id="jellyfin-api-key"
							type={showApiKey ? 'text' : 'password'}
							bind:value={connection.api_key}
							class="input input-bordered join-item flex-1"
							placeholder="Your Jellyfin API key"
						/>
						<button type="button" class="btn join-item" onclick={() => showApiKey = !showApiKey}>
							{showApiKey ? 'Hide' : 'Show'}
						</button>
					</div>
					<label class="label">
						<span class="label-text-alt text-base-content/50">Dashboard → API Keys → Create</span>
					</label>
				</div>

				{#if availableUsers.length > 0}
					<div class="form-control w-full">
						<label class="label" for="jellyfin-user">
							<span class="label-text">User</span>
						</label>
						<select
							id="jellyfin-user"
							bind:value={connection.user_id}
							class="select select-bordered w-full"
						>
							{#each availableUsers as user}
								<option value={user.id}>{user.name}</option>
							{/each}
						</select>
					</div>
				{:else}
					<div class="form-control w-full">
						<label class="label" for="jellyfin-user-id">
							<span class="label-text">User ID</span>
						</label>
						<input
							id="jellyfin-user-id"
							type="text"
							bind:value={connection.user_id}
							class="input input-bordered w-full"
							placeholder="Test connection to select user"
						/>
						<label class="label">
							<span class="label-text-alt text-base-content/50">Test connection to load available users</span>
						</label>
					</div>
				{/if}

				{#if testResult}
					<div class="alert" class:alert-success={testResult.success} class:alert-error={!testResult.success}>
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
							<span class="label-text font-medium">Enable Jellyfin Integration</span>
							<p class="text-xs text-base-content/50">
								{#if !testResult?.success && !wasAlreadyEnabled}
									Test connection first to enable
								{:else}
									Show recently played and favorite artists on the home page
								{/if}
							</p>
						</div>
					</label>
				</div>

				{#if message}
					<div class="alert" class:alert-success={message.includes('success')} class:alert-error={message.includes('Failed')}>
						<span>{message}</span>
					</div>
				{/if}

				<div class="flex justify-end gap-2 pt-2">
					<button type="button" class="btn btn-ghost" onclick={test} disabled={testing || !connection.jellyfin_url || !connection.api_key}>
						{#if testing}
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
