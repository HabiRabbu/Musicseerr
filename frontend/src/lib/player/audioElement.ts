import { AudioEngine } from './audioEngine';

let audioElement: HTMLAudioElement | null = null;
let engine: AudioEngine | null = null;

export function setAudioElement(el: HTMLAudioElement): void {
	if (audioElement === el && engine) return;
	if (engine) {
		engine.destroy();
		engine = null;
	}
	audioElement = el;
	try {
		const newEngine = new AudioEngine();
		newEngine.connect(el);
		engine = newEngine;
	} catch {
		// connect() can throw (InvalidStateError, SecurityError).
		// Audio element is still usable without EQ — engine stays null.
	}
}

export function getAudioElement(): HTMLAudioElement {
	if (!audioElement) {
		throw new Error('Audio element not mounted — setAudioElement() must be called before playback');
	}
	return audioElement;
}

export function getAudioEngine(): AudioEngine {
	if (!engine) {
		throw new Error('Audio engine not initialized — setAudioElement() must be called first');
	}
	return engine;
}

export function tryGetAudioEngine(): AudioEngine | null {
	return engine;
}

export function _resetAudioElement(): void {
	engine?.destroy();
	engine = null;
	audioElement = null;
}
