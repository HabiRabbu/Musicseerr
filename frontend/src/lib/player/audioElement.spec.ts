import { beforeEach, describe, expect, it } from 'vitest';

import { _resetAudioElement, getAudioElement, setAudioElement } from './audioElement';

describe('audioElement registry', () => {
	beforeEach(() => {
		_resetAudioElement();
	});

	it('throws when getting audio element before registration', () => {
		expect(() => getAudioElement()).toThrow('Audio element not mounted');
	});

	it('returns registered audio element', () => {
		const audio = {
			src: '',
		} as HTMLAudioElement;

		setAudioElement(audio);

		expect(getAudioElement()).toBe(audio);
	});

	it('allows replacing the registered audio element', () => {
		const first = { src: '' } as HTMLAudioElement;
		const second = { src: '' } as HTMLAudioElement;

		setAudioElement(first);
		setAudioElement(second);

		expect(getAudioElement()).toBe(second);
	});
});