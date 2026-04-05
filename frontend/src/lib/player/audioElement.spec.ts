import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./audioEngine', () => {
	const MockAudioEngine = vi.fn().mockImplementation(() => ({
		connect: vi.fn(),
		destroy: vi.fn(),
		isConnected: vi.fn(() => true)
	}));
	return { AudioEngine: MockAudioEngine };
});

import {
	_resetAudioElement,
	getAudioElement,
	getAudioEngine,
	tryGetAudioEngine,
	setAudioElement
} from './audioElement';

describe('audioElement registry', () => {
	beforeEach(() => {
		_resetAudioElement();
		vi.clearAllMocks();
	});

	it('throws when getting audio element before registration', () => {
		expect.assertions(1);
		expect(() => getAudioElement()).toThrow('Audio element not mounted');
	});

	it('returns registered audio element', () => {
		expect.assertions(1);
		const audio = { src: '' } as HTMLAudioElement;
		setAudioElement(audio);
		expect(getAudioElement()).toBe(audio);
	});

	it('allows replacing the registered audio element', () => {
		expect.assertions(1);
		const first = { src: '' } as HTMLAudioElement;
		const second = { src: '' } as HTMLAudioElement;
		setAudioElement(first);
		setAudioElement(second);
		expect(getAudioElement()).toBe(second);
	});

	it('is idempotent for the same element', () => {
		expect.assertions(1);
		const audio = { src: '' } as HTMLAudioElement;
		setAudioElement(audio);
		const engineFirst = tryGetAudioEngine();
		setAudioElement(audio);
		const engineSecond = tryGetAudioEngine();
		expect(engineFirst).toBe(engineSecond);
	});

	it('throws getAudioEngine before registration', () => {
		expect.assertions(1);
		expect(() => getAudioEngine()).toThrow('Audio engine not initialized');
	});

	it('returns engine after setAudioElement', () => {
		expect.assertions(2);
		const audio = { src: '' } as HTMLAudioElement;
		setAudioElement(audio);
		const engine = getAudioEngine();
		expect(engine).toBeDefined();
		expect(engine.connect).toBeDefined();
	});

	it('tryGetAudioEngine returns null before registration', () => {
		expect.assertions(1);
		expect(tryGetAudioEngine()).toBeNull();
	});

	it('tryGetAudioEngine returns engine after registration', () => {
		expect.assertions(1);
		const audio = { src: '' } as HTMLAudioElement;
		setAudioElement(audio);
		expect(tryGetAudioEngine()).not.toBeNull();
	});

	it('_resetAudioElement destroys engine', () => {
		expect.assertions(2);
		const audio = { src: '' } as HTMLAudioElement;
		setAudioElement(audio);
		const engine = getAudioEngine();
		_resetAudioElement();
		expect(engine.destroy).toHaveBeenCalled();
		expect(tryGetAudioEngine()).toBeNull();
	});
});
