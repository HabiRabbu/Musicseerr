<script lang="ts">
	import { getApiUrl } from '$lib/api/api-utils';
	import { browser } from '$app/environment';
	import { preferencesStore } from '$lib/stores/preferences';
	import { integrationStore } from '$lib/stores/integration';
	import type {
		UserPreferences,
		ReleaseTypeOption,
		LidarrMetadataProfilePreferences,
		MetadataProfile
	} from '$lib/types';

	let preferences: UserPreferences = $state({
		primary_types: [],
		secondary_types: [],
		release_statuses: []
	});
	let saving = $state(false);
	let saveMessage = $state('');

	let lidarrConfigured = $state(false);
	let lidarrProfiles: MetadataProfile[] = $state([]);
	let selectedProfileId: number | null = $state(null);
	let lidarrPrefs: LidarrMetadataProfilePreferences | null = $state(null);
	let lidarrLoading = $state(false);
	let lidarrError = $state('');
	let lidarrSyncing = $state(false);
	let lidarrMessage = $state('');
	let lidarrLoadAttempted = $state(false);

	const primaryTypes: ReleaseTypeOption[] = [
		{ id: 'album', title: 'Album', description: 'Full-length studio albums' },
		{ id: 'ep', title: 'EP', description: 'Extended Play releases (shorter than albums)' },
		{ id: 'single', title: 'Single', description: 'Individual track releases' },
		{ id: 'broadcast', title: 'Broadcast', description: 'Radio or TV broadcast recordings' },
		{ id: 'other', title: 'Other', description: 'Miscellaneous release types' }
	];

	const secondaryTypes: ReleaseTypeOption[] = [
		{ id: 'studio', title: 'Studio', description: 'Original studio recordings' },
		{ id: 'compilation', title: 'Compilation', description: 'Greatest hits and collections' },
		{ id: 'soundtrack', title: 'Soundtrack', description: 'Music from movies, games, or TV' },
		{ id: 'spokenword', title: 'Spoken Word', description: 'Audiobooks and spoken content' },
		{ id: 'interview', title: 'Interview', description: 'Interview recordings' },
		{ id: 'audio drama', title: 'Audio Drama', description: 'Dramatic audio productions' },
		{ id: 'live', title: 'Live', description: 'Live concert recordings' },
		{ id: 'remix', title: 'Remix', description: 'Remix albums' },
		{ id: 'dj-mix', title: 'DJ-mix', description: 'DJ mixed compilations' },
		{ id: 'mixtape/street', title: 'Mixtape/Street', description: 'Unofficial mixtapes' },
		{ id: 'demo', title: 'Demo', description: 'Demo recordings' }
	];

	const releaseStatuses: ReleaseTypeOption[] = [
		{
			id: 'official',
			title: 'Official',
			description: 'Officially released by the artist or label'
		},
		{ id: 'promotion', title: 'Promotion', description: 'Promotional releases' },
		{ id: 'bootleg', title: 'Bootleg', description: 'Unofficial bootleg recordings' },
		{ id: 'pseudo-release', title: 'Pseudo-Release', description: 'Placeholder or meta releases' }
	];

	function toggleType(
		category: 'primary_types' | 'secondary_types' | 'release_statuses',
		id: string
	) {
		const index = preferences[category].indexOf(id);
		if (index > -1) {
			preferences[category] = preferences[category].filter((t) => t !== id);
		} else {
			preferences[category] = [...preferences[category], id];
		}
	}

	function isLidarrEnabled(
		category: 'primary_types' | 'secondary_types' | 'release_statuses',
		id: string
	): boolean | null {
		if (!lidarrPrefs) return null;
		return lidarrPrefs[category].includes(id);
	}

	function getAllTypesForCategory(
		category: 'primary_types' | 'secondary_types' | 'release_statuses'
	): ReleaseTypeOption[] {
		if (category === 'primary_types') return primaryTypes;
		if (category === 'secondary_types') return secondaryTypes;
		return releaseStatuses;
	}

	const mismatchCount = $derived.by(() => {
		if (!lidarrPrefs) return 0;
		let count = 0;
		const categories = ['primary_types', 'secondary_types', 'release_statuses'] as const;
		for (const cat of categories) {
			for (const type of getAllTypesForCategory(cat)) {
				const msEnabled = preferences[cat].includes(type.id);
				const lrEnabled = lidarrPrefs[cat].includes(type.id);
				if (msEnabled !== lrEnabled) count++;
			}
		}
		return count;
	});

	async function loadLidarrPrefs() {
		lidarrLoadAttempted = true;
		lidarrLoading = true;
		lidarrError = '';
		try {
			if (lidarrProfiles.length === 0) {
				const profilesRes = await fetch(getApiUrl('/api/v1/settings/lidarr/metadata-profiles'));
				if (profilesRes.ok) {
					lidarrProfiles = await profilesRes.json();
				}
			}

			const params = selectedProfileId != null ? `?profile_id=${selectedProfileId}` : '';
			const response = await fetch(
				getApiUrl(`/api/v1/settings/lidarr/metadata-profile/preferences${params}`)
			);
			if (response.ok) {
				lidarrPrefs = await response.json();
				if (selectedProfileId == null && lidarrPrefs) {
					selectedProfileId = lidarrPrefs.profile_id;
				}
			} else {
				lidarrError = 'Could not load Lidarr metadata profile';
				lidarrPrefs = null;
			}
		} catch {
			lidarrError = 'Could not connect to Lidarr';
			lidarrPrefs = null;
		} finally {
			lidarrLoading = false;
		}
	}

	async function pushToLidarr() {
		lidarrSyncing = true;
		lidarrMessage = '';
		try {
			const params = selectedProfileId != null ? `?profile_id=${selectedProfileId}` : '';
			const response = await fetch(
				getApiUrl(`/api/v1/settings/lidarr/metadata-profile/preferences${params}`),
				{
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(preferences)
				}
			);
			if (response.ok) {
				lidarrPrefs = await response.json();
				lidarrMessage = 'Lidarr metadata profile updated successfully';
				setTimeout(() => {
					lidarrMessage = '';
				}, 5000);
			} else {
				try {
					const err = await response.json();
					lidarrMessage = err.error?.message || 'Failed to update Lidarr metadata profile';
				} catch {
					lidarrMessage = 'Failed to update Lidarr metadata profile';
				}
			}
		} catch {
			lidarrMessage = 'Failed to connect to Lidarr';
		} finally {
			lidarrSyncing = false;
		}
	}

	async function importFromLidarr() {
		if (!lidarrPrefs) return;
		preferences = {
			primary_types: [...lidarrPrefs.primary_types],
			secondary_types: [...lidarrPrefs.secondary_types],
			release_statuses: [...lidarrPrefs.release_statuses]
		};
		lidarrMessage = 'Imported from Lidarr — remember to save your settings';
		setTimeout(() => {
			lidarrMessage = '';
		}, 5000);
	}

	async function onProfileChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		selectedProfileId = parseInt(target.value, 10);
		lidarrPrefs = null;
		lidarrLoadAttempted = false;
		await loadLidarrPrefs();
	}

	async function handleSave() {
		saving = true;
		saveMessage = '';

		const success = await preferencesStore.save(preferences);

		if (success) {
			saveMessage = 'Settings saved Artist pages and search results will refresh automatically.';

			if (browser) {
				window.dispatchEvent(new CustomEvent('artist-refresh'));
				window.dispatchEvent(new CustomEvent('search-refresh'));
			}

			setTimeout(() => {
				saveMessage = '';
			}, 5000);
		} else {
			saveMessage = "Couldn't save your settings. Please try again.";
		}

		saving = false;
	}

	$effect(() => {
		preferencesStore.load();
		const unsubscribe = preferencesStore.subscribe((prefs) => {
			preferences = { ...prefs };
		});
		return unsubscribe;
	});

	$effect(() => {
		integrationStore.ensureLoaded();
		const unsubscribe = integrationStore.subscribe((status) => {
			lidarrConfigured = status.lidarr;
		});
		return unsubscribe;
	});

	$effect(() => {
		if (lidarrConfigured && !lidarrLoadAttempted) {
			loadLidarrPrefs();
		}
	});
