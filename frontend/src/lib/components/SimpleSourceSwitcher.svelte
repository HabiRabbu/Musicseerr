<script lang="ts">
	import { type MusicSource } from '$lib/stores/musicSource';
	import { integrationStore } from '$lib/stores/integration';
	import { fromStore } from 'svelte/store';

	interface Props {
		currentSource: MusicSource;
		onSourceChange?: (source: MusicSource) => void;
	}

	let { currentSource, onSourceChange }: Props = $props();

	const integrationState = fromStore(integrationStore);

	let switching = $state(false);

	let lbEnabled = $derived(integrationState.current.listenbrainz);
	let lfmEnabled = $derived(integrationState.current.lastfm);
	let showSwitcher = $derived(lbEnabled && lfmEnabled);

	async function handleSwitch(source: MusicSource) {
		if (source === currentSource || switching) return;
		switching = true;
		onSourceChange?.(source);
		switching = false;
	}
</script>

{#if showSwitcher}
	<div class="join">
		<button
			class="btn btn-sm join-item {currentSource === 'listenbrainz' ? 'btn-primary' : 'btn-ghost'}"
			disabled={switching}
			onclick={() => handleSwitch('listenbrainz')}
		>
			ListenBrainz
		</button>
		<button
			class="btn btn-sm join-item {currentSource === 'lastfm' ? 'btn-lastfm' : 'btn-ghost'}"
			disabled={switching}
			onclick={() => handleSwitch('lastfm')}
		>
			Last.fm
		</button>
	</div>
{/if}
