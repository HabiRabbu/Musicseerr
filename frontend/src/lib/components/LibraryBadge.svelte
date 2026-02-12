<script lang="ts">
	import { colors } from '$lib/colors';
	import { STATUS_COLORS } from '$lib/constants';
	import DeleteAlbumModal from './DeleteAlbumModal.svelte';
	import ArtistRemovedModal from './ArtistRemovedModal.svelte';

	interface Props {
		status: 'library' | 'requested';
		musicbrainzId: string;
		albumTitle: string;
		artistName: string;
		size?: 'sm' | 'md' | 'lg';
		positioning?: string;
		ondeleted?: (result: { artist_removed: boolean; artist_name?: string | null }) => void;
	}

	let {
		status,
		musicbrainzId,
		albumTitle,
		artistName,
		size = 'md',
		positioning = '',
		ondeleted
	}: Props = $props();

	let showDeleteModal = $state(false);
	let showArtistRemovedModal = $state(false);
	let removedArtistName = $state('');

	const sizeClasses = $derived({
		sm: { button: 'p-0.5', icon: 'w-2.5 h-2.5', strokeWidth: status === 'library' ? '3' : '2' },
		md: { button: 'p-1.5', icon: 'h-4 w-4', strokeWidth: status === 'library' ? '3' : '2' },
		lg: { button: 'p-0', icon: 'h-4 w-4 sm:h-5 sm:w-5', strokeWidth: status === 'library' ? '3' : '2' }
	}[size]);

	const lgButtonClass = $derived(size === 'lg' ? 'w-8 h-8 sm:w-10 sm:h-10 flex items-center justify-center' : '');
	const bgColor = $derived(status === 'library' ? colors.accent : STATUS_COLORS.REQUESTED);

	function handleClick(e: Event) {
		e.stopPropagation();
		e.preventDefault();
		showDeleteModal = true;
	}

	function handleDeleted(result: { artist_removed: boolean; artist_name?: string | null }) {
		showDeleteModal = false;
		if (result.artist_removed && result.artist_name) {
			removedArtistName = result.artist_name;
			showArtistRemovedModal = true;
		}
		ondeleted?.(result);
	}
</script>

<button
	class="{positioning} rounded-full shadow-sm transition-colors duration-200 group/badge {sizeClasses.button} {lgButtonClass}"
	style="background-color: {bgColor};"
	onclick={handleClick}
	onmouseenter={(e) => { e.currentTarget.style.backgroundColor = '#ef4444'; }}
	onmouseleave={(e) => { e.currentTarget.style.backgroundColor = bgColor; }}
	aria-label={status === 'library' ? 'Remove from library' : 'Remove request'}
>
	{#if status === 'library'}
		<svg xmlns="http://www.w3.org/2000/svg" class="{sizeClasses.icon} group-hover/badge:hidden" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width={sizeClasses.strokeWidth}>
			<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
		</svg>
	{:else}
		<svg xmlns="http://www.w3.org/2000/svg" class="{sizeClasses.icon} group-hover/badge:hidden" fill="none" viewBox="0 0 24 24" stroke={colors.secondary} stroke-width={sizeClasses.strokeWidth}>
			<path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
		</svg>
	{/if}
	<svg xmlns="http://www.w3.org/2000/svg" class="{sizeClasses.icon} hidden group-hover/badge:block" fill="none" viewBox="0 0 24 24" stroke="white" stroke-width="2">
		<path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
	</svg>
</button>

{#if showDeleteModal}
	<DeleteAlbumModal
		{albumTitle}
		{artistName}
		musicbrainzId={musicbrainzId}
		ondeleted={handleDeleted}
		onclose={() => { showDeleteModal = false; }}
	/>
{/if}

{#if showArtistRemovedModal}
	<ArtistRemovedModal
		artistName={removedArtistName}
		onclose={() => { showArtistRemovedModal = false; }}
	/>
{/if}
