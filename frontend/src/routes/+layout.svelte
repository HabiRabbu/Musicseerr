<script lang="ts">
	import "../app.css";
	import { goto } from '$app/navigation';
	let query = '';

	function handleSearch(e: Event) {
		e.preventDefault();
		if (query.trim()) {
			goto(`/search?q=${encodeURIComponent(query)}`);
			const modal = document.getElementById('search_modal') as HTMLDialogElement;
			if (modal) modal.close();
		}
	}
</script>

<div data-theme="musicseerr">
<div class="navbar bg-base-100 shadow-sm sticky top-0 z-10">
	<div class="navbar-start">
		<div class="dropdown">
			<div tabindex="0" role="button" class="btn btn-ghost btn-circle" aria-label="Open menu">
				<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7" />
				</svg>
			</div>
			<ul
				tabindex="-1"
				class="menu menu-sm dropdown-content bg-base-100 rounded-box z-1 mt-3 w-52 p-2 shadow">
				<li><a href="/">Homepage</a></li>
				<li><a href="/library">Library</a></li>
				<li><a href="/requests">Requests</a></li>
			</ul>
		</div>
	</div>
	<div class="navbar-center">
		<a href="/" class="btn btn-ghost" aria-label="Home">
			<img src="/logo_wide.png" alt="Musicseerr" class="h-8" />
		</a>
	</div>
	<div class="navbar-end">
		<button type="button" class="btn btn-ghost btn-circle" on:click={() => document.getElementById('search_modal')?.showModal()} aria-label="Open search">
			<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
			</svg>
		</button>
	</div>
</div>

<!-- Search Modal -->
<dialog id="search_modal" class="modal">
	<div class="modal-box">
		<form method="dialog">
			<button class="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" aria-label="Close">✕</button>
		</form>
		<h3 class="font-bold text-lg mb-4">Search</h3>
		<form on:submit|preventDefault={handleSearch}>
			<input
				type="text"
				placeholder="Search albums or artists..."
				bind:value={query}
				class="input input-bordered w-full"
				autofocus
			/>
			<div class="modal-action">
				<button type="submit" class="btn btn-primary">Search</button>
			</div>
		</form>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button aria-label="Close modal">close</button>
	</form>
</dialog>

<slot />
</div>
