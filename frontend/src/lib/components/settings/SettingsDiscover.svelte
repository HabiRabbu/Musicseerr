<script lang="ts">
	import type { HomeSettings } from '$lib/types';
	import { createSettingsForm } from '$lib/utils/settingsForm.svelte';
	import { invalidateQueriesWithPersister } from '$lib/queries/QueryClient';
	import { DiscoverQueryKeyFactory } from '$lib/queries/discover/DiscoverQueryKeyFactory';
	import { onMount, onDestroy } from 'svelte';

	const form = createSettingsForm<HomeSettings>({
		loadEndpoint: '/api/v1/settings/home',
		saveEndpoint: '/api/v1/settings/home',
		afterSave: async () => {
			await invalidateQueriesWithPersister({ queryKey: DiscoverQueryKeyFactory.prefix });
		}
	});

	async function load() {
		await form.load();
	}

	async function save() {
		await form.save();
	}

	onMount(() => {
		load();
	});

	onDestroy(() => form.cleanup());
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">Discover</h2>
		<p class="text-base-content/70 mb-4">Pick what appears on the Discover page.</p>

		{#if form.loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if form.data}
			<div class="space-y-4">
				<div class="form-control">
					<label class="label cursor-pointer justify-start gap-4">
						<input
							type="checkbox"
							bind:checked={form.data.show_globally_trending}
							class="toggle toggle-primary"
						/>
						<div>
							<span class="label-text font-medium">Show Globally Trending</span>
							<p class="text-xs text-base-content/50">
								Shows trending artists worldwide in Charts & Activity.
							</p>
						</div>
					</label>
				</div>

				{#if form.message}
					<div
						class="alert"
						class:alert-success={form.messageType === 'success'}
						class:alert-error={form.messageType === 'error'}
					>
						<span>{form.message}</span>
					</div>
				{/if}

				<div class="flex justify-end pt-2">
					<button type="button" class="btn btn-primary" onclick={save} disabled={form.saving}>
						{#if form.saving}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Save Settings
					</button>
				</div>
			</div>
		{:else if form.message}
			<div class="alert" class:alert-error={form.messageType === 'error'}>
				<span>{form.message}</span>
			</div>
		{/if}
	</div>
</div>
