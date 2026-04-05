<script lang="ts">
	import { musicSourceStore, type MusicSource } from '$lib/stores/musicSource';
	import { integrationStore } from '$lib/stores/integration';
	import { fromStore } from 'svelte/store';

	const integration = fromStore(integrationStore);
	const source = fromStore(musicSourceStore);

	let saving = $state(false);
	let message = $state('');

	const lbConnected = $derived(integration.current.listenbrainz);
	const lfmConnected = $derived(integration.current.lastfm);
	const currentSource = $derived(source.current.source);
	const bothConnected = $derived(lbConnected && lfmConnected);

	async function handleChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const newSource = target.value as MusicSource;
		if (newSource === currentSource) return;
		saving = true;
		message = '';
		const ok = await musicSourceStore.save(newSource);
		if (ok) {
			message = 'Default music source updated';
			setTimeout(() => {
				message = '';
			}, 5000);
		} else {
			message = "Couldn't save the default music source.";
		}
		saving = false;
	}

	$effect(() => {
		integrationStore.ensureLoaded();
		musicSourceStore.load();
	});
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">Primary Music Source</h2>
		<p class="text-base-content/70 mb-4">
			Choose which listening service powers Home and Discover by default. You can still switch
			sources on each page.
		</p>

		{#if !bothConnected}
			<div class="alert alert-info">
				<span>
					Connect both
					{#if !lbConnected}<a href="/settings?tab=listenbrainz" class="link font-medium"
							>ListenBrainz</a
						>{:else}ListenBrainz{/if}
					and
					{#if !lfmConnected}<a href="/settings?tab=lastfm" class="link font-medium">Last.fm</a
						>{:else}Last.fm{/if}
					before choosing a default source. Right now MusicSeerr is using {lbConnected
						? 'ListenBrainz'
						: lfmConnected
							? 'Last.fm'
							: 'no service'}.
				</span>
			</div>
		{:else}
			<fieldset class="fieldset">
				<legend class="fieldset-legend">Default source for discovery data</legend>
				<select
					class="select select-primary w-full max-w-xs"
					value={currentSource}
					onchange={handleChange}
					disabled={saving}
				>
					<option value="listenbrainz">ListenBrainz</option>
					<option value="lastfm">Last.fm</option>
				</select>
				<p class="label text-base-content/60">
					Shared sections like trending and recommendations use this source by default.
				</p>
			</fieldset>

			{#if saving}
				<div class="flex items-center gap-2 mt-2">
					<span class="loading loading-spinner loading-sm"></span>
					<span class="text-sm text-base-content/70">Saving…</span>
				</div>
			{/if}

			{#if message}
				<div class="mt-2">
					<span class="text-sm {message.includes('Failed') ? 'text-error' : 'text-success'}">
						{message}
					</span>
				</div>
			{/if}
		{/if}
	</div>
</div>
