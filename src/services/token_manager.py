"""Token manager for Flow2API with AT auto-refresh"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from ..core.database import Database
from ..core.models import Token, Project
from ..core.logger import debug_logger
from .flow_client import FlowClient
from .proxy_manager import ProxyManager


class TokenManager:
    """Token lifecycle manager with AT auto-refresh"""

    def __init__(self, db: Database, flow_client: FlowClient):
        self.db = db
        self.flow_client = flow_client
        self._lock = asyncio.Lock()

    # ========== Token CRUD ==========
 
    async def get_all_tokens(self) -> List[Token]:
        """Get all tokens"""
        return await self.db.get_all_tokens()

    async def get_active_tokens(self) -> List[Token]:
        """Get all active tokens"""
        return await self.db.get_active_tokens()

    async def get_token(self, token_id: int) -> Optional[Token]:
        """Get token by ID"""
        return await self.db.get_token(token_id)

    async def delete_token(self, token_id: int):
        """Delete token"""
        await self.db.delete_token(token_id)

    async def enable_token(self, token_id: int):
        """Enable a token and reset error count"""
        # Enable the token
        await self.db.update_token(token_id, is_active=True)
        # Reset error count when enabling (only reset total error_count, keep today_error_count)
        await self.db.reset_error_count(token_id)

    async def disable_token(self, token_id: int):
        """Disable a token"""
        await self.db.update_token(token_id, is_active=False)

    # ========== Token addition (Supports project creation) ==========

    async def add_token(
        self,
        st: str,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
        remark: Optional[str] = None,
        image_enabled: bool = True,
        video_enabled: bool = True,
        image_concurrency: int = -1,
        video_concurrency: int = -1
    ) -> Token:
        """Add a new token

        Args:
            st: Session Token (Required)
            project_id: Project ID (Optional, if provided then used directly, no new project created)
            project_name: Project name (Optional, if not provided it is auto-generated)
            remark: Remark
            image_enabled: Whether to enable image generation
            video_enabled: Whether to enable video generation
            image_concurrency: Image concurrency limit
            video_concurrency: Video concurrency limit

        Returns:
            Token object
        """
        # Step 1: Check if ST already exists
        existing_token = await self.db.get_token_by_st(st)
        if existing_token:
            raise ValueError(f"Token already exists (Email: {existing_token.email})")

        # Step 2: Convert ST to AT using Flow client
        debug_logger.log_info(f"[ADD_TOKEN] Converting ST to AT...")
        try:
            result = await self.flow_client.st_to_at(st)
            at = result["access_token"]
            expires = result.get("expires")
            user_info = result.get("user", {})
            email = user_info.get("email", "")
            name = user_info.get("name", email.split("@")[0] if email else "")

            # Parse expiration time
            at_expires = None
            if expires:
                try:
                    at_expires = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                except:
                    pass

        except Exception as e:
            raise ValueError(f"ST to AT conversion failed: {str(e)}")

        # Step 3: Check balance
        try:
            credits_result = await self.flow_client.get_credits(at)
            credits = credits_result.get("credits", 0)
            user_paygate_tier = credits_result.get("userPaygateTier")
        except:
            credits = 0
            user_paygate_tier = None

        # Step 4: Handle Project ID and name
        if project_id:
            # User provided project_id, use it directly
            debug_logger.log_info(f"[ADD_TOKEN] Using provided project_id: {project_id}")
            if not project_name:
                # If project_name is not provided, generate one
                now = datetime.now()
                project_name = now.strftime("%b %d - %H:%M")
        else:
            # User didn't provide project_id, need to create new project
            if not project_name:
                # Auto-generate project name
                now = datetime.now()
                project_name = now.strftime("%b %d - %H:%M")

            try:
                project_id = await self.flow_client.create_project(st, project_name)
                debug_logger.log_info(f"[ADD_TOKEN] Created new project: {project_name} (ID: {project_id})")
            except Exception as e:
                raise ValueError(f"Failed to create project: {str(e)}")

        # Step 5: Create Token object
        token = Token(
            st=st,
            at=at,
            at_expires=at_expires,
            email=email,
            name=name,
            remark=remark,
            is_active=True,
            credits=credits,
            user_paygate_tier=user_paygate_tier,
            current_project_id=project_id,
            current_project_name=project_name,
            image_enabled=image_enabled,
            video_enabled=video_enabled,
            image_concurrency=image_concurrency,
            video_concurrency=video_concurrency
        )

        # Step 6: Save to database
        token_id = await self.db.add_token(token)
        token.id = token_id

        # Step 7: Save Project to database
        project = Project(
            project_id=project_id,
            token_id=token_id,
            project_name=project_name,
            tool_name="PINHOLE"
        )
        await self.db.add_project(project)

        debug_logger.log_info(f"[ADD_TOKEN] Token added successfully (ID: {token_id}, Email: {email})")
        return token

    async def update_token(
        self,
        token_id: int,
        st: Optional[str] = None,
        at: Optional[str] = None,
        at_expires: Optional[datetime] = None,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
        remark: Optional[str] = None,
        image_enabled: Optional[bool] = None,
        video_enabled: Optional[bool] = None,
        image_concurrency: Optional[int] = None,
        video_concurrency: Optional[int] = None
    ):
        """Update token (Supports modifying project_id and project_name)

        When user edits and saves token, if token is not expired, automatically clear 429 disabled status
        """
        update_fields = {}

        if st is not None:
            update_fields["st"] = st
        if at is not None:
            update_fields["at"] = at
        if at_expires is not None:
            update_fields["at_expires"] = at_expires
        if project_id is not None:
            update_fields["current_project_id"] = project_id
        if project_name is not None:
            update_fields["current_project_name"] = project_name
        if remark is not None:
            update_fields["remark"] = remark
        if image_enabled is not None:
            update_fields["image_enabled"] = image_enabled
        if video_enabled is not None:
            update_fields["video_enabled"] = video_enabled
        if image_concurrency is not None:
            update_fields["image_concurrency"] = image_concurrency
        if video_concurrency is not None:
            update_fields["video_concurrency"] = video_concurrency

        # Check if token is disabled due to 429, if so and not expired, clear 429 status
        token = await self.db.get_token(token_id)
        if token and token.ban_reason == "429_rate_limit":
            # Check if token is expired
            is_expired = False
            if token.at_expires:
                now = datetime.now(timezone.utc)
                if token.at_expires.tzinfo is None:
                    at_expires_aware = token.at_expires.replace(tzinfo=timezone.utc)
                else:
                    at_expires_aware = token.at_expires
                is_expired = at_expires_aware <= now

            # If not expired, clear 429 disabled status
            if not is_expired:
                debug_logger.log_info(f"[UPDATE_TOKEN] Token {token_id} edited and saved, clearing 429 disabled status")
                update_fields["ban_reason"] = None
                update_fields["banned_at"] = None

        if update_fields:
            await self.db.update_token(token_id, **update_fields)

    # ========== AT Auto-refresh Logic (Core) ==========

    async def is_at_valid(self, token_id: int) -> bool:
        """Check if AT is valid, automatically refresh if invalid or about to expire

        Returns:
            True if AT is valid or refreshed successfully
            False if AT cannot be refreshed
        """
        token = await self.db.get_token(token_id)
        if not token:
            return False

        # If AT doesn't exist, need to refresh
        if not token.at:
            debug_logger.log_info(f"[AT_CHECK] Token {token_id}: AT does not exist, need refresh")
            return await self._refresh_at(token_id)

        # If no expiration time, assume refresh is needed
        if not token.at_expires:
            debug_logger.log_info(f"[AT_CHECK] Token {token_id}: AT expiration time unknown, attempting refresh")
            return await self._refresh_at(token_id)

        # Check if about to expire (refresh 1 hour in advance)
        now = datetime.now(timezone.utc)
        # Ensure at_expires is also timezone-aware
        if token.at_expires.tzinfo is None:
            at_expires_aware = token.at_expires.replace(tzinfo=timezone.utc)
        else:
            at_expires_aware = token.at_expires

        time_until_expiry = at_expires_aware - now

        if time_until_expiry.total_seconds() < 3600:  # 1 hour (3600 seconds)
            debug_logger.log_info(f"[AT_CHECK] Token {token_id}: AT about to expire ({time_until_expiry.total_seconds():.0f} seconds remaining), need refresh")
            return await self._refresh_at(token_id)

        # AT is valid
        return True

    async def _refresh_at(self, token_id: int) -> bool:
        """Internal method: refresh AT

        Returns:
            True if refresh successful, False otherwise
        """
        async with self._lock:
            token = await self.db.get_token(token_id)
            if not token:
                return False

            try:
                debug_logger.log_info(f"[AT_REFRESH] Token {token_id}: Starting AT refresh...")

                # Use ST to AT conversion
                result = await self.flow_client.st_to_at(token.st)
                new_at = result["access_token"]
                expires = result.get("expires")

                # Parse expiration time
                new_at_expires = None
                if expires:
                    try:
                        new_at_expires = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                    except:
                        pass

                # Update database
                await self.db.update_token(
                    token_id,
                    at=new_at,
                    at_expires=new_at_expires
                )

                debug_logger.log_info(f"[AT_REFRESH] Token {token_id}: AT refreshed successfully")
                debug_logger.log_info(f"  - New expiration time: {new_at_expires}")

                # Also refresh credits
                try:
                    credits_result = await self.flow_client.get_credits(new_at)
                    await self.db.update_token(
                        token_id,
                        credits=credits_result.get("credits", 0)
                    )
                except:
                    pass

                return True

            except Exception as e:
                debug_logger.log_error(f"[AT_REFRESH] Token {token_id}: AT refresh failed - {str(e)}")
                # Refresh failed, disable Token
                await self.disable_token(token_id)
                return False

    async def ensure_project_exists(self, token_id: int) -> str:
        """Ensure token has an available Project

        Returns:
            project_id
        """
        token = await self.db.get_token(token_id)
        if not token:
            raise ValueError("Token not found")

        # If already has project_id, return directly
        if token.current_project_id:
            return token.current_project_id

        # Create new Project
        now = datetime.now()
        project_name = now.strftime("%b %d - %H:%M")

        try:
            project_id = await self.flow_client.create_project(token.st, project_name)
            debug_logger.log_info(f"[PROJECT] Created project for token {token_id}: {project_name}")

            # Update Token
            await self.db.update_token(
                token_id,
                current_project_id=project_id,
                current_project_name=project_name
            )

            # Save Project to database
            project = Project(
                project_id=project_id,
                token_id=token_id,
                project_name=project_name
            )
            await self.db.add_project(project)

            return project_id

        except Exception as e:
            raise ValueError(f"Failed to create project: {str(e)}")

    # ========== Token Usage Statistics ==========

    async def record_usage(self, token_id: int, is_video: bool = False):
        """Record token usage"""
        await self.db.update_token(token_id, use_count=1, last_used_at=datetime.now())

        if is_video:
            await self.db.increment_token_stats(token_id, "video")
        else:
            await self.db.increment_token_stats(token_id, "image")

    async def record_error(self, token_id: int):
        """Record token error and auto-disable if threshold reached"""
        await self.db.increment_token_stats(token_id, "error")

        # Check if should auto-disable token (based on consecutive errors)
        stats = await self.db.get_token_stats(token_id)
        admin_config = await self.db.get_admin_config()

        if stats and stats.consecutive_error_count >= admin_config.error_ban_threshold:
            debug_logger.log_warning(
                f"[TOKEN_BAN] Token {token_id} consecutive error count ({stats.consecutive_error_count}) "
                f"reached threshold ({admin_config.error_ban_threshold}), auto-disabling"
            )
            await self.disable_token(token_id)

    async def record_success(self, token_id: int):
        """Record successful request (reset consecutive error count)

        This method resets error_count to 0, which is used for auto-disable threshold checking.
        Note: today_error_count and historical statistics are NOT reset.
        """
        await self.db.reset_error_count(token_id)

    async def ban_token_for_429(self, token_id: int):
        """Immediately disable token due to 429 error

        Args:
            token_id: Token ID
        """
        debug_logger.log_warning(f"[429_BAN] Disabling Token {token_id} (Reason: 429 Rate Limit)")
        await self.db.update_token(
            token_id,
            is_active=False,
            ban_reason="429_rate_limit",
            banned_at=datetime.now(timezone.utc)
        )

    async def auto_unban_429_tokens(self):
        """Automatically unban tokens disabled due to 429

        Rules:
        - Automatically unban 12 hours after disabling
        - Only unban tokens that have not expired
        - Only unban tokens disabled due to 429
        """
        all_tokens = await self.db.get_all_tokens()
        now = datetime.now(timezone.utc)

        for token in all_tokens:
            # Skip tokens not disabled by 429
            if token.ban_reason != "429_rate_limit":
                continue

            # Skip tokens that are already active
            if token.is_active:
                continue

            # Skip tokens without a ban time
            if not token.banned_at:
                continue

            # Check if token has already expired
            if token.at_expires:
                # Ensure timezone consistency
                if token.at_expires.tzinfo is None:
                    at_expires_aware = token.at_expires.replace(tzinfo=timezone.utc)
                else:
                    at_expires_aware = token.at_expires

                # If already expired, skip
                if at_expires_aware <= now:
                    debug_logger.log_info(f"[AUTO_UNBAN] Token {token.id} has expired, skipping unban")
                    continue

            # Ensure banned_at timezone consistency
            if token.banned_at.tzinfo is None:
                banned_at_aware = token.banned_at.replace(tzinfo=timezone.utc)
            else:
                banned_at_aware = token.banned_at

            # Check if 12 hours have passed
            time_since_ban = now - banned_at_aware
            if time_since_ban.total_seconds() >= 12 * 3600:  # 12 hours
                debug_logger.log_info(
                    f"[AUTO_UNBAN] Unbanning Token {token.id} (Banned at: {banned_at_aware}, "
                    f"{time_since_ban.total_seconds() / 3600:.1f} hours passed)"
                )
                await self.db.update_token(
                    token.id,
                    is_active=True,
                    ban_reason=None,
                    banned_at=None
                )
                # Reset error count
                await self.db.reset_error_count(token.id)

    # ========== Balance Refresh ==========

    async def refresh_credits(self, token_id: int) -> int:
        """Refresh token balance

        Returns:
            credits
        """
        token = await self.db.get_token(token_id)
        if not token:
            return 0

        # Ensure AT is valid
        if not await self.is_at_valid(token_id):
            return 0

        # Re-get token (AT might have been refreshed)
        token = await self.db.get_token(token_id)

        try:
            result = await self.flow_client.get_credits(token.at)
            credits = result.get("credits", 0)

            # Update database
            await self.db.update_token(token_id, credits=credits)

            return credits
        except Exception as e:
            debug_logger.log_error(f"Failed to refresh credits for token {token_id}: {str(e)}")
            return 0
