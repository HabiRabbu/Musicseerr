<script lang="ts">
	import { goto } from '$app/navigation';
	import { authStore } from '$lib/stores/auth.svelte';
	import { Music } from 'lucide-svelte';

	let username = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);

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

				<button type="submit" class="btn btn-primary w-full mt-2" disabled={loading}>
					{#if loading}
						<span class="loading loading-spinner loading-sm"></span>
					{/if}
					Sign In
				</button>
			</form>
		</div>
	</div>
</div>
