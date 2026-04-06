<script lang="ts">
	import { Eye, Download } from 'lucide-svelte';
	import { api } from '$lib/api/client';
	import { createEventDispatcher } from 'svelte';

	export let artistMbid: string;
	export let monitored: boolean = false;
	export let autoDownload: boolean = false;
	export let disabled: boolean = false;

	const dispatch = createEventDispatcher<{
		change: { monitored: boolean; autoDownload: boolean };
	}>();

	let saving = false;

	async function updateMonitoring(newMonitored: boolean, newAutoDownload: boolean) {
		if (saving) return;
		saving = true;
		try {
			await api.global.put(`/api/v1/artists/${artistMbid}/monitoring`, {
				monitored: newMonitored,
				auto_download: newAutoDownload
			});
			monitored = newMonitored;
			autoDownload = newAutoDownload;
			dispatch('change', { monitored, autoDownload });
		} catch {
			// revert is implicit: we only update state on success
		} finally {
			saving = false;
		}
	}

	async function handleMonitorToggle() {
		const newMonitored = !monitored;
		const newAutoDownload = newMonitored ? autoDownload : false;
		await updateMonitoring(newMonitored, newAutoDownload);
	}

	async function handleAutoDownloadToggle() {
		await updateMonitoring(monitored, !autoDownload);
	}
</script>

<div class="flex items-center gap-4 flex-wrap">
	<label class="label cursor-pointer gap-2" aria-label="Monitor this artist">
		<Eye class="h-4 w-4 text-base-content/70" />
		<span class="text-sm text-base-content/70">Monitor</span>
		<input
			type="checkbox"
			checked={monitored}
			on:change={handleMonitorToggle}
			disabled={disabled || saving}
			class="toggle toggle-sm toggle-accent"
		/>
	</label>
	<label
		class="label cursor-pointer gap-2 transition-opacity"
		class:opacity-40={!monitored}
		aria-label="Download new releases"
	>
		<Download class="h-4 w-4 text-base-content/70" />
		<span class="text-sm text-base-content/70">Download new releases</span>
		<input
			type="checkbox"
			checked={autoDownload}
			on:change={handleAutoDownloadToggle}
			disabled={disabled || saving || !monitored}
			class="toggle toggle-sm toggle-accent"
		/>
	</label>
</div>
