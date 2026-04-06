<script lang="ts">
	import { createSettingsForm } from '$lib/utils/settingsForm.svelte';
	import { onDestroy } from 'svelte';
	import type { NavidromeConnectionSettings } from '$lib/types';

	type NavidromeTestResult = { valid: boolean; message: string };
	type NavidromeSettingsForm = ReturnType<
		typeof createSettingsForm<NavidromeConnectionSettings>
	> & {
		testResult: NavidromeTestResult | null;
	};

	const form = createSettingsForm<NavidromeConnectionSettings>({
		loadEndpoint: '/api/v1/settings/navidrome',
		saveEndpoint: '/api/v1/settings/navidrome',
		testEndpoint: '/api/v1/settings/navidrome/verify',
		enabledField: 'enabled',
		refreshIntegration: true
	}) as NavidromeSettingsForm;

	let showPassword = $state(false);

	export async function load() {
		await form.load();
	}

	async function save() {
		await form.save();
	}

	async function test() {
		await form.test();
	}

	$effect(() => {
		form.load();
	});

	onDestroy(() => form.cleanup());
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">Navidrome Connection</h2>
		<p class="text-base-content/70 mb-4">
			Connect your Navidrome server for music streaming, recently played tracks, and favorites.
		</p>

		{#if form.loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if form.data}
			<div class="space-y-4">
				<div class="form-control w-full">
					<label class="label" for="navidrome-url">
						<span class="label-text">Navidrome URL</span>
					</label>
					<input
						id="navidrome-url"
						type="url"
						bind:value={form.data.navidrome_url}
						class="input input-bordered w-full"
						placeholder="http://localhost:4533"
					/>
				</div>

				<div class="form-control w-full">
					<label class="label" for="navidrome-username">
						<span class="label-text">Username</span>
					</label>
					<input
						id="navidrome-username"
						type="text"
						bind:value={form.data.username}
						class="input input-bordered w-full"
						placeholder="Your Navidrome username"
					/>
				</div>

				<div class="form-control w-full">
					<label class="label" for="navidrome-password">
						<span class="label-text">Password</span>
					</label>
					<div class="join w-full">
						<input
							id="navidrome-password"
							type={showPassword ? 'text' : 'password'}
							bind:value={form.data.password}
							class="input input-bordered join-item flex-1"
							placeholder="Your Navidrome password"
						/>
						<button
							type="button"
							class="btn join-item"
							onclick={() => (showPassword = !showPassword)}
						>
							{showPassword ? 'Hide' : 'Show'}
						</button>
					</div>
				</div>

				{#if form.testResult}
					<div
						class="alert"
						class:alert-success={form.testResult.valid}
						class:alert-error={!form.testResult.valid}
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
							disabled={!form.testResult?.valid && !form.wasAlreadyEnabled}
						/>
						<div>
							<span class="label-text font-medium">Enable Navidrome Integration</span>
							<p class="text-xs text-base-content/50">
								{#if !form.testResult?.valid && !form.wasAlreadyEnabled}
									Test connection first to enable
								{:else}
									Stream music, view recently played, and browse your Navidrome library
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
						disabled={form.testing ||
							!form.data.navidrome_url ||
							!form.data.username ||
							!form.data.password}
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
