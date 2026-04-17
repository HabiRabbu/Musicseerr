<script lang="ts">
	import type {
		AlbumBasicInfo,
		YouTubeTrackLink,
		YouTubeQuotaStatus,
		JellyfinAlbumMatch,
		JellyfinTrackInfo,
		LocalAlbumMatch,
		LocalTrackInfo,
		NavidromeAlbumMatch,
		NavidromeTrackInfo,
		PlexAlbumMatch,
		PlexTrackInfo
	} from '$lib/types';
	import type { MenuItem } from '$lib/components/ContextMenu.svelte';
	import type { RenderedTrackSection } from './albumTrackResolvers';
	import { resolveSourceTrack } from './albumTrackResolvers';
	import { normalizeDiscNumber, getDiscTrackKey } from '$lib/player/queueHelpers';
	import { formatDuration } from '$lib/utils/formatting';
	import { colors } from '$lib/colors';
	import { playerStore } from '$lib/stores/player.svelte';
	import NowPlayingIndicator from '$lib/components/NowPlayingIndicator.svelte';
	import TrackPlayButton from '$lib/components/TrackPlayButton.svelte';
	import TrackPreviewButton from '$lib/components/TrackPreviewButton.svelte';
	import TrackSourceButton from '$lib/components/TrackSourceButton.svelte';
	import ContextMenu from '$lib/components/ContextMenu.svelte';
	import JellyfinIcon from '$lib/components/JellyfinIcon.svelte';
	import LocalFilesIcon from '$lib/components/LocalFilesIcon.svelte';
	import NavidromeIcon from '$lib/components/NavidromeIcon.svelte';
	import PlexIcon from '$lib/components/PlexIcon.svelte';

	interface Props {
		album: AlbumBasicInfo;
		renderedTrackSections: RenderedTrackSection[];
		trackLinkMap: Map<string, YouTubeTrackLink>;
		jellyfinMatch: JellyfinAlbumMatch | null;
		localMatch: LocalAlbumMatch | null;
		navidromeMatch: NavidromeAlbumMatch | null;
		plexMatch: PlexAlbumMatch | null;
		jellyfinTrackMap: Map<string, JellyfinTrackInfo>;
		localTrackMap: Map<string, LocalTrackInfo>;
		navidromeTrackMap: Map<string, NavidromeTrackInfo>;
		plexTrackMap: Map<string, PlexTrackInfo>;
		jellyfinTracks: JellyfinTrackInfo[];
		localTracks: LocalTrackInfo[];
		navidromeTracks: NavidromeTrackInfo[];
		plexTracks: PlexTrackInfo[];
		trackLinks: YouTubeTrackLink[];
		youtubeEnabled: boolean;
		youtubeApiConfigured: boolean;
		previewCacheMap: Map<string, boolean>;
		jellyfinEnabled: boolean;
		localfilesEnabled: boolean;
		navidromeEnabled: boolean;
		plexEnabled: boolean;
		onPlaySourceTrack: (
			source: 'jellyfin' | 'local' | 'navidrome' | 'plex',
			trackPosition: number,
			discNumber: number,
			title: string
		) => void;
		onTrackGenerated: (link: YouTubeTrackLink) => void;
		onQuotaUpdate: (q: YouTubeQuotaStatus) => void;
		getTrackContextMenuItems: (
			track: { position: number; disc_number?: number | null; title: string },
			resolvedLocal: LocalTrackInfo | null,
			resolvedJellyfin: JellyfinTrackInfo | null,
			resolvedNavidrome: NavidromeTrackInfo | null,
			resolvedPlex: PlexTrackInfo | null
		) => MenuItem[];
	}

	let {
		album,
		renderedTrackSections,
		trackLinkMap,
		jellyfinMatch,
		localMatch,
		navidromeMatch,
		plexMatch,
		jellyfinTrackMap,
		localTrackMap,
		navidromeTrackMap,
		plexTrackMap,
		jellyfinTracks,
		localTracks,
		navidromeTracks,
		plexTracks,
		trackLinks,
		youtubeEnabled,
		youtubeApiConfigured,
		previewCacheMap,
		jellyfinEnabled,
		localfilesEnabled,
		navidromeEnabled,
		plexEnabled,
		onPlaySourceTrack,
		onTrackGenerated,
		onQuotaUpdate,
		getTrackContextMenuItems
	}: Props = $props();
</script>

