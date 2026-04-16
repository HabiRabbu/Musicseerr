import { browser } from '$app/environment';

const TOKEN_KEY = 'musicseerr_token';

function createAuthStore() {
	let token = $state<string | null>(browser ? localStorage.getItem(TOKEN_KEY) : null);
	let username = $state<string | null>(null);
	let role = $state<string | null>(null);
	let authEnabled = $state(false);
	let setupRequired = $state(false);
	let embySsoEnabled = $state(false);
	let checked = $state(false);

	async function checkStatus() {
		try {
			const res = await fetch('/api/v1/auth/status');
			if (res.ok) {
				const data = await res.json();
				authEnabled = data.auth_enabled;
				setupRequired = data.setup_required;
				embySsoEnabled = data.emby_enabled ?? false;
			}
		} catch {
			// backend unreachable — assume no auth
		}
		checked = true;
	}

	function getToken(): string | null {
		return token;
	}

	function setToken(t: string, user: string, userRole: string) {
		token = t;
		username = user;
		role = userRole;
		if (browser) localStorage.setItem(TOKEN_KEY, t);
	}

	function clearToken() {
		token = null;
		username = null;
		role = null;
		if (browser) localStorage.removeItem(TOKEN_KEY);
	}

	function isLoggedIn(): boolean {
		return !!token;
	}

	return {
		get token() {
			return token;
		},
		get username() {
			return username;
		},
		get role() {
			return role;
		},
		get authEnabled() {
			return authEnabled;
		},
		get setupRequired() {
			return setupRequired;
		},
		get embySsoEnabled() {
			return embySsoEnabled;
		},
		get checked() {
			return checked;
		},
		checkStatus,
		getToken,
		setToken,
		clearToken,
		isLoggedIn
	};
}

export const authStore = createAuthStore();
