<script lang="ts">
	import { onMount } from 'svelte';
	import { API } from '$lib/constants';
	import { api } from '$lib/api/client';
	import EmbyIcon from '$lib/components/EmbyIcon.svelte';
	import { CircleCheck, CircleAlert, Save, RefreshCw } from 'lucide-svelte';

	interface EmbyAuthSettings {
		emby_url: string;
		enabled: boolean;
		emby_api_key: string;
	}

	interface SyncResult {
		created: string[];
		skipped: string[];
	}

	let settings = $state<EmbyAuthSettings>({ emby_url: '', enabled: false, emby_api_key: '' });
	let loading = $state(true);
	let saving = $state(false);
	let testing = $state(false);
	let syncing = $state(false);
	let testResult = $state<{ success: boolean; message: string } | null>(null);
	let syncResult = $state<SyncResult | null>(null);
	let syncError = $state('');
	let saveMessage = $state('');

	async function load() {
		loading = true;
		try {
			settings = await api.global.get<EmbyAuthSettings>(API.embyAuthSettings());
		} catch {
			// If not configured yet, keep defaults
		} finally {
			loading = false;
		}
	}

	async function save() {
		saving = true;
		saveMessage = '';
		testResult = null;
		syncResult = null;
		syncError = '';
		try {
			settings = await api.global.put<EmbyAuthSettings>(API.embyAuthSettings(), settings);
			saveMessage = 'Saved';
			setTimeout(() => (saveMessage = ''), 2000);
		} catch {
			saveMessage = 'Failed to save';
		} finally {
			saving = false;
		}
	}

	async function test() {
		testing = true;
		testResult = null;
		try {
			testResult = await api.global.post<{ success: boolean; message: string }>(
				API.embyAuthVerify(),
				{
					emby_url: settings.emby_url,
					enabled: settings.enabled,
					emby_api_key: settings.emby_api_key
				}
			);
		} catch {
			testResult = { success: false, message: 'Could not reach server' };
		} finally {
			testing = false;
		}
	}

	async function syncUsers() {
		syncing = true;
		syncResult = null;
		syncError = '';
		try {
			syncResult = await api.global.post<SyncResult>(API.embySyncUsers(), {});
		} catch (e: unknown) {
			const msg = e instanceof Error ? e.message : '';
			syncError = msg || 'Sync failed';
		} finally {
			syncing = false;
		}
	}

	onMount(() => void load());
</script>

<div class="card bg-base-200">
	<div class="card-body gap-4">
		<div class="flex items-center gap-3">
			<div
				class="flex h-10 w-10 items-center justify-center rounded-xl bg-green-500/10 text-green-400"
			>
				<EmbyIcon class="h-5 w-5" />
			</div>
			<div>
				<h3 class="font-semibold">Emby</h3>
				<p class="text-xs text-base-content/50">Allow users to sign in with their Emby account</p>
			</div>
			<div class="ml-auto">
				<input
					type="checkbox"
					class="toggle toggle-primary toggle-sm"
					bind:checked={settings.enabled}
					disabled={loading}
				/>
			</div>
		</div>

		{#if settings.enabled}
			<div class="space-y-3 pt-1">
				<label class="form-control">
					<div class="label"><span class="label-text">Emby Server URL</span></div>
					<input
						type="url"
						class="input input-bordered input-sm"
						placeholder="http://your-emby-server:8096"
						bind:value={settings.emby_url}
					/>
				</label>

				<label class="form-control">
					<div class="label">
						<span class="label-text">API Key</span>
						<span class="label-text-alt text-base-content/40">Required for user sync</span>
					</div>
					<input
						type="password"
						class="input input-bordered input-sm"
						placeholder="Generate in Emby Dashboard → API Keys"
						bind:value={settings.emby_api_key}
					/>
				</label>

				{#if testResult}
					<div
						class="flex items-center gap-2 text-sm {testResult.success
							? 'text-success'
							: 'text-error'}"
					>
						{#if testResult.success}
							<CircleCheck class="h-4 w-4 shrink-0" />
						{:else}
							<CircleAlert class="h-4 w-4 shrink-0" />
						{/if}
						{testResult.message}
					</div>
				{/if}

				{#if syncResult}
					<div class="rounded-box bg-base-100 p-3 text-sm space-y-1">
						<p class="font-medium">Sync complete</p>
						<p class="text-success">
							{syncResult.created.length} user{syncResult.created.length !== 1 ? 's' : ''} imported
							{#if syncResult.created.length > 0}
								— {syncResult.created.join(', ')}
							{/if}
						</p>
						{#if syncResult.skipped.length > 0}
							<p class="text-base-content/50">
								{syncResult.skipped.length} already existed (skipped)
							</p>
						{/if}
					</div>
				{/if}

				{#if syncError}
					<div class="flex items-center gap-2 text-sm text-error">
						<CircleAlert class="h-4 w-4 shrink-0" />
						{syncError}
					</div>
				{/if}

				<div class="flex flex-wrap items-center gap-2">
					<button
						class="btn btn-outline btn-sm"
						onclick={() => void test()}
						disabled={testing || !settings.emby_url}
					>
						{#if testing}
							<span class="loading loading-spinner loading-xs"></span>
						{/if}
						Test Connection
					</button>
					<button
						class="btn btn-outline btn-sm gap-1"
						onclick={() => void syncUsers()}
						disabled={syncing || !settings.emby_api_key || !settings.emby_url}
						title={!settings.emby_api_key ? 'Enter an API key to sync users' : ''}
					>
						{#if syncing}
							<span class="loading loading-spinner loading-xs"></span>
						{:else}
							<RefreshCw class="h-3.5 w-3.5" />
						{/if}
						Sync Users
					</button>
					<button
						class="btn btn-primary btn-sm gap-1"
						onclick={() => void save()}
						disabled={saving}
					>
						{#if saving}
							<span class="loading loading-spinner loading-xs"></span>
						{:else}
							<Save class="h-3.5 w-3.5" />
						{/if}
						Save
					</button>
					{#if saveMessage}
						<span class="text-sm text-success">{saveMessage}</span>
					{/if}
				</div>
			</div>
		{:else}
			<div class="flex gap-2">
				<button
					class="btn btn-primary btn-sm"
					onclick={() => void save()}
					disabled={saving || loading}
				>
					Save
				</button>
				{#if saveMessage}
					<span class="text-sm text-success self-center">{saveMessage}</span>
				{/if}
			</div>
		{/if}
	</div>
</div>
