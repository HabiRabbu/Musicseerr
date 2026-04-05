<script lang="ts">
	import type { ListenBrainzConnectionSettings } from '$lib/types';
	import { createSettingsForm } from '$lib/utils/settingsForm.svelte';
	import { onMount, onDestroy } from 'svelte';
	import { ExternalLink, CircleCheck } from 'lucide-svelte';

	type ConnectionTestResult = { valid: boolean; message: string };

	const form = createSettingsForm<ListenBrainzConnectionSettings>({
		loadEndpoint: '/api/v1/settings/listenbrainz',
		saveEndpoint: '/api/v1/settings/listenbrainz',
		testEndpoint: '/api/v1/settings/listenbrainz/verify',
		enabledField: 'enabled',
		refreshIntegration: true
	});

	let showToken = $state(false);
	let showDetails = $state(false);
	let dataPersisted = $state(false);
	const testResult = $derived(form.testResult as ConnectionTestResult | null);

	const step1Complete = $derived(dataPersisted && !!form.data?.username);
	const step2Complete = $derived(form.wasAlreadyEnabled);
	const fullyConnected = $derived(step1Complete && step2Complete);
	const showForm = $derived(!fullyConnected || showDetails);

	async function save() {
		const ok = await form.save();
		if (ok) dataPersisted = true;
	}

	async function test() {
		await form.test();
	}

	async function saveAndTest() {
		const ok = await form.save();
		if (ok) {
			dataPersisted = true;
			await form.test();
		}
	}

	onMount(async () => {
		await form.load();
		dataPersisted = !!form.data?.username;
	});

	onDestroy(() => form.cleanup());
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">ListenBrainz</h2>
		<p class="text-base-content/70 mb-4">
			Connect to ListenBrainz for personalized recommendations and listening stats.
		</p>

		{#if form.loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if form.data}
			<ul class="steps steps-horizontal w-full mb-6">
				<li class="step" class:step-primary={step1Complete}>Credentials</li>
				<li class="step" class:step-primary={step2Complete}>Enable</li>
			</ul>

			{#if fullyConnected}
				<div class="alert alert-success mb-4">
					<CircleCheck class="w-5 h-5 shrink-0" />
					<span>Connected as <strong>{form.data.username}</strong></span>
					<button
						type="button"
						class="btn btn-ghost btn-sm ml-auto"
						onclick={() => (showDetails = !showDetails)}
					>
						{showDetails ? 'Hide details' : 'Edit settings'}
					</button>
				</div>
			{/if}

			{#if showForm}
				<div class="space-y-6">
					<div class="space-y-4">
						<h3 class="text-lg font-semibold">Step 1 — Credentials</h3>

						{#if !step1Complete}
							<div class="bg-base-300 rounded-lg p-4 space-y-2 text-sm">
								<p class="font-medium">To get started:</p>
								<ol class="list-decimal list-inside space-y-1 text-base-content/70">
									<li>
										Create a free account at
										<a
											href="https://listenbrainz.org"
											target="_blank"
											rel="noopener noreferrer"
											class="link link-primary inline-flex items-center gap-1"
										>
											listenbrainz.org
											<ExternalLink class="w-3 h-3" />
											<span class="sr-only">(opens in new tab)</span>
										</a>
									</li>
									<li>Enter your username below</li>
									<li>Optionally add your User Token for private statistics</li>
								</ol>
							</div>
						{/if}

						<div class="form-control w-full">
							<label class="label" for="lb-username">
								<span class="label-text">Username</span>
							</label>
							<input
								id="lb-username"
								type="text"
								bind:value={form.data.username}
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
									bind:value={form.data.user_token}
									class="input input-bordered join-item flex-1"
									placeholder="For private statistics"
								/>
								<button
									type="button"
									class="btn join-item"
									onclick={() => (showToken = !showToken)}
								>
									{showToken ? 'Hide' : 'Show'}
								</button>
							</div>
							<label class="label">
								<span class="label-text-alt text-base-content/50">
									Find your token at
									<a
										href="https://listenbrainz.org/settings/"
										target="_blank"
										rel="noopener noreferrer"
										class="link link-primary inline-flex items-center gap-1"
									>
										listenbrainz.org/settings
										<ExternalLink class="w-3 h-3" />
										<span class="sr-only">(opens in new tab)</span>
									</a>
								</span>
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

						<div class="flex flex-wrap justify-end gap-2">
							<button
								type="button"
								class="btn btn-ghost"
								onclick={test}
								disabled={form.testing || form.saving || !form.data.username}
							>
								{#if form.testing && !form.saving}
									<span class="loading loading-spinner loading-sm"></span>
								{/if}
								Test Connection
							</button>
							<button
								type="button"
								class="btn btn-primary"
								onclick={saveAndTest}
								disabled={form.saving || form.testing || !form.data.username}
							>
								{#if form.saving}
									<span class="loading loading-spinner loading-sm"></span>
								{/if}
								Save &amp; Test
							</button>
						</div>
					</div>

					{#if step1Complete || form.data.enabled}
						<div class="divider"></div>
						<div class="space-y-4">
							<h3 class="text-lg font-semibold">Step 2 — Enable</h3>

							<div class="form-control">
								<label class="label cursor-pointer justify-start gap-4">
									<input
										type="checkbox"
										bind:checked={form.data.enabled}
										class="toggle toggle-primary"
									/>
									<div>
										<span class="label-text font-medium">Enable ListenBrainz Integration</span>
										<p class="text-xs text-base-content/50">
											{#if form.data.enabled && !step1Complete}
												Integration is enabled but credentials are incomplete. Consider updating
												your username above.
											{:else}
												Show personalized recommendations and listening stats on the home page.
											{/if}
										</p>
									</div>
								</label>
							</div>

							<div class="flex justify-end pt-2">
								<button type="button" class="btn btn-primary" onclick={save} disabled={form.saving}>
									{#if form.saving}
										<span class="loading loading-spinner loading-sm"></span>
									{/if}
									Save Settings
								</button>
							</div>
						</div>
					{/if}

					{#if step2Complete}
						<div class="divider"></div>
						<div class="alert alert-info">
							<span>
								To scrobble your listening activity to ListenBrainz,
								<a href="/settings?tab=scrobbling" class="link font-medium"
									>enable it in the Scrobbling tab →</a
								>
							</span>
						</div>
					{/if}
				</div>
			{/if}

			{#if form.message}
				<div
					class="alert mt-4"
					class:alert-success={form.messageType === 'success'}
					class:alert-error={form.messageType === 'error'}
				>
					<span>{form.message}</span>
				</div>
			{/if}
		{:else if form.message}
			<div class="alert" class:alert-error={form.messageType === 'error'}>
				<span>{form.message}</span>
			</div>
		{/if}
	</div>
</div>
