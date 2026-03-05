let audioElement: HTMLAudioElement | null = null;

export function setAudioElement(el: HTMLAudioElement): void {
	audioElement = el;
}

export function getAudioElement(): HTMLAudioElement {
	if (!audioElement) {
		throw new Error('Audio element not mounted — setAudioElement() must be called before playback');
	}
	return audioElement;
}

export function _resetAudioElement(): void {
	audioElement = null;
}