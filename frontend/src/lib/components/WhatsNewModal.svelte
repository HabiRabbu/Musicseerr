<script lang="ts">
	import { goto } from '$app/navigation';
	import { isWhatsNewDismissed, dismissWhatsNew } from '$lib/stores/version.svelte';
	import { renderMarkdown } from '$lib/utils/markdown';
	import { X, Sparkles, ExternalLink } from 'lucide-svelte';

	interface Props {
		currentVersion: string | null;
		buildDate: string | null;
		releaseTag: string | null;
		releaseBody: string | null;
		releaseName: string | null;
	}
	let { currentVersion, buildDate, releaseTag, releaseBody, releaseName }: Props = $props();

	let dialogEl: HTMLDialogElement | undefined = $state();
	let renderedBody = $state('');

	const isDev = $derived(currentVersion === 'dev' || currentVersion === 'hosting-local');

	// In dev: key dismissal to build_date so modal shows once per rebuild, not every refresh
	// In prod: key to release tag so modal shows once per new version
	const dismissKey = $derived(isDev ? (buildDate ?? 'dev') : (releaseTag ?? currentVersion));

	const shouldShow = $derived(
		currentVersion !== null &&
			dismissKey !== null &&
			releaseBody !== null &&
			releaseBody.trim().length > 0 &&
			!isWhatsNewDismissed(dismissKey)
	);

	$effect(() => {
		if (releaseBody && releaseBody.trim()) {
			renderMarkdown(releaseBody)
				.then((html) => {
					renderedBody = html;
				})
				.catch(() => {
					renderedBody = '';
				});
		}
	});

	$effect(() => {
		if (shouldShow && dialogEl && !dialogEl.open) {
			dialogEl.showModal();
		}
	});

	function handleDismiss() {
		if (dismissKey) {
			dismissWhatsNew(dismissKey);
		}
		dialogEl?.close();
	}

	function onDialogClose() {
		if (dismissKey) {
			dismissWhatsNew(dismissKey);
		}
	}

	function handleViewChangelog() {
		handleDismiss();
		goto('/settings?tab=about');
	}
</script>

<dialog
	bind:this={dialogEl}
	class="modal whats-new-modal"
	onclose={onDialogClose}
	aria-labelledby="whats-new-title"
>
	<div
		class="modal-box whats-new-box max-w-2xl animate-fade-in-up border border-accent/10 p-5 sm:p-8"
	>
		<button
			class="whats-new-close absolute right-2 top-2 flex h-11 w-11 items-center justify-center rounded-lg text-base-content/60 transition-all duration-200 hover:bg-base-content/8 hover:text-base-content/80"
			onclick={handleDismiss}
			aria-label="Close"
		>
			<X class="h-3.5 w-3.5" />
		</button>

		<div class="mb-6 flex items-center gap-4">
			<div
				class="whats-new-icon-wrap relative flex h-11 w-11 items-center justify-center rounded-xl bg-accent/10 animate-glow-pulse"
			>
				<Sparkles class="text-accent h-5 w-5" />
			</div>
			<div>
				<h3 id="whats-new-title" class="text-xl font-bold tracking-tight">What's New</h3>
				{#if currentVersion}
					<p class="text-primary/70 mt-0.5 text-xs font-medium tracking-wide uppercase">
						{currentVersion}
					</p>
				{/if}
			</div>
		</div>

		<div class="divider my-0 opacity-10"></div>

		{#if releaseName}
			<p class="text-base-content mt-4 mb-4 text-sm font-semibold border-l-2 border-accent/50 pl-3">
				{releaseName}
			</p>
		{/if}

		{#if renderedBody}
			<div
				class="whats-new-content release-notes-prose prose prose-sm max-h-[55vh] max-w-none text-base-content/75 overflow-y-auto rounded-lg border border-base-content/5 bg-base-100/50 p-4 {releaseName
					? ''
					: 'mt-4'}"
			>
				<!-- eslint-disable-next-line svelte/no-at-html-tags -- sanitized via DOMPurify -->
				{@html renderedBody}
			</div>
		{:else}
			<div class="flex justify-center py-12">
				<span class="loading loading-spinner loading-md text-accent/60"></span>
			</div>
		{/if}

		<div class="modal-action mt-6 gap-3">
			<button
				class="btn btn-ghost btn-sm text-base-content/60 hover:text-base-content/80 gap-1.5"
				onclick={handleViewChangelog}
			>
				View full changelog
				<ExternalLink class="h-3 w-3" />
			</button>
			<button class="btn btn-accent btn-sm px-6 shadow-sm shadow-accent/15" onclick={handleDismiss}
				>Got it</button
			>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button>close</button>
	</form>
</dialog>

<style>
	.whats-new-box {
		background:
			radial-gradient(
				ellipse at top left,
				oklch(from var(--color-accent) l c h / 0.04),
				transparent 50%
			),
			radial-gradient(
				ellipse at bottom right,
				oklch(from var(--color-primary) l c h / 0.03),
				transparent 50%
			),
			var(--color-base-200);
		box-shadow:
			0 0 0 1px oklch(from var(--color-accent) l c h / 0.06),
			0 24px 80px -12px rgba(0, 0, 0, 0.6);
	}

	.whats-new-content {
		scrollbar-width: thin;
		scrollbar-color: oklch(from var(--color-accent) l c h / 0.15) transparent;
	}
</style>
