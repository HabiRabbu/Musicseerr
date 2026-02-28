<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { fade } from 'svelte/transition';
	import RequestCard from '$lib/components/RequestCard.svelte';
	import Pagination from '$lib/components/Pagination.svelte';
	import Toast from '$lib/components/Toast.svelte';
	import type { ActiveRequestItem, RequestHistoryItem } from '$lib/types';
	import { TriangleAlert, CheckCircle, Clock } from 'lucide-svelte';
	import {
		fetchActiveRequests,
		fetchRequestHistory,
		cancelRequest,
		retryRequest,
		clearHistoryItem,
		notifyRequestCountChanged
	} from '$lib/utils/requestsApi';
	import { isAbortError } from '$lib/utils/errorHandling';

	let activeTab = $state<'active' | 'history'>('active');

	let activeItems = $state<ActiveRequestItem[]>([]);
	let activeCount = $state(0);
	let activeLoading = $state(true);
	let activeError = $state<string | null>(null);

	let historyItems = $state<RequestHistoryItem[]>([]);
	let historyTotal = $state(0);
	let historyPage = $state(1);
	const historyPageSize = 20;
	let historyTotalPages = $state(1);
	let historyLoading = $state(true);
	let historyError = $state<string | null>(null);
	let historyFilter = $state<string | undefined>(undefined);

	let pollInterval: ReturnType<typeof setInterval> | null = null;
	let activeAbortController: AbortController | null = null;
	let historyAbortController: AbortController | null = null;
	let activeRequestId = 0;
	let historyRequestId = 0;
	let toastShow = $state(false);
	let toastMessage = $state('');
	let toastType = $state<'success' | 'error' | 'info'>('success');

	function abortActiveLoad() {
		if (activeAbortController) {
			activeAbortController.abort();
			activeAbortController = null;
		}
	}

	function abortHistoryLoad() {
		if (historyAbortController) {
			historyAbortController.abort();
			historyAbortController = null;
		}
	}

	function showToast(message: string, type: 'success' | 'error' | 'info' = 'success') {
		toastMessage = message;
		toastType = type;
		toastShow = true;
	}

	async function loadActive() {
		const requestId = ++activeRequestId;
		abortActiveLoad();
		const controller = new AbortController();
		activeAbortController = controller;
		try {
			const data = await fetchActiveRequests(controller.signal);
			if (controller.signal.aborted || requestId !== activeRequestId) {
				return;
			}
			activeItems = data.items;
			activeCount = data.count;
			notifyRequestCountChanged(activeCount);
			activeError = null;
		} catch (e) {
			if (isAbortError(e)) {
				return;
			}
			activeError = 'Failed to load active requests';
		} finally {
			if (!controller.signal.aborted && requestId === activeRequestId) {
				activeLoading = false;
			}
			if (activeAbortController === controller) {
				activeAbortController = null;
			}
		}
	}

	async function loadHistory() {
		const requestId = ++historyRequestId;
		abortHistoryLoad();
		const controller = new AbortController();
		historyAbortController = controller;
		historyLoading = true;
		try {
			const data = await fetchRequestHistory(
				historyPage,
				historyPageSize,
				historyFilter,
				controller.signal
			);
			if (controller.signal.aborted || requestId !== historyRequestId) {
				return;
			}
			historyItems = data.items;
			historyTotal = data.total;
			historyTotalPages = data.total_pages;
			historyError = null;
		} catch (e) {
			if (isAbortError(e)) {
				return;
			}
			historyError = 'Failed to load request history';
		} finally {
			if (!controller.signal.aborted && requestId === historyRequestId) {
				historyLoading = false;
			}
			if (historyAbortController === controller) {
				historyAbortController = null;
			}
		}
	}

	function startPolling() {
		stopPolling();
		void loadActive();
		pollInterval = setInterval(loadActive, 5000);
	}

	function stopPolling() {
		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
		abortActiveLoad();
	}

	function handleVisibility() {
		if (document.hidden) {
			stopPolling();
		} else if (activeTab === 'active') {
			startPolling();
		}
	}

	function switchTab(tab: 'active' | 'history') {
		activeTab = tab;
		if (tab === 'active') {
			abortHistoryLoad();
			startPolling();
		} else {
			stopPolling();
			void loadHistory();
		}
	}

	async function handleCancel(mbid: string) {
		try {
			const result = await cancelRequest(mbid);
			if (result.success) {
				showToast(result.message);
				activeItems = activeItems.filter((i) => i.musicbrainz_id !== mbid);
				activeCount = activeItems.length;
				notifyRequestCountChanged(activeCount);
			} else {
				showToast(result.message, 'error');
			}
		} catch {
			showToast('Failed to cancel request', 'error');
		}
	}

	async function handleRetry(mbid: string) {
		try {
			const result = await retryRequest(mbid);
			if (result.success) {
				showToast(result.message);
				await Promise.all([loadHistory(), loadActive()]);
			} else {
				showToast(result.message, 'error');
			}
		} catch {
			showToast('Failed to retry request', 'error');
		}
	}

	async function handleClear(mbid: string) {
		try {
			const result = await clearHistoryItem(mbid);
			if (result.success) {
				showToast('Removed from history');
				historyItems = historyItems.filter((i) => i.musicbrainz_id !== mbid);
				historyTotal = Math.max(0, historyTotal - 1);
			} else {
				showToast('Failed to remove', 'error');
			}
		} catch {
			showToast('Failed to remove from history', 'error');
		}
	}

	function handleRemoved() {
		void loadHistory();
	}

	function handleHistoryPageChange(page: number) {
		historyPage = page;
		void loadHistory();
	}

	function handleFilterChange(e: Event) {
		const value = (e.target as HTMLSelectElement).value;
		historyFilter = value || undefined;
		historyPage = 1;
		void loadHistory();
	}

	onMount(() => {
		startPolling();
		document.addEventListener('visibilitychange', handleVisibility);
		window.dispatchEvent(new CustomEvent('requests-page-active', { detail: true }));
	});

	onDestroy(() => {
		stopPolling();
		abortActiveLoad();
		abortHistoryLoad();
		document.removeEventListener('visibilitychange', handleVisibility);
		window.dispatchEvent(new CustomEvent('requests-page-active', { detail: false }));
	});
