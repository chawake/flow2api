import os
import json
import re
import base64
import aiohttp # Async test. Need to install
import asyncio


# --- Configuration ---
BASE_URL = os.getenv('GEMINI_FLOW2API_URL', 'http://127.0.0.1:8000')
BACKEND_URL = BASE_URL + "/v1/chat/completions"
API_KEY = os.getenv('GEMINI_FLOW2API_APIKEY', 'Bearer han1234')
if API_KEY is None:
    raise ValueError('[gemini flow2api] api key not set')
MODEL_LANDSCAPE = "gemini-3.0-pro-image-landscape"
MODEL_PORTRAIT = "gemini-3.0-pro-image-portrait"

# Modified: added model parameter, defaulting to None
async def request_backend_generation(
        prompt: str,
        images: list[bytes] = None,
        model: str = None) -> bytes | None:
    """
    Request backend to generate images.
    :param prompt: Prompt text
    :param images: List of image binary data
    :param model: Specified model name (optional)
    :return: Returns image bytes on success, None on failure
    """
    # Update token
    images = images or []
    
    # Logic: if no model specified, use Landscape by default
    use_model = model if model else MODEL_LANDSCAPE

    # 1. Construct Payload
    if images:
        content_payload = [{"type": "text", "text": prompt}]
        print(f"[Backend] Processing {len(images)} image inputs...")
        for img_bytes in images:
            b64_str = base64.b64encode(img_bytes).decode('utf-8')
            content_payload.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_str}"}
            })
    else:
        content_payload = prompt

    payload = {
        "model": use_model,  # Use selected model
        "messages": [{"role": "user", "content": content_payload}],
        "stream": True
    }
    
    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }

    image_url = None
    print(f"[Backend] Model: {use_model} | Requesting: {prompt[:20]}...") 
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(BACKEND_URL, json=payload, headers=headers, timeout=120) as response:
                if response.status != 200:
                    err_text = await response.text()
                    content = response.content
                    print(f"[Backend Error] Status {response.status}: {err_text} {content}")
                    raise Exception(f"API Error: {response.status}: {err_text}")

                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith('{"error'):
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        msg = delta['reasoning_content']
                        if '401' in msg:
                            msg += '\nAccess Token has expired, reconfiguration required.'
                        elif '400' in msg:
                            msg += '\nResponse content was intercepted.'
                        raise Exception(msg)

                    if not line_str or not line_str.startswith('data: '):
                        continue
                    
                    data_str = line_str[6:]
                    if data_str == '[DONE]':
                        break
                    
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        
                        # Print thinking process
                        if "reasoning_content" in delta:
                            print(delta['reasoning_content'], end="", flush=True)

                        # Extract image link from content
                        if "content" in delta:
                            content_text = delta["content"]
                            img_match = re.search(r'!\[.*?\]\((.*?)\)', content_text)
                            if img_match:
                                image_url = img_match.group(1)
                                print(f"\n[Backend] Captured image link: {image_url}")
                    except json.JSONDecodeError:
                        continue
            
            # 3. Download generated image
            if image_url:
                async with session.get(image_url) as img_resp:
                    if img_resp.status == 200:
                        image_bytes = await img_resp.read()
                        return image_bytes
                    else:
                        print(f"[Backend Error] Image download failed: {img_resp.status}")
    except Exception as e:
        print(f"[Backend Exception] {e}")
        raise e 
        
    return None

if __name__ == '__main__':
    async def main():
        print("=== AI Drawing API Test ===")
        user_prompt = input("Please enter prompt (e.g., 'a cat'): ").strip()
        if not user_prompt:
            user_prompt = "A cute cat in the garden"
        
        print(f"Requesting: {user_prompt}")
        
        # images empty list for testing text-to-image
        # for image-to-image, read local file:
        # with open("output_test.jpg", "rb") as f: img_data = f.read()
        # result = await request_backend_generation(user_prompt, [img_data])
        
        result = await request_backend_generation(user_prompt)
        
        if result:
            filename = "output_test.jpg"
            with open(filename, "wb") as f:
                f.write(result)
            print(f"\n[Success] Image saved as {filename}, size: {len(result)} bytes")
        else:
            print("\n[Failed] Generation failed")

    # Run test
    if os.name == 'nt':  # Windows compatibility
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())