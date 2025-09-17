"""
Zerodha Trading Bot using pykiteconnect

This script connects to the Zerodha Kite API to provide a real-time dashboard of the Nifty 50 stocks.

Features:
- Secure authentication with API key/secret and saves the access token for future sessions.
- Displays user's current holdings and open positions at startup.
- Shows a live, auto-updating table of Nifty 50 stocks with:
  - Last Traded Price (LTP)
  - Percentage change from the previous day's close.
  - Total traded volume for the day.
- Highlights the most actively traded stock by volume with a star (⭐).
- Periodically checks for and highlights stocks with >5% price change (every 5 minutes).
- Fetches 1-hour candle data to detect and flag "Open = High" (bearish) or "Open = Low" (bullish) patterns (every hour).

--- SETUP INSTRUCTIONS ---
1. Install the required libraries:
   pip install -r requirements.txt

2. Fill in your Zerodha API credentials:
   - Open this script (`trading_bot.py`).
   - Replace "YOUR_API_KEY" with your actual API key.
   - Replace "YOUR_API_SECRET" with your actual API secret.
   - The "REDIRECT_URL" is not strictly needed for this script's flow but is part of the library's setup.
     You can leave it as a placeholder if you are not hosting it.

3. Run the bot for the first time:
   - In your terminal, run the command: python trading_bot.py
   - The script will print a login URL. Copy and paste this into your web browser.
   - Log in with your Zerodha credentials.
   - After successful login, you will be redirected to your redirect URL.
   - The URL in your browser's address bar will now contain a `request_token`. It looks like this:
     https://your-redirect-url.com/?status=success&request_token=THIS_IS_THE_TOKEN
   - Copy the `request_token` value (the long string of characters).
   - Paste it into the terminal where the bot is prompting for it and press Enter.

4. Subsequent Runs:
   - The bot will save your `access_token` in a file named `access_token.txt`.
   - On future runs, it will automatically log in using this token. You won't need to go through the browser login again unless the token expires or is invalidated.

5. To Stop the Bot:
   - Press Ctrl+C in the terminal where the bot is running.
"""

# --- Imports ---
import os
import logging
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from kiteconnect import KiteConnect, KiteTicker
import schedule
import time
from datetime import datetime, timedelta

# --- Configuration ---
# Replace with your actual API key and secret
API_KEY = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"
# The redirect URL you specified when creating your Kite app
REDIRECT_URL = "YOUR_REDIRECT_URL"
ACCESS_TOKEN_FILE = "access_token.txt"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# --- Rich Console ---
console = Console()


def authenticate():
    """Handles the authentication process and returns a KiteConnect object."""
    log.info("Starting authentication...")
    kite = KiteConnect(api_key=API_KEY)

    # Check if access token exists
    if os.path.exists(ACCESS_TOKEN_FILE):
        log.info("Access token file found. Reading from it.")
        with open(ACCESS_TOKEN_FILE, 'r') as f:
            access_token = f.read()

        try:
            kite.set_access_token(access_token)
            # Validate the access token by fetching profile
            profile = kite.profile()
            log.info(f"Successfully logged in as {profile['user_name']}.")
            return kite
        except Exception as e:
            log.error(f"Failed to login with existing access token: {e}")
            log.info("Proceeding to generate a new access token.")
            os.remove(ACCESS_TOKEN_FILE) # Remove invalid token file

    # If access token does not exist or is invalid, generate a new one
    log.info("Access token not found or invalid. Generating a new one.")

    # Check if API_KEY and API_SECRET are set
    if API_KEY == "YOUR_API_KEY" or API_SECRET == "YOUR_API_SECRET":
        console.print("[bold red]Error: API_KEY or API_SECRET are not set in the script.[/bold red]")
        console.print("Please replace 'YOUR_API_KEY' and 'YOUR_API_SECRET' with your actual credentials.")
        exit()

    login_url = kite.login_url()
    console.print(f"Please login to Zerodha using this URL:\n[link={login_url}]{login_url}[/link]")

    try:
        request_token = console.input("Enter the request_token from the redirect URL: ")
    except KeyboardInterrupt:
        console.print("\n[bold red]Login process cancelled by user.[/bold red]")
        exit()

    if not request_token:
        console.print("[bold red]Error: Request token cannot be empty.[/bold red]")
        exit()

    try:
        data = kite.generate_session(request_token, api_secret=API_SECRET)
        access_token = data["access_token"]
        kite.set_access_token(access_token)

        with open(ACCESS_TOKEN_FILE, 'w') as f:
            f.write(access_token)
        log.info("Access token generated and saved successfully.")

        profile = kite.profile()
        log.info(f"Successfully logged in as {profile['user_name']}.")
        return kite
    except Exception as e:
        log.error(f"Authentication failed: {e}")
        console.print(f"[bold red]Authentication failed: {e}[/bold red]")
        exit()


