<script lang="ts">
	import { goto } from '$app/navigation';
	import AlbumImage from './AlbumImage.svelte';
	import DeleteAlbumModal from './DeleteAlbumModal.svelte';
	import ArtistRemovedModal from './ArtistRemovedModal.svelte';
	import type { ActiveRequestItem, RequestHistoryItem } from '$lib/types';

	interface Props {
		item: ActiveRequestItem | RequestHistoryItem;
		mode: 'active' | 'history';
		oncancel?: (mbid: string) => void;
		onretry?: (mbid: string) => void;
		onclear?: (mbid: string) => void;
		onremoved?: () => void;
	}

	let { item, mode, oncancel, onretry, onclear, onremoved }: Props = $props();

	let confirmingCancel = $state(false);
	let showDeleteModal = $state(false);
	let showArtistRemovedModal = $state(false);
	let removedArtistName = $state('');

	function formatRelativeTime(dateStr: string): string {
		const date = new Date(dateStr);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffMin = Math.floor(diffMs / 60000);
		if (diffMin < 1) return 'just now';
		if (diffMin < 60) return `${diffMin}m ago`;
		const diffHr = Math.floor(diffMin / 60);
		if (diffHr < 24) return `${diffHr}h ago`;
		const diffDays = Math.floor(diffHr / 24);
		if (diffDays < 7) return `${diffDays}d ago`;
		return date.toLocaleDateString();
	}

	function formatDate(dateStr: string): string {
		return new Date(dateStr).toLocaleString(undefined, {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
			hour: 'numeric',
			minute: '2-digit'
		});
	}

	function formatSize(bytes: number): string {
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
		return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
	}

	function formatEta(etaStr: string): string {
		const eta = new Date(etaStr);
		const now = new Date();
		const diffMs = eta.getTime() - now.getTime();
		if (diffMs <= 0) return 'any moment';
		const diffMin = Math.floor(diffMs / 60000);
		if (diffMin < 1) return '< 1 min';
		if (diffMin < 60) return `${diffMin} min`;
		const diffHr = Math.floor(diffMin / 60);
		const remainMin = diffMin % 60;
		return remainMin > 0 ? `${diffHr}h ${remainMin}m` : `${diffHr}h`;
	}

	const statusBadge = $derived.by(() => {
		switch (item.status) {
			case 'pending': return { class: 'badge-warning', label: 'Pending' };
			case 'downloading': return { class: 'badge-info', label: 'Downloading' };
			case 'importing': return { class: 'badge-info', label: 'Importing' };
			case 'importFailed': return { class: 'badge-error', label: 'Import Failed' };
			case 'importBlocked': return { class: 'badge-warning', label: 'Import Blocked' };
			case 'incomplete': return { class: 'badge-warning', label: 'Import Incomplete' };
			case 'imported': return { class: 'badge-success', label: 'Imported' };
			case 'failed': return { class: 'badge-error', label: 'Failed' };
			case 'cancelled': return { class: 'badge-ghost', label: 'Cancelled' };
			default: return { class: 'badge-ghost', label: item.status };
		}
	});

	let showStatusDetails = $state(false);
	const isFailedState = $derived(
		item.status === 'importFailed' || item.status === 'importBlocked' || item.status === 'failed'
	);

	function handleAlbumClick() {
		goto(`/album/${item.musicbrainz_id}`);
	}

	function handleArtistClick(e: Event) {
		e.stopPropagation();
		const mbid = 'artist_mbid' in item ? item.artist_mbid : null;
		if (mbid) goto(`/artist/${mbid}`);
	}

	function handleCancelClick(e: Event) {
		e.stopPropagation();
		if (confirmingCancel) {
			oncancel?.(item.musicbrainz_id);
			confirmingCancel = false;
		} else {
			confirmingCancel = true;
			setTimeout(() => { confirmingCancel = false; }, 3000);
		}
	}

	function handleCancelNo(e: Event) {
		e.stopPropagation();
		confirmingCancel = false;
	}

	function handleRetry(e: Event) {
		e.stopPropagation();
		onretry?.(item.musicbrainz_id);
	}

	function handleClear(e: Event) {
		e.stopPropagation();
		onclear?.(item.musicbrainz_id);
	}

	function handleRemoveFromLibrary(e: Event) {
		e.stopPropagation();
		showDeleteModal = true;
	}

	function handleDeleted(result: { artist_removed: boolean; artist_name?: string | null }) {
		showDeleteModal = false;
		if (result.artist_removed && result.artist_name) {
			removedArtistName = result.artist_name;
			showArtistRemovedModal = true;
		}
		onremoved?.();
	}

	const isActive = $derived(mode === 'active');
	const activeItem = $derived(item as ActiveRequestItem);
	const historyItem = $derived(item as RequestHistoryItem);
	const hasStatusMessages = $derived(
		isActive && activeItem.status_messages && activeItem.status_messages.length > 0
	);
</script>

<div
	class="flex flex-col bg-base-200 rounded-box hover:bg-base-300 transition-colors cursor-pointer"
	class:border-error={isFailedState}
	class:border={isFailedState}
