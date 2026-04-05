SHELL := /bin/bash

.DEFAULT_GOAL := help

ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
BACKEND_DIR := $(ROOT_DIR)/backend
FRONTEND_DIR := $(ROOT_DIR)/frontend
BACKEND_VENV_DIR := $(BACKEND_DIR)/.venv
BACKEND_VENV_PYTHON := $(BACKEND_VENV_DIR)/bin/python
BACKEND_VENV_STAMP := $(BACKEND_VENV_DIR)/.deps-stamp
BACKEND_VIRTUALENV_ZIPAPP := $(BACKEND_DIR)/.virtualenv.pyz
PYTHON ?= python3
NPM ?= npm

.PHONY: help backend-venv backend-lint backend-test backend-test-audiodb backend-test-audiodb-prewarm backend-test-audiodb-settings backend-test-coverart-audiodb backend-test-audiodb-phase8 backend-test-audiodb-phase9 backend-test-exception-handling backend-test-playlist backend-test-multidisc backend-test-performance backend-test-security backend-test-config-validation backend-test-home backend-test-home-genre backend-test-infra-hardening backend-test-library-pagination backend-test-search-top-result test-audiodb-all frontend-install frontend-build frontend-check frontend-lint frontend-test frontend-test-queuehelpers frontend-test-album-page frontend-test-playlist-detail frontend-test-audiodb-images frontend-browser-install project-map rebuild test check lint ci

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_.-]+:.*## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "%-26s %s\n", $$1, $$2}'

$(BACKEND_VENV_DIR):
	cd "$(BACKEND_DIR)" && test -f .virtualenv.pyz || curl -fsSLo .virtualenv.pyz https://bootstrap.pypa.io/virtualenv.pyz
	cd "$(BACKEND_DIR)" && $(PYTHON) .virtualenv.pyz .venv

$(BACKEND_VENV_STAMP): $(BACKEND_DIR)/requirements.txt $(BACKEND_DIR)/requirements-dev.txt | $(BACKEND_VENV_DIR)
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pip install --upgrade pip setuptools wheel
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pip install -r requirements-dev.txt pytest pytest-asyncio
	touch "$(BACKEND_VENV_STAMP)"

backend-venv: $(BACKEND_VENV_STAMP) ## Create or refresh the backend virtualenv

backend-lint: $(BACKEND_VENV_STAMP) ## Run backend Ruff checks
	cd "$(ROOT_DIR)" && $(BACKEND_VENV_DIR)/bin/ruff check backend

backend-test: $(BACKEND_VENV_STAMP) ## Run all backend tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest

backend-test-audiodb: $(BACKEND_VENV_STAMP) ## Run focused AudioDB backend tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/repositories/test_audiodb_repository.py tests/infrastructure/test_disk_metadata_cache.py tests/services/test_audiodb_image_service.py tests/services/test_artist_audiodb_population.py tests/services/test_album_audiodb_population.py tests/services/test_audiodb_detail_flows.py tests/services/test_search_audiodb_overlay.py

backend-test-audiodb-prewarm: $(BACKEND_VENV_STAMP) ## Run AudioDB prewarm tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/services/test_audiodb_prewarm.py tests/services/test_audiodb_sweep.py tests/services/test_audiodb_browse_queue.py tests/services/test_audiodb_fallback_gating.py tests/services/test_preferences_generic_settings.py

backend-test-coverart-audiodb: $(BACKEND_VENV_STAMP) ## Run AudioDB coverart provider tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/repositories/test_coverart_album_fetcher.py tests/repositories/test_coverart_audiodb_provider.py tests/repositories/test_coverart_repository_memory_cache.py tests/services/test_audiodb_byte_caching_integration.py

backend-test-audiodb-settings: $(BACKEND_VENV_STAMP) ## Run AudioDB settings tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/test_audiodb_settings.py tests/test_advanced_settings_roundtrip.py tests/routes/test_settings_audiodb_key.py

backend-test-audiodb-phase8: $(BACKEND_VENV_STAMP) ## Run AudioDB cross-cutting tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/repositories/test_audiodb_models.py tests/test_audiodb_schema_contracts.py tests/services/test_audiodb_byte_caching_integration.py tests/services/test_audiodb_url_only_integration.py tests/services/test_audiodb_fallback_integration.py tests/services/test_audiodb_negative_cache_expiry.py tests/test_audiodb_killswitch.py tests/test_advanced_settings_roundtrip.py

backend-test-audiodb-phase9: $(BACKEND_VENV_STAMP) ## Run AudioDB observability tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/test_phase9_observability.py

backend-test-exception-handling: $(BACKEND_VENV_STAMP) ## Run exception-handling regressions
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/routes/test_scrobble_routes.py tests/routes/test_scrobble_settings_routes.py tests/test_error_leakage.py tests/test_background_task_logging.py

backend-test-playlist: $(BACKEND_VENV_STAMP) ## Run playlist tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/services/test_playlist_service.py tests/services/test_playlist_source_resolution.py tests/repositories/test_playlist_repository.py tests/routes/test_playlist_routes.py

backend-test-multidisc: $(BACKEND_VENV_STAMP) ## Run multi-disc album tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/services/test_album_utils.py tests/services/test_album_service.py tests/infrastructure/test_cache_layer_followups.py

