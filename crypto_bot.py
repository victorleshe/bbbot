import os
import time
import json
import asyncio
import requests
import websockets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from requests.exceptions import RequestException

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

# Bybit API configurations
BYBIT_DERIVATIVES_API = "https://api.bybit.com/v2/public/tickers"
WEBHOOK_URL = "wss://stream.bybit.com/realtime"

# Coins to track
COINS = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT']

# Rate limit configuration
API_RATE_LIMIT = 75  # Maximum requests per minute
REQUEST_INTERVAL = 60 / API_RATE_LIMIT  # Time between requests to avoid exceeding the rate limit

# Function to send email
def send_email(subject, message):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = EMAIL_RECIPIENT
        msg['Subject'] = subject

        msg.attach(MIMEText(message, 'plain'))

        # Set up the SMTP server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, EMAIL_RECIPIENT, msg.as_string())
        server.quit()

        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Failed to send email: {e}")

# Function to fetch ticker data from Bybit in batches
def fetch_ticker_data():
    try:
        response = requests.get(BYBIT_DERIVATIVES_API)
        response.raise_for_status()  # Raise an exception for bad responses
        return response.json()
    except RequestException as e:
        print(f"API request failed: {e}")
        return None

# Function to check all-time highs and lows
def check_highs_lows():
    data = fetch_ticker_data()

    if data and 'result' in data:
        for ticker in data['result']:
            symbol = ticker['symbol']
            if symbol in COINS:
                last_price = float(ticker['last_price'])
                high_price = float(ticker['high_price'])
                low_price = float(ticker['low_price'])

                # Check for all-time high or low
                if last_price >= high_price:
                    subject = f"{symbol} reached an all-time high!"
                    message = f"{symbol} has reached a new all-time high of {last_price}."
                    send_email(subject, message)
                elif last_price <= low_price:
                    subject = f"{symbol} hit an all-time low!"
                    message = f"{symbol} has reached a new all-time low of {last_price}."
                    send_email(subject, message)

# WebSocket Subscription (For real-time updates)
async def websocket_ticker_updates():
    try:
        async with websockets.connect(WEBHOOK_URL) as websocket:
            for coin in COINS:
                # Subscribe to tickers for all selected coins
                subscription_message = {
                    "op": "subscribe",
                    "args": [f"instrument_info.100ms.{coin}"]
                }
                await websocket.send(json.dumps(subscription_message))
                print(f"Subscribed to {coin}")

            while True:
                message = await websocket.recv()
                ticker_update = json.loads(message)

                # Process WebSocket ticker update here if needed
                print(ticker_update)

    except websockets.exceptions.ConnectionClosedError as e:
        print(f"WebSocket connection closed: {e}")
        await asyncio.sleep(5)  # Wait before reconnecting
    except Exception as e:
        print(f"WebSocket error: {e}")
        await asyncio.sleep(5)

# Function to throttle requests and respect API rate limits
def throttle_requests():
    start_time = time.time()
    
    # First, check all-time highs and lows using the REST API
    check_highs_lows()

    elapsed_time = time.time() - start_time
    if elapsed_time < REQUEST_INTERVAL:
        time.sleep(REQUEST_INTERVAL - elapsed_time)

# Main function to run the script every 5 minutes
def main():
    start_time = time.time()
    
    # Call the REST API with rate limit in place
    throttle_requests()

    # Run WebSocket asynchronously (for real-time updates)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(websocket_ticker_updates())

    # Ensure script doesn't exceed 5-minute interval
    elapsed_time = time.time() - start_time
    if elapsed_time < 300:
        time.sleep(300 - elapsed_time)

# Entry point for cron job
if __name__ == "__main__":
    main()
