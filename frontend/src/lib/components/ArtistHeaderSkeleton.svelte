<script lang="ts">
</script>

<!-- Hero Banner Skeleton - matches the Spotify-like hero design -->
<div class="relative w-full min-h-[420px] md:min-h-[480px] mb-8">
	<!-- Gradient background skeleton -->
	<div class="absolute inset-0 bg-gradient-to-b from-base-300/80 via-base-300/40 to-base-100"></div>

	<!-- Hero content -->
	<div class="relative z-10 flex flex-col items-center justify-end h-full min-h-[420px] md:min-h-[480px] pb-8 pt-16 px-4">
		<!-- Circular artist image skeleton -->
		<div class="skeleton w-40 h-40 md:w-56 md:h-56 rounded-full mb-6 shadow-2xl"></div>

		<!-- Artist name skeleton -->
		<div class="skeleton h-12 md:h-16 w-64 md:w-96 mb-4"></div>

		<!-- Quick info badges skeleton -->
		<div class="flex flex-wrap justify-center gap-3 mb-4">
			<div class="skeleton h-6 w-20 rounded-full"></div>
			<div class="skeleton h-6 w-28 rounded-full"></div>
			<div class="skeleton h-6 w-24 rounded-full"></div>
		</div>

		<!-- Tags skeleton -->
		<div class="flex flex-wrap justify-center gap-2 mb-6 max-w-2xl">
			{#each Array(5) as _}
				<div class="skeleton h-7 w-16 rounded-full"></div>
			{/each}
		</div>

		<!-- Description skeleton -->
		<div class="w-full max-w-2xl bg-base-200/50 rounded-lg p-4">
			<div class="space-y-2">
				<div class="skeleton h-4 w-full"></div>
				<div class="skeleton h-4 w-full"></div>
				<div class="skeleton h-4 w-4/5"></div>
			</div>
		</div>
	</div>
</div>
