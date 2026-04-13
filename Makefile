SHELL := /bin/bash

.DEFAULT_GOAL := help

ROOT_DIR     := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
BACKEND_DIR  := $(ROOT_DIR)/backend
FRONTEND_DIR := $(ROOT_DIR)/frontend

BACKEND_VENV_DIR   := $(BACKEND_DIR)/.venv
BACKEND_VENV_STAMP := $(BACKEND_VENV_DIR)/.deps-stamp
PYTEST := cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest

PYTHON ?= python3
NPM    ?= pnpm

.PHONY: \
	help \
	backend-venv backend-lint backend-test \
	backend-test-album-refresh \
	backend-test-artist-lock \
	backend-test-artist-monitoring \
	backend-test-artist-page \
	backend-test-audiodb \
	backend-test-audiodb-parallel \
	backend-test-audiodb-phase8 \
	backend-test-audiodb-phase9 \
	backend-test-audiodb-prewarm \
	backend-test-audiodb-settings \
	backend-test-cache-cleanup \
	backend-test-config-validation \
	backend-test-coverart-audiodb \
	backend-test-dedup-cancellation \
	backend-test-discovery-precache \
	backend-test-exception-handling \
	backend-test-home \
	backend-test-home-genre \
	backend-test-infra-hardening \
	backend-test-jellyfin-proxy \
	backend-test-library-pagination \
	backend-test-lidarr-url \
	backend-test-local-files-fallback \
	backend-test-monitoring-cache \
	backend-test-multidisc \
	backend-test-mus15-status-race \
	backend-test-performance \
	backend-test-playlist \
	backend-test-request-queue \
	backend-test-request-service \
	backend-test-search-top-result \
	backend-test-security \
	backend-test-sync-coordinator \
	backend-test-sync-generation \
	backend-test-sync-resume \
	backend-test-sync-watchdog \
	test-audiodb-all test-mus14-all test-sync-all \
	frontend-install frontend-build frontend-browser-install \
	frontend-format-check frontend-check frontend-lint frontend-test frontend-test-server \
	frontend-test-album-page \
	frontend-test-audiodb-images \
	frontend-test-monitored-artists \
	frontend-test-playlist-detail \
	frontend-test-queuehelpers \
	rebuild \
	test tests check lint ci

# Help

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_.-]+:.*## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "%-34s %s\n", $$1, $$2}'

# Backend: virtualenv

$(BACKEND_VENV_DIR):
	cd "$(BACKEND_DIR)" && test -f .virtualenv.pyz || curl -fsSLo .virtualenv.pyz https://bootstrap.pypa.io/virtualenv.pyz
	cd "$(BACKEND_DIR)" && $(PYTHON) .virtualenv.pyz .venv

$(BACKEND_VENV_STAMP): $(BACKEND_DIR)/requirements.txt $(BACKEND_DIR)/requirements-dev.txt | $(BACKEND_VENV_DIR)
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pip install --upgrade pip setuptools wheel
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pip install -r requirements-dev.txt pytest pytest-asyncio
	touch "$(BACKEND_VENV_STAMP)"

backend-venv: $(BACKEND_VENV_STAMP) ## Create or refresh the backend virtualenv

# Backend: lint

backend-lint: $(BACKEND_VENV_STAMP) ## Run backend Ruff checks
	cd "$(ROOT_DIR)" && $(BACKEND_VENV_DIR)/bin/ruff check backend

# Backend: full test suite

backend-test: $(BACKEND_VENV_STAMP) ## Run all backend tests
	$(PYTEST)

# Backend: focused test targets

backend-test-album-refresh: $(BACKEND_VENV_STAMP) ## Run album refresh endpoint tests
	$(PYTEST) tests/routes/test_album_refresh.py tests/services/test_navidrome_cache_invalidation.py -v

backend-test-artist-lock: $(BACKEND_VENV_STAMP) ## Run MUS-14 per-artist lock tests
	$(PYTEST) tests/repositories/test_album_artist_lock.py -v