NIFTY50_STOCKS = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BPCL", "BHARTIARTL",
    "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
    "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC",
    "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LTIM",
    "LT", "M&M", "MARUTI", "NESTLEIND", "NTPC",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN",
    "SUNPHARMA", "TATAMOTORS", "TCS", "TATACONSUM", "TATASTEEL",
    "TECHM", "TITAN", "UPL", "ULTRACEMCO", "WIPRO"
]

def get_nifty50_instrument_tokens(kite):
    """Fetches instrument tokens for Nifty 50 stocks."""
    log.info("Fetching Nifty 50 instrument tokens...")
    try:
        instruments = kite.instruments("NSE")
        instrument_map = {inst['tradingsymbol']: inst['instrument_token'] for inst in instruments if inst['instrument_type'] == 'EQ'}

        # Also create a reverse map from token to symbol
        token_to_symbol_map = {v: k for k, v in instrument_map.items()}

        nifty50_tokens = [instrument_map.get(stock) for stock in NIFTY50_STOCKS]
        nifty50_tokens = [token for token in nifty50_tokens if token is not None] # Filter out any not found

        if len(nifty50_tokens) != len(NIFTY50_STOCKS):
            log.warning("Could not find instrument tokens for all Nifty 50 stocks.")
            found_symbols = [token_to_symbol_map.get(t) for t in nifty50_tokens]
            missing_symbols = list(set(NIFTY50_STOCKS) - set(found_symbols))
            log.warning(f"Missing symbols: {missing_symbols}")


        log.info(f"Found {len(nifty50_tokens)} Nifty 50 instrument tokens.")
        return nifty50_tokens, token_to_symbol_map
    except Exception as e:
        log.error(f"Error fetching Nifty 50 instrument tokens: {e}")
        console.print(f"[bold red]Error fetching Nifty 50 instrument tokens: {e}[/bold red]")
        return [], {}




def get_previous_day_close(kite, instrument_tokens):
    log.info("Fetching previous day's close for Nifty 50 stocks...")
    try:
        ohlc_data = kite.ohlc(instrument_tokens)
        prev_close_map = {int(token): data['ohlc']['close'] for token, data in ohlc_data.items()}
        log.info(f"Successfully fetched previous day's close for {len(prev_close_map)} stocks.")
        return prev_close_map
    except Exception as e:
        log.error(f"Error fetching previous day's close: {e}")
        return {}


# --- Global Data Store ---
live_data = {}
holdings_data = []
positions_data = []
kws = None # Will be initialized in main


def update_account_data(kite):
    """Scheduled job to fetch latest holdings and positions."""
    global holdings_data, positions_data
    log.info("Running job: update_account_data")
    try:
        latest_holdings = kite.holdings()
        latest_positions = kite.positions().get('net', [])

        # Check for profit alerts in positions
        for pos in latest_positions:
            instrument_token = pos.get('instrument_token')
            if instrument_token is None: continue

            old_pos_state = next((p for p in positions_data if p.get('instrument_token') == instrument_token), None)
            pnl = pos['pnl']
            alert_triggered = old_pos_state.get('pnl_alert_triggered', False) if old_pos_state else False

            if pnl > 5000 and not alert_triggered:
                console.print('\a', end='')  # Beep
                console.print(f"[bold yellow]🔔 PROFIT ALERT: {pos['tradingsymbol']} P&L is {pnl:,.2f}![/bold yellow]")
                pos['pnl_alert_triggered'] = True
            elif pnl <= 5000 and alert_triggered:
                pos['pnl_alert_triggered'] = False
            else:
                pos['pnl_alert_triggered'] = alert_triggered

        holdings_data = latest_holdings
        positions_data = latest_positions
    except Exception as e:
        log.error(f"Error in update_account_data job: {e}")


