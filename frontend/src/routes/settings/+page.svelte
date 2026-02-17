<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import SettingsPreferences from '$lib/components/settings/SettingsPreferences.svelte';
	import SettingsCache from '$lib/components/settings/SettingsCache.svelte';
	import SettingsLidarrConnection from '$lib/components/settings/SettingsLidarrConnection.svelte';
	import SettingsLibrarySync from '$lib/components/settings/SettingsLibrarySync.svelte';
	import SettingsJellyfin from '$lib/components/settings/SettingsJellyfin.svelte';
	import SettingsListenBrainz from '$lib/components/settings/SettingsListenBrainz.svelte';
	import SettingsYouTube from '$lib/components/settings/SettingsYouTube.svelte';
	import SettingsLocalFiles from '$lib/components/settings/SettingsLocalFiles.svelte';
	import SettingsAdvanced from '$lib/components/settings/SettingsAdvanced.svelte';

	let activeTab = $state('settings');

	const tabs = [
		{ id: 'settings', label: 'Release Preferences', group: 'Preferences', icon: 'M12 1v6m0 6v6m-9-9h6m6 0h6M4.5 5.5l4 4m6 6l4 4m0-14l-4 4m-6 6l-4 4' },
		{ id: 'lidarr', label: 'Library Sync', group: 'Library Management', icon: 'M9 18V5l12-2v13M6 18a3 3 0 100-6 3 3 0 000 6zM18 16a3 3 0 100-6 3 3 0 000 6z' },
		{ id: 'lidarr-connection', label: 'Lidarr Connection', group: 'External Services', icon: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' },
		{ id: 'jellyfin', label: 'Jellyfin', group: 'External Services', icon: 'M2 7h20v15a2 2 0 01-2 2H4a2 2 0 01-2-2V7zM17 2l-5 5-5-5' },
		{ id: 'listenbrainz', label: 'ListenBrainz', group: 'External Services', icon: 'M9 18V5l12-2v13M6 18a3 3 0 100-6 3 3 0 000 6zM18 16a3 3 0 100-6 3 3 0 000 6z' },
		{ id: 'youtube', label: 'YouTube', group: 'External Services', icon: 'M22.54 6.42a2.78 2.78 0 00-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 00-1.94 2A29 29 0 001 12a29 29 0 00.46 5.58 2.78 2.78 0 001.94 2C5.12 20 12 20 12 20s6.88 0 8.6-.46a2.78 2.78 0 001.94-2A29 29 0 0023 12a29 29 0 00-.46-5.58zM9.75 15.02V8.98L15.5 12l-5.75 3.02z' },
		{ id: 'local-files', label: 'Local Files', group: 'External Services', icon: 'M3 18v-6a9 9 0 0118 0v6M5 18a2 2 0 01-2-2v-1a2 2 0 012-2h1v5H5zM19 18a2 2 0 002-2v-1a2 2 0 00-2-2h-1v5h1z' },
		{ id: 'cache', label: 'Cache', group: 'System', icon: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V7M21 3H3v4h18V3zM10 12h4' },
		{ id: 'advanced', label: 'Advanced', group: 'System', icon: 'M12 12a3 3 0 100-6 3 3 0 000 6zM12 1v6m0 6v6M1 12h6m6 0h6M4.2 4.2l4.3 4.3m7 7l4.3 4.3M19.8 4.2l-4.3 4.3m-7 7l-4.3 4.3' }
	];

	const groups = [...new Set(tabs.map(t => t.group))];

	function getTabsByGroup(group: string) {
		return tabs.filter(t => t.group === group);
	}

	onMount(() => {
		const tabParam = $page.url.searchParams.get('tab');
		if (tabParam && tabs.some(t => t.id === tabParam)) {
			activeTab = tabParam;
		}
	});
</script>

<div class="min-h-screen bg-base-100">
	<div class="container mx-auto p-4 max-w-7xl">
		<div class="mb-6">
			<h1 class="text-3xl font-bold">Settings</h1>
			<p class="text-base-content/70 mt-2">Manage your preferences and application settings</p>
		</div>

		<div class="flex flex-col lg:flex-row gap-6">
			<aside class="w-full lg:w-80 space-y-4">
				{#each groups as group}
					<div class="bg-base-200 rounded-box p-2">
						<div class="px-4 py-2">
							<h3 class="text-xs font-semibold text-base-content/50 uppercase tracking-wider">{group}</h3>
						</div>
						<ul class="menu p-0">
							{#each getTabsByGroup(group) as tab}
								<li>
									<button
										class="text-base justify-start"
										class:btn-active={activeTab === tab.id}
										onclick={() => activeTab = tab.id}
									>
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5">
											<path d={tab.icon}></path>
										</svg>
										<span>{tab.label}</span>
									</button>
								</li>
							{/each}
						</ul>
					</div>
				{/each}
			</aside>

			<main class="flex-1">
				{#if activeTab === 'settings'}
					<SettingsPreferences />
				{:else if activeTab === 'cache'}
					<SettingsCache />
				{:else if activeTab === 'lidarr-connection'}
					<SettingsLidarrConnection />
				{:else if activeTab === 'lidarr'}
					<SettingsLibrarySync />
				{:else if activeTab === 'jellyfin'}
					<SettingsJellyfin />
				{:else if activeTab === 'listenbrainz'}
					<SettingsListenBrainz />
				{:else if activeTab === 'youtube'}
					<SettingsYouTube />
				{:else if activeTab === 'local-files'}
					<SettingsLocalFiles />
				{:else if activeTab === 'advanced'}
					<SettingsAdvanced />
				{/if}
			</main>
		</div>
	</div>
</div>
