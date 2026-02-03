<script lang="ts">
	import type { ListenBrainzConnectionSettings } from '$lib/types';

	let connection: ListenBrainzConnectionSettings | null = $state(null);
	let loading = $state(false);
	let saving = $state(false);
	let testing = $state(false);
	let message = $state('');
	let testResult: { valid: boolean; message: string } | null = $state(null);
	let showToken = $state(false);
	let wasAlreadyEnabled = $state(false);

	export async function load() {
		loading = true;
		message = '';
		try {
			const response = await fetch('/api/settings/listenbrainz');
			if (response.ok) {
				connection = await response.json();
				wasAlreadyEnabled = connection?.enabled ?? false;
			} else {
				message = 'Failed to load ListenBrainz settings';
			}
		} catch {
			message = 'Failed to load ListenBrainz settings';
		} finally {
			loading = false;
		}
	}

	async function save() {
		saving = true;
		message = '';
		try {
			const response = await fetch('/api/settings/listenbrainz', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(connection)
			});

			if (response.ok) {
				message = 'ListenBrainz settings saved successfully!';
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
		try {
			const response = await fetch('/api/settings/listenbrainz/verify', {
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
		<h2 class="card-title text-2xl">ListenBrainz</h2>
		<p class="text-base-content/70 mb-4">
			Connect to ListenBrainz for personalized recommendations and listening stats.
		</p>

		{#if loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if connection}
			<div class="space-y-4">
				<div class="form-control w-full">
					<label class="label" for="lb-username">
						<span class="label-text">Username</span>
					</label>
					<input
						id="lb-username"
						type="text"
						bind:value={connection.username}
						class="input input-bordered w-full"
						placeholder="Your ListenBrainz username"
					/>
				</div>

				<div class="form-control w-full">
					<label class="label" for="lb-token">
						<span class="label-text">User Token (optional)</span>
					</label>
					<div class="join w-full">
						<input
							id="lb-token"
							type={showToken ? 'text' : 'password'}
							bind:value={connection.user_token}
							class="input input-bordered join-item flex-1"
							placeholder="For private statistics"
						/>
						<button type="button" class="btn join-item" onclick={() => showToken = !showToken}>
							{showToken ? 'Hide' : 'Show'}
						</button>
					</div>
					<label class="label">
						<span class="label-text-alt text-base-content/50">Profile → Settings → User Token</span>
					</label>
				</div>

				{#if testResult}
					<div class="alert" class:alert-success={testResult.valid} class:alert-error={!testResult.valid}>
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
							<span class="label-text font-medium">Enable ListenBrainz Integration</span>
							<p class="text-xs text-base-content/50">
								{#if !testResult?.valid && !wasAlreadyEnabled}
									Test connection first to enable
								{:else}
									Show personalized recommendations and listening stats on the home page
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
					<button type="button" class="btn btn-ghost" onclick={test} disabled={testing || !connection.username}>
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
