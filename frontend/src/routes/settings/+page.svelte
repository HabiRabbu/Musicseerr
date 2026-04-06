<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { fromStore } from 'svelte/store';
	import { integrationStore } from '$lib/stores/integration';
	import SettingsPreferences from '$lib/components/settings/SettingsPreferences.svelte';
	import SettingsCache from '$lib/components/settings/SettingsCache.svelte';
	import SettingsLidarrConnection from '$lib/components/settings/SettingsLidarrConnection.svelte';
	import SettingsLibrarySync from '$lib/components/settings/SettingsLibrarySync.svelte';
	import SettingsJellyfin from '$lib/components/settings/SettingsJellyfin.svelte';
	import SettingsNavidrome from '$lib/components/settings/SettingsNavidrome.svelte';
	import SettingsListenBrainz from '$lib/components/settings/SettingsListenBrainz.svelte';
	import SettingsYouTube from '$lib/components/settings/SettingsYouTube.svelte';
	import SettingsLocalFiles from '$lib/components/settings/SettingsLocalFiles.svelte';
	import SettingsLastFm from '$lib/components/settings/SettingsLastFm.svelte';
	import SettingsScrobbling from '$lib/components/settings/SettingsScrobbling.svelte';
	import SettingsMusicSource from '$lib/components/settings/SettingsMusicSource.svelte';
	import SettingsAdvanced from '$lib/components/settings/SettingsAdvanced.svelte';
	import {
		Settings2,
		Music,
		Shield,
		Youtube,
		Headphones,
		Database,
		Settings,
		Radio,
		Activity,
		BarChart3
	} from 'lucide-svelte';
	import JellyfinIcon from '$lib/components/JellyfinIcon.svelte';
	import NavidromeIcon from '$lib/components/NavidromeIcon.svelte';

	const integration = fromStore(integrationStore);

	const connectionMap: Record<
		string,
		'lastfm' | 'listenbrainz' | 'jellyfin' | 'navidrome' | 'youtube' | 'localfiles' | 'lidarr'
	> = {
		lastfm: 'lastfm',
		listenbrainz: 'listenbrainz',
		jellyfin: 'jellyfin',
		navidrome: 'navidrome',
		youtube: 'youtube',
		'local-files': 'localfiles',
		'lidarr-connection': 'lidarr'
	};

	let activeTab = $state('settings');

	const tabs = [
		{ id: 'settings', label: 'Release Preferences', group: 'Preferences', icon: Settings2 },
		{ id: 'lastfm', label: 'Last.fm', group: 'Music Tracking', icon: Radio },
		{ id: 'listenbrainz', label: 'ListenBrainz', group: 'Music Tracking', icon: Music },
		{ id: 'scrobbling', label: 'Scrobbling', group: 'Music Tracking', icon: Activity },
		{ id: 'music-source', label: 'Music Source', group: 'Music Tracking', icon: BarChart3 },
		{ id: 'jellyfin', label: 'Jellyfin', group: 'Media Servers', icon: JellyfinIcon },
		{ id: 'navidrome', label: 'Navidrome', group: 'Media Servers', icon: NavidromeIcon },
		{
			id: 'lidarr-connection',
			label: 'Lidarr Connection',
			group: 'Library & Sources',
			icon: Shield
		},
		{ id: 'lidarr', label: 'Library Sync', group: 'Library & Sources', icon: Music },
		{ id: 'youtube', label: 'YouTube', group: 'Library & Sources', icon: Youtube },
		{ id: 'local-files', label: 'Local Files', group: 'Library & Sources', icon: Headphones },
		{ id: 'cache', label: 'Cache', group: 'System', icon: Database },
		{ id: 'advanced', label: 'Advanced', group: 'System', icon: Settings }
	];

	const groups = [...new Set(tabs.map((t) => t.group))];

	function getTabsByGroup(group: string) {
		return tabs.filter((t) => t.group === group);
	}

	onMount(() => {
		integrationStore.ensureLoaded();
	});

	$effect(() => {
		const tabParam = page.url.searchParams.get('tab');
		if (tabParam && tabs.some((t) => t.id === tabParam)) {
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
			<aside
				class="w-full lg:w-80 space-y-4 lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto"
			>
				{#each groups as group, i (`group-${i}`)}
					<div class="bg-base-200 rounded-box p-2">
						<div class="px-4 py-2">
							<h3 class="text-xs font-semibold text-base-content/50 uppercase tracking-wider">
								{group}
							</h3>
						</div>
						<ul class="menu p-0">
							{#each getTabsByGroup(group) as tab (tab.id)}
								{@const Icon = tab.icon}
								<li>
									<button
										class="text-base justify-start"
										class:btn-active={activeTab === tab.id}
										onclick={() => (activeTab = tab.id)}
									>
										<Icon class="w-5 h-5" />
										<span>{tab.label}</span>
										{#if tab.id in connectionMap}
											{@const storeKey = connectionMap[tab.id]}
											{@const connected = integration.current[storeKey]}
											<span
												class="w-2 h-2 rounded-full ml-auto {connected
													? 'bg-success'
													: 'bg-base-content/20'}"
											>
												<span class="sr-only">{connected ? 'Connected' : 'Not connected'}</span>
											</span>
										{/if}
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
				{:else if activeTab === 'music-source'}
					<SettingsMusicSource />
				{:else if activeTab === 'cache'}
					<SettingsCache />
				{:else if activeTab === 'lidarr-connection'}
					<SettingsLidarrConnection />
				{:else if activeTab === 'lidarr'}
					<SettingsLibrarySync />
				{:else if activeTab === 'jellyfin'}
					<SettingsJellyfin />
				{:else if activeTab === 'navidrome'}
					<SettingsNavidrome />
				{:else if activeTab === 'listenbrainz'}
					<SettingsListenBrainz />
				{:else if activeTab === 'youtube'}
					<SettingsYouTube />
				{:else if activeTab === 'local-files'}
					<SettingsLocalFiles />
				{:else if activeTab === 'lastfm'}
					<SettingsLastFm />
				{:else if activeTab === 'scrobbling'}
					<SettingsScrobbling />
				{:else if activeTab === 'advanced'}
					<SettingsAdvanced />
				{/if}
			</main>
		</div>
	</div>
</div>