def on_ticks(ws, ticks):
    for tick in ticks:
        token = tick['instrument_token']
        if token in live_data:
            live_data[token]['ltp'] = tick['last_price']
            live_data[token]['volume'] = tick['volume_traded']
            live_data[token]['ohlc'] = tick.get('ohlc', live_data[token]['ohlc'])
            live_data[token]['last_trade_time'] = tick.get('last_trade_time')

            # Calculate % change
            prev_close = live_data[token]['prev_close']
            if prev_close:
                change = tick['last_price'] - prev_close
                live_data[token]['change_percent'] = (change / prev_close) * 100

def on_connect(ws, response):
    log.info("WebSocket connected. Subscribing to Nifty 50 ticks.")
    ws.subscribe(list(live_data.keys()))
    ws.set_mode(ws.MODE_FULL, list(live_data.keys()))
    log.info(f"Subscribed to {len(live_data.keys())} Nifty 50 instruments.")

def on_close(ws, code, reason):
    log.warning(f"WebSocket connection closed. Code: {code}, Reason: {reason}")

def on_error(ws, code, reason):
    log.error(f"WebSocket error. Code: {code}, Reason: {reason}")


def check_high_percentage_change():
    """Scheduled job to check for stocks with high % change."""
    log.info("Running job: check_high_percentage_change")
    for token, data in live_data.items():
        if abs(data['change_percent']) > 5:
            if data['change_percent'] > 0:
                data['highlight'] = 'high_positive'
            else:
                data['highlight'] = 'high_negative'
        else:
            data['highlight'] = None

def detect_candle_patterns(kite):
    """Scheduled job to detect O=H/L patterns from 1-hour candles."""
    log.info("Running job: detect_candle_patterns")
    try:
        to_date = datetime.now().date()
        from_date = to_date - timedelta(days=5)

        for token in live_data.keys():
            try:
                records = kite.historical_data(token, from_date, to_date, "hour")
                if records:
                    last_candle = records[-1]
                    if last_candle['open'] == last_candle['high']:
                        live_data[token]['pattern'] = "Bearish O=H"
                    elif last_candle['open'] == last_candle['low']:
                        live_data[token]['pattern'] = "Bullish O=L"
                    else:
                        live_data[token]['pattern'] = None
            except Exception as e:
                log.error(f"Error fetching historical data for token {token}: {e}")
    except Exception as e:
        log.error(f"Error in detect_candle_patterns job: {e}")

def generate_dashboard() -> Group:
    """Generates the rich Group for live display."""
    # Holdings Table
    holdings_table = Table(title="[bold green]Holdings[/bold green]", show_header=True, header_style="bold magenta", border_style="green")
    holdings_table.add_column("Symbol", style="cyan")
    holdings_table.add_column("Qty", justify="right")
    holdings_table.add_column("Avg. Price", justify="right", style="yellow")
    holdings_table.add_column("LTP", justify="right", style="green")
    holdings_table.add_column("P&L", justify="right")

    total_holdings_pnl = 0
    if holdings_data:
        for h in holdings_data:
            pnl = (h['last_price'] - h['average_price']) * h['quantity']
            total_holdings_pnl += pnl
            pnl_style = "green" if pnl >= 0 else "red"
            holdings_table.add_row(
                h['tradingsymbol'], str(h['quantity']),
                f"{h['average_price']:.2f}", f"{h['last_price']:.2f}",
                f"[{pnl_style}]{pnl:,.2f}[/{pnl_style}]"
            )

    # Positions Table
    positions_table = Table(title="[bold blue]Open Positions[/bold blue]", show_header=True, header_style="bold magenta", border_style="blue")
    positions_table.add_column("Product", style="cyan")
    positions_table.add_column("Symbol", style="cyan")
    positions_table.add_column("Qty", justify="right")
    positions_table.add_column("Avg. Price", justify="right", style="yellow")
    positions_table.add_column("LTP", justify="right", style="green")
    positions_table.add_column("P&L", justify="right")

    total_positions_pnl = 0
    if positions_data:
        for p in positions_data:
            if p['quantity'] != 0:
                pnl = p['pnl']
                total_positions_pnl += pnl
                pnl_style = "green" if pnl >= 0 else "red"

                row_style = ""
                if pnl > 5000:
                    row_style = "on #f5f542"

                positions_table.add_row(
                    p['product'], p['tradingsymbol'], str(p['quantity']),
                    f"{p['average_price']:.2f}", f"{p['last_price']:.2f}",
                    f"[{pnl_style}]{pnl:,.2f}[/{pnl_style}]",
                    style=row_style
                )

    # Nifty 50 Table
    nifty_table = Table(title=f"[bold purple]Nifty 50 Live Tracker[/bold purple] (Last updated: {datetime.now().strftime('%H:%M:%S')})", show_header=True, header_style="bold magenta", border_style="purple")
    nifty_table.add_column("Symbol", style="cyan", no_wrap=True)
    nifty_table.add_column("LTP", justify="right", style="green")
    nifty_table.add_column("% Change", justify="right")
    nifty_table.add_column("Volume", justify="right", style="yellow")
    nifty_table.add_column("Pattern (1H)", justify="left")

    if live_data:
        most_active_token = max(live_data, key=lambda t: live_data[t]['volume'])
        sorted_tokens = sorted(live_data.keys(), key=lambda t: live_data[t]['symbol'])

        for token in sorted_tokens:
            data = live_data[token]
            row_style = ""
            if data['highlight'] == 'high_positive': row_style = "on #004d00"
            elif data['highlight'] == 'high_negative': row_style = "on #660000"

            symbol = f"⭐ {data['symbol']}" if token == most_active_token else data['symbol']
            change_percent = data['change_percent']
            pnl_style = "green" if change_percent >= 0 else "red"

            pattern_text = ""
            if data['pattern'] == "Bullish O=L": pattern_text = f"[bold green]🟢 Bullish O=L[/bold green]"
            elif data['pattern'] == "Bearish O=H": pattern_text = f"[bold red]🔴 Bearish O=H[/bold red]"

            nifty_table.add_row(
                symbol, f"{data['ltp']:.2f}", f"[{pnl_style}]{change_percent:+.2f}%[/{pnl_style}]",
                f"{data['volume']:,}", pattern_text, style=row_style
            )

    # Totals Panel
    holdings_pnl_style = "bold green" if total_holdings_pnl >= 0 else "bold red"
    positions_pnl_style = "bold green" if total_positions_pnl >= 0 else "bold red"
    totals_summary = (
        f"Total Holdings P&L: [{holdings_pnl_style}]{total_holdings_pnl:,.2f}[/{holdings_pnl_style}]   |   "
        f"Total Positional P&L: [{positions_pnl_style}]{total_positions_pnl:,.2f}[/{positions_pnl_style}]"
    )

    return Group(
        Panel(totals_summary, title="[bold yellow]Account Summary[/bold yellow]", border_style="yellow"),
        holdings_table,
        positions_table,
        nifty_table
    )

