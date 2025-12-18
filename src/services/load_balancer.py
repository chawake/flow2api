"""Load balancing module for Flow2API"""
import random
from typing import Optional
from ..core.models import Token
from .concurrency_manager import ConcurrencyManager
from ..core.logger import debug_logger


class LoadBalancer:
    """Token load balancer with random selection"""

    def __init__(self, token_manager, concurrency_manager: Optional[ConcurrencyManager] = None):
        self.token_manager = token_manager
        self.concurrency_manager = concurrency_manager

    async def select_token(
        self,
        for_image_generation: bool = False,
        for_video_generation: bool = False,
        model: Optional[str] = None
    ) -> Optional[Token]:
        """
        Select a token using random load balancing

        Args:
            for_image_generation: If True, only select tokens with image_enabled=True
            for_video_generation: If True, only select tokens with video_enabled=True
            model: Model name (used to filter tokens for specific models)

        Returns:
            Selected token or None if no available tokens
        """
        debug_logger.log_info(f"[LOAD_BALANCER] Starting token selection (Image={for_image_generation}, Video={for_video_generation}, Model={model})")

        active_tokens = await self.token_manager.get_active_tokens()
        debug_logger.log_info(f"[LOAD_BALANCER] Obtained {len(active_tokens)} active tokens")

        if not active_tokens:
            debug_logger.log_info(f"[LOAD_BALANCER] ❌ No active tokens")
            return None

        # Filter tokens based on generation type
        available_tokens = []
        filtered_reasons = {}  # Record filtering reasons

        for token in active_tokens:
            # Check if token has valid AT (not expired)
            if not await self.token_manager.is_at_valid(token.id):
                filtered_reasons[token.id] = "AT invalid or expired"
                continue

            # Filter for gemini-3.0 models (skip free tier tokens)
            if model and model in ["gemini-3.0-pro-image-landscape", "gemini-3.0-pro-image-portrait"]:
                if token.user_paygate_tier == "PAYGATE_TIER_NOT_PAID":
                    filtered_reasons[token.id] = "gemini-3.0 model does not support free accounts"
                    continue

            # Filter for image generation
            if for_image_generation:
                if not token.image_enabled:
                    filtered_reasons[token.id] = "Image generation disabled"
                    continue

                # Check concurrency limit
                if self.concurrency_manager and not await self.concurrency_manager.can_use_image(token.id):
                    filtered_reasons[token.id] = "Image concurrency full"
                    continue

            # Filter for video generation
            if for_video_generation:
                if not token.video_enabled:
                    filtered_reasons[token.id] = "Video generation disabled"
                    continue

                # Check concurrency limit
                if self.concurrency_manager and not await self.concurrency_manager.can_use_video(token.id):
                    filtered_reasons[token.id] = "Video concurrency full"
                    continue

            available_tokens.append(token)

        # Output filtering info
        if filtered_reasons:
            debug_logger.log_info(f"[LOAD_BALANCER] Filtered tokens:")
            for token_id, reason in filtered_reasons.items():
                debug_logger.log_info(f"[LOAD_BALANCER]   - Token {token_id}: {reason}")

        if not available_tokens:
            debug_logger.log_info(f"[LOAD_BALANCER] ❌ No available tokens (Image={for_image_generation}, Video={for_video_generation})")
            return None

        # Random selection
        selected = random.choice(available_tokens)
        debug_logger.log_info(f"[LOAD_BALANCER] ✅ Selected Token {selected.id} ({selected.email}) - Balance: {selected.credits}")
        return selected
