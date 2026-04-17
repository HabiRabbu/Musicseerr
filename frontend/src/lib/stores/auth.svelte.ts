import { browser } from '$app/environment';

const TOKEN_KEY = 'musicseerr_token';

function parseJwtPayload(token: string): Record<string, unknown> | null {
	try {
		const parts = token.split('.');
		if (parts.length !== 3) return null;
		const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
		return JSON.parse(atob(payload));
	} catch {
		return null;
	}
}

function createAuthStore() {
	const storedToken = browser ? localStorage.getItem(TOKEN_KEY) : null;
	const storedPayload = storedToken ? parseJwtPayload(storedToken) : null;

	let token = $state<string | null>(storedToken);
	let username = $state<string | null>(storedPayload ? String(storedPayload.sub ?? '') : null);
	let role = $state<string | null>(storedPayload ? String(storedPayload.role ?? '') : null);
	let authEnabled = $state(false);
	let setupRequired = $state(false);
	let embySsoEnabled = $state(false);
	let plexSsoEnabled = $state(false);
	let isPrimaryAdmin = $state(false);
	let checked = $state(false);

	async function checkStatus() {
		try {
			const res = await fetch('/api/v1/auth/status');
			if (res.ok) {
				const data = await res.json();
				authEnabled = data.auth_enabled;
				setupRequired = data.setup_required;
				embySsoEnabled = data.emby_enabled ?? false;
				plexSsoEnabled = data.plex_enabled ?? false;
			}
		} catch {
			// backend unreachable — assume no auth
		}
		checked = true;
	}

	function getToken(): string | null {
		return token;
	}

	function setToken(t: string, user: string, userRole: string, primary = false) {
		token = t;
		username = user;
		role = userRole;
		isPrimaryAdmin = primary;
		if (browser) localStorage.setItem(TOKEN_KEY, t);
	}

	function clearToken() {
		token = null;
		username = null;
		role = null;
		isPrimaryAdmin = false;
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
		get plexSsoEnabled() {
			return plexSsoEnabled;
		},
		get isPrimaryAdmin() {
			return isPrimaryAdmin;
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
