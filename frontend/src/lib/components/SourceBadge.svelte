<script lang="ts">
	import { Radio, Headphones } from 'lucide-svelte';

	interface Props {
		source?: string;
	}

	let { source }: Props = $props();
</script>

{#if source === 'lastfm'}
	<span
		class="badge badge-xs sm:badge-sm border-0 gap-1"
		style="background-color: rgb(var(--brand-lastfm) / 0.15); color: rgb(var(--brand-lastfm));"
	>
		<Radio class="w-2.5 h-2.5 sm:w-3 sm:h-3" />
		Last.fm
	</span>
{:else if source === 'listenbrainz'}
	<span
		class="badge badge-xs sm:badge-sm border-0 gap-1"
		style="background-color: rgb(var(--brand-listenbrainz) / 0.15); color: rgb(var(--brand-listenbrainz));"
	>
		<Headphones class="w-2.5 h-2.5 sm:w-3 sm:h-3" />
		ListenBrainz
	</span>
{:else if source}
	<span class="badge badge-ghost badge-xs sm:badge-sm capitalize">{source}</span>
{/if}
