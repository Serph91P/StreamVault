import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.constants import TIMEOUTS, ASYNC_DELAYS
from app.config.logging_config import setup_logging
from app.services.system.development_test_runner import run_development_tests
from app.database import database_lifecycle, SessionLocal
from app.services.core.auth_service import AuthService
import app.models as models
from app.dependencies import get_event_registry
from app.services.images.image_sync_service import image_sync_service
from app.tasks.websocket_broadcast_task import websocket_broadcast_task

logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application initialization...")

    # Initialize services
    event_registry = None
    cleanup_task = None
    log_cleanup_task = None
    recording_service = None
    background_services_task = None

    # Database migrations are the only fatal startup task in this best-effort block.
    logger.info("🔄 Running database migrations...")
    from app.services.system.migration_service import MigrationService

    migration_success = MigrationService.run_safe_migrations()
    if not migration_success:
        raise RuntimeError("Database migrations did not complete successfully")
    logger.info("✅ All database migrations completed successfully")

    try:
        # Image migration check and execution
        logger.info("🖼️ Checking image migration status...")
        from app.services.migration.image_migration_service import (
            image_migration_service,
        )

        try:
            # Check if migration is needed
            old_dirs_exist = (
                image_migration_service.old_images_dir.exists()
                or image_migration_service.old_artwork_dir.exists()
            )

            if old_dirs_exist:
                logger.info(
                    "🔄 Running image migration from old directory structure..."
                )
                migration_stats = await image_migration_service.migrate_all_images()
                logger.info(f"✅ Image migration completed: {migration_stats}")
            else:
                logger.info(
                    "✅ No image migration needed - directory structure is up to date"
                )
        except Exception as e:
            logger.error(f"❌ Image migration failed: {e}")
            logger.warning("⚠️ Continuing startup without image migration")

        # Generate Streamlink configuration from settings
        logger.info("🔧 Generating Streamlink configuration...")
        from app.services.system.streamlink_config_service import (
            streamlink_config_service,
        )

        try:
            config_success = (
                await streamlink_config_service.update_config_from_settings()
            )
            if config_success:
                logger.info("✅ Streamlink configuration generated successfully")
            else:
                logger.warning(
                    "⚠️ Failed to generate Streamlink config - using command-line args only"
                )
        except Exception as e:
            logger.error(f"❌ Streamlink config generation failed: {e}")
            logger.warning("⚠️ Continuing without config file - using command-line args")

        # Image refresh check for missing images
        logger.info("🔄 Checking for missing images...")
        from app.services.images.image_refresh_service import image_refresh_service

        try:
            # Run image refresh in background (non-blocking) with error handling
            async def safe_image_refresh():
                try:
                    await image_refresh_service.check_and_refresh_missing_images()
                    logger.info("✅ Image refresh task completed successfully")
                except Exception as e:
                    logger.error(f"❌ Image refresh task failed: {e}")

            asyncio.create_task(safe_image_refresh())
            logger.info("✅ Image refresh task started in background")
        except Exception as e:
            logger.error(f"❌ Image refresh failed to start: {e}")
            logger.warning("⚠️ Images may not be available until manually refreshed")

        # Create any remaining tables from models (after migrations)
        logger.info("🔄 Creating remaining tables from models...")
        try:
            models.Base.metadata.create_all(bind=database_lifecycle.sync_engine)
            logger.info("✅ All model tables ensured")
        except Exception as e:
            logger.error(f"❌ Error creating model tables: {e}")
            logger.warning(
                "⚠️ Application will continue but may have limited functionality"
            )

        from app.services.twitch_upstream_coordinator import (
            twitch_upstream_coordinator,
        )

        reconciled_leases = await twitch_upstream_coordinator.reconcile()
        logger.info("Reconciled %s stale Twitch upstream leases", reconciled_leases)

        # Initialize EventSub
        event_registry = await get_event_registry()
        await event_registry.initialize_eventsub()
        logger.info("EventSub initialized successfully")

        # Get recording service reference for graceful shutdown
        try:
            recording_service = getattr(event_registry, "recording_service", None)
            if recording_service:
                logger.info(
                    "Recording service reference obtained for graceful shutdown"
                )
        except Exception as e:
            logger.warning(f"Could not get recording service reference: {e}")

        # Start log cleanup service
        try:
            from app.services.system.logging_service import logging_service

            # Use the global logging service instance instead of creating a new one
            log_cleanup_task = asyncio.create_task(
                logging_service._schedule_cleanup(interval_hours=24)
            )
            logger.info("Log cleanup service started")
            logger.info(
                f"Logging service base directory: {logging_service.logs_base_dir}"
            )
        except Exception as e:
            logger.error(f"Failed to start log cleanup service: {e}")

        # Initialize background queue service (will be done later in initialize_background_services)
        try:
            logger.info(
                "Background queue initialization deferred to initialize_background_services()"
            )

            # Background queue cleanup will be handled by initialize_background_services()
            logger.info("✅ Background queue auto-cleanup will be initialized later")

        except Exception as e:
            logger.error(f"Failed to initialize background queue service: {e}")
            logger.exception("Full error details:")

        # Automated recovery service will be handled by initialize_background_services()
        try:
            logger.info(
                "✅ Startup recovery check scheduled (runs once after 2 minutes)"
            )

        except Exception as e:
            logger.error(f"❌ Failed to start startup recovery check: {e}")
            logger.warning("⚠️ Failed recordings will not be automatically recovered")

        # Start recording cleanup service
        try:
            from app.services.system.cleanup_service import CleanupService

            async def scheduled_recording_cleanup():
                while True:
                    try:
                        await CleanupService.run_scheduled_cleanup()
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(
                            f"Error in scheduled recording cleanup: {e}", exc_info=True
                        )

                    # Run every 12 hours
                    await asyncio.sleep(12 * 3600)

            cleanup_task = asyncio.create_task(scheduled_recording_cleanup())
            logger.info("Recording cleanup service started")
        except Exception as e:
            logger.error(f"Failed to start recording cleanup service: {e}")

        # Start expired session cleanup service
        try:

            async def scheduled_session_cleanup():
                """Periodically clean up expired sessions to prevent table bloat."""
                while True:
                    try:
                        await asyncio.sleep(6 * 3600)  # Run every 6 hours
                        db = SessionLocal()
                        try:
                            auth_service = AuthService(db=db)
                            expired_count = (
                                await auth_service.cleanup_expired_sessions()
                            )
                            if expired_count > 0:
                                logger.info(
                                    f"🧹 Cleaned up {expired_count} expired sessions"
                                )
                        finally:
                            db.close()
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"Error in session cleanup: {e}", exc_info=True)

            asyncio.create_task(scheduled_session_cleanup())
            logger.info("✅ Session cleanup service started (runs every 6 hours)")
        except Exception as e:
            logger.error(f"Failed to start session cleanup service: {e}")

        # Wait a moment for migrations to fully complete before starting services
        await asyncio.sleep(ASYNC_DELAYS.BRIEF_PAUSE)

        # Start background services AFTER migrations are guaranteed to be complete
        try:
            from app.services.init.startup_init import initialize_background_services

            async def launch_background_services():
                try:
                    await initialize_background_services()
                except Exception as init_error:
                    logger.error(
                        f"❌ Error during background services initialization: {init_error}",
                        exc_info=True,
                    )
                    logger.warning(
                        "⚠️ Application will continue but background processing may be limited"
                    )

            # Run heavy startup tasks in the background so the frontend becomes available immediately
            background_services_task = asyncio.create_task(launch_background_services())
            logger.info("🚀 Background services initialization running in background")
        except Exception as e:
            logger.error(
                f"❌ Failed to schedule background services initialization: {e}",
                exc_info=True,
            )
            logger.warning(
                "⚠️ Application will continue but background processing may be limited"
            )

        # Start image sync service
        try:
            await image_sync_service.start_sync_worker()
            logger.info("✅ Image sync service started")
        except Exception as e:
            logger.error(f"❌ Error starting image sync service: {e}", exc_info=True)

        # Start WebSocket broadcast task for real-time updates
        try:
            await websocket_broadcast_task.start()
            logger.info("WebSocket broadcast task started")
        except Exception as e:
            logger.error(f"Error starting WebSocket broadcast task: {e}", exc_info=True)

        # Start Proxy Health Check Service
        try:
            from app.services.proxy.proxy_health_service import proxy_health_service

            await proxy_health_service.start()
            logger.info("✅ Proxy health check service started")
        except Exception as e:
            logger.error(
                f"❌ Error starting proxy health check service: {e}", exc_info=True
            )

        # Run development tests if in debug mode
        try:
            test_success = await run_development_tests()
            if test_success:
                logger.info("✅ All development tests passed")
            else:
                logger.warning("⚠️ Some development tests failed - check logs above")
        except Exception as e:
            logger.error(f"Error running development tests: {e}", exc_info=True)

        logger.info("Application startup complete")

    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)

    yield

    # Shutdown
    logger.info("🛑 Starting application shutdown...")

    # Gracefully shutdown recording service first (most critical)
    if recording_service:
        try:
            logger.info("🔄 Gracefully shutting down recording service...")
            await recording_service.graceful_shutdown(
                timeout=TIMEOUTS.GRACEFUL_SHUTDOWN
            )
            logger.info("✅ Recording service shutdown completed")
        except Exception as e:
            logger.error(f"❌ Error during recording service shutdown: {e}")

    # Shutdown live streaming service
    try:
        logger.info("🔄 Stopping live streaming service...")
        from app.services.live_streaming_service import live_streaming_service

        await live_streaming_service.stop()
        logger.info("✅ Live streaming service stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error during live streaming service shutdown: {e}")

    # Shutdown active recordings broadcaster
    try:
        logger.info("🔄 Stopping active recordings broadcaster...")

        logger.info("✅ Active recordings broadcaster stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error during active recordings broadcaster shutdown: {e}")

    # Stop WebSocket broadcast task
    try:
        logger.info("🔄 Stopping WebSocket broadcast task...")
        await websocket_broadcast_task.stop()
        logger.info("✅ WebSocket broadcast task stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error stopping WebSocket broadcast task: {e}")

    # Stop Proxy Health Check Service
    try:
        logger.info("🔄 Stopping proxy health check service...")
        from app.services.proxy.proxy_health_service import proxy_health_service

        await proxy_health_service.stop()
        logger.info("✅ Proxy health check service stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error stopping proxy health check service: {e}")

    # Ensure background services initialization finished
    if background_services_task:
        if not background_services_task.done():
            logger.info(
                "🔄 Waiting for background services initialization to finish..."
            )
        try:
            await background_services_task
        except asyncio.CancelledError:
            logger.info("✅ Background services initialization task cancelled")
        except Exception as e:
            logger.error(
                f"❌ Background services initialization task failed during shutdown: {e}",
                exc_info=True,
            )

    # Shutdown background queue service
    try:
        logger.info("🔄 Stopping background queue service...")
        from app.services.background_queue_service import background_queue_service

        await background_queue_service.stop()
        logger.info("✅ Background queue service stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error during background queue service shutdown: {e}")

    # Cancel cleanup tasks
    for task_name, task in [
        ("cleanup", cleanup_task),
        ("log_cleanup", log_cleanup_task),
    ]:
        if task and not task.done():
            logger.info(f"🔄 Cancelling {task_name} task...")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"✅ {task_name} task cancelled successfully")
            except Exception as e:
                logger.error(f"❌ Error cancelling {task_name} task: {e}")

    # Stop EventSub properly
    if event_registry:
        try:
            # Try to access eventsub attribute safely
            eventsub = getattr(event_registry, "eventsub", None)
            if eventsub and hasattr(eventsub, "stop"):
                logger.info("🔄 Stopping EventSub...")
                await eventsub.stop()
                logger.info("✅ EventSub stopped successfully")
            elif hasattr(event_registry, "cleanup"):
                logger.info("🔄 Cleaning up event registry...")
                await event_registry.cleanup()
                logger.info("✅ Event registry cleaned up")
        except Exception as e:
            logger.error(f"❌ Error during EventSub shutdown: {e}")

    # Stop image sync service
    try:
        await image_sync_service.stop_sync_worker()
        logger.info("✅ Image sync service stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping image sync service: {e}")

    # Stop recording auto-fix service (optional component; ignore if not present)
    try:
        try:
            from app.services.recording.recording_auto_fix_service import (  # type: ignore[import-not-found]
                recording_auto_fix_service,
            )
        except ModuleNotFoundError:
            recording_auto_fix_service = None  # type: ignore
        if recording_auto_fix_service and hasattr(recording_auto_fix_service, "stop"):
            await recording_auto_fix_service.stop()
            logger.info("✅ Recording auto-fix service stopped")
        else:
            logger.debug("Recording auto-fix service not available; skipping")
    except Exception as e:
        logger.error(f"❌ Error stopping recording auto-fix service: {e}")

    # Close database connections
    try:
        await database_lifecycle.adispose()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Error disposing database engine: {e}")

    logger.info("🎯 Application shutdown complete")
