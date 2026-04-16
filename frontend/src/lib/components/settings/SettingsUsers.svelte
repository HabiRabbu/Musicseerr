<script lang="ts">
	import { onMount } from 'svelte';
	import { API } from '$lib/constants';
	import { api } from '$lib/api/client';
	import {
		Users,
		Shield,
		Trash2,
		Pencil,
		Check,
		X,
		Infinity as InfinityIcon,
		RotateCcw
	} from 'lucide-svelte';

	interface User {
		username: string;
		role: string;
		auth_provider: string | null;
		can_request: boolean;
		request_quota: number | null;
		quota_days: number | null;
	}

	interface DefaultSettings {
		quota: number | null;
		quota_days: number;
		can_request: boolean;
	}

	let users = $state<User[]>([]);
	let defaults = $state<DefaultSettings>({ quota: 20, quota_days: 7, can_request: true });
	let loading = $state(true);
	let error = $state('');
	let editingUser = $state<string | null>(null);
	let editForm = $state<Partial<User>>({});
	let savingUser = $state(false);
	let deletingUser = $state<string | null>(null);
	let savingDefaults = $state(false);
	let defaultsMessage = $state('');

	async function load() {
		loading = true;
		error = '';
		try {
			[users, defaults] = await Promise.all([
				api.global.get<User[]>(API.adminUsers()),
				api.global.get<DefaultSettings>(API.adminRequestSettings())
			]);
		} catch {
			error = 'Failed to load users';
		} finally {
			loading = false;
		}
	}

	function startEdit(user: User) {
		editingUser = user.username;
		editForm = {
			role: user.role,
			can_request: user.can_request,
			request_quota: user.request_quota,
			quota_days: user.quota_days
		};
	}

	function cancelEdit() {
		editingUser = null;
		editForm = {};
	}

	async function saveUser(username: string) {
		savingUser = true;
		try {
			const body: Record<string, unknown> = {
				role: editForm.role,
				can_request: editForm.can_request
			};
			// null quota_days means "use default"
			if (editForm.request_quota === null && editForm.quota_days === null) {
				body.clear_quota = true;
			} else {
				body.request_quota = editForm.request_quota ?? null;
				body.quota_days = editForm.quota_days ?? null;
			}
			const updated = await api.global.put<User>(API.adminUser(username), body);
			users = users.map((u) => (u.username === username ? updated : u));
			editingUser = null;
		} catch {
			// keep editing open on error
		} finally {
			savingUser = false;
		}
	}

	async function deleteUser(username: string) {
		if (!confirm(`Remove user "${username}"? This cannot be undone.`)) return;
		deletingUser = username;
		try {
			await api.global.delete(API.adminUser(username));
			users = users.filter((u) => u.username !== username);
		} catch {
			// ignore
		} finally {
			deletingUser = null;
		}
	}

	async function saveDefaults() {
		savingDefaults = true;
		defaultsMessage = '';
		try {
			await api.global.put(API.adminRequestSettings(), defaults);
			defaultsMessage = 'Saved';
			setTimeout(() => (defaultsMessage = ''), 2000);
		} catch {
			defaultsMessage = 'Failed to save';
		} finally {
			savingDefaults = false;
		}
	}

	function effectiveQuota(user: User): string {
		if (user.role === 'admin') return 'Unlimited';
		const q = user.request_quota ?? defaults.quota;
		const d = user.quota_days ?? defaults.quota_days;
		if (q === null || q === 0) return 'Unlimited';
		return `${q} / ${d}d`;
	}

	onMount(() => void load());
</script>

