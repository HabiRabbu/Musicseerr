import { EQ_FREQUENCIES, EQ_BAND_COUNT, EQ_MIN_GAIN, EQ_MAX_GAIN } from '../stores/eqPresets';

const DEFAULT_Q = 1.4;

export class AudioEngine {
	private context: AudioContext | null = null;
	private source: MediaElementAudioSourceNode | null = null;
	private filters: BiquadFilterNode[] = [];
	private connectedElement: HTMLAudioElement | null = null;

	connect(audio: HTMLAudioElement): void {
		if (this.connectedElement === audio) return;
		if (this.connectedElement) {
			this.destroy();
		}

		this.context = new AudioContext();
		this.source = this.context.createMediaElementSource(audio);

		this.filters = EQ_FREQUENCIES.map((freq) => {
			const filter = this.context!.createBiquadFilter();
			filter.type = 'peaking';
			filter.frequency.value = freq;
			filter.Q.value = DEFAULT_Q;
			filter.gain.value = 0;
			return filter;
		});

		let prev: AudioNode = this.source;
		for (const filter of this.filters) {
			prev.connect(filter);
			prev = filter;
		}
		prev.connect(this.context.destination);

		this.connectedElement = audio;
	}

	setBandGain(index: number, dB: number): void {
		if (index < 0 || index >= EQ_BAND_COUNT || !this.filters[index]) return;
		this.filters[index].gain.value = Math.max(EQ_MIN_GAIN, Math.min(EQ_MAX_GAIN, dB));
	}

	setAllGains(gains: readonly number[]): void {
		for (let i = 0; i < EQ_BAND_COUNT; i++) {
			if (this.filters[i]) {
				this.filters[i].gain.value = Math.max(EQ_MIN_GAIN, Math.min(EQ_MAX_GAIN, gains[i] ?? 0));
			}
		}
	}

	setEnabled(enabled: boolean, storedGains: readonly number[]): void {
		if (enabled) {
			this.setAllGains(storedGains);
		} else {
			for (const filter of this.filters) {
				filter.gain.value = 0;
			}
		}
	}

	getFrequencies(): readonly number[] {
		return EQ_FREQUENCIES;
	}

	isConnected(): boolean {
		return this.connectedElement !== null;
	}

	async resume(): Promise<void> {
		if (this.context && this.context.state === 'suspended') {
			await this.context.resume();
		}
	}

	destroy(): void {
		for (const filter of this.filters) {
			filter.disconnect();
		}
		this.source?.disconnect();
		if (this.context && this.context.state !== 'closed') {
			void this.context.close();
		}
		this.filters = [];
		this.source = null;
		this.context = null;
		this.connectedElement = null;
	}
}
