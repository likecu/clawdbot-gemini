import sys
import os
import json
import logging

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from adapters.lark.lark_client import LarkWSClient
from config.settings import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_lark_send")

def test_send_file(receive_id):
    logger.info("Initializing Lark Client...")
    # Ensure settings are loaded
    settings = get_settings()
    if not settings.lark_app_id:
        logger.error("Lark settings not configured!")
        return

    client = LarkWSClient()
    
    # Create dummy python file
    file_path = "/tmp/hello_clawdbot.py"
    with open(file_path, "w") as f:
        f.write("# Hello from Clawdbot\n")
        f.write("print('This file was sent via Clawdbot API!')\n")
        f.write("def hello():\n    return 'Hello World'\n")
    
    logger.info(f"Created test file: {file_path}")
    
    # Upload file
    logger.info("Uploading file to Feishu...")
    # file_type "stream" is often used for generic files, or "python" if supported, but usually stream/pdf/doc etc.
    # checking documentation, usually "stream" is safe for unknown types or generic files.
    file_key = client.upload_file(file_path, file_type="stream")
    
    if not file_key:
        logger.error("File upload failed!")
        return
        
    logger.info(f"File uploaded successfully. Key: {file_key}")
    
    # Send file message
    logger.info(f"Sending file message to user: {receive_id}...")
    content = {
        "msg_type": "file",
        "content": {"file_key": file_key}
    }
    
    result = client.send_message(receive_id, content)
    
    if result.get("success"):
        logger.info(f"Message sent successfully! Message ID: {result.get('message_id')}")
    else:
        logger.error(f"Failed to send message: {result.get('error')}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/verify_lark_send.py <receive_id>")
        print("Example: python src/verify_lark_send.py ou_xxxxxxxx")
        sys.exit(1)
    
    receive_id = sys.argv[1]
    test_send_file(receive_id)
