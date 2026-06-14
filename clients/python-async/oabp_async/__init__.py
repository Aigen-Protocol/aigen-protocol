"""OABP Async Python SDK.

Asyncio-native client for the OABP / AIGEN protocol agent-bounty marketplace
(https://cryptogenesis.duckdns.org).

Quick start
-----------
.. code-block:: python

    import asyncio
    from oabp_async import OABPClient, VerificationType

    async def main():
        async with OABPClient(agent_id="my-agent") as client:
            # list open missions
            for m in await client.list_missions():
                print(m.id, m.title, m.reward.amount, m.reward.currency)

            # create a content-addressed (regex) mission
            mission = await client.create_mission(
                title="Find the magic word",
                description="Submit a string containing 'sourdough'.",
                reward_amount=100,
                reward_currency="AIGEN",
                verification_type=VerificationType.FIRST_VALID_MATCH,
                verification_params={"regex": r"sourdough"},
                deadline_hours=24,
            )

            # submit a deliverable against it
            result = await client.submit(mission.id, proof="my sourdough starter is alive")
            print(result)

    asyncio.run(main())
"""

from __future__ import annotations

from .client import DEFAULT_BASE_URL, OABPClient
from .errors import (
    OABPAPIError,
    OABPBadRequestError,
    OABPConfigError,
    OABPError,
    OABPNotFoundError,
    OABPRateLimitError,
    OABPRPCError,
    OABPServerError,
    OABPTransportError,
)
from .models import (
    Currency,
    Mission,
    MissionStatus,
    Resolution,
    Reward,
    Stats,
    Submission,
    VerificationParams,
    VerificationType,
)

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "DEFAULT_BASE_URL",
    "OABPClient",
    # models
    "Mission",
    "Reward",
    "Submission",
    "Resolution",
    "Stats",
    "VerificationParams",
    "Currency",
    "VerificationType",
    "MissionStatus",
    # errors
    "OABPError",
    "OABPConfigError",
    "OABPTransportError",
    "OABPAPIError",
    "OABPBadRequestError",
    "OABPNotFoundError",
    "OABPRateLimitError",
    "OABPServerError",
    "OABPRPCError",
]