def main():
    """Main function to run the bot."""
    console.print("[bold cyan]Starting Zerodha Trading Bot...[/bold cyan]")
    global live_data, kws, holdings_data, positions_data

    # 1. Authentication
    kite = authenticate()
    if not kite:
        return

    # 2. Fetch Nifty 50 Stocks
    nifty50_tokens, token_map = get_nifty50_instrument_tokens(kite)
    if not nifty50_tokens:
        console.print("[bold red]Could not fetch Nifty 50 instrument tokens. Exiting.[/bold red]")
        return

    # 3. Fetch Initial Data
    prev_close_data = get_previous_day_close(kite, nifty50_tokens)
    live_data = {
        token: {
            'symbol': token_map.get(token, 'N/A'), 'prev_close': prev_close_data.get(token, 0),
            'ltp': prev_close_data.get(token, 0), 'volume': 0, 'ohlc': {}, 'change_percent': 0,
            'last_trade_time': None, 'highlight': None, 'pattern': None,
        } for token in nifty50_tokens
    }

    # 4. Setup WebSocket
    kws = KiteTicker(API_KEY, kite.access_token)
    kws.on_ticks = on_ticks; kws.on_connect = on_connect; kws.on_close = on_close; kws.on_error = on_error
    kws.connect(threaded=True)

    # Schedule jobs
    schedule.every(5).seconds.do(update_account_data, kite=kite)
    schedule.every(5).minutes.do(check_high_percentage_change)
    schedule.every(1).hour.do(detect_candle_patterns, kite=kite)

    # Run initial data fetch for all components
    update_account_data(kite)
    detect_candle_patterns(kite)

    # 5. Setup Rich Live Display & Main Loop
    with Live(generate_dashboard(), redirect_stderr=False, refresh_per_second=1) as live:
        console.print("[bold yellow]Bot is running. Press Ctrl+C to stop.[/bold yellow]")
        while True:
            try:
                schedule.run_pending()
                live.update(generate_dashboard())
                time.sleep(1)
            except KeyboardInterrupt:
                console.print("\n[bold red]Bot stopped by user.[/bold red]")
                if kws: kws.close()
                break

if __name__ == "__main__":
    main()
