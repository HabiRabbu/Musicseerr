<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy, tick } from 'svelte';
	import { SvelteMap } from 'svelte/reactivity';

	interface Props {
		letters: string[];
		sectionIdPrefix?: string;
		onBeforeJump?: (letter: string) => void | Promise<void>;
	}

	let { letters, sectionIdPrefix = 'letter-', onBeforeJump }: Props = $props();

	const ALL_LETTERS = [...'ABCDEFGHIJKLMNOPQRSTUVWXYZ', '#'];

	let activeLetter = $state('');
	let observer: IntersectionObserver | null = null;
	let sectionRatios = new SvelteMap<string, number>();
	let mobileNavEl: HTMLElement | null = $state(null);

	const letterSet = $derived(new Set(letters));

	function getFallbackActiveLetter(): string {
		if (!browser || letters.length === 0) return '';

		const offset = 160;
		let fallback = letters[0];

		for (const letter of letters) {
			const el = document.getElementById(`${sectionIdPrefix}${letter}`);
			if (!el) continue;
			if (el.getBoundingClientRect().top - offset <= 0) {
				fallback = letter;
			} else {
				break;
			}
		}

		return fallback;
	}

	function recalculateActive() {
		const candidates = letters
			.map((l) => ({ letter: l, ratio: sectionRatios.get(l) ?? 0 }))
			.filter((c) => c.ratio > 0);

		if (candidates.length > 0) {
			candidates.sort((a, b) => b.ratio - a.ratio);
			activeLetter = candidates[0].letter;
		} else {
			activeLetter = getFallbackActiveLetter();
		}
	}

	function setupObserver() {
		if (!browser) return;

		observer?.disconnect();
		observer = null;

		if (letters.length === 0) {
			activeLetter = '';
			return;
		}

		observer = new IntersectionObserver(
			(entries) => {
				for (const entry of entries) {
					const id = (entry.target as HTMLElement).id;
					const letter = id.replace(sectionIdPrefix, '');
					sectionRatios.set(letter, entry.isIntersecting ? entry.intersectionRatio : 0);
				}
				recalculateActive();
			},
			{ rootMargin: '-10% 0px -60% 0px', threshold: [0, 0.1, 0.25, 0.5, 0.75, 1] }
		);

		for (const letter of letters) {
			const el = document.getElementById(`${sectionIdPrefix}${letter}`);
			if (el) observer.observe(el);
		}

		activeLetter = getFallbackActiveLetter();
	}

	async function jumpTo(letter: string) {
		if (!letterSet.has(letter)) return;

		if (onBeforeJump) {
			await onBeforeJump(letter);
			await tick();
		}

		const el = document.getElementById(`${sectionIdPrefix}${letter}`);
		if (!el) return;
		el.scrollIntoView({ behavior: 'smooth', block: 'start' });
		activeLetter = letter;
	}

	$effect(() => {
		// eslint-disable-next-line @typescript-eslint/no-unused-expressions
		sectionIdPrefix; // Track reactivity
		// eslint-disable-next-line @typescript-eslint/no-unused-expressions
		letters; // Track reactivity
		if (!browser) return;

		const timeoutId = window.setTimeout(setupObserver, 50);
		return () => window.clearTimeout(timeoutId);
	});

	$effect(() => {
		const _active = activeLetter;
		if (!browser || !mobileNavEl || !_active) return;
		const activeBtn = mobileNavEl.querySelector('[aria-current="true"]');
		if (activeBtn) {
			activeBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
		}
	});

	onDestroy(() => {
		observer?.disconnect();
		observer = null;
	});

	const show = $derived(letters.length > 1);
</script>

{#if show}
	<nav
		class="hidden xl:flex fixed right-2 top-1/2 -translate-y-1/2 z-30
			flex-col items-center gap-0.5 rounded-full bg-base-200/80 backdrop-blur-sm
			py-2 px-1 shadow-lg border border-base-content/5"
		aria-label="Jump to letter"
	>
		{#each ALL_LETTERS as letter (letter)}
			{@const available = letterSet.has(letter)}
			{@const active = activeLetter === letter}
			<button
				onclick={() => jumpTo(letter)}
				disabled={!available}
				class="w-6 h-5 flex items-center justify-center text-[11px] font-medium rounded-sm
					transition-colors duration-100
					{active
					? 'text-primary-content bg-primary font-bold'
					: available
						? 'text-base-content/60 hover:text-primary hover:bg-base-300/60'
						: 'text-base-content/15 cursor-default'}"
				aria-label="Jump to {letter === '#' ? 'numbers and symbols' : letter}"
				aria-current={active ? 'true' : undefined}
			>
				{letter}
			</button>
		{/each}
	</nav>

	<nav
		bind:this={mobileNavEl}
		class="xl:hidden sticky top-0 z-30 -mx-4 md:-mx-6 lg:-mx-8 px-2
			flex items-center gap-1 overflow-x-auto scrollbar-none
			bg-base-100/90 backdrop-blur-md border-b border-base-content/5 py-2"
		aria-label="Jump to letter"
	>
		{#each ALL_LETTERS as letter (letter)}
			{@const available = letterSet.has(letter)}
			{@const active = activeLetter === letter}
			<button
				onclick={() => jumpTo(letter)}
				disabled={!available}
				class="shrink-0 min-w-7 h-7 flex items-center justify-center text-xs font-medium
					rounded-md transition-colors duration-100
					{active
					? 'text-primary-content bg-primary font-bold'
					: available
						? 'text-base-content/60 hover:text-primary hover:bg-base-300/60'
						: 'text-base-content/15 cursor-default'}"
				aria-label="Jump to {letter === '#' ? 'numbers and symbols' : letter}"
				aria-current={active ? 'true' : undefined}
			>
				{letter}
			</button>
		{/each}
	</nav>
{/if}

<style>
	.scrollbar-none {
		-ms-overflow-style: none;
		scrollbar-width: none;
	}
	.scrollbar-none::-webkit-scrollbar {
		display: none;
	}
</style>