<div class="bg-base-200 rounded-box overflow-visible">
	<ul class="list">
		{#each renderedTrackSections as section (section.discNumber)}
			{#if renderedTrackSections.length > 1}
				<li class="list-row min-h-0 cursor-default px-3 sm:px-4 pt-4 pb-2">
					<div
						class="inline-flex items-center gap-2 rounded-full border border-base-content/10 bg-base-100/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] opacity-70"
					>
						<span class="h-1.5 w-1.5 rounded-full bg-accent"></span>
						Disc {section.discNumber}
					</div>
				</li>
			{/if}
			{#each section.items as row (row.globalIndex)}
				{@const track = row.track}
				{@const trackDiscNumber = normalizeDiscNumber(track.disc_number)}
				{@const tl = trackLinkMap.get(getDiscTrackKey(track)) ?? null}
				{@const jellyfinTrack = resolveSourceTrack(
					trackDiscNumber,
					track.position,
					row.globalIndex,
					jellyfinTrackMap,
					jellyfinTracks
				)}
				{@const localTrack = resolveSourceTrack(
					trackDiscNumber,
					track.position,
					row.globalIndex,
					localTrackMap,
					localTracks
				)}
				{@const navidromeTrack = resolveSourceTrack(
					trackDiscNumber,
					track.position,
					row.globalIndex,
					navidromeTrackMap,
					navidromeTracks
				)}
				{@const plexTrack = resolveSourceTrack(
					trackDiscNumber,
					track.position,
					row.globalIndex,
					plexTrackMap,
					plexTracks
				)}
				{@const isCurrentlyPlaying =
					playerStore.nowPlaying?.albumId === album.musicbrainz_id &&
					(playerStore.currentQueueItem?.discNumber ?? 1) === trackDiscNumber &&
					playerStore.currentQueueItem?.trackNumber === track.position &&
					playerStore.isPlaying}
				{@const showJellyfinBtn = jellyfinEnabled && jellyfinMatch?.found}
				{@const showLocalBtn = localfilesEnabled && localMatch?.found}
				{@const showNavidromeBtn = navidromeEnabled && navidromeMatch?.found}
				{@const showPlexBtn = plexEnabled && plexMatch?.found}
				{@const hasAnySource =
					tl !== null ||
					jellyfinTrack !== null ||
					localTrack !== null ||
					navidromeTrack !== null ||
					plexTrack !== null}
				{@const showPreview = youtubeApiConfigured && !hasAnySource}
				<li
					class="list-row group hover:bg-base-300/50 transition-colors p-3 sm:p-4"
					style={isCurrentlyPlaying ? `background-color: ${colors.accent}20;` : ''}
				>
					<div class="list-col-grow flex items-center gap-4 w-full">
						<div
							class="font-medium w-8 text-center shrink-0 {isCurrentlyPlaying
								? ''
								: 'text-base-content/60'}"
							style={isCurrentlyPlaying ? `color: ${colors.accent};` : ''}
						>
							{#if isCurrentlyPlaying}
								<NowPlayingIndicator />
							{:else}
								{track.position}
							{/if}
						</div>

						<div class="flex-1 min-w-0">
							<div
								class="font-medium truncate"
								style={isCurrentlyPlaying ? `color: ${colors.accent};` : ''}
							>
								{track.title}
							</div>
						</div>

						<div class="text-base-content/60 text-sm shrink-0">
							{formatDuration(track.length)}
						</div>

						{#if youtubeEnabled || showPreview || showJellyfinBtn || showLocalBtn || showNavidromeBtn || showPlexBtn}
							<div class="flex items-center gap-1.5 shrink-0 ml-auto">
								{#if showPreview}
									<TrackPreviewButton
										artist={album.artist_name}
										track={track.title}
										ytConfigured={youtubeApiConfigured}
										initialCached={previewCacheMap.get(
											`${album.artist_name.toLowerCase()}|${track.title.toLowerCase()}`
										) ?? null}
										albumId={album.musicbrainz_id}
										coverUrl={album.cover_url ?? null}
										artistId={album.artist_id}
									/>
								{/if}

								{#if youtubeEnabled}
									<TrackPlayButton
										trackNumber={track.position}
										discNumber={trackDiscNumber}
										trackName={track.title}
										trackLink={tl}
										allTrackLinks={trackLinks}
										albumId={album.musicbrainz_id}
										albumName={album.title}
										artistName={album.artist_name}
										coverUrl={album.cover_url ?? null}
										artistId={album.artist_id}
										apiConfigured={youtubeApiConfigured}
										onGenerated={onTrackGenerated}
										{onQuotaUpdate}
									/>
								{/if}

								{#if showJellyfinBtn}
									<TrackSourceButton
										available={jellyfinTrack !== null}
										sourceColor="rgb(var(--brand-jellyfin))"
										onclick={() =>
											onPlaySourceTrack('jellyfin', track.position, trackDiscNumber, track.title)}
										ariaLabel={jellyfinTrack ? 'Play on Jellyfin' : 'Not available on Jellyfin'}
									>
										{#snippet icon()}
											<JellyfinIcon class="h-4 w-4" />
										{/snippet}
									</TrackSourceButton>
								{/if}

								{#if showLocalBtn}
									<TrackSourceButton
										available={localTrack !== null}
										sourceColor="rgb(var(--brand-localfiles))"
										onclick={() =>
											onPlaySourceTrack('local', track.position, trackDiscNumber, track.title)}
										ariaLabel={localTrack ? 'Play local file' : 'Not available locally'}
									>
										{#snippet icon()}
											<LocalFilesIcon class="h-4 w-4" />
										{/snippet}
									</TrackSourceButton>
								{/if}

								{#if showNavidromeBtn}
									<TrackSourceButton
										available={navidromeTrack !== null}
										sourceColor="rgb(var(--brand-navidrome))"
										onclick={() =>
											onPlaySourceTrack('navidrome', track.position, trackDiscNumber, track.title)}
										ariaLabel={navidromeTrack ? 'Play on Navidrome' : 'Not available on Navidrome'}
									>
										{#snippet icon()}
											<NavidromeIcon class="h-4 w-4" />
										{/snippet}
									</TrackSourceButton>
								{/if}

								{#if showPlexBtn}
									<TrackSourceButton
										available={plexTrack !== null}
										sourceColor="rgb(var(--brand-plex))"
										onclick={() =>
											onPlaySourceTrack('plex', track.position, trackDiscNumber, track.title)}
										ariaLabel={plexTrack ? 'Play on Plex' : 'Not available on Plex'}
									>
										{#snippet icon()}
											<PlexIcon class="h-4 w-4" />
										{/snippet}
									</TrackSourceButton>
								{/if}

								<div>
									<ContextMenu
										items={getTrackContextMenuItems(
											track,
											localTrack,
											jellyfinTrack,
											navidromeTrack,
											plexTrack
										)}
										position="end"
										size="xs"
									/>
								</div>
							</div>
						{/if}
					</div>
				</li>
			{/each}
		{/each}
	</ul>
</div>
