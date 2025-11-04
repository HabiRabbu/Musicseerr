<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { preferencesStore } from '$lib/stores/preferences';
	import type { UserPreferences, ReleaseTypeOption } from '$lib/types';

	let activeTab = 'settings';
	let preferences: UserPreferences = {
		primary_types: [],
		secondary_types: [],
		release_statuses: []
	};
	let saving = false;
	let saveMessage = '';

	
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
		{ id: 'audiobook', title: 'Audio Drama', description: 'Dramatic audio productions' },
		{ id: 'live', title: 'Live', description: 'Live concert recordings' },
		{ id: 'remix', title: 'Remix', description: 'Remix albums' },
		{ id: 'dj-mix', title: 'DJ-mix', description: 'DJ mixed compilations' },
		{ id: 'mixtape/street', title: 'Mixtape/Street', description: 'Unofficial mixtapes' },
		{ id: 'demo', title: 'Demo', description: 'Demo recordings' }
	];

	
	const releaseStatuses: ReleaseTypeOption[] = [
		{ id: 'official', title: 'Official', description: 'Officially released by the artist or label' },
		{ id: 'promotion', title: 'Promotion', description: 'Promotional releases' },
		{ id: 'bootleg', title: 'Bootleg', description: 'Unofficial bootleg recordings' },
		{ id: 'pseudo-release', title: 'Pseudo-Release', description: 'Placeholder or meta releases' }
	];

	function toggleType(category: 'primary_types' | 'secondary_types' | 'release_statuses', id: string) {
		const index = preferences[category].indexOf(id);
		if (index > -1) {
			preferences[category] = preferences[category].filter((t) => t !== id);
		} else {
			preferences[category] = [...preferences[category], id];
		}
	}

	async function handleSave() {
		saving = true;
		saveMessage = '';

		const success = await preferencesStore.save(preferences);

		if (success) {
			saveMessage = 'Settings saved successfully! Artist pages and search results will refresh automatically.';
			
			
			if (browser) {
				window.dispatchEvent(new CustomEvent('artist-refresh'));
				window.dispatchEvent(new CustomEvent('search-refresh'));
			}
			
			setTimeout(() => {
				saveMessage = '';
			}, 5000);
		} else {
			saveMessage = 'Failed to save settings. Please try again.';
		}

		saving = false;
	}

	onMount(async () => {
		await preferencesStore.load();
		preferencesStore.subscribe((prefs) => {
			preferences = { ...prefs };
		});
	});
</script>

<div class="min-h-screen bg-base-100">
	<div class="container mx-auto p-4 max-w-7xl">
		
		<div class="mb-6">
			<h1 class="text-3xl font-bold">Settings</h1>
			<p class="text-base-content/70 mt-2">
				Manage your preferences and application settings
			</p>
		</div>

		<div class="flex flex-col lg:flex-row gap-6">
			
			<aside class="w-full lg:w-64">
				<ul class="menu bg-base-200 rounded-box">
					<li>
						<button
							class:btn-active={activeTab === 'settings'}
							on:click={() => (activeTab = 'settings')}
						>
							<svg
								xmlns="http:
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								class="w-5 h-5"
							>
								<circle cx="12" cy="12" r="3"></circle>
								<path
									d="M12 1v6m0 6v6m-9-9h6m6 0h6M4.5 5.5l4 4m6 6l4 4m0-14l-4 4m-6 6l-4 4"
								></path>
							</svg>
							<span>Settings</span>
						</button>
					</li>
				</ul>
			</aside>

			
			<main class="flex-1">
				{#if activeTab === 'settings'}
					<div class="card bg-base-200">
						<div class="card-body">
							<h2 class="card-title text-2xl mb-4">Included Releases</h2>
							<p class="text-base-content/70 mb-6">
								Choose which types of releases to show in artist pages and search results.
							</p>

							
							<div class="mb-8">
								<h3 class="text-xl font-semibold mb-4">Primary Types</h3>
								<div class="overflow-x-auto">
									<table class="table">
										<tbody>
											{#each primaryTypes as type}
												<tr>
													<td class="w-12">
														<input
															type="checkbox"
															class="checkbox checkbox-primary"
															checked={preferences.primary_types.includes(type.id)}
															on:change={() => toggleType('primary_types', type.id)}
														/>
													</td>
													<td class="font-medium">{type.title}</td>
													<td class="text-base-content/70">{type.description}</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</div>

							
							<div class="mb-8">
								<h3 class="text-xl font-semibold mb-4">Secondary Types</h3>
								<div class="overflow-x-auto">
									<table class="table">
										<tbody>
											{#each secondaryTypes as type}
												<tr>
													<td class="w-12">
														<input
															type="checkbox"
															class="checkbox checkbox-primary"
															checked={preferences.secondary_types.includes(type.id)}
															on:change={() => toggleType('secondary_types', type.id)}
														/>
													</td>
													<td class="font-medium">{type.title}</td>
													<td class="text-base-content/70">{type.description}</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</div>

							
							<div class="mb-8">
								<h3 class="text-xl font-semibold mb-4">Release Statuses</h3>
								<div class="overflow-x-auto">
									<table class="table">
										<tbody>
											{#each releaseStatuses as status}
												<tr>
													<td class="w-12">
														<input
															type="checkbox"
															class="checkbox checkbox-primary"
															checked={preferences.release_statuses.includes(status.id)}
															on:change={() => toggleType('release_statuses', status.id)}
														/>
													</td>
													<td class="font-medium">{status.title}</td>
													<td class="text-base-content/70">{status.description}</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</div>

							
							<div class="card-actions justify-end items-center gap-4">
								{#if saveMessage}
									<div
										class="alert flex-1"
										class:alert-success={saveMessage.includes('success')}
										class:alert-error={saveMessage.includes('Failed')}
									>
										{#if saveMessage.includes('success')}
											<svg
												xmlns="http:
												class="h-6 w-6 shrink-0 stroke-current"
												fill="none"
												viewBox="0 0 24 24"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													stroke-width="2"
													d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
												/>
											</svg>
										{:else}
											<svg
												xmlns="http:
												class="h-6 w-6 shrink-0 stroke-current"
												fill="none"
												viewBox="0 0 24 24"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													stroke-width="2"
													d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
												/>
											</svg>
										{/if}
										<span>{saveMessage}</span>
									</div>
								{/if}
								<button class="btn btn-primary" on:click={handleSave} disabled={saving}>
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
				{/if}
			</main>
		</div>
	</div>
</div>