backend-test-artist-monitoring: $(BACKEND_VENV_STAMP) ## Run MUS-15B artist monitoring tests
	$(PYTEST) tests/test_artist_monitoring.py -v

backend-test-artist-page: $(BACKEND_VENV_STAMP) ## Run artist page latency tests (basic route, releases, Last.fm fast path)
	$(PYTEST) tests/routes/test_artist_basic_route.py tests/routes/test_artist_releases_route.py tests/services/test_artist_basic_info.py tests/services/test_top_albums_lastfm_fast.py -v

backend-test-audiodb: $(BACKEND_VENV_STAMP) ## Run focused AudioDB backend tests
	$(PYTEST) tests/repositories/test_audiodb_repository.py tests/infrastructure/test_disk_metadata_cache.py tests/services/test_audiodb_image_service.py tests/services/test_artist_audiodb_population.py tests/services/test_album_audiodb_population.py tests/services/test_audiodb_detail_flows.py tests/services/test_search_audiodb_overlay.py

backend-test-audiodb-parallel: $(BACKEND_VENV_STAMP) ## Run AudioDB parallel prewarm tests
	$(PYTEST) tests/test_audiodb_parallel.py -v

backend-test-audiodb-phase8: $(BACKEND_VENV_STAMP) ## Run AudioDB cross-cutting tests
	$(PYTEST) tests/repositories/test_audiodb_models.py tests/test_audiodb_schema_contracts.py tests/services/test_audiodb_byte_caching_integration.py tests/services/test_audiodb_url_only_integration.py tests/services/test_audiodb_fallback_integration.py tests/services/test_audiodb_negative_cache_expiry.py tests/test_audiodb_killswitch.py tests/test_advanced_settings_roundtrip.py

backend-test-audiodb-phase9: $(BACKEND_VENV_STAMP) ## Run AudioDB observability tests
	$(PYTEST) tests/test_phase9_observability.py

backend-test-audiodb-prewarm: $(BACKEND_VENV_STAMP) ## Run AudioDB prewarm tests
	$(PYTEST) tests/services/test_audiodb_prewarm.py tests/services/test_audiodb_sweep.py tests/services/test_audiodb_browse_queue.py tests/services/test_audiodb_fallback_gating.py tests/services/test_preferences_generic_settings.py

backend-test-audiodb-settings: $(BACKEND_VENV_STAMP) ## Run AudioDB settings tests
	$(PYTEST) tests/test_audiodb_settings.py tests/test_advanced_settings_roundtrip.py tests/routes/test_settings_audiodb_key.py

backend-test-cache-cleanup: $(BACKEND_VENV_STAMP) ## Run cache cleanup tests
	$(PYTEST) tests/test_cache_cleanup.py -v

backend-test-config-validation: $(BACKEND_VENV_STAMP) ## Run config validation tests
	$(PYTEST) tests/test_config_validation.py

backend-test-coverart-audiodb: $(BACKEND_VENV_STAMP) ## Run AudioDB coverart provider tests
	$(PYTEST) tests/repositories/test_coverart_album_fetcher.py tests/repositories/test_coverart_audiodb_provider.py tests/repositories/test_coverart_repository_memory_cache.py tests/services/test_audiodb_byte_caching_integration.py

backend-test-dedup-cancellation: $(BACKEND_VENV_STAMP) ## Run deduplicator cancellation tests
	$(PYTEST) tests/infrastructure/test_dedup_cancellation.py tests/infrastructure/test_disconnect.py -v

backend-test-discovery-precache: $(BACKEND_VENV_STAMP) ## Run artist discovery precache tests
	$(PYTEST) tests/services/test_discovery_precache_progress.py tests/services/test_discovery_precache_lock.py tests/infrastructure/test_retry_non_breaking.py -v

backend-test-exception-handling: $(BACKEND_VENV_STAMP) ## Run exception-handling regressions
	$(PYTEST) tests/routes/test_scrobble_routes.py tests/routes/test_scrobble_settings_routes.py tests/test_error_leakage.py tests/test_background_task_logging.py

