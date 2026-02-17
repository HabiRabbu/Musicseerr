import type { SourceType } from './types';
import { HowlerPlaybackBase } from './HowlerPlaybackBase';

export class LocalPlaybackSource extends HowlerPlaybackBase {
	readonly type: SourceType = 'howler';
}
