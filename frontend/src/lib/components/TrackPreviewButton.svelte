<script lang="ts">
	import { Play, Loader2 } from 'lucide-svelte';
	import { API } from '$lib/constants';
	import { api } from '$lib/api/client';
	import { launchYouTubePlayback } from '$lib/player/launchYouTubePlayback';
	import { onDestroy } from 'svelte';

	interface Props {
		artist: string;
		track: string;
		ytConfigured: boolean;
		initialCached?: boolean | null;
		size?: 'sm' | 'md';
		albumId?: string;
		coverUrl?: string | null;
		artistId?: string;
	}

	let {
		artist,
		track,
		ytConfigured = false,
		initialCached = null,
		size = 'sm',
		albumId = '',
		coverUrl = null,
		artistId
	}: Props = $props();

	let searching = $state(false);
	let cached = $state<boolean | null>(null);
	let errorFlash = $state(false);
	let errorTimer: ReturnType<typeof setTimeout> | null = null;

	$effect(() => {
		if (initialCached !== null && initialCached !== undefined) {
			cached = initialCached;
		}
	});

	function cleanup() {
		if (errorTimer) {
			clearTimeout(errorTimer);
			errorTimer = null;
		}
	}

	onDestroy(cleanup);

	const TERMINAL_ERRORS = ['not_found', 'quota_exceeded', 'not_configured'];

	async function doSearch(): Promise<{ success: boolean; terminal: boolean }> {
		const url = API.discoverQueueYoutubeTrackSearch(artist, track);
		let data: { video_id?: string; cached?: boolean; embed_url?: string; error?: string };
		try {
			data = await api.global.get(url);
		} catch {
			return { success: false, terminal: false };
		}
		if (data.error && TERMINAL_ERRORS.includes(data.error)) {
			return { success: false, terminal: true };
		}
		if (data.video_id) {
			cached = data.cached ?? false;
			await launchYouTubePlayback({
				albumId: albumId || `preview-${artist}-${track}`,
				albumName: track,
				artistName: artist,
				videoId: data.video_id,
				coverUrl,
				embedUrl: data.embed_url,
				artistId
			});
			if (!data.cached) {
				cached = true;
			}
			return { success: true, terminal: false };
		}
		return { success: false, terminal: true };
	}

	async function handlePlay(e: MouseEvent) {
		e.stopPropagation();
		e.preventDefault();
		if (searching || !ytConfigured) return;
		searching = true;
		try {
			const result = await doSearch();
			if (result.success) return;
			if (result.terminal) {
				showError();
				return;
			}
			await new Promise((r) => setTimeout(r, 1500));
			const retry = await doSearch();
			if (!retry.success) showError();
		} catch {
			try {
				await new Promise((r) => setTimeout(r, 1500));
				const retry = await doSearch();
				if (!retry.success) showError();
			} catch {
				showError();
			}
		} finally {
			searching = false;
		}
	}

	function showError() {
		errorFlash = true;
		cleanup();
		errorTimer = setTimeout(() => {
			errorFlash = false;
		}, 600);
	}

	const tooltip = $derived(
		!ytConfigured
			? 'Set up YouTube API key in Settings to preview'
			: errorFlash
				? 'Preview failed - tap to retry'
				: cached === true
					? 'Play · cached, no quota used'
					: 'Preview · uses 1 YouTube lookup'
	);

	const btnClasses = $derived.by(() => {
		const base = size === 'sm' ? 'btn btn-circle btn-ghost btn-sm' : 'btn btn-circle btn-ghost';
		if (!ytConfigured) return `${base} text-base-content/20 cursor-not-allowed`;
		if (searching) return `${base} text-primary`;
		if (errorFlash) return `${base} text-error`;
		if (cached === true) return `${base} text-success hover:text-success/80 ring-1 ring-success/30`;
		return `${base} text-base-content/50 hover:text-primary`;
	});

	const iconSize = $derived(size === 'sm' ? 'h-4 w-4' : 'h-5 w-5');
</script>

<div class="tooltip tooltip-top z-50" data-tip={tooltip}>
	<button
		type="button"
		class={btnClasses}
		onclick={handlePlay}
		disabled={searching || !ytConfigured}
	>
		{#if searching}
			<Loader2 class="{iconSize} animate-spin" />
		{:else}
			<Play class="{iconSize} {cached === true ? 'fill-current' : ''}" />
		{/if}
	</button>
</div>
