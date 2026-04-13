<script lang="ts">
	import { page } from '$app/stores';
	import { API } from '$lib/constants';
	import SourcePlaylistDetail from '$lib/components/SourcePlaylistDetail.svelte';
	import JellyfinIcon from '$lib/components/JellyfinIcon.svelte';

	let playlistId = $derived($page.params.id ?? '');
</script>

<SourcePlaylistDetail
	{playlistId}
	detailUrl={API.jellyfinLibrary.playlistDetail}
	importUrl={API.jellyfinLibrary.playlistImport}
	backFallback="/library/jellyfin/playlists"
>
	{#snippet icon()}
		<JellyfinIcon class="w-6 h-6" />
	{/snippet}
</SourcePlaylistDetail>