backend-test-performance: $(BACKEND_VENV_STAMP) ## Run performance regression tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/services/test_album_singleflight.py tests/services/test_artist_singleflight.py tests/services/test_genre_batch_parallel.py tests/services/test_cache_stats_nonblocking.py tests/services/test_settings_cache_invalidation.py tests/services/test_discover_enrich_singleflight.py

backend-test-security: $(BACKEND_VENV_STAMP) ## Run security regression tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/test_rate_limiter_middleware.py tests/test_url_validation.py tests/test_error_leakage.py

backend-test-config-validation: $(BACKEND_VENV_STAMP) ## Run config validation tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/test_config_validation.py

backend-test-home: $(BACKEND_VENV_STAMP) ## Run home page backend tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/services/test_home_service.py tests/routes/test_home_routes.py

backend-test-home-genre: $(BACKEND_VENV_STAMP) ## Run home genre decoupling tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/services/test_home_genre_decoupling.py

backend-test-infra-hardening: $(BACKEND_VENV_STAMP) ## Run infrastructure hardening tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/infrastructure/test_circuit_breaker_sync.py tests/infrastructure/test_disk_cache_periodic.py tests/infrastructure/test_retry_non_breaking.py

backend-test-discovery-precache: $(BACKEND_VENV_STAMP) ## Run artist discovery precache tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/services/test_discovery_precache_progress.py tests/infrastructure/test_retry_non_breaking.py -v

backend-test-library-pagination: $(BACKEND_VENV_STAMP) ## Run library pagination tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/infrastructure/test_library_pagination.py -v

backend-test-search-top-result: $(BACKEND_VENV_STAMP) ## Run search top result detection tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/services/test_search_top_result.py -v

backend-test-cache-cleanup: $(BACKEND_VENV_STAMP) ## Run cache cleanup tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/test_cache_cleanup.py -v

backend-test-lidarr-url: $(BACKEND_VENV_STAMP) ## Run dynamic Lidarr URL resolution tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/test_lidarr_url_dynamic.py -v

backend-test-sync-coordinator: $(BACKEND_VENV_STAMP) ## Run sync coordinator tests (cooldown, dedup)
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/test_sync_coordinator.py -v

backend-test-local-files-fallback: $(BACKEND_VENV_STAMP) ## Run local files stale-while-error fallback tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/test_local_files_fallback.py -v

backend-test-jellyfin-proxy: $(BACKEND_VENV_STAMP) ## Run Jellyfin stream proxy tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/routes/test_stream_routes.py -v

backend-test-sync-watchdog: $(BACKEND_VENV_STAMP) ## Run adaptive watchdog timeout tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/test_sync_watchdog.py -v

backend-test-sync-resume: $(BACKEND_VENV_STAMP) ## Run sync resume-on-failure tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/test_sync_resume.py -v

backend-test-audiodb-parallel: $(BACKEND_VENV_STAMP) ## Run AudioDB parallel prewarm tests
	cd "$(BACKEND_DIR)" && .venv/bin/python -m pytest tests/test_audiodb_parallel.py -v

test-audiodb-all: backend-test-audiodb backend-test-audiodb-prewarm backend-test-audiodb-settings backend-test-coverart-audiodb backend-test-audiodb-phase8 backend-test-audiodb-phase9 frontend-test-audiodb-images ## Run every AudioDB test target

test-sync-all: backend-test-sync-watchdog backend-test-sync-resume backend-test-audiodb-parallel ## Run all sync robustness tests

frontend-install: ## Install frontend npm dependencies
	cd "$(FRONTEND_DIR)" && $(NPM) install

frontend-build: ## Run frontend production build
	cd "$(FRONTEND_DIR)" && $(NPM) run build

frontend-check: ## Run frontend type checks
	cd "$(FRONTEND_DIR)" && $(NPM) run check

frontend-lint: ## Run frontend linting
	cd "$(FRONTEND_DIR)" && $(NPM) run lint

frontend-test: ## Run the frontend vitest suite
	cd "$(FRONTEND_DIR)" && $(NPM) run test

frontend-test-queuehelpers: ## Run queue helper regressions
	cd "$(FRONTEND_DIR)" && npx vitest run --project server src/lib/player/queueHelpers.spec.ts

frontend-test-album-page: ## Run the album page browser test
	cd "$(FRONTEND_DIR)" && npx vitest run --project client src/routes/album/[id]/page.svelte.spec.ts

frontend-test-playlist-detail: ## Run playlist page browser tests
	cd "$(FRONTEND_DIR)" && npx vitest run --project client src/routes/playlists/[id]/page.svelte.spec.ts

frontend-browser-install: ## Install Playwright Chromium for browser tests
	cd "$(FRONTEND_DIR)" && npx playwright install chromium

frontend-test-audiodb-images: ## Run AudioDB image tests
	cd "$(FRONTEND_DIR)" && npx vitest run --project server src/lib/utils/imageSuffix.spec.ts
	cd "$(FRONTEND_DIR)" && npx vitest run --project client src/lib/components/BaseImage.svelte.spec.ts

project-map: ## Refresh the project map block
	cd "$(ROOT_DIR)" && $(PYTHON) scripts/gen-project-map.py

rebuild: ## Rebuild the application
	cd "$(ROOT_DIR)" && ./manage.sh --rebuild

test: backend-test frontend-test ## Run backend and frontend tests

check: backend-test frontend-check ## Run backend tests and frontend type checks

lint: backend-lint frontend-lint ## Run linting targets

ci: backend-test backend-lint frontend-check frontend-lint frontend-test ## Run the local CI checks