backend-test-home: $(BACKEND_VENV_STAMP) ## Run home page backend tests
	$(PYTEST) tests/services/test_home_service.py tests/routes/test_home_routes.py

backend-test-home-genre: $(BACKEND_VENV_STAMP) ## Run home genre decoupling tests
	$(PYTEST) tests/services/test_home_genre_decoupling.py

backend-test-infra-hardening: $(BACKEND_VENV_STAMP) ## Run infrastructure hardening tests
	$(PYTEST) tests/infrastructure/test_circuit_breaker_sync.py tests/infrastructure/test_disk_cache_periodic.py tests/infrastructure/test_retry_non_breaking.py

backend-test-jellyfin-proxy: $(BACKEND_VENV_STAMP) ## Run Jellyfin stream proxy tests
	$(PYTEST) tests/routes/test_stream_routes.py -v

backend-test-library-pagination: $(BACKEND_VENV_STAMP) ## Run library pagination tests
	$(PYTEST) tests/infrastructure/test_library_pagination.py -v

backend-test-lidarr-url: $(BACKEND_VENV_STAMP) ## Run dynamic Lidarr URL resolution tests
	$(PYTEST) tests/test_lidarr_url_dynamic.py -v

backend-test-local-files-fallback: $(BACKEND_VENV_STAMP) ## Run local files stale-while-error fallback tests
	$(PYTEST) tests/test_local_files_fallback.py -v

backend-test-monitoring-cache: $(BACKEND_VENV_STAMP) ## Run artist monitoring cache/flag refresh tests
	$(PYTEST) tests/services/test_refresh_library_flags.py tests/test_queue_disk_invalidation.py tests/services/test_artist_utils_tags.py -v

backend-test-multidisc: $(BACKEND_VENV_STAMP) ## Run multi-disc album tests
	$(PYTEST) tests/services/test_album_utils.py tests/services/test_album_service.py tests/infrastructure/test_cache_layer_followups.py

backend-test-mus15-status-race: $(BACKEND_VENV_STAMP) ## Run MUS-15 status race condition tests
	$(PYTEST) tests/test_mus15_status_race.py -v

backend-test-performance: $(BACKEND_VENV_STAMP) ## Run performance regression tests
	$(PYTEST) tests/services/test_album_singleflight.py tests/services/test_artist_singleflight.py tests/services/test_genre_batch_parallel.py tests/services/test_cache_stats_nonblocking.py tests/services/test_settings_cache_invalidation.py tests/services/test_discover_enrich_singleflight.py

backend-test-playlist: $(BACKEND_VENV_STAMP) ## Run playlist tests
	$(PYTEST) tests/services/test_playlist_service.py tests/services/test_playlist_source_resolution.py tests/repositories/test_playlist_repository.py tests/routes/test_playlist_routes.py

backend-test-request-queue: $(BACKEND_VENV_STAMP) ## Run MUS-14 request queue tests (dedup, cancel, concurrency)
	$(PYTEST) tests/infrastructure/test_request_queue_mus14.py tests/infrastructure/test_queue_persistence.py -v

backend-test-request-service: $(BACKEND_VENV_STAMP) ## Run request service tests
	$(PYTEST) tests/services/test_request_service.py -v

backend-test-search-top-result: $(BACKEND_VENV_STAMP) ## Run search top result detection tests
	$(PYTEST) tests/services/test_search_top_result.py -v

backend-test-security: $(BACKEND_VENV_STAMP) ## Run security regression tests
	$(PYTEST) tests/test_rate_limiter_middleware.py tests/test_url_validation.py tests/test_error_leakage.py

backend-test-sync-coordinator: $(BACKEND_VENV_STAMP) ## Run sync coordinator tests (cooldown, dedup)
	$(PYTEST) tests/test_sync_coordinator.py -v

