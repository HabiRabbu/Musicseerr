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
			message = 'Primary music source updated!';
			setTimeout(() => {
				message = '';
			}, 5000);
		} else {
			message = 'Failed to save primary music source.';
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
			Choose which service provides listening data for Home and Discover pages. You can also
			override per page using the inline source switcher.
		</p>

		{#if !bothConnected}
			<div class="alert alert-info">
				<span>
					Connect both ListenBrainz and Last.fm in External Services to choose a primary source.
					Currently using {lbConnected ? 'ListenBrainz' : lfmConnected ? 'Last.fm' : 'no service'}.
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
					Shared sections (trending, recommended) will use data from this service by default.
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
