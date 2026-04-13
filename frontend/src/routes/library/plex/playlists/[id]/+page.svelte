<script lang="ts">
	import { page } from '$app/stores';
	import { API } from '$lib/constants';
	import SourcePlaylistDetail from '$lib/components/SourcePlaylistDetail.svelte';
	import PlexIcon from '$lib/components/PlexIcon.svelte';

	let playlistId = $derived($page.params.id ?? '');
</script>

<SourcePlaylistDetail
	{playlistId}
	detailUrl={API.plexLibrary.playlistDetail}
	importUrl={API.plexLibrary.playlistImport}
	backFallback="/library/plex/playlists"
>
	{#snippet icon()}
		<PlexIcon class="w-6 h-6" />
	{/snippet}
</SourcePlaylistDetail>