</script>

{#snippet typeTable(
	types: ReleaseTypeOption[],
	category: 'primary_types' | 'secondary_types' | 'release_statuses'
)}
	<div class="overflow-x-auto">
		<table class="table">
			<thead>
				<tr>
					<th class="w-12 text-center">
						<span class="text-xs opacity-60">MS</span>
					</th>
					{#if lidarrConfigured && lidarrPrefs}
						<th class="w-12 text-center">
							<span class="text-xs opacity-60">Lidarr</span>
						</th>
					{/if}
					<th>Type</th>
					<th class="hidden sm:table-cell">Description</th>
				</tr>
			</thead>
			<tbody>
				{#each types as type (type.id)}
					{@const msEnabled = preferences[category].includes(type.id)}
					{@const lrEnabled = isLidarrEnabled(category, type.id)}
					{@const mismatch = lrEnabled !== null && msEnabled !== lrEnabled}
					<tr class={mismatch ? 'bg-warning/5' : ''}>
						<td class="w-12 text-center">
							<input
								type="checkbox"
								class="checkbox checkbox-primary checkbox-sm"
								checked={msEnabled}
								onchange={() => toggleType(category, type.id)}
							/>
						</td>
						{#if lidarrConfigured && lidarrPrefs}
							<td class="w-12 text-center">
								<input
									type="checkbox"
									class="checkbox checkbox-sm"
									class:checkbox-success={lrEnabled && !mismatch}
									class:checkbox-warning={mismatch}
									checked={lrEnabled ?? false}
									disabled
								/>
							</td>
						{/if}
						<td class="font-medium">
							{type.title}
							{#if mismatch}
								<span class="badge badge-warning badge-xs ml-1">differs</span>
							{/if}
						</td>
						<td class="text-base-content/70 hidden sm:table-cell">{type.description}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/snippet}

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl mb-4">Included Releases</h2>
		<p class="text-base-content/70 mb-6">
			Choose which types of releases to show in artist pages and search results.
		</p>

		{#if lidarrConfigured}
			<div class="flex flex-wrap items-center gap-3 mb-6 p-3 rounded-lg bg-base-300/50">
				{#if lidarrLoading}
					<span class="loading loading-spinner loading-sm"></span>
					<span class="text-sm text-base-content/70">Loading Lidarr profile…</span>
				{:else if lidarrError}
					<span class="text-sm text-error">{lidarrError}</span>
					<button class="btn btn-ghost btn-xs" onclick={loadLidarrPrefs}>Retry</button>
				{:else if lidarrPrefs}
					<label class="flex items-center gap-2 text-sm text-base-content/70">
						Lidarr profile:
						{#if lidarrProfiles.length > 1}
							<select
								class="select select-sm select-ghost font-semibold"
								value={selectedProfileId}
								onchange={onProfileChange}
							>
								{#each lidarrProfiles as profile (profile.id)}
									<option value={profile.id}>{profile.name}</option>
								{/each}
							</select>
						{:else}
							<span class="font-semibold">{lidarrPrefs.profile_name}</span>
						{/if}
					</label>
					{#if mismatchCount > 0}
						<span class="badge badge-warning badge-sm">
							{mismatchCount} difference{mismatchCount !== 1 ? 's' : ''}
						</span>
					{:else}
						<span class="badge badge-success badge-sm">In sync</span>
					{/if}
					<div class="ml-auto flex gap-2">
						<button class="btn btn-soft btn-sm" onclick={importFromLidarr} disabled={lidarrSyncing}>
							Import from Lidarr
						</button>
						<button class="btn btn-primary btn-sm" onclick={pushToLidarr} disabled={lidarrSyncing}>
							{#if lidarrSyncing}
								<span class="loading loading-spinner loading-xs"></span>
							{/if}
							Update Lidarr
						</button>
					</div>
				{/if}
				{#if lidarrMessage}
					<div
						class="w-full mt-2 alert text-sm"
						class:alert-success={lidarrMessage.includes('success')}
						class:alert-warning={lidarrMessage.includes('remember')}
						class:alert-error={!lidarrMessage.includes('success') &&
							!lidarrMessage.includes('remember')}
					>
						<span>{lidarrMessage}</span>
					</div>
				{/if}
			</div>
		{/if}

		<div class="mb-8">
			<h3 class="text-xl font-semibold mb-4">Primary Types</h3>
			{@render typeTable(primaryTypes, 'primary_types')}
		</div>

		<div class="mb-8">
			<h3 class="text-xl font-semibold mb-4">Secondary Types</h3>
			{@render typeTable(secondaryTypes, 'secondary_types')}
		</div>

		<div class="mb-8">
			<h3 class="text-xl font-semibold mb-4">Release Statuses</h3>
			{@render typeTable(releaseStatuses, 'release_statuses')}
		</div>

		<div class="card-actions justify-end items-center gap-4">
			{#if saveMessage}
				<div
					class="alert flex-1"
					class:alert-success={saveMessage.includes('success')}
					class:alert-error={saveMessage.includes('Failed')}
				>
					<span>{saveMessage}</span>
				</div>
			{/if}
			<button class="btn btn-primary" onclick={handleSave} disabled={saving}>
				{#if saving}
					<span class="loading loading-spinner loading-sm"></span>
					Saving...
				{:else}
					Save Settings
				{/if}
			</button>
		</div>
	</div>
</div>
