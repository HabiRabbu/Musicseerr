<script lang="ts">
	import type { ScrobbleSettings } from '$lib/types';
	import { throwOnApiError, handleFetchError } from '$lib/utils/errorHandling';
	import { integrationStore } from '$lib/stores/integration';
	import { scrobbleManager } from '$lib/stores/scrobble.svelte';
	import { fromStore } from 'svelte/store';

	import { onMount } from 'svelte';

	const integration = fromStore(integrationStore);

	let settings: ScrobbleSettings | null = $state(null);
	let loading = $state(false);
	let saving = $state(false);
	let message = $state('');
	let messageType = $state<'success' | 'error' | 'info'>('info');

	const lastfmConnected = $derived(integration.current.lastfm);
	const listenbrainzConnected = $derived(integration.current.listenbrainz);

	async function load() {
		loading = true;
		message = '';
		try {
			const response = await fetch('/api/settings/scrobble');
			await throwOnApiError(response, 'Failed to load scrobble settings');
			settings = await response.json();
		} catch (error) {
			message = handleFetchError(error, 'Failed to load scrobble settings') ?? '';
			messageType = 'error';
		} finally {
			loading = false;
		}
	}

	async function save() {
		if (!settings) return;
		saving = true;
		message = '';
		try {
			const response = await fetch('/api/settings/scrobble', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(settings),
			});
			await throwOnApiError(response, 'Failed to save scrobble settings');
			settings = await response.json();
			await scrobbleManager.refreshSettings();
			message = 'Scrobble settings saved!';
			messageType = 'success';
			setTimeout(() => {
				message = '';
			}, 5000);
		} catch (error) {
			message = handleFetchError(error, 'Failed to save scrobble settings') ?? '';
			messageType = 'error';
		} finally {
			saving = false;
		}
	}

	onMount(() => {
		load();
	});
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">Scrobbling</h2>
		<p class="text-base-content/70 mb-4">
			Choose which services receive your listening activity. Tracks are scrobbled after 50% of
			playback or 4 minutes, whichever comes first.
		</p>

		{#if loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if settings}
			<div class="space-y-4">
				<div class="form-control">
					<label class="label cursor-pointer justify-start gap-4">
						<div
							class="tooltip tooltip-right"
							class:tooltip-open={false}
							data-tip={!lastfmConnected ? 'Connect Last.fm first in the Last.fm settings tab' : ''}
						>
							<input
								type="checkbox"
								bind:checked={settings.scrobble_to_lastfm}
								class="toggle toggle-primary"
								disabled={!lastfmConnected}
							/>
						</div>
						<div>
							<span class="label-text font-medium">Scrobble to Last.fm</span>
							<p class="text-xs text-base-content/50">
								{#if !lastfmConnected}
									Last.fm is not connected
								{:else}
									Send listening activity to your Last.fm profile
								{/if}
							</p>
						</div>
					</label>
				</div>

				<div class="form-control">
					<label class="label cursor-pointer justify-start gap-4">
						<div
							class="tooltip tooltip-right"
							data-tip={!listenbrainzConnected ? 'Connect ListenBrainz first in the ListenBrainz settings tab' : ''}
						>
							<input
								type="checkbox"
								bind:checked={settings.scrobble_to_listenbrainz}
								class="toggle toggle-primary"
								disabled={!listenbrainzConnected}
							/>
						</div>
						<div>
							<span class="label-text font-medium">Scrobble to ListenBrainz</span>
							<p class="text-xs text-base-content/50">
								{#if !listenbrainzConnected}
									ListenBrainz is not connected
								{:else}
									Send listening activity to your ListenBrainz profile
								{/if}
							</p>
						</div>
					</label>
				</div>

				{#if message}
					<div
						class="alert"
				class:alert-success={messageType === 'success'}
					class:alert-error={messageType === 'error'}
					>
						<span>{message}</span>
					</div>
				{/if}

				<div class="flex justify-end pt-2">
					<button type="button" class="btn btn-primary" onclick={save} disabled={saving}>
						{#if saving}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Save Settings
					</button>
				</div>
			</div>
		{:else if message}
			<div class="alert" class:alert-error={messageType === 'error'}>
				<span>{message}</span>
			</div>
		{/if}
	</div>
</div>