<div class="space-y-6">
	<!-- Default quota settings -->
	<div class="card bg-base-200">
		<div class="card-body gap-4">
			<div>
				<h2 class="card-title text-xl flex items-center gap-2">
					<Shield class="h-5 w-5" />
					Default Request Limits
				</h2>
				<p class="text-base-content/60 text-sm mt-1">
					Applied to all users without a personal override. Admins are always unlimited.
				</p>
			</div>

			<div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
				<label class="form-control">
					<div class="label"><span class="label-text">Requests per window</span></div>
					<input
						type="number"
						min="0"
						class="input input-bordered input-sm"
						placeholder="Unlimited"
						value={defaults.quota ?? ''}
						oninput={(e) => {
							const v = (e.target as HTMLInputElement).value;
							defaults.quota = v === '' ? null : parseInt(v);
						}}
					/>
					<div class="label">
						<span class="label-text-alt text-base-content/50">0 or blank = unlimited</span>
					</div>
				</label>

				<label class="form-control">
					<div class="label"><span class="label-text">Window (days)</span></div>
					<input
						type="number"
						min="1"
						class="input input-bordered input-sm"
						bind:value={defaults.quota_days}
					/>
				</label>

				<label class="form-control">
					<div class="label"><span class="label-text">New users can request</span></div>
					<div class="flex items-center gap-3 mt-2">
						<input
							type="checkbox"
							class="toggle toggle-primary toggle-sm"
							bind:checked={defaults.can_request}
						/>
						<span class="text-sm">{defaults.can_request ? 'Yes' : 'No'}</span>
					</div>
				</label>
			</div>

			<div class="flex items-center gap-3">
				<button
					class="btn btn-primary btn-sm"
					onclick={() => void saveDefaults()}
					disabled={savingDefaults}
				>
					{#if savingDefaults}
						<span class="loading loading-spinner loading-xs"></span>
					{/if}
					Save Defaults
				</button>
				{#if defaultsMessage}
					<span class="text-sm text-success">{defaultsMessage}</span>
				{/if}
			</div>
		</div>
	</div>

	<!-- User table -->
	<div class="card bg-base-200">
		<div class="card-body gap-4">
			<div class="flex items-center justify-between">
				<h2 class="card-title text-xl flex items-center gap-2">
					<Users class="h-5 w-5" />
					Users
				</h2>
				<button class="btn btn-ghost btn-sm gap-1" onclick={() => void load()}>
					<RotateCcw class="h-3.5 w-3.5" />
					Refresh
				</button>
			</div>

			{#if loading}
				<div class="flex justify-center py-8">
					<span class="loading loading-spinner loading-md"></span>
				</div>
			{:else if error}
				<div class="alert alert-error text-sm py-2">{error}</div>
			{:else if users.length === 0}
				<p class="text-base-content/50 text-sm py-4 text-center">No users yet.</p>
			{:else}
				<div class="overflow-x-auto">
					<table class="table table-sm">
						<thead>
							<tr>
								<th>User</th>
								<th>Role</th>
								<th>Can Request</th>
								<th>Quota (req/window)</th>
								<th></th>
							</tr>
						</thead>
						<tbody>
							{#each users as user (user.username)}
								{#if editingUser === user.username}
									<tr class="bg-base-300/40">
										<td>
											<div class="flex flex-col">
												<span class="font-medium">{user.username}</span>
												{#if user.auth_provider}
													<span class="text-xs text-base-content/40">{user.auth_provider}</span>
												{/if}
											</div>
										</td>
										<td>
											<select class="select select-bordered select-xs" bind:value={editForm.role}>
												<option value="admin">Admin</option>
												<option value="user">User</option>
											</select>
										</td>
										<td>
											<input
												type="checkbox"
												class="toggle toggle-primary toggle-xs"
												bind:checked={editForm.can_request}
											/>
										</td>
										<td>
											<div class="flex items-center gap-1">
												<input
													type="number"
													min="0"
													placeholder="Default"
													class="input input-bordered input-xs w-20"
													value={editForm.request_quota ?? ''}
													oninput={(e) => {
														const v = (e.target as HTMLInputElement).value;
														editForm.request_quota = v === '' ? null : parseInt(v);
													}}
												/>
												<span class="text-xs text-base-content/50">/</span>
												<input
													type="number"
													min="1"
													placeholder="Default"
													class="input input-bordered input-xs w-20"
													value={editForm.quota_days ?? ''}
													oninput={(e) => {
														const v = (e.target as HTMLInputElement).value;
														editForm.quota_days = v === '' ? null : parseInt(v);
													}}
												/>
												<span class="text-xs text-base-content/50">days</span>
											</div>
										</td>
										<td>
											<div class="flex gap-1">
												<button
													class="btn btn-ghost btn-xs btn-circle"
													onclick={() => void saveUser(user.username)}
													disabled={savingUser}
												>
													{#if savingUser}
														<span class="loading loading-spinner loading-xs"></span>
													{:else}
														<Check class="h-3.5 w-3.5 text-success" />
													{/if}
												</button>
												<button class="btn btn-ghost btn-xs btn-circle" onclick={cancelEdit}>
													<X class="h-3.5 w-3.5 text-error" />
												</button>
											</div>
										</td>
									</tr>
								{:else}
									<tr>
										<td>
											<div class="flex flex-col">
												<span class="font-medium">{user.username}</span>
												{#if user.auth_provider}
													<span class="text-xs text-base-content/40">{user.auth_provider}</span>
												{/if}
											</div>
										</td>
										<td>
											<span
												class="badge badge-sm {user.role === 'admin'
													? 'badge-primary'
													: 'badge-ghost'}"
											>
												{user.role}
											</span>
										</td>
										<td>
											{#if user.role === 'admin' || user.can_request}
												<span class="text-success text-xs">Yes</span>
											{:else}
												<span class="text-error text-xs">No</span>
											{/if}
										</td>
										<td class="text-sm text-base-content/70">
											{#if user.role === 'admin'}
												<span class="flex items-center gap-1 text-base-content/40">
													<InfinityIcon class="h-3.5 w-3.5" /> Unlimited
												</span>
											{:else}
												{effectiveQuota(user)}
												{#if user.request_quota === null && user.quota_days === null}
													<span class="text-xs text-base-content/40 ml-1">(default)</span>
												{/if}
											{/if}
										</td>
										<td>
											<div class="flex gap-1">
												<button
													class="btn btn-ghost btn-xs btn-circle"
													onclick={() => startEdit(user)}
												>
													<Pencil class="h-3.5 w-3.5" />
												</button>
												<button
													class="btn btn-ghost btn-xs btn-circle text-error"
													onclick={() => void deleteUser(user.username)}
													disabled={deletingUser === user.username}
												>
													{#if deletingUser === user.username}
														<span class="loading loading-spinner loading-xs"></span>
													{:else}
														<Trash2 class="h-3.5 w-3.5" />
													{/if}
												</button>
											</div>
										</td>
									</tr>
								{/if}
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	</div>
</div>
