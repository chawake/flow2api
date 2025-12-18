"""Generation handler for Flow2API"""
import asyncio
import base64
import json
import time
from typing import Optional, AsyncGenerator, List, Dict, Any
from ..core.logger import debug_logger
from ..core.config import config
from ..core.models import Task, RequestLog
from .file_cache import FileCache


# Model configuration
MODEL_CONFIG = {
    # Image generation - GEM_PIX (Gemini 2.5 Flash)
    "gemini-2.5-flash-image-landscape": {
        "type": "image",
        "model_name": "GEM_PIX",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE"
    },
    "gemini-2.5-flash-image-portrait": {
        "type": "image",
        "model_name": "GEM_PIX",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT"
    },

    # Image generation - GEM_PIX_2 (Gemini 3.0 Pro)
    "gemini-3.0-pro-image-landscape": {
        "type": "image",
        "model_name": "GEM_PIX_2",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE"
    },
    "gemini-3.0-pro-image-portrait": {
        "type": "image",
        "model_name": "GEM_PIX_2",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT"
    },

    # Image generation - IMAGEN_3_5 (Imagen 4.0)
    "imagen-4.0-generate-preview-landscape": {
        "type": "image",
        "model_name": "IMAGEN_3_5",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE"
    },
    "imagen-4.0-generate-preview-portrait": {
        "type": "image",
        "model_name": "IMAGEN_3_5",
        "aspect_ratio": "IMAGE_ASPECT_RATIO_PORTRAIT"
    },

    # ========== Text to Video (T2V) ==========
    # No image upload supported, only text prompts for generation

    # veo_3_1_t2v_fast_portrait (Portrait)
    # Upstream model name: veo_3_1_t2v_fast_portrait
    "veo_3_1_t2v_fast_portrait": {
        "type": "video",
        "video_type": "t2v",
        "model_key": "veo_3_1_t2v_fast_portrait",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
        "supports_images": False
    },
    # veo_3_1_t2v_fast_landscape (Landscape)
    # Upstream model name: veo_3_1_t2v_fast
    "veo_3_1_t2v_fast_landscape": {
        "type": "video",
        "video_type": "t2v",
        "model_key": "veo_3_1_t2v_fast",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
        "supports_images": False
    },

    # veo_2_1_fast_d_15_t2v (Landscape and Portrait)
    "veo_2_1_fast_d_15_t2v_portrait": {
        "type": "video",
        "video_type": "t2v",
        "model_key": "veo_2_1_fast_d_15_t2v",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
        "supports_images": False
    },
    "veo_2_1_fast_d_15_t2v_landscape": {
        "type": "video",
        "video_type": "t2v",
        "model_key": "veo_2_1_fast_d_15_t2v",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
        "supports_images": False
    },

    # veo_2_0_t2v (Landscape and Portrait)
    "veo_2_0_t2v_portrait": {
        "type": "video",
        "video_type": "t2v",
        "model_key": "veo_2_0_t2v",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
        "supports_images": False
    },
    "veo_2_0_t2v_landscape": {
        "type": "video",
        "video_type": "t2v",
        "model_key": "veo_2_0_t2v",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
        "supports_images": False
    },

    # ========== Image to Video (I2V) ==========
    # Support 1-2 images: 1 as start frame, 2 as start and end frames 

    # veo_3_1_i2v_s_fast_fl (Landscape and Portrait)
    "veo_3_1_i2v_s_fast_fl_portrait": {
        "type": "video",
        "video_type": "i2v",
        "model_key": "veo_3_1_i2v_s_fast_fl",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
        "supports_images": True,
        "min_images": 1,
        "max_images": 2
    },
    "veo_3_1_i2v_s_fast_fl_landscape": {
        "type": "video",
        "video_type": "i2v",
        "model_key": "veo_3_1_i2v_s_fast_fl",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
        "supports_images": True,
        "min_images": 1,
        "max_images": 2
    },

    # veo_2_1_fast_d_15_i2v (Landscape and Portrait)
    "veo_2_1_fast_d_15_i2v_portrait": {
        "type": "video",
        "video_type": "i2v",
        "model_key": "veo_2_1_fast_d_15_i2v",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
        "supports_images": True,
        "min_images": 1,
        "max_images": 2
    },
    "veo_2_1_fast_d_15_i2v_landscape": {
        "type": "video",
        "video_type": "i2v",
        "model_key": "veo_2_1_fast_d_15_i2v",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
        "supports_images": True,
        "min_images": 1,
        "max_images": 2
    },

    # veo_2_0_i2v (Landscape and Portrait)
    "veo_2_0_i2v_portrait": {
        "type": "video",
        "video_type": "i2v",
        "model_key": "veo_2_0_i2v",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
        "supports_images": True,
        "min_images": 1,
        "max_images": 2
    },
    "veo_2_0_i2v_landscape": {
        "type": "video",
        "video_type": "i2v",
        "model_key": "veo_2_0_i2v",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
        "supports_images": True,
        "min_images": 1,
        "max_images": 2
    },

    # ========== Reference Images to Video (R2V) ==========
    # Supports multiple images, no quantity limit

    # veo_3_0_r2v_fast (Landscape and Portrait)
    "veo_3_0_r2v_fast_portrait": {
        "type": "video",
        "video_type": "r2v",
        "model_key": "veo_3_0_r2v_fast",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT",
        "supports_images": True,
        "min_images": 0,
        "max_images": None  # No limit
    },
    "veo_3_0_r2v_fast_landscape": {
        "type": "video",
        "video_type": "r2v",
        "model_key": "veo_3_0_r2v_fast",
        "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
        "supports_images": True,
        "min_images": 0,
        "max_images": None  # No limit
    }
}


