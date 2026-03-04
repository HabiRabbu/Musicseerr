<script lang="ts">
	import { goto } from '$app/navigation';
	import { onDestroy, untrack } from 'svelte';
	import { deletePlaylist, fetchPlaylist, type PlaylistDetail } from '$lib/api/playlists';
	import { playlistTrackToQueueItem } from '$lib/player/queueHelpers';
	import { playerStore } from '$lib/stores/player.svelte';
	import { toastStore } from '$lib/stores/toast';
	import { extractDominantColor, DEFAULT_GRADIENT } from '$lib/utils/colors';
	import { Music } from 'lucide-svelte';
	import BackButton from '$lib/components/BackButton.svelte';
	import type { PageData } from './$types';
	import PlaylistHeader from './PlaylistHeader.svelte';
	import PlaylistTrackList from './PlaylistTrackList.svelte';
	import DeletePlaylistModal from './DeletePlaylistModal.svelte';

	let { data }: { data: PageData } = $props();

	let playlist = $state<PlaylistDetail | null>(null);
	let loading = $state(true);
	let loadError = $state<string | null>(null);
	let activeLoadToken = 0;
	let deleting = $state(false);

	let deleteModal = $state<ReturnType<typeof DeletePlaylistModal> | null>(null);
	let trackList = $state<ReturnType<typeof PlaylistTrackList> | null>(null);
	let header = $state<ReturnType<typeof PlaylistHeader> | null>(null);

	async function loadPlaylist(playlistId: string) {
		const token = ++activeLoadToken;
		loading = true;
		loadError = null;
		playlist = null;
		trackList?.clearReorderState();
		header?.cleanupPreview();

		try {
			const loaded = await fetchPlaylist(playlistId);
			if (token !== activeLoadToken) return;
			playlist = loaded ?? null;
			if (!playlist) {
				loadError = 'Failed to load playlist';
			}
		} catch (e) {
			if (token !== activeLoadToken) return;
			if (e instanceof Error && /404|not found/i.test(e.message)) {
				loadError = 'Playlist not found';
			} else {
				loadError = 'Failed to load playlist';
			}
		} finally {
			if (token === activeLoadToken) {
				loading = false;
			}
		}
	}

	$effect(() => {
		const playlistId = data.playlistId;
		untrack(() => {
			void loadPlaylist(playlistId);
		});
	});

	function playAll() {
		if (!playlist || playlist.tracks.length === 0) return;
		const items = playlist.tracks
			.map(playlistTrackToQueueItem)
			.filter((item): item is NonNullable<typeof item> => item !== null);
		if (items.length === 0) {
			toastStore.show({ message: 'No playable tracks', type: 'info' });
			return;
		}
		playerStore.playQueue(items, 0, false);
	}

	function shuffleAll() {
		if (!playlist || playlist.tracks.length < 2) return;
		const items = playlist.tracks
			.map(playlistTrackToQueueItem)
			.filter((item): item is NonNullable<typeof item> => item !== null);
		if (items.length === 0) {
			toastStore.show({ message: 'No playable tracks', type: 'info' });
			return;
		}
		playerStore.playQueue(items, 0, true);
	}

	async function confirmDelete() {
		if (!playlist || deleting) return;
		deleting = true;
		try {
			await deletePlaylist(playlist.id);
			toastStore.show({ message: 'Playlist deleted', type: 'success' });
			await goto('/playlists');
		} catch {
			toastStore.show({ message: 'Failed to delete playlist', type: 'error' });
		} finally {
			deleting = false;
		}
	}

	let heroGradient = $state(DEFAULT_GRADIENT);
	let heroBgLoaded = $state(false);

	let heroBgUrl = $derived.by(() => {
		if (!playlist) return null;
		if (playlist.custom_cover_url) return playlist.custom_cover_url;
		if (playlist.cover_urls.length > 0) return playlist.cover_urls[0];
		return null;
	});

	$effect(() => {
		const url = heroBgUrl;
		if (url) {
			heroBgLoaded = false;
			extractDominantColor(url).then((gradient) => (heroGradient = gradient));
		} else {
			heroGradient = DEFAULT_GRADIENT;
			heroBgLoaded = false;
		}
	});

	onDestroy(() => {
		activeLoadToken += 1;
		trackList?.clearReorderState();
		header?.cleanupPreview();
	});