backend-test-sync-generation: $(BACKEND_VENV_STAMP) ## Run MUS-19 sync generation counter tests
	$(PYTEST) tests/test_sync_generation.py -v

backend-test-sync-resume: $(BACKEND_VENV_STAMP) ## Run sync resume-on-failure tests
	$(PYTEST) tests/test_sync_resume.py -v

backend-test-sync-watchdog: $(BACKEND_VENV_STAMP) ## Run adaptive watchdog timeout tests
	$(PYTEST) tests/test_sync_watchdog.py -v

# Backend: aggregate test targets

test-audiodb-all: backend-test-audiodb backend-test-audiodb-prewarm backend-test-audiodb-settings backend-test-coverart-audiodb backend-test-audiodb-phase8 backend-test-audiodb-phase9 frontend-test-audiodb-images ## Run every AudioDB test target

test-mus14-all: backend-test-request-queue backend-test-artist-lock backend-test-request-service ## Run all MUS-14 request system tests
	$(PYTEST) tests/repositories/test_lidarr_library_cache.py -v

test-sync-all: backend-test-sync-watchdog backend-test-sync-resume backend-test-audiodb-parallel backend-test-sync-generation ## Run all sync robustness tests

# Frontend: setup

frontend-install: ## Install frontend npm dependencies
	cd "$(FRONTEND_DIR)" && $(NPM) install

frontend-build: ## Run frontend production build
	cd "$(FRONTEND_DIR)" && $(NPM) run build

frontend-browser-install: ## Install Playwright Chromium for browser tests
	cd "$(FRONTEND_DIR)" && $(NPM) exec playwright install chromium

# Frontend: lint & checks

frontend-format-check: ## Run frontend formatting checks
	cd "$(FRONTEND_DIR)" && $(NPM) run format:check

frontend-check: ## Run frontend type checks
	cd "$(FRONTEND_DIR)" && $(NPM) run check

frontend-lint: ## Run frontend linting
	cd "$(FRONTEND_DIR)" && $(NPM) run lint

# Frontend: full test suite

frontend-test: ## Run the frontend vitest suite (all projects, needs Playwright)
	cd "$(FRONTEND_DIR)" && $(NPM) run test

frontend-test-server: ## Run frontend server-project tests only (no Playwright)
	cd "$(FRONTEND_DIR)" && $(NPM) exec vitest run --project server

# Frontend: focused test targets

frontend-test-album-page: ## Run the album page browser test
	cd "$(FRONTEND_DIR)" && $(NPM) exec vitest run --project client src/routes/album/[id]/page.svelte.spec.ts

frontend-test-audiodb-images: ## Run AudioDB image tests
	cd "$(FRONTEND_DIR)" && $(NPM) exec vitest run --project server src/lib/utils/imageSuffix.spec.ts
	cd "$(FRONTEND_DIR)" && $(NPM) exec vitest run --project client src/lib/components/BaseImage.svelte.spec.ts

frontend-test-monitored-artists: ## Run pending monitored artist store tests
	cd "$(FRONTEND_DIR)" && $(NPM) exec vitest run --project server src/lib/stores/monitoredArtists.spec.ts

frontend-test-playlist-detail: ## Run playlist page browser tests
	cd "$(FRONTEND_DIR)" && $(NPM) exec vitest run --project client src/routes/playlists/[id]/page.svelte.spec.ts

frontend-test-queuehelpers: ## Run queue helper regressions
	cd "$(FRONTEND_DIR)" && $(NPM) exec vitest run --project server src/lib/player/queueHelpers.spec.ts

# Utilities

rebuild: ## Rebuild the application
	cd "$(ROOT_DIR)" && ./manage.sh --rebuild

# Aggregate targets

test: backend-test frontend-test ## Run backend and frontend tests

tests: test ## Alias for 'test'

check: backend-test frontend-check ## Run backend tests and frontend type checks

lint: backend-lint frontend-lint ## Run linting targets

ci: backend-test backend-lint frontend-check frontend-lint frontend-format-check frontend-test-server ## Run the local CI checks