>
	<div
		class="flex items-center gap-4 p-4"
		onclick={handleAlbumClick}
		onkeydown={(e) => e.key === 'Enter' && handleAlbumClick()}
		role="button"
		tabindex="0"
	>
		<div class="w-16 h-16 sm:w-20 sm:h-20 flex-shrink-0 rounded-lg overflow-hidden">
			<AlbumImage
				mbid={item.musicbrainz_id}
				customUrl={item.cover_url ?? null}
				alt={item.album_title}
				size="sm"
				rounded="lg"
				className="w-full h-full"
			/>
		</div>

		<div class="flex-1 min-w-0">
			<h3 class="font-semibold text-base-content line-clamp-1">{item.album_title}</h3>
			<button
				class="text-sm text-base-content/70 hover:text-primary transition-colors line-clamp-1 text-left"
				onclick={handleArtistClick}
			>
				{item.artist_name}
			</button>
			<p class="text-xs text-base-content/50 mt-0.5">
				Requested {formatRelativeTime(item.requested_at)}
				{#if item.year}
					<span class="mx-1">•</span>{item.year}
				{/if}
			</p>
		</div>

		<div class="flex flex-col items-end gap-2 flex-shrink-0">
			<span class="badge {statusBadge.class} badge-sm">{statusBadge.label}</span>

			{#if isActive && activeItem.status === 'downloading'}
				<div class="flex flex-col items-end gap-1 w-32 sm:w-48">
					<div class="flex items-center gap-2 w-full">
						<progress
							class="progress progress-info flex-1"
							value={activeItem.progress ?? 0}
							max="100"
						></progress>
						<span class="text-xs text-base-content/70 min-w-[3ch] text-right">
							{activeItem.progress?.toFixed(0) ?? 0}%
						</span>
					</div>
					{#if activeItem.eta}
						<span class="text-xs text-base-content/50">ETA: {formatEta(activeItem.eta)}</span>
					{/if}
					{#if activeItem.size && activeItem.size_remaining != null}
						<span class="text-xs text-base-content/50">
							{formatSize(activeItem.size - (activeItem.size_remaining ?? 0))} / {formatSize(activeItem.size)}
						</span>
					{/if}
				</div>
			{:else if isActive && isFailedState && activeItem.error_message}
				<span class="text-xs text-error max-w-48 text-right line-clamp-1">{activeItem.error_message}</span>
			{:else if !isActive && historyItem.completed_at}
				<span class="text-xs text-base-content/50">{formatDate(historyItem.completed_at)}</span>
			{/if}

			<div class="flex gap-1">
				{#if isActive && hasStatusMessages}
					<button
						class="btn btn-xs btn-ghost"
						onclick={(e) => { e.stopPropagation(); showStatusDetails = !showStatusDetails; }}
						title={showStatusDetails ? 'Hide details' : 'Show details'}
					>
						<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 transition-transform" class:rotate-180={showStatusDetails} fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
						</svg>
					</button>
				{/if}
				{#if isActive}
					{#if confirmingCancel}
						<span class="text-xs text-base-content/70 mr-1 self-center">Cancel?</span>
						<button class="btn btn-xs btn-error" onclick={handleCancelClick}>Yes</button>
						<button class="btn btn-xs btn-ghost" onclick={handleCancelNo}>No</button>
					{:else}
						<button
							class="btn btn-xs btn-ghost btn-error"
							onclick={handleCancelClick}
							title="Cancel download"
						>
							<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
								<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
							</svg>
						</button>
					{/if}
				{:else}
					{#if historyItem.status === 'failed' || historyItem.status === 'cancelled' || historyItem.status === 'incomplete'}
						<button class="btn btn-xs btn-primary" onclick={handleRetry} title="Retry">
							<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
								<path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
							</svg>
						</button>
					{/if}
					{#if historyItem.status === 'imported' && historyItem.in_library}
						<button class="btn btn-xs btn-ghost" onclick={handleRemoveFromLibrary} title="Remove from library">
							<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
								<path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
							</svg>
						</button>
					{/if}
					<button class="btn btn-xs btn-ghost" onclick={handleClear} title="Clear from history">
						<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				{/if}
			</div>
		</div>
	</div>

	{#if showStatusDetails && hasStatusMessages}
		<div class="px-4 pb-4 -mt-1">
			<div class="bg-base-300 rounded-lg p-3 text-xs max-h-48 overflow-y-auto">
				{#each activeItem.status_messages ?? [] as msg}
					{#if msg.title}
						<div class="font-medium text-base-content/80 mt-2 first:mt-0">{msg.title}</div>
					{/if}
					{#each msg.messages as message}
						<div class="text-error/80 ml-4 mt-0.5">• {message}</div>
					{/each}
				{/each}
			</div>
		</div>
	{/if}
</div>

{#if showDeleteModal}
	<DeleteAlbumModal
		albumTitle={item.album_title}
		artistName={item.artist_name}
		musicbrainzId={item.musicbrainz_id}
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
