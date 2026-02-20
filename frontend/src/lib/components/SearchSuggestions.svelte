<script lang="ts">
	import type { SuggestResult } from '$lib/types';
	import { API } from '$lib/constants';

	interface Props {
		query: string;
		onSearch: () => void;
		onSelect: (result: SuggestResult) => void;
		placeholder?: string;
		inputClass?: string;
		autofocus?: boolean;
		id?: string;
	}

	let {
		query = $bindable(),
		onSearch,
		onSelect,
		placeholder = 'Search...',
		inputClass = '',
		autofocus = false,
		id = 'suggest'
	}: Props = $props();

	const listboxId = $derived(`${id}-listbox`);

	let suggestions = $state<SuggestResult[]>([]);
	let loading = $state(false);
	let showDropdown = $state(false);
	let debounceTimeout: ReturnType<typeof setTimeout>;
	let abortController: AbortController | null = null;
	let rootRef: HTMLDivElement;
	let fetchGeneration = 0;

	function coverUrl(result: SuggestResult): string {
		return result.type === 'artist'
			? `/api/covers/artist/${result.musicbrainz_id}?size=250`
			: `/api/covers/release-group/${result.musicbrainz_id}?size=250`;
	}

	function handleInput() {
		clearTimeout(debounceTimeout);
		abortController?.abort();
		abortController = null;

		if (query.trim().length < 2) {
			suggestions = [];
			showDropdown = false;
			loading = false;
			return;
		}

		loading = true;
		showDropdown = true;

		debounceTimeout = setTimeout(async () => {
			abortController = new AbortController();
			const generation = ++fetchGeneration;

			try {
				const res = await fetch(API.search.suggest(query.trim(), 5), {
					signal: abortController.signal
				});
				if (generation !== fetchGeneration) return;
				if (res.ok) {
					const data: { results?: SuggestResult[] } = await res.json();
					suggestions = data.results ?? [];
					showDropdown = suggestions.length > 0 || loading;
				} else {
					suggestions = [];
					showDropdown = false;
				}
			} catch (e) {
				if (e instanceof DOMException && e.name === 'AbortError') return;
				if (generation !== fetchGeneration) return;
				suggestions = [];
				showDropdown = false;
			} finally {
				if (generation === fetchGeneration) {
					loading = false;
				}
			}
		}, 400);
	}

	function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		showDropdown = false;
		suggestions = [];
		onSearch();
	}

	function handleSelect(result: SuggestResult) {
		showDropdown = false;
		suggestions = [];
		onSelect(result);
	}

	function handleViewAll() {
		showDropdown = false;
		suggestions = [];
		onSearch();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			if (showDropdown) {
				e.preventDefault();
				e.stopPropagation();
				showDropdown = false;
				suggestions = [];
			}
		}
	}

	function handleFocusOut(e: FocusEvent) {
		if (rootRef && !rootRef.contains(e.relatedTarget as Node)) {
			showDropdown = false;
		}
	}

	$effect(() => {
		if (!showDropdown) return;
		const handlePointerDown = (e: PointerEvent) => {
			if (rootRef && !rootRef.contains(e.target as Node)) {
				showDropdown = false;
			}
		};
		document.addEventListener('pointerdown', handlePointerDown);
		return () => document.removeEventListener('pointerdown', handlePointerDown);
	});

	$effect(() => {
		return () => {
			clearTimeout(debounceTimeout);
			abortController?.abort();
		};
	});
</script>

<div
	bind:this={rootRef}
	class="relative w-full"
	role="combobox"
	aria-expanded={showDropdown}
	aria-haspopup="listbox"
	aria-controls={listboxId}
	onfocusout={handleFocusOut}
>
	<form onsubmit={handleSubmit}>
		<label class="input input-bordered flex items-center gap-2 w-full {inputClass}">
			<svg class="h-[1em] opacity-50" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
				<g
					stroke-linejoin="round"
					stroke-linecap="round"
					stroke-width="2.5"
					fill="none"
					stroke="currentColor"
				>
					<circle cx="11" cy="11" r="8"></circle>
					<path d="m21 21-4.3-4.3"></path>
				</g>
			</svg>
			<input
				type="search"
				{placeholder}
				bind:value={query}
				oninput={handleInput}
				onkeydown={handleKeydown}
				class="grow"
				autocomplete="off"
				aria-autocomplete="list"
				aria-controls={listboxId}
				{autofocus}
			/>
			{#if loading}
				<span class="loading loading-spinner loading-sm"></span>
			{/if}
		</label>
	</form>

	{#if showDropdown && (suggestions.length > 0 || loading)}
		<ul
			role="listbox"
			id={listboxId}
			class="absolute top-full left-0 right-0 z-[60] mt-1 rounded-box bg-base-200 shadow-xl"
		>
			{#each suggestions as result (result.musicbrainz_id)}
				<li
					role="option"
					aria-selected="false"
					class="flex items-center gap-3 p-3 cursor-pointer hover:bg-base-300 transition-colors"
					onclick={() => handleSelect(result)}
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') handleSelect(result);
					}}
					tabindex="-1"
				>
					<div class="avatar avatar-placeholder">
						<div class="w-10 h-10 rounded bg-base-300">
							<img
								src={coverUrl(result)}
								alt={result.title}
								onerror={(e: Event) => {
									const target = e.currentTarget as HTMLImageElement;
									target.style.display = 'none';
								}}
							/>
						</div>
					</div>
					<div class="flex-1 min-w-0">
						<div class="font-medium truncate">{result.title}</div>
						<div class="text-sm opacity-70 truncate">
							{#if result.type === 'album' && result.artist}
								{result.artist}
							{:else if result.type === 'artist'}
								Artist
							{/if}
							{#if result.year}
								&middot; {result.year}
							{/if}
							{#if result.disambiguation}
								({result.disambiguation})
							{/if}
						</div>
					</div>
					<div class="flex gap-1">
						<span class="badge badge-sm badge-ghost">
							{result.type === 'artist' ? 'Artist' : 'Album'}
						</span>
						{#if result.in_library}
							<span class="badge badge-sm badge-success">In Library</span>
						{/if}
						{#if result.requested}
							<span class="badge badge-sm badge-warning">Requested</span>
						{/if}
					</div>
				</li>
			{/each}

			{#if suggestions.length > 0}
				<li class="p-3 text-center border-t border-base-300">
					<button class="text-sm link link-hover opacity-70" onclick={handleViewAll}>
						View all results
					</button>
				</li>
			{/if}

			{#if loading && suggestions.length === 0}
				<li class="p-4 flex justify-center">
					<span class="loading loading-spinner loading-md"></span>
				</li>
			{/if}
		</ul>
	{/if}
</div>
