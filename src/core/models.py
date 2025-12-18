"""Data models for Flow2API"""
from pydantic import BaseModel
from typing import Optional, List, Union, Any
from datetime import datetime


class Token(BaseModel):
    """Token model for Flow2API"""
    id: Optional[int] = None

    # Authentication information (Core)
    st: str  # Session Token (__Secure-next-auth.session-token)
    at: Optional[str] = None  # Access Token (Converted from ST)
    at_expires: Optional[datetime] = None  # AT expiration time

    # Basic information 
    email: str
    name: Optional[str] = ""
    remark: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    use_count: int = 0

    # VideoFX specific fields
    credits: int = 0  # Remaining credits
    user_paygate_tier: Optional[str] = None  # PAYGATE_TIER_ONE

    # Project management
    current_project_id: Optional[str] = None  # UUID of the current project
    current_project_name: Optional[str] = None  # Project name

    # Feature switches
    image_enabled: bool = True
    video_enabled: bool = True

    # Concurrency limit
    image_concurrency: int = -1  # -1 means unlimited
    video_concurrency: int = -1  # -1 means unlimited

    # 429 Ban related
    ban_reason: Optional[str] = None  # Ban reason: "429_rate_limit" or None
    banned_at: Optional[datetime] = None  # Ban time


class Project(BaseModel):
    """Project model for VideoFX"""
    id: Optional[int] = None
    project_id: str  # VideoFX project UUID
    token_id: int  # Associated Token ID
    project_name: str  # Project name
    tool_name: str = "PINHOLE"  # Tool name, fixed to PINHOLE
    is_active: bool = True
    created_at: Optional[datetime] = None


class TokenStats(BaseModel):
    """Token statistics"""
    token_id: int
    image_count: int = 0
    video_count: int = 0
    success_count: int = 0
    error_count: int = 0  # Historical total errors (never reset)
    last_success_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    # Daily statistics
    today_image_count: int = 0
    today_video_count: int = 0
    today_error_count: int = 0
    today_date: Optional[str] = None
    # Consecutive error count (used for auto-disable judgment)
    consecutive_error_count: int = 0


class Task(BaseModel):
    """Generation task"""
    id: Optional[int] = None
    task_id: str  # operation name returned by Flow API
    token_id: int
    model: str
    prompt: str
    status: str  # processing, completed, failed
    progress: int = 0  # 0-100
    result_urls: Optional[List[str]] = None
    error_message: Optional[str] = None
    scene_id: Optional[str] = None  # sceneId from Flow API
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class RequestLog(BaseModel):
    """API request log"""
    id: Optional[int] = None
    token_id: Optional[int] = None
    operation: str
    request_body: Optional[str] = None
    response_body: Optional[str] = None
    status_code: int
    duration: float
    created_at: Optional[datetime] = None


class AdminConfig(BaseModel):
    """Admin configuration"""
    id: int = 1
    username: str
    password: str
    api_key: str
    error_ban_threshold: int = 3  # Auto-disable token after N consecutive errors


class ProxyConfig(BaseModel):
    """Proxy configuration"""
    id: int = 1
    enabled: bool = False
    proxy_url: Optional[str] = None


class GenerationConfig(BaseModel):
    """Generation timeout configuration"""
    id: int = 1
    image_timeout: int = 300  # seconds
    video_timeout: int = 1500  # seconds


class CacheConfig(BaseModel):
    """Cache configuration"""
    id: int = 1
    cache_enabled: bool = False
    cache_timeout: int = 7200  # seconds (2 hours)
    cache_base_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DebugConfig(BaseModel):
    """Debug configuration"""
    id: int = 1
    enabled: bool = False
    log_requests: bool = True
    log_responses: bool = True
    mask_token: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CaptchaConfig(BaseModel):
    """Captcha configuration"""
    id: int = 1
    captcha_method: str = "browser"  # yescaptcha or browser
    yescaptcha_api_key: str = ""
    yescaptcha_base_url: str = "https://api.yescaptcha.com"
    website_key: str = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"
    page_action: str = "FLOW_GENERATION"
    browser_proxy_enabled: bool = False  # Whether to use proxy for browser captcha
    browser_proxy_url: Optional[str] = None  # Browser captcha proxy URL
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# OpenAI Compatible Request Models
class ChatMessage(BaseModel):
    """Chat message"""
    role: str
    content: Union[str, List[dict]]  # string or multimodal array


class ChatCompletionRequest(BaseModel):
    """Chat completion request (OpenAI compatible)"""
    model: str
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    # Flow2API specific parameters
    image: Optional[str] = None  # Base64 encoded image (deprecated, use messages)
    video: Optional[str] = None  # Base64 encoded video (deprecated)
