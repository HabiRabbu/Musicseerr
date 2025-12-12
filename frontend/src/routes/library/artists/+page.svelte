<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import ArtistCard from '$lib/components/ArtistCard.svelte';
	import type { Artist } from '$lib/types';

	type LibraryArtist = {
		name: string;
		mbid: string;
		album_count: number;
		date_added: string | null;
	};

	let allArtists: LibraryArtist[] = [];
	let loading = true;

	onMount(async () => {
		await loadArtists();
	});

	async function loadArtists() {
		loading = true;
		try {
			const res = await fetch('/api/library/artists');
			if (res.ok) {
				const data = await res.json();
				allArtists = data.artists;
			}
		} catch (error) {
			console.error('Failed to load artists:', error);
		} finally {
			loading = false;
		}
	}

	function convertToArtist(libArtist: LibraryArtist): Artist {
		return {
			title: libArtist.name,
			musicbrainz_id: libArtist.mbid,
			in_library: true
		};
	}

	$: artistsByLetter = allArtists.reduce((acc, artist) => {
		const firstLetter = artist.name.charAt(0).toUpperCase();
		const letter = /[A-Z]/.test(firstLetter) ? firstLetter : '#';
		if (!acc[letter]) acc[letter] = [];
		acc[letter].push(artist);
		return acc;
	}, {} as Record<string, LibraryArtist[]>);

	$: sortedArtistLetters = Object.keys(artistsByLetter).sort((a, b) => {
		if (a === '#') return 1;
		if (b === '#') return -1;
		return a.localeCompare(b);
	});
</script>

<div class="container mx-auto p-4 md:p-6 lg:p-8">
	<!-- Header with back button -->
	<div class="flex items-center gap-4 mb-6">
		<button
			class="btn btn-ghost btn-circle"
			on:click={() => goto('/library')}
			aria-label="Back to library"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
				stroke-width="2"
				stroke="currentColor"
				class="w-6 h-6"
			>
				<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
			</svg>
		</button>
		<div>
			<h1 class="text-3xl font-bold">All Artists</h1>
			<p class="text-base-content/70 text-sm mt-1">
				{allArtists.length} {allArtists.length === 1 ? 'artist' : 'artists'}
			</p>
		</div>
	</div>

	{#if loading}
		<div class="flex justify-center items-center min-h-[400px]">
			<span class="loading loading-spinner loading-lg"></span>
		</div>
	{:else if allArtists.length === 0}
		<div class="flex flex-col items-center justify-center min-h-[400px] text-center">
			<div class="text-6xl mb-4">🎤</div>
			<h2 class="text-2xl font-semibold mb-2">No artists found</h2>
			<p class="text-base-content/70 mb-4">
				Your library doesn't contain any artists yet.
			</p>
		</div>
	{:else}
		<!-- Artists Grouped Alphabetically -->
		<div class="space-y-8">
			{#each sortedArtistLetters as letter}
				<div>
					<div class="divider divider-start text-xl font-bold text-primary">{letter}</div>
					<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
						{#each artistsByLetter[letter] as artist}
							<ArtistCard artist={convertToArtist(artist)} />
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
