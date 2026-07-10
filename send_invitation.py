import json
import urllib.request
import ssl
import sys

# Standalone script to test direct WhatsApp template dispatch

# Configuration
URL = "https://103.229.250.150/unified/v2/send"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJJbmZpbml0byIsImlhdCI6MTczNDU5NjcyNSwic3ViIjoic3JlZW5pZGhpYmR2dml5cTRnNTRkOGUzIn0.9nsgFzRXqeTXyUwtXOADX6pP1G50cOsc40pwn0NVyS4"
FROM_NUMBER = "918712010771"
TEMPLATE_ID = "1776508"

def send_message(recipient, guest_name):
    # Normalize phone: strip leading '0' or spaces, ensure '91' prefix
    phone = "".join(filter(str.isdigit, recipient))
    if phone.startswith("0"):
        phone = phone[1:]
    if not phone.startswith("91") and len(phone) == 10:
        phone = "91" + phone

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}",
        "User-Agent": "SNIST-Direct-Sender/1.0"
    }

    payload = {
        "apiver": "1.0",
        "whatsapp": {
            "ver": "2.0",
            "dlr": {
                "url": ""
            },
            "messages": [
                {
                    "coding": "1",
                    "id": "direct_cli_send",
                    "msgtype": "3",  # Trans with Media
                    "templateinfo": f"{TEMPLATE_ID}~{guest_name.split()[0] if guest_name else ''}~you to be a part of our Founder's Day celebrations~personalized  digital entry pass",
                    "type": "image",
                    "contenttype": "image/png",
                    "mediadata": "https://files.catbox.moe/9ngu8y.png",
                    "filename": "pass.png",
                    "text": "",
                    "addresses": [
                        {
                            "seq": "1",
                            "to": phone,
                            "from": FROM_NUMBER,
                            "tag": "direct-cli"
                        }
                    ]
                }
            ]
        }
    }

    print(f"\nSending Template {TEMPLATE_ID} to {phone} ({guest_name})...")
    
    try:
        # Ignore SSL certification checks for the local IP host
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        json_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(URL, data=json_data, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as response:
            status = response.status
            body = response.read().decode("utf-8")
            print(f"\n--- API Response (HTTP {status}) ---")
            print(body)
            if "Incorrect Template Details" in body:
                print("\n[!] Warning: Gateway flagged incorrect template parameters.")
            elif "Success" in body:
                print("\n[+] Success: Message accepted by gateway.")
    except Exception as e:
        print(f"\n[!] Error: Connection failed - {str(e)}")

if __name__ == "__main__":
    print("=== SNIST WhatsApp Direct Sender ===")
    
    # Check if arguments are passed via command line
    if len(sys.argv) >= 3:
        recipient_num = sys.argv[1]
        name = sys.argv[2]
    else:
        recipient_num = input("Enter Recipient Mobile Number (e.g. 9704083464): ").strip()
        name = input("Enter Guest Name (e.g. Bhaskar Sharma): ").strip()
        
    if not recipient_num or not name:
        print("Error: Mobile number and name are required.")
        sys.exit(1)
        
    send_message(recipient_num, name)
