"""Flow API Client for VideoFX (Veo)"""
import time
import uuid
import random
import base64
from typing import Dict, Any, Optional, List
from curl_cffi.requests import AsyncSession
from ..core.logger import debug_logger
from ..core.config import config


class FlowClient:
    """VideoFX API Client"""

    def __init__(self, proxy_manager):
        self.proxy_manager = proxy_manager
        self.labs_base_url = config.flow_labs_base_url  # https://labs.google/fx/api
        self.api_base_url = config.flow_api_base_url    # https://aisandbox-pa.googleapis.com/v1
        self.timeout = config.flow_timeout

    async def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        use_st: bool = False,
        st_token: Optional[str] = None,
        use_at: bool = False,
        at_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Unified HTTP request handling

        Args:
            method: HTTP method (GET/POST)
            url: Complete URL
            headers: Request headers
            json_data: JSON request body
            use_st: Whether to use ST authentication (Cookie method)
            st_token: Session Token
            use_at: Whether to use AT authentication (Bearer method)
            at_token: Access Token
        """
        proxy_url = await self.proxy_manager.get_proxy_url()

        if headers is None:
            headers = {}

        # ST Authentication - use Cookie
        if use_st and st_token:
            headers["Cookie"] = f"__Secure-next-auth.session-token={st_token}"

        # AT Authentication - use Bearer
        if use_at and at_token:
            headers["authorization"] = f"Bearer {at_token}"

        # Common request headers
        headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        # Log request
        if config.debug_enabled:
            debug_logger.log_request(
                method=method,
                url=url,
                headers=headers,
                body=json_data,
                proxy=proxy_url
            )

        start_time = time.time()

        try:
            async with AsyncSession() as session:
                if method.upper() == "GET":
                    response = await session.get(
                        url,
                        headers=headers,
                        proxy=proxy_url,
                        timeout=self.timeout,
                        impersonate="chrome110"
                    )
                else:  # POST
                    response = await session.post(
                        url,
                        headers=headers,
                        json=json_data,
                        proxy=proxy_url,
                        timeout=self.timeout,
                        impersonate="chrome110"
                    )

                duration_ms = (time.time() - start_time) * 1000

                # Log response
                if config.debug_enabled:
                    debug_logger.log_response(
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        body=response.text,
                        duration_ms=duration_ms
                    )

                response.raise_for_status()
                return response.json()

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = str(e)

            if config.debug_enabled:
                debug_logger.log_error(
                    error_message=error_msg,
                    status_code=getattr(e, 'status_code', None),
                    response_text=getattr(e, 'response_text', None)
                )

            raise Exception(f"Flow API request failed: {error_msg}")

    # ========== Authentication related (using ST) ==========

    async def st_to_at(self, st: str) -> dict:
        """Convert ST to AT

        Args:
            st: Session Token

        Returns:
            {
                "access_token": "AT",
                "expires": "2025-11-15T04:46:04.000Z",
                "user": {...}
            }
        """
        url = f"{self.labs_base_url}/auth/session"
        result = await self._make_request(
            method="GET",
            url=url,
            use_st=True,
            st_token=st
        )
        return result

    # ========== Project Management (using ST) ==========

    async def create_project(self, st: str, title: str) -> str:
        """Create project, return project_id

        Args:
            st: Session Token
            title: Project title

        Returns:
            project_id (UUID)
        """
        url = f"{self.labs_base_url}/trpc/project.createProject"
        json_data = {
            "json": {
                "projectTitle": title,
                "toolName": "PINHOLE"
            }
        }

        result = await self._make_request(
            method="POST",
            url=url,
            json_data=json_data,
            use_st=True,
            st_token=st
        )

        # Parse returned project_id
        project_id = result["result"]["data"]["json"]["result"]["projectId"]
        return project_id

    async def delete_project(self, st: str, project_id: str):
        """Delete project

        Args:
            st: Session Token
            project_id: Project ID
        """
        url = f"{self.labs_base_url}/trpc/project.deleteProject"
        json_data = {
            "json": {
                "projectToDeleteId": project_id
            }
        }

        await self._make_request(
            method="POST",
            url=url,
            json_data=json_data,
            use_st=True,
            st_token=st
        )

    # ========== Balance Query (using AT) ==========

    async def get_credits(self, at: str) -> dict:
        """Query balance

        Args:
            at: Access Token

        Returns:
            {
                "credits": 920,
                "userPaygateTier": "PAYGATE_TIER_ONE"
            }
        """
        url = f"{self.api_base_url}/credits"
        result = await self._make_request(
            method="GET",
            url=url,
            use_at=True,
            at_token=at
        )
        return result

    # ========== Image Upload (using AT) ==========

    async def upload_image(
        self,
        at: str,
        image_bytes: bytes,
        aspect_ratio: str = "IMAGE_ASPECT_RATIO_LANDSCAPE"
    ) -> str:
        """Upload image, return mediaGenerationId

        Args:
            at: Access Token
            image_bytes: Image byte data
            aspect_ratio: Image or video aspect ratio (automatically converted to image format)

        Returns:
            mediaGenerationId (CAM...)
        """
        # Convert video aspect_ratio to image aspect_ratio
        # VIDEO_ASPECT_RATIO_LANDSCAPE -> IMAGE_ASPECT_RATIO_LANDSCAPE
        # VIDEO_ASPECT_RATIO_PORTRAIT -> IMAGE_ASPECT_RATIO_PORTRAIT
        if aspect_ratio.startswith("VIDEO_"):
            aspect_ratio = aspect_ratio.replace("VIDEO_", "IMAGE_")

        # Encode as base64 (remove prefix)
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        url = f"{self.api_base_url}:uploadUserImage"
        json_data = {
            "imageInput": {
                "rawImageBytes": image_base64,
                "mimeType": "image/jpeg",
                "isUserUploaded": True,
                "aspectRatio": aspect_ratio
            },
            "clientContext": {
                "sessionId": self._generate_session_id(),
                "tool": "ASSET_MANAGER"
            }
        }

        result = await self._make_request(
            method="POST",
            url=url,
            json_data=json_data,
            use_at=True,
            at_token=at
        )

        # Return mediaGenerationId
        media_id = result["mediaGenerationId"]["mediaGenerationId"]
        return media_id

    # ========== Image Generation (using AT) - Synchronous Return ==========

    async def generate_image(
        self,
        at: str,
        project_id: str,
        prompt: str,
        model_name: str,
        aspect_ratio: str,
        image_inputs: Optional[List[Dict]] = None
    ) -> dict:
        """Generate image (synchronous return)

        Args:
            at: Access Token
            project_id: Project ID
            prompt: Prompt text
            model_name: GEM_PIX, GEM_PIX_2 or IMAGEN_3_5
            aspect_ratio: Image aspect ratio
            image_inputs: Reference image list (used for image-to-image)

        Returns:
            {
                "media": [{
                    "image": {
                        "generatedImage": {
                            "fifeUrl": "Image URL",
                            ...
                        }
                    }
                }]
            }
        """
        url = f"{self.api_base_url}/projects/{project_id}/flowMedia:batchGenerateImages"

        # Get reCAPTCHA token
        recaptcha_token = await self._get_recaptcha_token(project_id) or ""
        session_id = self._generate_session_id()

        # Build request
        request_data = {
            "clientContext": {
                "recaptchaToken": recaptcha_token,
                "projectId": project_id,
                "sessionId": session_id,
                "tool": "PINHOLE"
            },
            "seed": random.randint(1, 99999),
            "imageModelName": model_name,
            "imageAspectRatio": aspect_ratio,
            "prompt": prompt,
            "imageInputs": image_inputs or []
        }

        json_data = {
            "clientContext": {
                "recaptchaToken": recaptcha_token,
                "sessionId": session_id
            },
            "requests": [request_data]
        }

        result = await self._make_request(
            method="POST",
            url=url,
            json_data=json_data,
            use_at=True,
            at_token=at
        )

        return result

    # ========== Video Generation (using AT) - Asynchronous Return ==========

    async def generate_video_text(
        self,
        at: str,
        project_id: str,
        prompt: str,
        model_key: str,
        aspect_ratio: str,
        user_paygate_tier: str = "PAYGATE_TIER_ONE"
    ) -> dict:
        """Text to video, return task_id

        Args:
            at: Access Token
            project_id: Project ID
            prompt: Prompt text
            model_key: veo_3_1_t2v_fast etc.
            aspect_ratio: Video aspect ratio
            user_paygate_tier: User tier

        Returns:
            {
                "operations": [{
                    "operation": {"name": "task_id"},
                    "sceneId": "uuid",
                    "status": "MEDIA_GENERATION_STATUS_PENDING"
                }],
                "remainingCredits": 900
            }
        """
        url = f"{self.api_base_url}/video:batchAsyncGenerateVideoText"

        # Get reCAPTCHA token
        recaptcha_token = await self._get_recaptcha_token(project_id) or ""
        session_id = self._generate_session_id()
        scene_id = str(uuid.uuid4())

        json_data = {
            "clientContext": {
                "recaptchaToken": recaptcha_token,
                "sessionId": session_id,
                "projectId": project_id,
                "tool": "PINHOLE",
                "userPaygateTier": user_paygate_tier
            },
            "requests": [{
                "aspectRatio": aspect_ratio,
                "seed": random.randint(1, 99999),
                "textInput": {
                    "prompt": prompt
                },
                "videoModelKey": model_key,
                "metadata": {
                    "sceneId": scene_id
                }
            }]
        }

        result = await self._make_request(
            method="POST",
            url=url,
            json_data=json_data,
            use_at=True,
            at_token=at
        )

        return result

    async def generate_video_reference_images(
        self,
        at: str,
        project_id: str,
        prompt: str,
        model_key: str,
        aspect_ratio: str,
        reference_images: List[Dict],
        user_paygate_tier: str = "PAYGATE_TIER_ONE"
    ) -> dict:
        """Image to video, return task_id

        Args:
            at: Access Token
            project_id: Project ID
            prompt: Prompt text
            model_key: veo_3_0_r2v_fast
            aspect_ratio: Video aspect ratio
            reference_images: Reference image list [{"imageUsageType": "IMAGE_USAGE_TYPE_ASSET", "mediaId": "..."}]
            user_paygate_tier: User tier

        Returns:
            Same as generate_video_text
        """
        url = f"{self.api_base_url}/video:batchAsyncGenerateVideoReferenceImages"

        # Get reCAPTCHA token
        recaptcha_token = await self._get_recaptcha_token(project_id) or ""
        session_id = self._generate_session_id()
        scene_id = str(uuid.uuid4())

        json_data = {
            "clientContext": {
                "recaptchaToken": recaptcha_token,
                "sessionId": session_id,
                "projectId": project_id,
                "tool": "PINHOLE",
                "userPaygateTier": user_paygate_tier
            },
            "requests": [{
                "aspectRatio": aspect_ratio,
                "seed": random.randint(1, 99999),
                "textInput": {
                    "prompt": prompt
                },
                "videoModelKey": model_key,
                "referenceImages": reference_images,
                "metadata": {
                    "sceneId": scene_id
                }
            }]
        }

        result = await self._make_request(
            method="POST",
            url=url,
            json_data=json_data,
            use_at=True,
            at_token=at
        )

        return result

    async def generate_video_start_end(
        self,
        at: str,
        project_id: str,
        prompt: str,
        model_key: str,
        aspect_ratio: str,
        start_media_id: str,
        end_media_id: str,
        user_paygate_tier: str = "PAYGATE_TIER_ONE"
    ) -> dict:
        """Head and tail frame video generation, return task_id

        Args:
            at: Access Token
            project_id: Project ID
            prompt: Prompt text
            model_key: veo_3_1_i2v_s_fast_fl
            aspect_ratio: Video aspect ratio
            start_media_id: Start frame mediaId
            end_media_id: End frame mediaId
            user_paygate_tier: User tier

        Returns:
            Same as generate_video_text
        """
        url = f"{self.api_base_url}/video:batchAsyncGenerateVideoStartAndEndImage"

        # Get reCAPTCHA token
        recaptcha_token = await self._get_recaptcha_token(project_id) or ""
        session_id = self._generate_session_id()
        scene_id = str(uuid.uuid4())

        json_data = {
            "clientContext": {
                "recaptchaToken": recaptcha_token,
                "sessionId": session_id,
                "projectId": project_id,
                "tool": "PINHOLE",
                "userPaygateTier": user_paygate_tier
            },
            "requests": [{
                "aspectRatio": aspect_ratio,
                "seed": random.randint(1, 99999),
                "textInput": {
                    "prompt": prompt
                },
                "videoModelKey": model_key,
                "startImage": {
                    "mediaId": start_media_id
                },
                "endImage": {
                    "mediaId": end_media_id
                },
                "metadata": {
                    "sceneId": scene_id
                }
            }]
        }

        result = await self._make_request(
            method="POST",
            url=url,
            json_data=json_data,
            use_at=True,
            at_token=at
        )

        return result

    async def generate_video_start_image(
        self,
        at: str,
        project_id: str,
        prompt: str,
        model_key: str,
        aspect_ratio: str,
        start_media_id: str,
        user_paygate_tier: str = "PAYGATE_TIER_ONE"
    ) -> dict:
        """Start frame only video generation, return task_id

        Args:
            at: Access Token
            project_id: Project ID
            prompt: Prompt text
            model_key: veo_3_1_i2v_s_fast_fl etc.
            aspect_ratio: Video aspect ratio
            start_media_id: Start frame mediaId
            user_paygate_tier: User tier

        Returns:
            Same as generate_video_text
        """
        url = f"{self.api_base_url}/video:batchAsyncGenerateVideoStartAndEndImage"

        # Get reCAPTCHA token
        recaptcha_token = await self._get_recaptcha_token(project_id) or ""
        session_id = self._generate_session_id()
        scene_id = str(uuid.uuid4())

        json_data = {
            "clientContext": {
                "recaptchaToken": recaptcha_token,
                "sessionId": session_id,
                "projectId": project_id,
                "tool": "PINHOLE",
                "userPaygateTier": user_paygate_tier
            },
            "requests": [{
                "aspectRatio": aspect_ratio,
                "seed": random.randint(1, 99999),
                "textInput": {
                    "prompt": prompt
                },
                "videoModelKey": model_key,
                "startImage": {
                    "mediaId": start_media_id
                },
                # Note: No endImage field, only start frame used
                "metadata": {
                    "sceneId": scene_id
                }
            }]
        }

        result = await self._make_request(
            method="POST",
            url=url,
            json_data=json_data,
            use_at=True,
            at_token=at
        )

        return result

    # ========== Task Polling (using AT) ==========

    async def check_video_status(self, at: str, operations: List[Dict]) -> dict:
        """Check video generation status

        Args:
            at: Access Token
            operations: Operation list [{"operation": {"name": "task_id"}, "sceneId": "...", "status": "..."}]

        Returns:
            {
                "operations": [{
                    "operation": {
                        "name": "task_id",
                        "metadata": {...}  # Includes video info when complete
                    },
                    "status": "MEDIA_GENERATION_STATUS_SUCCESSFUL"
                }]
            }
        """
        url = f"{self.api_base_url}/video:batchCheckAsyncVideoGenerationStatus"

        json_data = {
            "operations": operations
        }

        result = await self._make_request(
            method="POST",
            url=url,
            json_data=json_data,
            use_at=True,
            at_token=at
        )

        return result

    # ========== Media Deletion (using ST) ==========

    async def delete_media(self, st: str, media_names: List[str]):
        """Delete media

        Args:
            st: Session Token
            media_names: Media ID list
        """
        url = f"{self.labs_base_url}/trpc/media.deleteMedia"
        json_data = {
            "json": {
                "names": media_names
            }
        }

        await self._make_request(
            method="POST",
            url=url,
            json_data=json_data,
            use_st=True,
            st_token=st
        )

    # ========== Helper Methods ==========

    def _generate_session_id(self) -> str:
        """Generate sessionId: ;timestamp"""
        return f";{int(time.time() * 1000)}"

    def _generate_scene_id(self) -> str:
        """Generate sceneId: UUID"""
        return str(uuid.uuid4())

    async def _get_recaptcha_token(self, project_id: str) -> Optional[str]:
        """Get reCAPTCHA token - Supports two methods"""
        captcha_method = config.captcha_method

        # Permanent browser captcha
        if captcha_method == "personal":
            try:
                from .browser_captcha_personal import BrowserCaptchaService
                service = await BrowserCaptchaService.get_instance(self.proxy_manager)
                return await service.get_token(project_id)
            except Exception as e:
                debug_logger.log_error(f"[reCAPTCHA Browser] error: {str(e)}")
                return None
        # Headless browser captcha
        elif captcha_method == "browser":
            try:
                from .browser_captcha import BrowserCaptchaService
                service = await BrowserCaptchaService.get_instance(self.proxy_manager)
                return await service.get_token(project_id)
            except Exception as e:
                debug_logger.log_error(f"[reCAPTCHA Browser] error: {str(e)}")
                return None
        else:
            # YesCaptcha captcha
            client_key = config.yescaptcha_api_key
            if not client_key:
                debug_logger.log_info("[reCAPTCHA] API key not configured, skipping")
                return None

            website_key = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"
            website_url = f"https://labs.google/fx/tools/flow/project/{project_id}"
            base_url = config.yescaptcha_base_url
            page_action = "FLOW_GENERATION"

            try:
                async with AsyncSession() as session:
                    create_url = f"{base_url}/createTask"
                    create_data = {
                        "clientKey": client_key,
                        "task": {
                            "websiteURL": website_url,
                            "websiteKey": website_key,
                            "type": "RecaptchaV3TaskProxylessM1",
                            "pageAction": page_action
                        }
                    }

                    result = await session.post(create_url, json=create_data, impersonate="chrome110")
                    result_json = result.json()
                    task_id = result_json.get('taskId')

                    debug_logger.log_info(f"[reCAPTCHA] created task_id: {task_id}")

                    if not task_id:
                        return None

                    get_url = f"{base_url}/getTaskResult"
                    for i in range(40):
                        get_data = {
                            "clientKey": client_key,
                            "taskId": task_id
                        }
                        result = await session.post(get_url, json=get_data, impersonate="chrome110")
                        result_json = result.json()

                        debug_logger.log_info(f"[reCAPTCHA] polling #{i+1}: {result_json}")

                        solution = result_json.get('solution', {})
                        response = solution.get('gRecaptchaResponse')

                        if response:
                            return response

                        time.sleep(3)

                    return None

            except Exception as e:
                debug_logger.log_error(f"[reCAPTCHA] error: {str(e)}")
                return None
