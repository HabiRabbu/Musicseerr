<script lang="ts">
	import { onMount } from 'svelte';
	import { API } from '$lib/constants';
	import YouTubeIcon from '$lib/components/YouTubeIcon.svelte';
	import AlbumImage from '$lib/components/AlbumImage.svelte';
	import YouTubeLinkModal from '$lib/components/YouTubeLinkModal.svelte';
	import YouTubeDetailModal from '$lib/components/YouTubeDetailModal.svelte';
	import type { YouTubeLink } from '$lib/types';

	let links = $state<YouTubeLink[]>([]);
	let loading = $state(true);

	let editModalOpen = $state(false);
	let editingLink = $state<YouTubeLink | null>(null);

	let detailModalOpen = $state(false);
	let detailLink = $state<YouTubeLink | null>(null);
	let returnToDetailAfterEdit = $state<YouTubeLink | null>(null);

	async function fetchLinks(): Promise<void> {
		loading = true;
		try {
			const res = await fetch(API.youtube.links());
			if (res.ok) links = await res.json();
		} catch {} finally {
			loading = false;
		}
	}

	function openAddModal(): void {
		editingLink = null;
		editModalOpen = true;
	}

	function openDetail(link: YouTubeLink): void {
		detailLink = link;
		detailModalOpen = true;
	}

	function handleDetailEdit(link: YouTubeLink): void {
		returnToDetailAfterEdit = link;
		detailModalOpen = false;
		editingLink = link;
		editModalOpen = true;
	}

	function handleDetailDelete(albumId: string): void {
		links = links.filter((l) => l.album_id !== albumId);
		detailLink = null;
	}

	function handleDetailClose(): void {
		detailLink = null;
	}

	function handleEditModalSave(link: YouTubeLink): void {
		if (editingLink) {
			links = links.map((l) => (l.album_id === link.album_id ? link : l));
		} else {
			links = [link, ...links];
		}
		if (returnToDetailAfterEdit) {
			const updated = links.find((l) => l.album_id === link.album_id);
			if (updated) {
				detailLink = updated;
				detailModalOpen = true;
			}
			returnToDetailAfterEdit = null;
		}
		editingLink = null;
	}

	function handleEditModalClose(): void {
		if (returnToDetailAfterEdit) {
			const current = links.find((l) => l.album_id === returnToDetailAfterEdit!.album_id);
			if (current) {
				detailLink = current;
				detailModalOpen = true;
			}
			returnToDetailAfterEdit = null;
		}
		editingLink = null;
	}

	onMount(() => {
		fetchLinks();
	});
</script>

<div class="container mx-auto p-6">
	<div class="flex items-center gap-3 mb-6">
		<YouTubeIcon class="h-8 w-8 text-red-500" />
		<h1 class="text-2xl font-bold">YouTube Links</h1>
		<span class="badge badge-neutral">{links.length}</span>
	</div>

	{#if loading}
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
			{#each Array(12) as _}
				<div class="card bg-base-100 shadow-sm animate-pulse">
					<div class="aspect-square bg-base-300"></div>
					<div class="card-body p-3">
						<div class="h-4 bg-base-300 rounded w-3/4"></div>
						<div class="h-3 bg-base-300 rounded w-1/2 mt-1"></div>
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
			<button
				class="card bg-base-100 w-full shadow-sm border-2 border-dashed border-base-content/20 hover:border-accent transition-colors cursor-pointer flex items-center justify-center aspect-square"
				onclick={openAddModal}
			>
				<div class="flex flex-col items-center gap-2 opacity-60">
					<svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
						<path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
					</svg>
					<span class="text-sm font-medium">Add Link</span>
				</div>
			</button>

			{#each links as link (link.album_id)}
				<div
					class="card bg-base-100 w-full shadow-sm group relative cursor-pointer transition-transform hover:scale-105 hover:shadow-lg active:scale-95"
					onclick={() => openDetail(link)}
					onkeydown={(e) => e.key === 'Enter' && openDetail(link)}
					role="button"
					tabindex="0"
				>
					<figure class="aspect-square overflow-hidden relative">
						<AlbumImage
							mbid={link.album_id}
							customUrl={link.cover_url}
							alt={link.album_name}
							size="full"
							rounded="none"
							className="w-full h-full"
						/>
						<div class="absolute top-2 left-2">
							<div class="badge badge-sm gap-1" style="background-color: #FF0000; color: white; border: none;">
								<YouTubeIcon class="h-3 w-3" />
							</div>
						</div>
						{#if link.track_count > 0}
							<div class="absolute top-2 right-2">
								<div class="badge badge-sm badge-accent">{link.track_count} tracks</div>
							</div>
						{/if}
					</figure>

					<div class="card-body p-3">
						<h2 class="card-title text-sm line-clamp-2 min-h-[2.5rem]">{link.album_name}</h2>
						<p class="text-xs opacity-70 line-clamp-1">{link.artist_name}</p>
					</div>
				</div>
			{/each}
		</div>

		{#if links.length === 0}
			<div class="card bg-base-200 mt-4">
				<div class="card-body items-center text-center">
					<YouTubeIcon class="h-12 w-12 opacity-20" />
					<p class="text-lg opacity-60">No saved YouTube links</p>
					<p class="text-sm opacity-40">Generate links from album pages or add them manually.</p>
				</div>
			</div>
		{/if}
	{/if}
</div>

<YouTubeDetailModal
	bind:open={detailModalOpen}
	link={detailLink}
	onclose={handleDetailClose}
	onedit={handleDetailEdit}
	ondelete={handleDetailDelete}
/>

<YouTubeLinkModal
	bind:open={editModalOpen}
	editLink={editingLink}
	onclose={handleEditModalClose}
	onsave={handleEditModalSave}
/>
