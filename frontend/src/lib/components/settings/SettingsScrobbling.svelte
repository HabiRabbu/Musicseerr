<script lang="ts">
	import type { ScrobbleSettings } from '$lib/types';
	import { createSettingsForm } from '$lib/utils/settingsForm.svelte';
	import { integrationStore } from '$lib/stores/integration';
	import { scrobbleManager } from '$lib/stores/scrobble.svelte';
	import { fromStore } from 'svelte/store';

	import { onMount, onDestroy } from 'svelte';

	const integration = fromStore(integrationStore);
	const form = createSettingsForm<ScrobbleSettings>({
		loadEndpoint: '/api/v1/settings/scrobble',
		saveEndpoint: '/api/v1/settings/scrobble',
		afterSave: async () => {
			await scrobbleManager.refreshSettings();
		}
	});

	const lastfmConnected = $derived(integration.current.lastfm);
	const listenbrainzConnected = $derived(integration.current.listenbrainz);

	async function load() {
		await form.load();
	}

	async function save() {
		await form.save();
	}

	onMount(() => {
		load();
	});

	onDestroy(() => form.cleanup());
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">Scrobbling</h2>
		<p class="text-base-content/70 mb-4">
			Choose which services receive your listening activity. Tracks are scrobbled after 50% of
			playback or 4 minutes, whichever comes first.
		</p>

		{#if form.loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if form.data}
			<div class="space-y-4">
				<div class="form-control">
					<label class="label cursor-pointer justify-start gap-4">
						<input
							type="checkbox"
							bind:checked={form.data.scrobble_to_lastfm}
							class="toggle toggle-primary"
							disabled={!lastfmConnected}
						/>
						<div>
							<span class="label-text font-medium">Scrobble to Last.fm</span>
							<p class="text-xs text-base-content/50">
								{#if !lastfmConnected}
									<a href="/settings?tab=lastfm" class="link link-primary"
										>Connect Last.fm first →</a
									>
								{:else}
									Send listening activity to your Last.fm profile
								{/if}
							</p>
						</div>
					</label>
				</div>

				<div class="form-control">
					<label class="label cursor-pointer justify-start gap-4">
						<input
							type="checkbox"
							bind:checked={form.data.scrobble_to_listenbrainz}
							class="toggle toggle-primary"
							disabled={!listenbrainzConnected}
						/>
						<div>
							<span class="label-text font-medium">Scrobble to ListenBrainz</span>
							<p class="text-xs text-base-content/50">
								{#if !listenbrainzConnected}
									<a href="/settings?tab=listenbrainz" class="link link-primary"
										>Connect ListenBrainz first →</a
									>
								{:else}
									Send listening activity to your ListenBrainz profile
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

				<div class="flex justify-end pt-2">
					<button type="button" class="btn btn-primary" onclick={save} disabled={form.saving}>
						{#if form.saving}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Save Settings
					</button>
				</div>
			</div>
		{:else if form.message}
			<div class="alert" class:alert-error={form.messageType === 'error'}>
				<span>{form.message}</span>
			</div>
		{/if}
	</div>
</div>
