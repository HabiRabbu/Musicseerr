<script lang="ts">
</script>

<div class="mb-8">
	<!-- Hero section skeleton -->
	<div class="relative mb-8">
		<div class="skeleton w-full h-64 md:h-96"></div>
		<div class="absolute inset-0 bg-gradient-to-t from-base-300 to-transparent"></div>
	</div>

	<!-- Artist info skeleton -->
	<div class="container mx-auto px-4">
		<div class="flex flex-col md:flex-row gap-6 items-start">
			<!-- Artist image skeleton -->
			<div class="skeleton w-48 h-48 rounded-full flex-shrink-0"></div>
			
			<!-- Artist details skeleton -->
			<div class="flex-1 space-y-4">
				<div class="skeleton h-10 w-3/4 mb-2"></div>
				<div class="skeleton h-5 w-1/2 mb-4"></div>
				
				<!-- Tags skeleton -->
				<div class="flex flex-wrap gap-2 mb-4">
					{#each Array(5) as _}
						<div class="skeleton h-7 w-20"></div>
					{/each}
				</div>
				
				<!-- Stats skeleton -->
				<div class="flex gap-4">
					<div class="skeleton h-6 w-32"></div>
					<div class="skeleton h-6 w-32"></div>
				</div>
			</div>
		</div>

		<!-- Bio skeleton -->
		<div class="mt-8 space-y-2">
			<div class="skeleton h-4 w-full"></div>
			<div class="skeleton h-4 w-full"></div>
			<div class="skeleton h-4 w-5/6"></div>
		</div>
	</div>
</div>