</script>

<div class="container mx-auto p-4 md:p-6 lg:p-8">
	<div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
		<div>
			<h1 class="text-3xl font-bold">Requests</h1>
			<p class="text-base-content/70 text-sm mt-1">
				Track your album requests and downloads
			</p>
		</div>
	</div>

	<div role="tablist" class="tabs tabs-box mb-6">
		<button
			role="tab"
			class="tab"
			class:tab-active={activeTab === 'active'}
			onclick={() => switchTab('active')}
		>
			Active
			{#if activeCount > 0}
				<span class="badge badge-sm badge-info ml-2">{activeCount}</span>
			{/if}
		</button>
		<button
			role="tab"
			class="tab"
			class:tab-active={activeTab === 'history'}
			onclick={() => switchTab('history')}
		>
			History
			{#if historyTotal > 0}
				<span class="badge badge-sm badge-ghost ml-2">{historyTotal}</span>
			{/if}
		</button>
	</div>

	{#if activeTab === 'active'}
		<div in:fade={{ duration: 200 }}>
			{#if activeError}
				<div class="alert alert-warning mb-4">
					<TriangleAlert class="h-5 w-5" />
					<span>{activeError}</span>
					<button class="btn btn-sm" onclick={loadActive}>Retry</button>
				</div>
			{/if}

			{#if activeLoading && activeItems.length === 0}
				<div class="flex flex-col gap-3">
					{#each Array(3) as _}
						<div class="flex items-center gap-4 p-4 bg-base-200 rounded-box animate-pulse">
							<div class="w-16 h-16 sm:w-20 sm:h-20 bg-base-300 rounded-lg"></div>
							<div class="flex-1">
								<div class="h-4 bg-base-300 rounded w-48 mb-2"></div>
								<div class="h-3 bg-base-300 rounded w-32 mb-1"></div>
								<div class="h-3 bg-base-300 rounded w-24"></div>
							</div>
							<div class="flex flex-col items-end gap-2">
								<div class="h-5 bg-base-300 rounded w-20"></div>
								<div class="h-2 bg-base-300 rounded w-32"></div>
							</div>
						</div>
					{/each}
				</div>
			{:else if activeItems.length === 0}
				<div class="flex flex-col items-center justify-center min-h-[200px] text-center py-12">
					<CheckCircle class="h-16 w-16 text-base-content/20 mb-4" />
					<h2 class="text-xl font-semibold mb-2 text-base-content/50">No active requests</h2>
					<p class="text-base-content/40">Search for albums and request them to see downloads here</p>
				</div>
			{:else}
				<div class="flex flex-col gap-3">
					{#each activeItems as item (item.musicbrainz_id)}
						<RequestCard
							{item}
							mode="active"
							oncancel={handleCancel}
						/>
					{/each}
				</div>
			{/if}
		</div>
	{:else}
		<div in:fade={{ duration: 200 }}>
			<div class="flex justify-between items-center mb-4">
				<select class="select select-bordered select-sm" aria-label="Filter by status" onchange={handleFilterChange}>
					<option value="">All</option>
					<option value="imported">Imported</option>
					<option value="incomplete">Import Incomplete</option>
					<option value="failed">Failed</option>
					<option value="cancelled">Cancelled</option>
				</select>

				{#if historyTotalPages > 1}
					<Pagination
						current={historyPage}
						total={historyTotalPages}
						onchange={handleHistoryPageChange}
					/>
				{/if}
			</div>

			{#if historyError}
				<div class="alert alert-error mb-4">
					<span>{historyError}</span>
					<button class="btn btn-sm" onclick={loadHistory}>Retry</button>
				</div>
			{/if}

			{#if historyLoading && historyItems.length === 0}
				<div class="flex flex-col gap-3">
					{#each Array(5) as _}
						<div class="flex items-center gap-4 p-4 bg-base-200 rounded-box animate-pulse">
							<div class="w-16 h-16 sm:w-20 sm:h-20 bg-base-300 rounded-lg"></div>
							<div class="flex-1">
								<div class="h-4 bg-base-300 rounded w-48 mb-2"></div>
								<div class="h-3 bg-base-300 rounded w-32"></div>
							</div>
							<div class="flex flex-col items-end gap-2">
								<div class="h-5 bg-base-300 rounded w-16"></div>
								<div class="h-3 bg-base-300 rounded w-24"></div>
							</div>
						</div>
					{/each}
				</div>
			{:else if historyItems.length === 0}
				<div class="flex flex-col items-center justify-center min-h-[200px] text-center py-12">
					<Clock class="h-16 w-16 text-base-content/20 mb-4" />
					<h2 class="text-xl font-semibold mb-2 text-base-content/50">No request history</h2>
					<p class="text-base-content/40">Completed and failed requests will appear here</p>
				</div>
			{:else}
				<div class="flex flex-col gap-3">
					{#each historyItems as item (item.musicbrainz_id)}
						<RequestCard
							{item}
							mode="history"
							onretry={handleRetry}
							onclear={handleClear}
							onremoved={handleRemoved}
						/>
					{/each}
				</div>

				{#if historyTotalPages > 1}
					<div class="flex justify-center mt-6">
						<Pagination
							current={historyPage}
							total={historyTotalPages}
							onchange={handleHistoryPageChange}
						/>
					</div>
				{/if}
			{/if}
		</div>
	{/if}
</div>

<Toast bind:show={toastShow} message={toastMessage} type={toastType} />
