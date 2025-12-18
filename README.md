# Flow2API

<div align="center"> 

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.119.0-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](https://www.docker.com/)

**A full-featured OpenAI-compatible API service that provides a unified interface for Flow**

</div>

## ✨ Key Features

- 🎨 **Text-to-Image** / **Image-to-Image**
- 🎬 **Text-to-Video** / **Image-to-Video**
- 🎞️ **First/Last Frame Video**
- 🔄 **Automatic AT Refresh**
- 📊 **Credits Display** - Query and display VideoFX Credits in real time
- 🚀 **Load Balancing** - Multi-token rotation and concurrency control
- 🌐 **Proxy Support** - HTTP/SOCKS5 proxies
- 📱 **Web Admin UI** - Intuitive token and configuration management
- 🎨 **Continuous Conversation for Image Generation**

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose (recommended)
- Or Python 3.8+

- Since Flow adds an extra captcha step, you can choose either browser-based captcha solving or a third-party service.
Register at [YesCaptcha](https://yescaptcha.com/i/13Xd8K) and get an API key, then fill it in the system settings page under `YesCaptcha API Key`.

### Option 1: Docker Deployment (Recommended)

#### Standard Mode (No Proxy)

```bash
# Clone the repository
git clone https://github.com/TheSmallHanCat/flow2api.git
cd flow2api

# Start the service
docker-compose up -d

# View logs
docker-compose logs -f
```

#### WARP Mode (With Proxy)

```bash
# Start with WARP proxy
docker-compose -f docker-compose.warp.yml up -d

# View logs
docker-compose -f docker-compose.warp.yml logs -f
```

### Option 2: Local Deployment

```bash
# Clone the repository
git clone https://github.com/TheSmallHanCat/flow2api.git
cd sora2api

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the service
python main.py
```

### First Login

After the service starts, open the admin console at **http://localhost:8000**. Please change the password immediately after your first login.

- **Username**: `admin`
- **Password**: `admin`

## 📋 Supported Models

### Image Generation

| Model Name | Description | Size |
|---------|--------|--------|
| `gemini-2.5-flash-image-landscape` | Image/Text-to-Image | Landscape |
| `gemini-2.5-flash-image-portrait` | Image/Text-to-Image | Portrait |
| `gemini-3.0-pro-image-landscape` | Image/Text-to-Image | Landscape |
| `gemini-3.0-pro-image-portrait` | Image/Text-to-Image | Portrait |
| `imagen-4.0-generate-preview-landscape` | Image/Text-to-Image | Landscape |
| `imagen-4.0-generate-preview-portrait` | Image/Text-to-Image | Portrait |

### Video Generation

#### Text-to-Video (T2V)
⚠️ **Image upload is not supported**

| Model Name | Description | Size |
|---------|---------|--------|
| `veo_3_1_t2v_fast_portrait` | Text-to-Video | Portrait |
| `veo_3_1_t2v_fast_landscape` | Text-to-Video | Landscape |
| `veo_2_1_fast_d_15_t2v_portrait` | Text-to-Video | Portrait |
| `veo_2_1_fast_d_15_t2v_landscape` | Text-to-Video | Landscape |
| `veo_2_0_t2v_portrait` | Text-to-Video | Portrait |
| `veo_2_0_t2v_landscape` | Text-to-Video | Landscape |

#### First/Last Frame Models (I2V - Image to Video)
📸 **Supports 1-2 images: first and last frames**

| Model Name | Description | Size |
|---------|---------|--------|
| `veo_3_1_i2v_s_fast_fl_portrait` | Image-to-Video | Portrait |
| `veo_3_1_i2v_s_fast_fl_landscape` | Image-to-Video | Landscape |
| `veo_2_1_fast_d_15_i2v_portrait` | Image-to-Video | Portrait |
| `veo_2_1_fast_d_15_i2v_landscape` | Image-to-Video | Landscape |
| `veo_2_0_i2v_portrait` | Image-to-Video | Portrait |
| `veo_2_0_i2v_landscape` | Image-to-Video | Landscape |

#### Multi-Image Generation (R2V - Reference Images to Video)
🖼️ **Supports multiple images**

| Model Name | Description | Size |
|---------|---------|--------|
| `veo_3_0_r2v_fast_portrait` | Image-to-Video | Portrait |
| `veo_3_0_r2v_fast_landscape` | Image-to-Video | Landscape |

## 📡 API Usage Examples (Streaming Required)

### Text-to-Image

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer han1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-2.5-flash-image-landscape",
    "messages": [
      {
        "role": "user",
        "content": "A cute cat playing in the garden"
      }
    ],
    "stream": true
  }'
```

### Image-to-Image

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer han1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "imagen-4.0-generate-preview-landscape",
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Turn this image into a watercolor style"
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "data:image/jpeg;base64,<base64_encoded_image>"
            }
          }
        ]
      }
    ],
    "stream": true
  }'
```

### Text-to-Video

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer han1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "veo_3_1_t2v_fast_landscape",
    "messages": [
      {
        "role": "user",
        "content": "A kitten chasing butterflies on the grass"
      }
    ],
    "stream": true
  }'
```

### First/Last Frame Video Generation

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer han1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "veo_3_1_i2v_s_fast_fl_landscape",
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Transition from the first image to the second image"
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "data:image/jpeg;base64,<first_frame_base64>"
            }
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "data:image/jpeg;base64,<last_frame_base64>"
            }
          }
        ]
      }
    ],
    "stream": true
  }'
```

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [PearNoDec](https://github.com/PearNoDec) for the YesCaptcha solving solution
- [raomaiping](https://github.com/raomaiping) for the headless solving solution
Thanks to all contributors and users for your support!

---

## 📞 Contact

- Submit an issue: [GitHub Issues](https://github.com/TheSmallHanCat/flow2api/issues)

---

**⭐ If this project helps you, please give it a Star!**

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=TheSmallHanCat/flow2api&type=date&legend=top-left)](https://www.star-history.com/#TheSmallHanCat/flow2api&type=date&legend=top-left)
