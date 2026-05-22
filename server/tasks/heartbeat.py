"""Remote executor heartbeat polling and system status management."""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import timedelta
from typing import Any

import httpx
from asgiref.sync import async_to_sync, sync_to_async
from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from server.models.system import System

logger = logging.getLogger(__name__)


@shared_task
def poll_remote_executors_for_heartbeat() -> None:
    """
    Poll all remote executor systems to check health and update
    last_heartbeat.  Also check for stale heartbeats and toggle
    system status between online/offline.
    """
    logger.info("Starting remote executor heartbeat polling process...")

    # 1. Poll remote executors and update last_heartbeat
    remote_executors_to_poll = System.objects.filter(
        ~Q(executor_url__exact=""),
        ~Q(executor_mode="local"),
        executor_url__isnull=False,
    )

    logger.info(
        f"Identified {remote_executors_to_poll.count()} remote executor(s) for polling."
    )
    for system in remote_executors_to_poll:
        logger.info(
            f"  - Preparing to poll SystemModel: '{system.name}' "
            f"(PK: {system.pk}), URL: {system.executor_url}"
        )

    async def _poll_executor(system: Any) -> None:
        """Send a single heartbeat poll to *system*."""
        logger.debug(f"Attempting to poll system '{system.name}' (PK: {system.pk})...")
        try:
            headers = {"X-API-Key": system.executor_api_key}
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{system.executor_url}/", headers=headers, timeout=5
                )
                response.raise_for_status()
                data = response.json()
                if data.get("status") == "ok":
                    system.last_heartbeat = timezone.now()
                    await sync_to_async(system.save)(update_fields=["last_heartbeat"])
                    logger.info(
                        f"Successfully polled heartbeat for system "
                        f"'{system.name}' (PK: {system.pk})."
                    )
                else:
                    logger.warning(
                        f"Heartbeat poll for system '{system.name}' "
                        f"(PK: {system.pk}) returned non-ok status: {data}."
                    )
        except httpx.RequestError as e:
            logger.error(
                f"Network or request error while polling system "
                f"'{system.name}' (PK: {system.pk}): {e} {traceback.format_exc()}"
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error while polling system '{system.name}' "
                f"(PK: {system.pk}) - Status {e.response.status_code}: "
                f"{e.response.text}"
            )
        except Exception as e:
            logger.error(
                f"Unexpected error while polling system '{system.name}' "
                f"(PK: {system.pk}): {e} {traceback.format_exc()}",
                exc_info=True,
            )

    async def _run_all_polls() -> None:
        """Run all heartbeat polls concurrently via asyncio.gather."""
        if remote_executors_to_poll.exists():
            logger.info(
                "Starting concurrent polling of remote executors via asyncio.gather..."
            )
            await asyncio.gather(
                *[_poll_executor(system) for system in remote_executors_to_poll]
            )
            logger.info("Finished concurrent polling of remote executors.")
        else:
            logger.info("No remote executors found, skipping concurrent polling.")

    # Run all polling tasks concurrently
    try:
        async_to_sync(_run_all_polls)()
    except Exception as e:
        logger.error(
            f"Error during async_to_sync execution of polling tasks: "
            f"{e} {traceback.format_exc()}",
            exc_info=True,
        )

    # 2. Update system statuses based on heartbeats
    stale_threshold = timezone.now() - timedelta(minutes=2)

    online_and_stale_systems = System.objects.filter(status="online").filter(
        Q(last_heartbeat__lt=stale_threshold) | Q(last_heartbeat__isnull=True)
    )

    if online_and_stale_systems.exists():
        logger.info(
            f"Found {online_and_stale_systems.count()} stale system(s) "
            "to mark as offline."
        )
        for system in online_and_stale_systems:
            system.status = System.SystemStatusChoices.OFFLINE
            system.save(update_fields=["status"])
            logger.info(
                f"Marked system '{system.name}' (ID: {system.pk}) as offline."
            )
    else:
        logger.info("No stale systems found.")

    offline_but_fresh_systems = System.objects.filter(
        status="offline", last_heartbeat__gte=stale_threshold
    )

    if offline_but_fresh_systems.exists():
        logger.info(
            f"Found {offline_but_fresh_systems.count()} system(s) marked offline "
            "but with a recent heartbeat. Marking them online."
        )
        for system in offline_but_fresh_systems:
            system.status = System.SystemStatusChoices.ONLINE
            system.save(update_fields=["status"])
            logger.info(
                f"Marked system '{system.name}' (ID: {system.pk}) as online."
            )

    logger.info("Finished polling remote executors and updating system statuses.")
