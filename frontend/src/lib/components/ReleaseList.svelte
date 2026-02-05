<script lang="ts">
	import { goto } from '$app/navigation';
	import { colors } from '$lib/colors';
	import { STATUS_COLORS } from '$lib/constants';
	import AlbumImage from './AlbumImage.svelte';

	interface Release {
		id: string;
		title: string;
		year?: number | null;
		in_library?: boolean;
		requested?: boolean;
	}

	export let title: string;
	export let releases: Release[];
	export let collapsed: boolean = false;
	export let requestingIds: Set<string>;
	export let showLoadingIndicator: boolean = false;
	export let onRequest: (id: string, title?: string) => void;
	export let onToggleCollapse: () => void;

	function goToAlbum(albumId: string) {
		goto(`/album/${albumId}`);
	}
</script>

<div class="mb-6">
	<div class="bg-base-300 rounded-t-box">
		<button
			class="w-full flex items-center justify-between px-4 py-3 hover:bg-base-content/5 transition-colors rounded-t-box"
			on:click={onToggleCollapse}
		>
			<span class="text-xl sm:text-2xl font-bold">{title} ({releases.length})</span>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				class="h-6 w-6 transition-transform duration-200 {collapsed ? '' : 'rotate-180'}"
				fill="none"
				viewBox="0 0 24 24"
				stroke="currentColor"
			>
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
			</svg>
		</button>
	</div>
	{#if !collapsed}
		<div class="border border-base-300 border-t-0 rounded-b-box bg-base-200/30">
			<div class="list" role="list">
				{#each releases as rg}
					<div class="list-row group hover:bg-base-200 transition-colors p-0" role="listitem">
						<button
							class="flex items-center gap-2 sm:gap-3 flex-1 p-2 sm:p-3 cursor-pointer text-left min-w-0"
							on:click={() => goToAlbum(rg.id)}
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
						</button>
						<div class="flex items-center flex-shrink-0 ml-auto mr-3 sm:mr-4">
							{#if rg.in_library}
								<div
									class="w-8 h-8 sm:w-10 sm:h-10 rounded-full shadow-sm flex items-center justify-center"
									style="background-color: {colors.accent};"
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										class="h-4 w-4 sm:h-5 sm:w-5"
										fill="none"
										viewBox="0 0 24 24"
										stroke={colors.secondary}
										stroke-width="3"
									>
										<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
									</svg>
								</div>
							{:else if rg.requested}
								<div
									class="w-8 h-8 sm:w-10 sm:h-10 rounded-full shadow-sm flex items-center justify-center"
									style="background-color: {STATUS_COLORS.REQUESTED};"
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										class="h-4 w-4 sm:h-5 sm:w-5"
										fill="none"
										viewBox="0 0 24 24"
										stroke={colors.secondary}
										stroke-width="2"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
										/>
									</svg>
								</div>
							{:else}
								<button
									class="w-8 h-8 sm:w-10 sm:h-10 rounded-full opacity-100 lg:opacity-0 lg:group-hover:opacity-100 transition-opacity duration-200 border-none flex items-center justify-center shadow-sm"
									style="background-color: {colors.accent};"
									on:click={(e) => {
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
										<svg
											xmlns="http://www.w3.org/2000/svg"
											class="h-4 w-4 sm:h-5 sm:w-5"
											fill="none"
											viewBox="0 0 24 24"
											stroke={colors.secondary}
											stroke-width="2.5"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
											/>
										</svg>
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
