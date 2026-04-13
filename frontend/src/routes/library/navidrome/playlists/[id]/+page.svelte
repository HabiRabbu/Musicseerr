<script lang="ts">
	import { page } from '$app/stores';
	import { API } from '$lib/constants';
	import SourcePlaylistDetail from '$lib/components/SourcePlaylistDetail.svelte';
	import NavidromeIcon from '$lib/components/NavidromeIcon.svelte';

	let playlistId = $derived($page.params.id ?? '');
</script>

<SourcePlaylistDetail
	{playlistId}
	detailUrl={API.navidromeLibrary.playlistDetail}
	importUrl={API.navidromeLibrary.playlistImport}
	backFallback="/library/navidrome/playlists"
>
	{#snippet icon()}
		<NavidromeIcon class="w-6 h-6" />
	{/snippet}
</SourcePlaylistDetail>
