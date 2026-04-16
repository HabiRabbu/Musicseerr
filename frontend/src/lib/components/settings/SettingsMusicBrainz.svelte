<script lang="ts">
	import { API } from '$lib/constants';
	import { createSettingsForm } from '$lib/utils/settingsForm.svelte';
	import { onDestroy } from 'svelte';

	type MusicBrainzConnectionSettings = {
		api_url: string;
		rate_limit: number;
		concurrent_searches: number;
	};

	type MusicBrainzTestResult = { valid: boolean; message: string };
	type MusicBrainzSettingsForm = ReturnType<
		typeof createSettingsForm<MusicBrainzConnectionSettings>
	> & {
		testResult: MusicBrainzTestResult | null;
	};

	const form = createSettingsForm<MusicBrainzConnectionSettings>({
		loadEndpoint: API.settingsMusicbrainz(),
		saveEndpoint: API.settingsMusicbrainz(),
		testEndpoint: API.settingsMusicbrainzVerify(),
		defaultValue: {
			api_url: 'https://musicbrainz.org/ws/2',
			rate_limit: 1.0,
			concurrent_searches: 6
		}
	}) as MusicBrainzSettingsForm;

	export async function load() {
		await form.load();
	}

	async function save() {
		await form.save();
	}

	async function test() {
		await form.test();
	}

	function resetToDefaults() {
		if (form.data) {
			form.data.api_url = 'https://musicbrainz.org/ws/2';
			form.data.rate_limit = 1.0;
			form.data.concurrent_searches = 6;
			form.testResult = null;
		}
	}

	let hasPassedTest = $derived(
		form.testResult != null && (form.testResult as MusicBrainzTestResult).valid === true
	);

	$effect(() => {
		form.load();
	});

	onDestroy(() => form.cleanup());
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">MusicBrainz</h2>
		<p class="text-base-content/70 mb-4">
			Configure the MusicBrainz API endpoint and rate limiting. Defaults work for the public API.
			Change these only if you run a self-hosted MusicBrainz instance.
		</p>

		{#if form.loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if form.data}
			<div class="space-y-4">
				<div class="form-control w-full">
					<label class="label" for="mb-api-url">
						<span class="label-text">API Endpoint URL</span>
					</label>
					<input
						id="mb-api-url"
						type="text"
						bind:value={form.data.api_url}
						class="input w-full"
						placeholder="https://musicbrainz.org/ws/2"
					/>
					<p class="text-xs text-base-content/50 mt-1 ml-1">
						The full URL to the MusicBrainz API, including the version path. For self-hosted
						instances, use your server's API URL (e.g. https://my-mb-server.example.org/ws/2).
					</p>
				</div>

				<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
					<div class="form-control w-full">
						<label class="label" for="mb-rate-limit">
							<span class="label-text">Rate Limit (requests/sec)</span>
						</label>
						<input
							id="mb-rate-limit"
							type="number"
							min="0.1"
							max="50"
							step="0.1"
							bind:value={form.data.rate_limit}
							class="input w-full"
						/>
						<p class="text-xs text-base-content/50 mt-1 ml-1">
							Maximum sustained requests per second. The official MusicBrainz limit is ~1 req/sec.
							Self-hosted instances may support higher rates.
						</p>
					</div>

					<div class="form-control w-full">
						<label class="label" for="mb-concurrent">
							<span class="label-text">Concurrent Searches</span>
						</label>
						<input
							id="mb-concurrent"
							type="number"
							min="1"
							max="30"
							bind:value={form.data.concurrent_searches}
							class="input w-full"
						/>
						<p class="text-xs text-base-content/50 mt-1 ml-1">
							Burst capacity for parallel API requests (default: 6).
						</p>
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

				{#if form.message}
					<div
						class="alert"
						class:alert-success={form.messageType === 'success'}
						class:alert-error={form.messageType === 'error'}
					>
						<span>{form.message}</span>
					</div>
				{/if}

				<div class="flex justify-between items-center pt-2">
					<button type="button" class="btn btn-outline btn-error btn-sm" onclick={resetToDefaults}>
						Reset to Defaults
					</button>
					<div class="flex gap-2">
						<button
							type="button"
							class="btn btn-ghost"
							onclick={test}
							disabled={form.testing || !form.data.api_url}
						>
							{#if form.testing}
								<span class="loading loading-spinner loading-sm"></span>
							{/if}
							Test Connection
						</button>
						<div
							class="tooltip"
							class:tooltip-left={!hasPassedTest}
							data-tip={!hasPassedTest ? 'Test connection before saving' : ''}
						>
							<button
								type="button"
								class="btn btn-primary"
								onclick={save}
								disabled={form.saving || !hasPassedTest}
							>
								{#if form.saving}
									<span class="loading loading-spinner loading-sm"></span>
								{/if}
								Save Settings
							</button>
						</div>
					</div>
				</div>
			</div>
		{/if}
	</div>
</div>
