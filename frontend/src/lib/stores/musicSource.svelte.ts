import { PAGE_SOURCE_KEYS } from '$lib/constants';
import { api } from '$lib/api/client';
import { PersistedState } from 'runed';

export type MusicSourceType = 'listenbrainz' | 'lastfm';
export type MusicSourcePage = keyof typeof PAGE_SOURCE_KEYS;

const CACHED_SOURCE_KEY = 'musicseerr_primary_source';
const DEFAULT_SOURCE: MusicSourceType = 'listenbrainz';

function isMusicSource(value: unknown): value is MusicSourceType {
	return value === 'listenbrainz' || value === 'lastfm';
}

class MusicSourceBackend {
	private readonly primary = new PersistedState<MusicSourceType>(CACHED_SOURCE_KEY, DEFAULT_SOURCE);
	private readonly pages = new Map<MusicSourcePage, PersistedState<MusicSourceType>>();

	loaded = $state(false);

	private loadPromise: Promise<void> | null = null;
	private mutationVersion = 0;

	private normalize(value: unknown): MusicSourceType {
		return isMusicSource(value) ? value : DEFAULT_SOURCE;
	}

	private getPageState(page: MusicSourcePage): PersistedState<MusicSourceType> {
		const existing = this.pages.get(page);
		if (existing) return existing;

		const state = new PersistedState<MusicSourceType>(
			PAGE_SOURCE_KEYS[page],
			this.normalize(this.primary.current)
		);
		this.pages.set(page, state);
		return state;
	}

	get primaryCurrent(): MusicSourceType {
		return this.normalize(this.primary.current);
	}

	set primaryCurrent(source: MusicSourceType) {
		this.mutationVersion += 1;
		this.primary.current = source;
		this.loaded = true;
	}

	getPageCurrent(page: MusicSourcePage): MusicSourceType {
		return this.normalize(this.getPageState(page).current);
	}

	setPageCurrent(page: MusicSourcePage, source: MusicSourceType): void {
		this.getPageState(page).current = source;
	}

	async load(): Promise<void> {
		if (this.loaded) return;
		if (this.loadPromise) return this.loadPromise;

		const loadStartedAtVersion = this.mutationVersion;

		this.loadPromise = (async () => {
			try {
				const data = await api.global.get<{ source: unknown }>('/api/v1/settings/primary-source');
				const fetched = this.normalize(data.source);

				if (this.mutationVersion === loadStartedAtVersion) {
					this.primary.current = fetched;
				}
			} catch {
				// keep persisted/default source on failure
			} finally {
				this.loaded = true;
				this.loadPromise = null;
			}
		})();

		return this.loadPromise;
	}

	/**
	 * Saves the current primary source to the backend.
	 * @returns true if the save was successful, false otherwise.
	 */
	async savePrimaryCurrent(source: MusicSourceType): Promise<boolean> {
		const saveVersion = ++this.mutationVersion;

		try {
			await api.global.put('/api/v1/settings/primary-source', { source });
			this.primary.current = source;

			if (this.mutationVersion === saveVersion) {
				this.loaded = true;
			}

			return true;
		} catch {
			return false;
		}
	}
}

const backend = new MusicSourceBackend();

export class MusicSource {
	readonly page: () => MusicSourcePage;

	constructor(page: () => MusicSourcePage) {
		this.page = page;
		void backend.load();
	}

	private resolvePage(): MusicSourcePage {
		return this.page();
	}

	get current(): MusicSourceType {
		return backend.getPageCurrent(this.resolvePage());
	}

	set current(source: MusicSourceType) {
		backend.setPageCurrent(this.resolvePage(), source);
	}

	get ready(): boolean {
		return backend.loaded;
	}

	/**
	 * Saves the current primary source to the backend.
	 * This should be called when the user explicitly changes their source preference, to ensure it persists across sessions and devices.
	 */
	async save(): Promise<boolean> {
		return backend.savePrimaryCurrent(this.current);
	}
}