class GenerationHandler:
    """Unified generation handler"""

    def __init__(self, flow_client, token_manager, load_balancer, db, concurrency_manager, proxy_manager):
        self.flow_client = flow_client
        self.token_manager = token_manager
        self.load_balancer = load_balancer
        self.db = db
        self.concurrency_manager = concurrency_manager
        self.file_cache = FileCache(
            cache_dir="tmp",
            default_timeout=config.cache_timeout,
            proxy_manager=proxy_manager
        )

    async def check_token_availability(self, is_image: bool, is_video: bool) -> bool:
        """Check token availability

        Args:
            is_image: Whether to check token for image generation
            is_video: Whether to check token for video generation

        Returns:
            True means token is available, False means no token is available
        """
        token_obj = await self.load_balancer.select_token(
            for_image_generation=is_image,
            for_video_generation=is_video
        )
        return token_obj is not None

    async def handle_generation(
        self,
        model: str,
        prompt: str,
        images: Optional[List[bytes]] = None,
        stream: bool = False
    ) -> AsyncGenerator:
        """Unified generation entry point

        Args:
            model: Model name
            prompt: Prompt
            images: Image list (bytes format)
            stream: Whether to stream output
        """
        start_time = time.time()
        token = None

        # 1. Validate model
        if model not in MODEL_CONFIG:
            error_msg = f"Unsupported model: {model}"
            debug_logger.log_error(error_msg)
            yield self._create_error_response(error_msg)
            return

        model_config = MODEL_CONFIG[model]
        generation_type = model_config["type"]
        debug_logger.log_info(f"[GENERATION] Starting generation - Model: {model}, Type: {generation_type}, Prompt: {prompt[:50]}...")

        # Non-streaming mode: only check availability
        if not stream:
            is_image = (generation_type == "image")
            is_video = (generation_type == "video")
            available = await self.check_token_availability(is_image, is_video)

            if available:
                if is_image:
                    message = "All tokens are available for image generation. Please enable streaming mode to use generation functionality."
                else:
                    message = "All tokens are available for video generation. Please enable streaming mode to use generation functionality."
            else:
                if is_image:
                    message = "No tokens available for image generation"
                else:
                    message = "No tokens available for video generation"

            yield self._create_completion_response(message, is_availability_check=True)
            return

        # Show start info to user
        if stream:
            yield self._create_stream_chunk(
                f"✨ {'Video' if generation_type == 'video' else 'Image'} generation task started\n",
                role="assistant"
            )

        # 2. Select Token
        debug_logger.log_info(f"[GENERATION] Selecting available token...")

        if generation_type == "image":
            token = await self.load_balancer.select_token(for_image_generation=True, model=model)
        else:
            token = await self.load_balancer.select_token(for_video_generation=True, model=model)

        if not token:
            error_msg = self._get_no_token_error_message(generation_type)
            debug_logger.log_error(f"[GENERATION] {error_msg}")
            if stream:
                yield self._create_stream_chunk(f"❌ {error_msg}\n")
            yield self._create_error_response(error_msg)
            return

        debug_logger.log_info(f"[GENERATION] Token selected: {token.id} ({token.email})")

        try:
            # 3. Ensure AT is valid
            debug_logger.log_info(f"[GENERATION] Checking token AT validity...")
            if stream:
                yield self._create_stream_chunk("Initializing generation environment...\n")

            if not await self.token_manager.is_at_valid(token.id):
                error_msg = "Token AT invalid or refresh failed"
                debug_logger.log_error(f"[GENERATION] {error_msg}")
                if stream:
                    yield self._create_stream_chunk(f"❌ {error_msg}\n")
                yield self._create_error_response(error_msg)
                return

            # Re-get token (AT may have refreshed)
            token = await self.token_manager.get_token(token.id)

            # 4. Ensure Project exists
            debug_logger.log_info(f"[GENERATION] Checking/creating Project...")

            project_id = await self.token_manager.ensure_project_exists(token.id)
            debug_logger.log_info(f"[GENERATION] Project ID: {project_id}")

            # 5. Handle based on type
            if generation_type == "image":
                debug_logger.log_info(f"[GENERATION] Starting image generation flow...")
                async for chunk in self._handle_image_generation(
                    token, project_id, model_config, prompt, images, stream
                ):
                    yield chunk
            else:  # video
                debug_logger.log_info(f"[GENERATION] Starting video generation flow...")
                async for chunk in self._handle_video_generation(
                    token, project_id, model_config, prompt, images, stream
                ):
                    yield chunk

            # 6. Record usage
            is_video = (generation_type == "video")
            await self.token_manager.record_usage(token.id, is_video=is_video)

            # Reset error count (Clear consecutive error count on successful request)
            await self.token_manager.record_success(token.id)

            debug_logger.log_info(f"[GENERATION] ✅ Generation completed successfully")

            # 7. Record success log
            duration = time.time() - start_time
            await self._log_request(
                token.id,
                f"generate_{generation_type}",
                {"model": model, "prompt": prompt[:100], "has_images": images is not None and len(images) > 0},
                {"status": "success"},
                200,
                duration
            )

        except Exception as e:
            error_msg = f"Generation failed: {str(e)}"
            debug_logger.log_error(f"[GENERATION] ❌ {error_msg}")
            if stream:
                yield self._create_stream_chunk(f"❌ {error_msg}\n")
            if token:
                # Detect 429 error, immediately disable token
                if "429" in str(e) or "HTTP Error 429" in str(e):
                    debug_logger.log_warning(f"[429_BAN] Token {token.id} encountered 429 error, disabling immediately")
                    await self.token_manager.ban_token_for_429(token.id)
                else:
                    await self.token_manager.record_error(token.id)
            yield self._create_error_response(error_msg)

            # Record failure log
            duration = time.time() - start_time
            await self._log_request(
                token.id if token else None,
                f"generate_{generation_type if model_config else 'unknown'}",
                {"model": model, "prompt": prompt[:100], "has_images": images is not None and len(images) > 0},
                {"error": error_msg},
                500,
                duration
            )

    def _get_no_token_error_message(self, generation_type: str) -> str:
        """Get detailed error message when no token is available"""
        if generation_type == "image":
            return "No tokens available for image generation. All tokens are disabled, in cooldown, locked, or expired."
        else:
            return "No tokens available for video generation. All tokens are disabled, in cooldown, quota exhausted, or expired."

    async def _handle_image_generation(
        self,
        token,
        project_id: str,
        model_config: dict,
        prompt: str,
        images: Optional[List[bytes]],
        stream: bool
    ) -> AsyncGenerator:
        """Process image generation (Synchronous return)"""

        # Acquire concurrency slot
        if self.concurrency_manager:
            if not await self.concurrency_manager.acquire_image(token.id):
                yield self._create_error_response("Image concurrency limit reached")
                return

        try:
            # Upload images (if any)
            image_inputs = []
            if images and len(images) > 0:
                if stream:
                    yield self._create_stream_chunk(f"Uploading {len(images)} reference images...\n")

                # Support multi-image input
                for idx, image_bytes in enumerate(images):
                    media_id = await self.flow_client.upload_image(
                        token.at,
                        image_bytes,
                        model_config["aspect_ratio"]
                    )
                    image_inputs.append({
                        "name": media_id,
                        "imageInputType": "IMAGE_INPUT_TYPE_REFERENCE"
                    })
                    if stream:
                        yield self._create_stream_chunk(f"Uploaded {idx + 1}/{len(images)} images\n")

            # Call generation API
            if stream:
                yield self._create_stream_chunk("Generating image...\n")

            result = await self.flow_client.generate_image(
                at=token.at,
                project_id=project_id,
                prompt=prompt,
                model_name=model_config["model_name"],
                aspect_ratio=model_config["aspect_ratio"],
                image_inputs=image_inputs
            )

            # Extract URL
            media = result.get("media", [])
            if not media:
                yield self._create_error_response("Generation result is empty")
                return

            image_url = media[0]["image"]["generatedImage"]["fifeUrl"]

            # Cache image (if enabled)
            local_url = image_url
            if config.cache_enabled:
                try:
                    if stream:
                        yield self._create_stream_chunk("Caching image...\n")
                    cached_filename = await self.file_cache.download_and_cache(image_url, "image")
                    local_url = f"{self._get_base_url()}/tmp/{cached_filename}"
                    if stream:
                        yield self._create_stream_chunk("✅ Image cached successfully, preparing to return cached URL...\n")
                except Exception as e:
                    debug_logger.log_error(f"Failed to cache image: {str(e)}")
                    # Cache failure does not affect result return, use original URL
                    local_url = image_url
                    if stream:
                        yield self._create_stream_chunk(f"⚠️ Cache failed: {str(e)}\nReturning source link...\n")
            else:
                if stream:
                    yield self._create_stream_chunk("Cache disabled, returning source link...\n")

            # Return result
            if stream:
                yield self._create_stream_chunk(
                    f"![Generated Image]({local_url})",
                    finish_reason="stop"
                )
            else:
                yield self._create_completion_response(
                    local_url,  # Pass URL directly, let method format internally
                    media_type="image"
                )

        finally:
            # Release concurrency slot
            if self.concurrency_manager:
                await self.concurrency_manager.release_image(token.id)

    async def _handle_video_generation(
        self,
        token,
        project_id: str,
        model_config: dict,
        prompt: str,
        images: Optional[List[bytes]],
        stream: bool
    ) -> AsyncGenerator:
        """Process video generation (Asynchronous polling)"""

        # Acquire concurrency slot
        if self.concurrency_manager:
            if not await self.concurrency_manager.acquire_video(token.id):
                yield self._create_error_response("Video concurrency limit reached")
                return

        try:
            # Get model type and config
            video_type = model_config.get("video_type")
            supports_images = model_config.get("supports_images", False)
            min_images = model_config.get("min_images", 0)
            max_images = model_config.get("max_images", 0)

            # Image count
            image_count = len(images) if images else 0

            # ========== Validate and process images ==========

            # T2V: Text to Video - No image support
            if video_type == "t2v":
                if image_count > 0:
                    if stream:
                        yield self._create_stream_chunk("⚠️ T2V model does not support image upload, ignoring images and using text prompt only\n")
                    debug_logger.log_warning(f"[T2V] Model {model_config['model_key']} does not support images, ignored {image_count} images")
                images = None  # Clear images
                image_count = 0

            # I2V: Image to Video - Needs 1-2 images
            elif video_type == "i2v":
                if image_count < min_images or image_count > max_images:
                    error_msg = f"❌ I2V model needs {min_images}-{max_images} images, {image_count} provided"
                    if stream:
                        yield self._create_stream_chunk(f"{error_msg}\n")
                    yield self._create_error_response(error_msg)
                    return

            # R2V: Reference Images to Video - Supports multiple images, no limit
            elif video_type == "r2v":
                # No longer limit maximum image count
                pass

            # ========== Upload images ==========
            start_media_id = None
            end_media_id = None
            reference_images = []

            # I2V: Process start/end frames
            if video_type == "i2v" and images:
                if image_count == 1:
                    # 1 image: Only as start frame
                    if stream:
                        yield self._create_stream_chunk("Uploading start frame image...\n")
                    start_media_id = await self.flow_client.upload_image(
                        token.at, images[0], model_config["aspect_ratio"]
                    )
                    debug_logger.log_info(f"[I2V] Only uploaded start frame: {start_media_id}")

                elif image_count == 2:
                    # 2 images: Start frame + end frame
                    if stream:
                        yield self._create_stream_chunk("Uploading start and end frame images...\n")
                    start_media_id = await self.flow_client.upload_image(
                        token.at, images[0], model_config["aspect_ratio"]
                    )
                    end_media_id = await self.flow_client.upload_image(
                        token.at, images[1], model_config["aspect_ratio"]
                    )
                    debug_logger.log_info(f"[I2V] Uploaded start/end frames: {start_media_id}, {end_media_id}")

            # R2V: Process multiple images
            elif video_type == "r2v" and images:
                if stream:
                    yield self._create_stream_chunk(f"Uploading {image_count} reference images...\n")

                for idx, img in enumerate(images):  # Upload all images, no limit
                    media_id = await self.flow_client.upload_image(
                        token.at, img, model_config["aspect_ratio"]
                    )
                    reference_images.append({
                        "imageUsageType": "IMAGE_USAGE_TYPE_ASSET",
                        "mediaId": media_id
                    })
                debug_logger.log_info(f"[R2V] Uploaded {len(reference_images)} reference images")

            # ========== Call generation API ==========
            if stream:
                yield self._create_stream_chunk("Submitting video generation task...\n")

            # I2V: Start/end frame generation
            if video_type == "i2v" and start_media_id:
                if end_media_id:
                    # With start and end frames
                    result = await self.flow_client.generate_video_start_end(
                        at=token.at,
                        project_id=project_id,
                        prompt=prompt,
                        model_key=model_config["model_key"],
                        aspect_ratio=model_config["aspect_ratio"],
                        start_media_id=start_media_id,
                        end_media_id=end_media_id,
                        user_paygate_tier=token.user_paygate_tier or "PAYGATE_TIER_ONE"
                    )
                else:
                    # Only start frame
                    result = await self.flow_client.generate_video_start_image(
                        at=token.at,
                        project_id=project_id,
                        prompt=prompt,
                        model_key=model_config["model_key"],
                        aspect_ratio=model_config["aspect_ratio"],
                        start_media_id=start_media_id,
                        user_paygate_tier=token.user_paygate_tier or "PAYGATE_TIER_ONE"
                    )

            # R2V: Reference images generation
            elif video_type == "r2v" and reference_images:
                result = await self.flow_client.generate_video_reference_images(
                    at=token.at,
                    project_id=project_id,
                    prompt=prompt,
                    model_key=model_config["model_key"],
                    aspect_ratio=model_config["aspect_ratio"],
                    reference_images=reference_images,
                    user_paygate_tier=token.user_paygate_tier or "PAYGATE_TIER_ONE"
                )

            # T2V or R2V with no images: Pure text generation
            else:
                result = await self.flow_client.generate_video_text(
                    at=token.at,
                    project_id=project_id,
                    prompt=prompt,
                    model_key=model_config["model_key"],
                    aspect_ratio=model_config["aspect_ratio"],
                    user_paygate_tier=token.user_paygate_tier or "PAYGATE_TIER_ONE"
                )

            # Get task_id and operations
            operations = result.get("operations", [])
            if not operations:
                yield self._create_error_response("Video generation task creation failed")
                return

            operation = operations[0]
            task_id = operation["operation"]["name"]
            scene_id = operation.get("sceneId")

            # Save task to database
            task = Task(
                task_id=task_id,
                token_id=token.id,
                model=model_config["model_key"],
                prompt=prompt,
                status="processing",
                scene_id=scene_id
            )
            await self.db.create_task(task)

            # Poll results
            if stream:
                yield self._create_stream_chunk(f"Generating video...\n")

            async for chunk in self._poll_video_result(token, operations, stream):
                yield chunk

        finally:
            # Release concurrency slot
            if self.concurrency_manager:
                await self.concurrency_manager.release_video(token.id)

    async def _poll_video_result(
        self,
        token,
        operations: List[Dict],
        stream: bool
    ) -> AsyncGenerator:
        """Poll for video generation result"""

        max_attempts = config.max_poll_attempts
        poll_interval = config.poll_interval

        for attempt in range(max_attempts):
            await asyncio.sleep(poll_interval)

            try:
                result = await self.flow_client.check_video_status(token.at, operations)
                checked_operations = result.get("operations", [])

                if not checked_operations:
                    continue

                operation = checked_operations[0]
                status = operation.get("status")

                # Progress update - report every 20 seconds (poll_interval=3s, 20s about 7 polls)
                progress_update_interval = 7  # Every 7 polls = 21 seconds
                if stream and attempt % progress_update_interval == 0:  # Report progress every 20s
                    progress = min(int((attempt / max_attempts) * 100), 95)
                    yield self._create_stream_chunk(f"Generation progress: {progress}%\n")

                # Check status
                if status == "MEDIA_GENERATION_STATUS_SUCCESSFUL":
                    # Success
                    metadata = operation["operation"].get("metadata", {})
                    video_info = metadata.get("video", {})
                    video_url = video_info.get("fifeUrl")

                    if not video_url:
                        yield self._create_error_response("Video URL is empty")
                        return

                    # Cache video (if enabled)
                    local_url = video_url
                    if config.cache_enabled:
                        try:
                            if stream:
                                yield self._create_stream_chunk("Caching video file...\n")
                            cached_filename = await self.file_cache.download_and_cache(video_url, "video")
                            local_url = f"{self._get_base_url()}/tmp/{cached_filename}"
                            if stream:
                                yield self._create_stream_chunk("✅ Video cached successfully, preparing to return cached URL...\n")
                        except Exception as e:
                            debug_logger.log_error(f"Failed to cache video: {str(e)}")
                            # Cache failure does not affect result return, use original URL
                            local_url = video_url
                            if stream:
                                yield self._create_stream_chunk(f"⚠️ Cache failed: {str(e)}\nReturning source link...\n")
                    else:
                        if stream:
                            yield self._create_stream_chunk("Cache disabled, returning source link...\n")

                    # Update database
                    task_id = operation["operation"]["name"]
                    await self.db.update_task(
                        task_id,
                        status="completed",
                        progress=100,
                        result_urls=[local_url],
                        completed_at=time.time()
                    )

                    # Return result
                    if stream:
                        yield self._create_stream_chunk(
                            f"<video src='{local_url}' controls style='max-width:100%'></video>",
                            finish_reason="stop"
                        )
                    else:
                        yield self._create_completion_response(
                            local_url,  # Pass URL directly, let method format internally
                            media_type="video"
                        )
                    return

                elif status.startswith("MEDIA_GENERATION_STATUS_ERROR"):
                    # Failure
                    yield self._create_error_response(f"Video generation failed: {status}")
                    return

            except Exception as e:
                debug_logger.log_error(f"Poll error: {str(e)}")
                continue

        # Timeout
        yield self._create_error_response(f"Video generation timeout (polled {max_attempts} times)")

    # ========== Response Formatting ==========

    def _create_stream_chunk(self, content: str, role: str = None, finish_reason: str = None) -> str:
        """Create streaming response chunk"""
        import json
        import time

        chunk = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "flow2api",
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": finish_reason
            }]
        }

        if role:
            chunk["choices"][0]["delta"]["role"] = role

        if finish_reason:
            chunk["choices"][0]["delta"]["content"] = content
        else:
            chunk["choices"][0]["delta"]["reasoning_content"] = content

        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    def _create_completion_response(self, content: str, media_type: str = "image", is_availability_check: bool = False) -> str:
        """Create non-streaming response

        Args:
            content: Media URL or plain text message
            media_type: Media type ("image" or "video")
            is_availability_check: Whether it is an availability check response (plain text message)

        Returns:
            JSON formatted response
        """
        import json
        import time

        # Availability check: return plain text message
        if is_availability_check:
            formatted_content = content
        else:
            # Media generation: format content as Markdown based on media type
            if media_type == "video":
                formatted_content = f"```html\n<video src='{content}' controls></video>\n```"
            else:  # image
                formatted_content = f"![Generated Image]({content})"

        response = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "flow2api",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": formatted_content
                },
                "finish_reason": "stop"
            }]
        }

        return json.dumps(response, ensure_ascii=False)

    def _create_error_response(self, error_message: str) -> str:
        """Create error response"""
        import json

        error = {
            "error": {
                "message": error_message,
                "type": "invalid_request_error",
                "code": "generation_failed"
            }
        }

        return json.dumps(error, ensure_ascii=False)

    def _get_base_url(self) -> str:
        """Get base URL for cached file access"""
        # Prefer configured cache_base_url
        if config.cache_base_url:
            return config.cache_base_url
        # Otherwise use server address
        return f"http://{config.server_host}:{config.server_port}"

    async def _log_request(
        self,
        token_id: Optional[int],
        operation: str,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
        status_code: int,
        duration: float
    ):
        """Log request to database"""
        try:
            log = RequestLog(
                token_id=token_id,
                operation=operation,
                request_body=json.dumps(request_data, ensure_ascii=False),
                response_body=json.dumps(response_data, ensure_ascii=False),
                status_code=status_code,
                duration=duration
            )
            await self.db.add_request_log(log)
        except Exception as e:
            # Log failure does not affect main process
            debug_logger.log_error(f"Failed to log request: {e}")

