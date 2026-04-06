<script lang="ts">
	import {
		MusicSource,
		type MusicSourceType,
		type MusicSourcePage
	} from '$lib/stores/musicSource.svelte';
	import { integrationStore } from '$lib/stores/integration';
	import { fromStore } from 'svelte/store';

	interface Props {
		pageKey: MusicSourcePage;
		onSourceChange?: (source: MusicSourceType) => void;
	}

	let { pageKey, onSourceChange }: Props = $props();

	const integrationState = fromStore(integrationStore);
	const pageMusicSourceState = new MusicSource(() => pageKey);

	let switching = $state(false);
	let currentSource = $derived(pageMusicSourceState.current);

	let lbEnabled = $derived(integrationState.current.listenbrainz);
	let lfmEnabled = $derived(integrationState.current.lastfm);
	let showSwitcher = $derived(lbEnabled && lfmEnabled);

	async function handleSwitch(source: MusicSourceType) {
		if (source === currentSource || switching) return;
		switching = true;
		try {
			pageMusicSourceState.current = source;
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
