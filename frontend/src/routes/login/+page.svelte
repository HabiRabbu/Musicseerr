<script lang="ts">
	import { goto } from '$app/navigation';
	import { authStore } from '$lib/stores/auth.svelte';
	import { API } from '$lib/constants';
	import { Music } from 'lucide-svelte';
	import PlexIcon from '$lib/components/PlexIcon.svelte';
	import EmbyIcon from '$lib/components/EmbyIcon.svelte';

	let username = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);
	let plexPending = $state(false);

	// Emby sign-in
	let embyExpanded = $state(false);
	let embyUsername = $state('');
	let embyPassword = $state('');
	let embyLoading = $state(false);

	async function handleLogin(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		loading = true;

		try {
			const res = await fetch('/api/v1/auth/login', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, password }),
			});

			if (!res.ok) {
				const data = await res.json().catch(() => ({}));
				error = data.detail || 'Login failed';
				return;
			}

			const data = await res.json();
			authStore.setToken(data.token, data.username, data.role);
			goto('/');
		} catch {
			error = 'Could not connect to the server';
		} finally {
			loading = false;
		}
	}

	async function handlePlexLogin() {
		error = '';
		plexPending = true;
		try {
			const pinRes = await fetch(API.plexAuthPin(), { method: 'POST' });
			if (!pinRes.ok) throw new Error('Could not start Plex authentication');
			const { pin_id, auth_url } = await pinRes.json();
			window.open(auth_url, '_blank', 'noopener');
			await pollPlexPin(pin_id);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Plex authentication failed';
			plexPending = false;
		}
	}

	async function pollPlexPin(pinId: number) {
		const maxAttempts = 60;
		for (let i = 0; i < maxAttempts; i++) {
			await new Promise((r) => setTimeout(r, 3000));
			if (!plexPending) return;
			try {
				const res = await fetch(API.plexAuthPoll(pinId));
				if (!res.ok) break;
				const data = await res.json();
				if (data.completed && data.auth_token) {
					await finishPlexLogin(data.auth_token);
					return;
				}
			} catch {
				break;
			}
		}
		error = 'Plex authentication timed out or was cancelled';
		plexPending = false;
	}

	async function finishPlexLogin(plexToken: string) {
		const res = await fetch(API.plexLogin(), {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ plex_token: plexToken }),
		});
		if (!res.ok) {
			const data = await res.json().catch(() => ({}));
			error = data.detail || 'Plex login failed';
			plexPending = false;
			return;
		}
		const data = await res.json();
		authStore.setToken(data.token, data.username, data.role);
		goto('/');
	}

	function cancelPlexLogin() {
		plexPending = false;
	}

	async function handleEmbyLogin(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		embyLoading = true;
		try {
			const res = await fetch(API.embyLogin(), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username: embyUsername, password: embyPassword }),
			});
			if (!res.ok) {
				const data = await res.json().catch(() => ({}));
				error = data.detail || 'Emby login failed';
				return;
			}
			const data = await res.json();
			authStore.setToken(data.token, data.username, data.role);
			goto('/');
		} catch {
			error = 'Could not connect to the server';
		} finally {
			embyLoading = false;
		}
	}
</script>

<div class="min-h-screen flex items-center justify-center bg-base-200 p-4">
	<div class="card w-full max-w-sm bg-base-100 shadow-xl">
		<div class="card-body gap-6">
			<div class="flex flex-col items-center gap-3">
				<div class="bg-primary/10 rounded-2xl p-4">
					<Music class="h-10 w-10 text-primary" />
				</div>
				<div class="text-center">
					<h1 class="text-2xl font-bold">Musicseerr</h1>
					<p class="text-base-content/60 text-sm mt-1">Sign in to continue</p>
				</div>
			</div>

			<form onsubmit={handleLogin} class="flex flex-col gap-4">
				{#if error}
					<div class="alert alert-error text-sm py-2">{error}</div>
				{/if}

				<label class="form-control">
					<div class="label"><span class="label-text">Username</span></div>
					<input
						type="text"
						class="input input-bordered"
						placeholder="Enter your username"
						bind:value={username}
						required
						autocomplete="username"
					/>
				</label>

				<label class="form-control">
					<div class="label"><span class="label-text">Password</span></div>
					<input
						type="password"
						class="input input-bordered"
						placeholder="••••••••"
						bind:value={password}
						required
						autocomplete="current-password"
					/>
				</label>

				<button type="submit" class="btn btn-primary w-full mt-2" disabled={loading || plexPending}>
					{#if loading}
						<span class="loading loading-spinner loading-sm"></span>
					{/if}
					Sign In
				</button>
			</form>

			<div class="divider text-xs text-base-content/40">or</div>

			{#if plexPending}
				<div class="flex flex-col items-center gap-3">
					<span class="loading loading-spinner loading-md text-warning"></span>
					<p class="text-sm text-base-content/60 text-center">
						Complete sign-in in the Plex window, then return here.
					</p>
					<button class="btn btn-ghost btn-sm" onclick={cancelPlexLogin}>Cancel</button>
				</div>
			{:else}
				<button
					type="button"
					class="btn btn-outline w-full gap-2"
					onclick={handlePlexLogin}
					disabled={loading || embyLoading}
				>
					<PlexIcon class="h-5 w-5" />
					Sign in with Plex
				</button>
			{/if}

			{#if authStore.embySsoEnabled}
				{#if embyExpanded}
					<form onsubmit={handleEmbyLogin} class="flex flex-col gap-3 pt-1">
						<p class="text-xs text-base-content/50 text-center">Sign in with your Emby account</p>
						<input
							type="text"
							class="input input-bordered input-sm"
							placeholder="Emby username"
							bind:value={embyUsername}
							required
							autocomplete="username"
						/>
						<input
							type="password"
							class="input input-bordered input-sm"
							placeholder="Emby password"
							bind:value={embyPassword}
							autocomplete="current-password"
						/>
						<div class="flex gap-2">
							<button
								type="submit"
								class="btn btn-sm flex-1 gap-2"
								style="background-color: #52b54b; border-color: #52b54b; color: white;"
								disabled={embyLoading || loading}
							>
								{#if embyLoading}
									<span class="loading loading-spinner loading-xs"></span>
								{:else}
									<EmbyIcon class="h-4 w-4" />
								{/if}
								Sign in
							</button>
							<button
								type="button"
								class="btn btn-ghost btn-sm"
								onclick={() => { embyExpanded = false; embyUsername = ''; embyPassword = ''; }}
							>
								Cancel
							</button>
						</div>
					</form>
				{:else}
					<button
						type="button"
						class="btn btn-outline w-full gap-2"
						onclick={() => (embyExpanded = true)}
						disabled={loading || plexPending}
					>
						<EmbyIcon class="h-5 w-5" />
						Sign in with Emby
					</button>
				{/if}
			{/if}
		</div>
	</div>
</div>
