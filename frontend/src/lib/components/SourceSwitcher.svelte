<script lang="ts">
	import {
		musicSourceStore,
		type MusicSource,
		type MusicSourcePage
	} from '$lib/stores/musicSource';
	import { integrationStore } from '$lib/stores/integration';
	import { fromStore } from 'svelte/store';

	interface Props {
		pageKey: MusicSourcePage;
		onSourceChange?: (source: MusicSource) => void;
	}

	let { pageKey, onSourceChange }: Props = $props();

	const sourceState = fromStore(musicSourceStore);
	const integrationState = fromStore(integrationStore);

	let switching = $state(false);
	let currentSource = $state<MusicSource>('listenbrainz');

	let lbEnabled = $derived(integrationState.current.listenbrainz);
	let lfmEnabled = $derived(integrationState.current.lastfm);
	let showSwitcher = $derived(lbEnabled && lfmEnabled);

	$effect(() => {
		// TODO should be refactored
		// eslint-disable-next-line @typescript-eslint/no-unused-expressions
		sourceState.current.source; // Reactivity
		currentSource = musicSourceStore.getPageSource(pageKey);
	});

	async function handleSwitch(source: MusicSource) {
		if (source === currentSource || switching) return;
		switching = true;
		try {
			musicSourceStore.setPageSource(pageKey, source);
			currentSource = source;
			onSourceChange?.(source);
		} finally {
			switching = false;
		}
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
