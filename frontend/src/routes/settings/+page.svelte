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
	import SettingsPlex from '$lib/components/settings/SettingsPlex.svelte';
	import SettingsListenBrainz from '$lib/components/settings/SettingsListenBrainz.svelte';
	import SettingsYouTube from '$lib/components/settings/SettingsYouTube.svelte';
	import SettingsLocalFiles from '$lib/components/settings/SettingsLocalFiles.svelte';
	import SettingsLastFm from '$lib/components/settings/SettingsLastFm.svelte';
	import SettingsScrobbling from '$lib/components/settings/SettingsScrobbling.svelte';
	import SettingsMusicSource from '$lib/components/settings/SettingsMusicSource.svelte';
	import SettingsAdvanced from '$lib/components/settings/SettingsAdvanced.svelte';
	import SettingsUsers from '$lib/components/settings/SettingsUsers.svelte';
	import SettingsEmbyAuth from '$lib/components/settings/SettingsEmbyAuth.svelte';
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
		BarChart3,
		Lock
	} from 'lucide-svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { api } from '$lib/api/client';

	let authToggling = $state(false);
	let authToggleError = $state('');
	let authToggleNeedsSetup = $state(false);

	async function toggleAuth(enabled: boolean) {
		authToggling = true;
		authToggleError = '';
		authToggleNeedsSetup = false;
		try {
			await api.put('/api/v1/auth/settings', { enabled });
			await authStore.checkStatus();
		} catch (e: unknown) {
			const msg = e instanceof Error ? e.message : '';
			if (msg === 'NO_USERS') {
				authToggleNeedsSetup = true;
			} else {
				authToggleError = msg || 'Failed to update auth setting';
			}
		} finally {
			authToggling = false;
		}
	}
	import JellyfinIcon from '$lib/components/JellyfinIcon.svelte';
	import NavidromeIcon from '$lib/components/NavidromeIcon.svelte';
	import PlexIcon from '$lib/components/PlexIcon.svelte';

	const integration = fromStore(integrationStore);

	const connectionMap: Record<
		string,
		| 'lastfm'
		| 'listenbrainz'
		| 'jellyfin'
		| 'navidrome'
		| 'plex'
		| 'youtube'
		| 'localfiles'
		| 'lidarr'
	> = {
		lastfm: 'lastfm',
		listenbrainz: 'listenbrainz',
		jellyfin: 'jellyfin',
		navidrome: 'navidrome',
		plex: 'plex',
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
		{ id: 'plex', label: 'Plex', group: 'Media Servers', icon: PlexIcon },
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
		{ id: 'advanced', label: 'Advanced', group: 'System', icon: Settings },
		{ id: 'users', label: 'Users & Access', group: 'System', icon: Lock }
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
			<p class="text-base-content/70 mt-2">Manage your preferences and app settings.</p>
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
				{:else if activeTab === 'plex'}
					<SettingsPlex />
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
				{:else if activeTab === 'users'}
					<div class="space-y-6">
						<div class="card bg-base-200">
							<div class="card-body gap-4">
								<div>
									<h2 class="card-title text-xl">Authentication</h2>
									<p class="text-base-content/60 text-sm mt-1">
										Control whether a login is required to access Musicseerr.
									</p>
								</div>

								{#if authToggleNeedsSetup}
									<div class="alert alert-warning text-sm py-2 gap-2 flex-col items-start">
										<div class="flex gap-2 items-center">
											<Lock class="h-4 w-4 shrink-0" />
											<span>No admin account exists yet. Create one before enabling login.</span>
										</div>
										<a href="/setup" class="btn btn-sm btn-warning w-full">Go to /setup</a>
									</div>
								{:else if authToggleError}
									<div class="alert alert-error text-sm py-2">{authToggleError}</div>
								{/if}

								<div class="flex items-center justify-between gap-4 bg-base-100 rounded-box p-4">
									<div>
										<p class="font-medium">Require Login</p>
										<p class="text-sm text-base-content/60">
											When enabled, users must sign in with a username and password.
										</p>
									</div>
									<input
										type="checkbox"
										class="toggle toggle-primary"
										checked={authStore.authEnabled}
										disabled={authToggling}
										onchange={(e) => toggleAuth((e.target as HTMLInputElement).checked)}
									/>
								</div>
							</div>
						</div>

						{#if authStore.authEnabled && authStore.role === 'admin'}
							<div>
								<h3 class="text-xs font-semibold uppercase tracking-widest text-base-content/50 mb-3">Authentication Providers</h3>
								<SettingsEmbyAuth />
							</div>
							<SettingsUsers />
						{/if}
					</div>
				{/if}
			</main>
		</div>
	</div>
</div>
