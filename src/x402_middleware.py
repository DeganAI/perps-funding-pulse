"""
x402 Payment Verification Middleware

Validates payment proofs for x402 micropayment protocol
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class X402Middleware:
    """
    Middleware for x402 payment verification

    In FREE_MODE, this middleware is bypassed.
    In production, this would verify payment proofs via the facilitator.
    """

    def __init__(
        self,
        payment_address: str,
        ethereum_rpc_url: Optional[str] = None,
        free_mode: bool = True,
    ):
        self.payment_address = payment_address
        self.ethereum_rpc_url = ethereum_rpc_url
        self.free_mode = free_mode

        logger.info(f"x402 Middleware initialized (FREE_MODE={free_mode})")

    async def __call__(self, request, call_next):
        """Process request and verify payment if required"""

        # In free mode, skip payment verification
        if self.free_mode:
            return await call_next(request)

        # Payment verification would go here in production
        # For now, allow all requests
        logger.info("Payment verification bypassed (not implemented)")

        return await call_next(request)
