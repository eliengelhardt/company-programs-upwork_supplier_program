import requests
from datetime import datetime, timedelta
import hashlib
import hmac
import pytz

# Constants provided by the API documentation
public_key = "E3D890B7-9A01-42CC-B7BF-4F064BAEA91E"
service_id = "2663BF8D-E788-4A07-8562-E492C83EF174"
user = "experiencia_hcb@appexternasclinicabiblica.onmicrosoft.com"
private_key = "$2y$06$8OCHOCNbWOIRYIWEWED2.iR1RzqAxo0Uo18YtHUaCs3eO9PrWQwG"

# Generate the timestamp (60 minutes ahead) in the required format
now = datetime.now(pytz.timezone('America/Costa_Rica'))  # Adjust to the required timezone if necessary
future_time = now + timedelta(minutes=60)
# Ensure fractional seconds have exactly seven digits
fractional_seconds = f'{future_time.microsecond:06d}0'  # Append '0' to ensure seven digits
timestamp = future_time.strftime('%Y-%m-%dT%H:%M:%S.') + fractional_seconds + '-06:00'
print(f"Timestamp: {timestamp}")

# Create the HMAC
message = timestamp + user + private_key
hmac_hash = hmac.new(private_key.encode(), message.encode(), hashlib.sha256).hexdigest()

# Payload for the POST request
payload = {
    "grant_type": "hcbauth",
    "PublicKey": public_key,
    "Servicio": service_id,
    "TimeStamp": timestamp,
    "HMAC": hmac_hash
}
print("Payload:", payload)

# URL for the token request
url = "https://servicios.clinicabiblica.com/EXTERNOCITASHCB/API/api/token"

# Headers
headers = {
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}

# Making the POST request to obtain the token
response = requests.post(url, data=payload, headers=headers)

# Checking the response
if response.status_code == 200:
    token = response.json().get("access_token")
    print(f"Token: {token}")
else:
    print(f"Failed to obtain token: {response.status_code} - {response.text}")
