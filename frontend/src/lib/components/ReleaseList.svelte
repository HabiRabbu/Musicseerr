<script lang="ts">
	import { albumHref } from '$lib/utils/entityRoutes';
	import { ChevronDown, Download } from 'lucide-svelte';
	import { colors } from '$lib/colors';
	import { libraryStore } from '$lib/stores/library';
	import AlbumImage from './AlbumImage.svelte';
	import LibraryBadge from './LibraryBadge.svelte';

	interface Release {
		id: string;
		title: string;
		year?: number | null;
		in_library?: boolean;
		requested?: boolean;
	}

	interface RemoveResult {
		artist_removed: boolean;
		artist_name?: string | null;
	}

	interface Props {
		title: string;
		releases: Release[];
		collapsed?: boolean;
		requestingIds: Set<string>;
		showLoadingIndicator?: boolean;
		artistName?: string;
		onRequest: (id: string, title?: string) => void;
		onToggleCollapse: () => void;
		onRemoved?: ((result: RemoveResult) => void) | undefined;
	}

	let {
		title,
		releases = $bindable(),
		collapsed = false,
		requestingIds,
		showLoadingIndicator = false,
		artistName = 'Unknown',
		onRequest,
		onToggleCollapse,
		onRemoved = undefined
	}: Props = $props();

	function handleDeleted(rg: Release, result: RemoveResult) {
		rg.in_library = false;
		rg.requested = false;
		releases = releases;
		onRemoved?.(result);
	}
</script>

<div class="mb-6">
	<div class="bg-base-300 rounded-t-box">
		<button
			class="w-full flex items-center justify-between px-4 py-3 hover:bg-base-content/5 transition-colors rounded-t-box"
			onclick={onToggleCollapse}
		>
			<span class="text-xl sm:text-2xl font-bold">{title} ({releases.length})</span>
			<ChevronDown
				class="h-6 w-6 transition-transform duration-200 {collapsed ? '' : 'rotate-180'}"
			/>
		</button>
	</div>
	{#if !collapsed}
		<div class="border border-base-300 border-t-0 rounded-b-box bg-base-200/30">
			<div class="list" role="list">
				{#each releases as rg (rg.id)}
					<div class="list-row group hover:bg-base-200 transition-colors p-0" role="listitem">
						<a
							href={albumHref(rg.id)}
							class="flex items-center gap-2 sm:gap-3 flex-1 p-2 sm:p-3 cursor-pointer text-left min-w-0"
						>
							<AlbumImage
								mbid={rg.id}
								alt="{rg.title} cover"
								size="sm"
								rounded="lg"
								className="w-12 h-12 sm:w-16 sm:h-16"
							/>
							<div class="list-col-grow min-w-0">
								<div class="font-semibold text-sm sm:text-base truncate">{rg.title}</div>
								<div class="text-xs sm:text-sm text-base-content/60">
									{#if rg.year}{rg.year}{/if}
								</div>
							</div>
						</a>
						<div class="flex items-center shrink-0 ml-auto mr-3 sm:mr-4">
							{#if libraryStore.isInLibrary(rg.id) || rg.in_library}
								<LibraryBadge
									status="library"
									musicbrainzId={rg.id}
									albumTitle={rg.title}
									{artistName}
									size="lg"
									ondeleted={(result) => handleDeleted(rg, result)}
								/>
							{:else if !libraryStore.isInLibrary(rg.id) && (rg.requested || libraryStore.isRequested(rg.id))}
								<LibraryBadge
									status="requested"
									musicbrainzId={rg.id}
									albumTitle={rg.title}
									{artistName}
									size="lg"
									ondeleted={(result) => handleDeleted(rg, result)}
								/>
							{:else}
								<button
									class="w-8 h-8 sm:w-10 sm:h-10 rounded-full opacity-100 lg:opacity-0 lg:group-hover:opacity-100 transition-opacity duration-200 border-none flex items-center justify-center shadow-sm"
									style="background-color: {colors.accent};"
									onclick={(e) => {
										e.stopPropagation();
										onRequest(rg.id, rg.title);
									}}
									disabled={requestingIds.has(rg.id)}
									aria-label="Request {title.toLowerCase().slice(0, -1)}"
								>
									{#if requestingIds.has(rg.id)}
										<span
											class="loading loading-spinner loading-xs"
											style="color: {colors.secondary};"
										></span>
									{:else}
										<Download
											class="h-4 w-4 sm:h-5 sm:w-5"
											color={colors.secondary}
											strokeWidth={2.5}
										/>
									{/if}
								</button>
							{/if}
						</div>
					</div>
				{/each}
			</div>
			{#if showLoadingIndicator}
				<div class="flex items-center justify-center gap-2 p-3">
					<span class="loading loading-spinner loading-sm" style="color: {colors.accent};"></span>
				</div>
			{/if}
		</div>
	{/if}
</div>
