<script lang="ts">
	type YouTubeConnectionSettings = {
		api_key: string;
		enabled: boolean;
		daily_quota_limit: number;
	};

	let connection: YouTubeConnectionSettings | null = $state(null);
	let loading = $state(false);
	let saving = $state(false);
	let testing = $state(false);
	let message = $state('');
	let testResult: { valid: boolean; message: string } | null = $state(null);
	let showKey = $state(false);
	let wasAlreadyEnabled = $state(false);

	export async function load() {
		loading = true;
		message = '';
		try {
			const response = await fetch('/api/settings/youtube');
			if (response.ok) {
				connection = await response.json();
				wasAlreadyEnabled = connection?.enabled ?? false;
			} else {
				message = 'Failed to load YouTube settings';
			}
		} catch {
			message = 'Failed to load YouTube settings';
		} finally {
			loading = false;
		}
	}

	async function save() {
		saving = true;
		message = '';
		try {
			const response = await fetch('/api/settings/youtube', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(connection)
			});

			if (response.ok) {
				message = 'YouTube settings saved successfully!';
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
			const response = await fetch('/api/settings/youtube/verify', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(connection)
			});

			if (response.ok) {
				testResult = await response.json();
			} else {
				const error = await response.json();
				testResult = { valid: false, message: error.detail || 'Validation failed' };
			}
		} catch {
			testResult = { valid: false, message: 'Failed to test connection' };
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
		<h2 class="card-title text-2xl">YouTube</h2>
		<p class="text-base-content/70 mb-4">
			Connect a YouTube Data API key to enable embedded video previews in the Discover Queue. Get
			a free key from the
			<a
				href="https://console.cloud.google.com/apis/library/youtube.googleapis.com"
				target="_blank"
				rel="noopener noreferrer"
				class="link link-primary">Google Cloud Console</a
			>.
		</p>

		{#if loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if connection}
			<div class="space-y-4">
				<div class="form-control w-full">
					<label class="label" for="yt-api-key">
						<span class="label-text">API Key</span>
					</label>
					<div class="join w-full">
						<input
							id="yt-api-key"
							type={showKey ? 'text' : 'password'}
							bind:value={connection.api_key}
							class="input input-bordered join-item flex-1"
							placeholder="Your YouTube Data API v3 key"
						/>
						<button
							type="button"
							class="btn join-item"
							onclick={() => (showKey = !showKey)}
						>
							{showKey ? 'Hide' : 'Show'}
						</button>
					</div>
					<label class="label">
						<span class="label-text-alt text-base-content/50"
							>Enable YouTube Data API v3, then create an API key in Credentials</span
						>
					</label>
				</div>

				{#if testResult}
					<div
						class="alert"
						class:alert-success={testResult.valid}
						class:alert-error={!testResult.valid}
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
							disabled={!testResult?.valid && !wasAlreadyEnabled}
						/>
						<div>
							<span class="label-text font-medium">Enable YouTube Integration</span>
							<p class="text-xs text-base-content/50">
								{#if !testResult?.valid && !wasAlreadyEnabled}
									Test connection first to enable
								{:else}
									Show embedded video previews in the Discover Queue (uses ~100
									searches/day free quota)
								{/if}
							</p>
						</div>
					</label>
				</div>

				<div class="form-control w-full">
					<label class="label" for="yt-quota-limit">
						<span class="label-text">Daily Quota Limit</span>
					</label>
					<input
						id="yt-quota-limit"
						type="number"
						min="1"
						max="10000"
						bind:value={connection.daily_quota_limit}
						class="input input-bordered w-32"
					/>
					<label class="label" for="yt-quota-limit">
						<span class="label-text-alt text-base-content/50">
							Maximum video lookups per day (default: 80)
						</span>
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
						disabled={testing || !connection.api_key}
					>
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
