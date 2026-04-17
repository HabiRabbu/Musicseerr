export const PlaylistQueryKeyFactory = {
	prefix: ['playlists'] as const,
	list: () => [...PlaylistQueryKeyFactory.prefix, 'list'] as const
};
