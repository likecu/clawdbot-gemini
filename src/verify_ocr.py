import sys
import os
import requests

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from adapters.gemini.gemini_ocr import GeminiOCR
    from config.settings import get_settings
except ImportError:
    # Fallback if run from src directory directly
    sys.path.append(os.path.join(os.getcwd(), '..'))
    from adapters.gemini.gemini_ocr import GeminiOCR
    from config.settings import get_settings

def test_ocr():
    print("Initializing Settings...")
    settings = get_settings()
    if not settings.gemini_api_key:
        print("ERROR: GEMINI_API_KEY is not set!")
        return
        
    print(f"API Key present. Length: {len(settings.gemini_api_key)}")
    
    print("Initializing GeminiOCR...")
    ocr = GeminiOCR(api_key=settings.gemini_api_key)
    print(f"\nCurrent Model: {ocr.model_name}")
    
    priority = ocr.model_priority.get('image_supported', [])
    print(f"Image Supported Models Priority: {priority}")

    # Download a test image
    img_url = "https://www.python.org/static/community_logos/python-logo-master-v3-TM.png"
    img_path = "/tmp/test_ocr_verify.png"
    
    print(f"\nDownloading test image from {img_url}...")
    try:
        resp = requests.get(img_url, timeout=15)
        resp.raise_for_status()
        with open(img_path, "wb") as f:
            f.write(resp.content)
        print(f"Image saved to {img_path}, size: {os.path.getsize(img_path)} bytes")
    except Exception as e:
        print(f"Failed to download image: {e}")
        return

    print("\nRunning recognize_image...")
    print(f"Asking: 'Describe this image.'")
    
    try:
        result = ocr.recognize_image(img_path, "Describe this image.")
        
        print("\n" + "="*30)
        print(f"EXECUTION COMPLETED. Success: {result.get('success')}")
        print("RESPONSE CONTENT:")
        print(result.get('response'))
        print("="*30 + "\n")
        
        if result.get('error'):
             print(f"ERROR DETAIL: {result.get('error')}")

    except Exception as e:
        print(f"CRITICAL EXCEPTION during call: {e}")

    # Initial cleanup
    if os.path.exists(img_path):
        os.remove(img_path)

if __name__ == "__main__":
    test_ocr()