</script>

<svelte:head>
	<title>{playlist?.name ?? 'Playlist'} - Musicseerr</title>
</svelte:head>

<div class="w-full px-2 sm:px-4 lg:px-8 py-4 sm:py-8 max-w-7xl mx-auto">
{#if loading}
	<div class="space-y-6 sm:space-y-8">
		<div class="skeleton h-10 w-10 rounded-full"></div>
		<div class="flex flex-col lg:flex-row gap-6 lg:gap-8">
			<div class="skeleton w-full lg:w-64 xl:w-80 aspect-square rounded-box flex-shrink-0"></div>
			<div class="flex-1 flex flex-col justify-end space-y-4">
				<div class="skeleton h-4 w-20"></div>
				<div class="skeleton h-12 w-3/4"></div>
				<div class="skeleton h-6 w-1/2"></div>
				<div class="flex gap-4 mt-6">
					<div class="skeleton h-12 w-32"></div>
					<div class="skeleton h-12 w-32"></div>
				</div>
			</div>
		</div>
		<div class="space-y-2">
			{#each Array(4) as _}
				<div class="skeleton h-14 w-full"></div>
			{/each}
		</div>
	</div>
{:else if loadError}
	<div class="flex flex-col items-center justify-center py-20 gap-4 text-center">
		<Music class="h-16 w-16 text-base-content/20" />
		<h2 class="text-lg font-semibold text-base-content/80">Unable to load playlist</h2>
		<p class="text-sm text-base-content/60">{loadError}</p>
		<div class="flex items-center gap-2">
			<button class="btn btn-sm btn-accent" onclick={() => void loadPlaylist(data.playlistId)}>
				Retry
			</button>
			<BackButton fallback="/playlists" />
		</div>
	</div>
{:else if !playlist}
	<div class="flex flex-col items-center justify-center py-20 gap-4">
		<Music class="h-16 w-16 text-base-content/20" />
		<h2 class="text-lg font-semibold text-base-content/60">Playlist not found</h2>
		<BackButton fallback="/playlists" />
	</div>
{:else}
	<div class="space-y-6 sm:space-y-8">
		<!-- Header with subtle gradient background -->
		<div class="relative overflow-hidden rounded-box">
			<div class="absolute inset-0 bg-gradient-to-b {heroGradient} transition-all duration-1000"></div>
			{#if heroBgUrl}
				<div class="absolute inset-0 overflow-hidden">
					<img
						src={heroBgUrl}
						alt=""
						class="w-full h-full object-cover scale-110 blur-3xl transition-opacity duration-700 {heroBgLoaded ? 'opacity-15' : 'opacity-0'}"
						loading="eager"
						onload={() => (heroBgLoaded = true)}
					/>
					<div class="absolute inset-0 bg-gradient-to-b from-transparent via-base-100/50 to-base-100/80"></div>
				</div>
			{/if}

			<div class="relative z-10 p-4 sm:p-6 lg:p-8">
				<div class="mb-4">
					<BackButton fallback="/playlists" />
				</div>

				<PlaylistHeader
					bind:this={header}
					{playlist}
					onplayall={playAll}
					onshuffleall={shuffleAll}
					ondeleteclick={() => deleteModal?.showModal()}
					onplaylistupdate={() => {}}
				/>
			</div>
		</div>

		<PlaylistTrackList bind:this={trackList} {playlist} ontrackchange={() => {}} />
	</div>

	<DeletePlaylistModal
		bind:this={deleteModal}
		playlistName={playlist.name}
		{deleting}
		onconfirm={() => void confirmDelete()}
	/>
{/if}
</div>
