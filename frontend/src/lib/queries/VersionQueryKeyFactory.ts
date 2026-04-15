export const VersionQueryKeyFactory = {
	prefix: ['version'] as const,
	info: () => [...VersionQueryKeyFactory.prefix, 'info'] as const,
	updateCheck: () => [...VersionQueryKeyFactory.prefix, 'update-check'] as const,
	releases: () => [...VersionQueryKeyFactory.prefix, 'releases'] as const
};
