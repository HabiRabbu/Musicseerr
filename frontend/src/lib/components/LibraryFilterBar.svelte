<script lang="ts">
	import { Search, X, ArrowDown } from 'lucide-svelte';

	interface Props {
		searchQuery: string;
		onSearchInput?: () => void;
		placeholder?: string;
		ariaLabel?: string;
		sortOptions?: { value: string; label: string }[];
		sortBy?: string;
		onSortChange?: (value: string) => void;
		sortOrder?: string;
		onToggleSortOrder?: () => void;
		ascValue?: string;
		genres?: string[];
		selectedGenre?: string;
		onGenreChange?: (value: string) => void;
		resultCount?: number | null;
		loading?: boolean;
	}

	let {
		searchQuery = $bindable(),
		onSearchInput,
		placeholder = 'Search albums...',
		ariaLabel = 'Search albums',
		sortOptions,
		sortBy,
		onSortChange,
		sortOrder,
		onToggleSortOrder,
		ascValue = 'asc',
		genres,
		selectedGenre,
		onGenreChange,
		resultCount,
		loading = false
	}: Props = $props();

	let isSearching = $derived(searchQuery.trim().length > 0);
	let hasSortControls = $derived(sortOptions && sortOptions.length > 0);
	let hasGenreFilter = $derived(genres && genres.length > 0);
	let hasSecondRow = $derived(hasSortControls || hasGenreFilter || resultCount != null);
	let isAscending = $derived(sortOrder === ascValue);

	function clearSearch(): void {
		searchQuery = '';
		onSearchInput?.();
	}

	function handleSortSelect(e: Event): void {
		const value = (e.target as HTMLSelectElement).value;
		onSortChange?.(value);
	}

	function handleGenreSelect(e: Event): void {
		const value = (e.target as HTMLSelectElement).value;
		onGenreChange?.(value);
	}
</script>

<div class="mb-6">
	<div class="relative group">
		<Search
			class="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-base-content/40
			group-focus-within:text-primary transition-colors duration-200 pointer-events-none"
		/>
		<input
			type="text"
			{placeholder}
			class="input input-md w-full rounded-full pl-11 pr-12
				bg-base-200/50 border-base-content/10
				focus:border-primary focus:bg-base-200/80
				transition-all duration-200
				placeholder:text-base-content/30"
			bind:value={searchQuery}
			oninput={() => onSearchInput?.()}
			aria-label={ariaLabel}
		/>
		{#if isSearching}
			<button
				type="button"
				class="absolute right-3 top-1/2 -translate-y-1/2 btn btn-sm btn-ghost btn-circle"
				onclick={clearSearch}
				aria-label="Clear search"
			>
				<X class="h-4 w-4" />
			</button>
		{/if}
	</div>

	{#if hasSecondRow}
		<div class="flex flex-wrap items-center gap-3 mt-3">
			{#if hasSortControls}
				<select
					class="select select-sm rounded-full bg-base-200/50 border-base-content/10
						focus:border-primary transition-all duration-200"
					onchange={handleSortSelect}
					aria-label="Sort by"
				>
					{#each sortOptions! as opt (opt.value)}
						<option value={opt.value} selected={sortBy === opt.value}>{opt.label}</option>
					{/each}
				</select>
				<button
					type="button"
					class="btn btn-sm btn-ghost btn-circle"
					onclick={() => onToggleSortOrder?.()}
					aria-label={isAscending ? 'Switch to descending sort' : 'Switch to ascending sort'}
					title={isAscending ? 'Ascending' : 'Descending'}
				>
					<ArrowDown class="h-4 w-4 transition-transform {isAscending ? '' : 'rotate-180'}" />
				</button>
			{/if}

			{#if hasGenreFilter}
				<select
					class="select select-sm rounded-full bg-base-200/50 border-base-content/10
						focus:border-primary transition-all duration-200"
					onchange={handleGenreSelect}
					aria-label="Filter by genre"
				>
					<option value="">All Genres</option>
					{#each genres! as genre (genre)}
						<option value={genre} selected={selectedGenre === genre}>{genre}</option>
					{/each}
				</select>
			{/if}

			{#if resultCount != null && !loading}
				<span class="text-sm text-base-content/50">{resultCount} results</span>
			{/if}
		</div>
	{/if}
</div>
