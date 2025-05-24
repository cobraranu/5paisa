# Main script for the NiftyBEES trading bot
import configparser
import os
import csv # Added for CSV handling
from datetime import datetime, timedelta
from py5paisa import FivePaisaClient
# from py5paisa.order import OrderType # Not directly used as we pass 'B' or 'S'

# --- Constants ---
# IMPORTANT: User must verify NIFTYBEES_SCRIP_ID (currently 26000) for NSE.
# This ID can change or might be different for specific accounts/segments.
# Check your 5paisa API documentation or use API calls to find the correct ScripCode.
NIFTYBEES_SCRIP_ID = 26000  # Example ScripCode for NIFTYBEES on NSE (Cash segment)
NIFTYBEES_SCRIP_NAME = "NIFTYBEES" # Used for logging or display, API calls use ScripCode
NIFTYBEES_EXCHANGE = "N"        # NSE
NIFTYBEES_EXCHANGE_TYPE = "C"   # Cash segment

# CSV File Paths (relative to this script's directory)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRADING_LOG_FILE = os.path.join(SCRIPT_DIR, 'trading_log.csv')
POSITION_STATUS_FILE = os.path.join(SCRIPT_DIR, 'position_status.csv')
NIFTYBEES_SCRIP_NAME_CONST = NIFTYBEES_SCRIP_NAME # Using existing constant

# --- Trading Parameters ---
TARGET_PROFIT_PERCENT = 2.0  # 2%
PRICE_DROP_MIN_PERCENT = 1.0 # 1% (Minimum drop from day's open or yesterday's close to consider buying)
PRICE_DROP_MAX_PERCENT = 3.0 # 3% (Maximum drop from day's open or yesterday's close to consider buying)
INVESTMENT_PER_TRADE = 5000  # Rupees (Target investment amount for each buy trade)
MAX_TOTAL_INVESTMENT = 100000 # Rupees (Maximum total invested amount in NiftyBEES)


# Global variable for the FivePaisaClient instance
client = None

# --- Credential and Client Initialization ---
def load_credentials(config_file='keys.conf'):
    config_path = os.path.join(SCRIPT_DIR, config_file) 
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file '{config_file}' not found in {SCRIPT_DIR}.")
    config = configparser.ConfigParser()
    config.read(config_path)
    if '5PAISA_API_CREDS' not in config or 'USER_DETAILS' not in config:
        raise KeyError("Config must contain [5PAISA_API_CREDS] and [USER_DETAILS] sections.")
    api_creds_section = config['5PAISA_API_CREDS']
    user_details_section = config['USER_DETAILS']
    required_api_keys = ['APP_NAME', 'APP_SOURCE', 'USER_ID', 'PASSWORD', 'USER_KEY', 'ENCRYPTION_KEY']
    required_user_details = ['EMAIL', 'PASSWD', 'DOB']
    loaded_creds = {"cred": {}, "email": "", "passwd": "", "dob": ""}
    for key in required_api_keys:
        if key not in api_creds_section: raise KeyError(f"Missing key '{key}' in [5PAISA_API_CREDS].")
        loaded_creds["cred"][key] = api_creds_section[key]
    for key in required_user_details:
        if key not in user_details_section: raise KeyError(f"Missing key '{key}' in [USER_DETAILS].")
        loaded_creds[key.lower()] = user_details_section[key]
    return loaded_creds

def initialize_client(credentials):
    global client
    try:
        client = FivePaisaClient(
            email=credentials['email'], passwd=credentials['passwd'],
            dob=credentials['dob'], cred=credentials['cred']
        )
        if hasattr(client, 'Jwt_token') and client.Jwt_token:
            print("5Paisa Client Login Successful!")
            return True
        else:
            print("5Paisa Client Login Failed. Check credentials and DOB.")
            if hasattr(client, 'response') and client.response: print(f"Response: {client.response.json()}")
            if hasattr(client, 'error_message') and client.error_message: print(f"Error Message: {client.error_message}")
            return False
    except Exception as e: print(f"Error during client initialization or login: {e}"); return False

# --- API Interaction Functions ---
def get_current_price(scrip_code_id: int, exchange: str = NIFTYBEES_EXCHANGE, exchange_type: str = NIFTYBEES_EXCHANGE_TYPE) -> float | None:
    global client
    if not client: print("Client not initialized for get_current_price."); return None
    try:
        req_list = [{"Exch": exchange, "ExchType": exchange_type, "ScripCode": scrip_code_id}]
        response = client.fetch_market_feed(req_list)
        if response and response.get('body') and response['body'].get('Data') and len(response['body']['Data']) > 0:
            market_data = response['body']['Data'][0]
            if 'LTP' in market_data: return float(market_data['LTP'])
            else: print(f"LTP not found for {scrip_code_id}: {market_data}"); return None
        else: print(f"Could not fetch market feed for {scrip_code_id}: {response}"); return None
    except Exception as e: print(f"Error in get_current_price for {scrip_code_id}: {e}"); return None

def get_todays_open_price(scrip_code_id: int, exchange: str = NIFTYBEES_EXCHANGE, exchange_type: str = NIFTYBEES_EXCHANGE_TYPE) -> float | None:
    global client
    if not client: print("Client not initialized for get_todays_open_price."); return None
    try:
        req_list = [{"Exch": exchange, "ExchType": exchange_type, "ScripCode": scrip_code_id}]
        response = client.fetch_market_feed(req_list)
        if response and response.get('body') and response['body'].get('Data') and len(response['body']['Data']) > 0:
            market_data = response['body']['Data'][0]
            if 'Open' in market_data: return float(market_data['Open'])
            else: print(f"Open price not found for {scrip_code_id}: {market_data}"); return None
        else: print(f"Could not fetch market feed for {scrip_code_id}: {response}"); return None
    except Exception as e: print(f"Error in get_todays_open_price for {scrip_code_id}: {e}"); return None

def get_yesterdays_close_price(scrip_code_id: int, exchange: str = NIFTYBEES_EXCHANGE, exchange_type: str = NIFTYBEES_EXCHANGE_TYPE) -> float | None:
    global client
    if not client: print("Client not initialized for get_yesterdays_close_price."); return None
    try:
        today = datetime.today()
        if today.weekday() == 0: prev_day_obj = today - timedelta(days=3) # Monday -> Friday
        elif today.weekday() == 6: prev_day_obj = today - timedelta(days=2) # Sunday -> Friday
        else: prev_day_obj = today - timedelta(days=1) # Other weekdays
        prev_day_str = prev_day_obj.strftime('%Y-%m-%d')
        hist_data = client.historical_data(Exch=exchange, ExchangeSegment=exchange_type, ScripCode=scrip_code_id, time='1d', From=prev_day_str, To=prev_day_str)
        if hist_data is not None:
            if hasattr(hist_data, 'iloc') and not hist_data.empty: return float(hist_data['Close'].iloc[0])
            elif isinstance(hist_data, list) and len(hist_data) > 0:
                if 'Close' in hist_data[0]: return float(hist_data[0]['Close'])
                elif 'Cls' in hist_data[0]: return float(hist_data[0]['Cls'])
                else: print(f"Close key not found in historical data: {hist_data[0]}"); return None
            else: print(f"Historical data empty/unexpected for {scrip_code_id} on {prev_day_str}: {hist_data}"); return None
        else: print(f"No historical data (None) for {scrip_code_id} on {prev_day_str}."); return None
    except Exception as e: print(f"Error in get_yesterdays_close_price for {scrip_code_id}: {e}"); return None

def place_delivery_order(scrip_code_id: int, quantity: int, order_type: str, 
                         exchange: str = NIFTYBEES_EXCHANGE, exchange_type: str = NIFTYBEES_EXCHANGE_TYPE,
                         price: float = 0) -> dict | None:
    global client
    if not client: print("Client not initialized for place_delivery_order."); return None
    api_order_type = 'B' if order_type.upper() == "BUY" else 'S'
    # IMPORTANT: Actual order placement is SIMULATED for safety during development/testing.
    # To enable live trading, uncomment the actual client.place_order call and handle its response.
    # order_response = client.place_order(
    #     OrderType=api_order_type, Exchange=exchange, ExchangeType=exchange_type, 
    #     ScripCode=scrip_code_id, Qty=quantity, Price=price, IsIntraday=False
    # )
    # print(f"Actual order response: {order_response}") # Log actual response if live
    sim_order_id = f"SIM_{order_type.upper()}_{int(datetime.now().timestamp())}"
    print(f"SIMULATING order: {order_type} {quantity} of {scrip_code_id} at price {price if price > 0 else 'MARKET'}. Simulated OrderID: {sim_order_id}")
    # Simulate success; in a real scenario, check order_response
    return {"status": "success", "message": "Order placement simulated.", "OrderID": sim_order_id}


def get_active_holdings_from_api() -> list:
    global client
    if not client: print("Client not initialized for get_active_holdings_from_api."); return []
    try:
        holdings_response = client.holdings()
        if holdings_response and holdings_response.get('body') and holdings_response['body'].get('Data'):
            return holdings_response['body']['Data']
        else: print(f"Could not fetch holdings or data empty: {holdings_response}"); return []
    except Exception as e: print(f"Error in get_active_holdings_from_api: {e}"); return []

# --- CSV State Management Functions ---
def load_position_status(scrip_name: str) -> dict:
    default_status = {"scrip": scrip_name, "quantity": 0, "average_price": 0.0, "total_invested": 0.0}
    try:
        if not os.path.exists(POSITION_STATUS_FILE): return default_status
        with open(POSITION_STATUS_FILE, mode='r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['Scrip'] == scrip_name:
                    return {"scrip": row['Scrip'], "quantity": int(row['Quantity']), 
                            "average_price": float(row['AveragePrice']), "total_invested": float(row['TotalInvested'])}
            return default_status
    except Exception as e: print(f"Error loading position for {scrip_name}: {e}"); return default_status

def save_position_status(scrip_name: str, quantity: int, avg_price: float, total_invested: float):
    fieldnames = ['Scrip', 'Quantity', 'AveragePrice', 'TotalInvested']
    rows = []
    found = False
    try:
        if os.path.exists(POSITION_STATUS_FILE):
            with open(POSITION_STATUS_FILE, mode='r', newline='') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['Scrip'] == scrip_name:
                        row['Quantity'] = quantity; row['AveragePrice'] = round(avg_price, 2); row['TotalInvested'] = round(total_invested, 2)
                        found = True
                    rows.append(row)
        if not found: rows.append({'Scrip': scrip_name, 'Quantity': quantity, 'AveragePrice': round(avg_price, 2), 'TotalInvested': round(total_invested, 2)})
        with open(POSITION_STATUS_FILE, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader(); writer.writerows(rows)
    except Exception as e: print(f"Error saving position for {scrip_name}: {e}")

def log_trade_event(event: str, scrip: str, action: str = "", quantity: int = 0, price: float = 0.0, 
                    avg_cost_before: float = 0.0, avg_cost_after: float = 0.0, 
                    profit_percent: float = 0.0, reason: str = "", order_id: str = ""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fieldnames = ['Timestamp', 'Event', 'Scrip', 'Action', 'Quantity', 'Price', 
                  'AvgCostBefore', 'AvgCostAfter', 'ProfitPercent', 'Reason', 'OrderID']
    row_dict = {'Timestamp': timestamp, 'Event': event, 'Scrip': scrip, 'Action': action, 'Quantity': quantity, 
                'Price': round(price, 2), 'AvgCostBefore': round(avg_cost_before, 2), 
                'AvgCostAfter': round(avg_cost_after, 2), 'ProfitPercent': round(profit_percent, 2), 
                'Reason': reason, 'OrderID': order_id}
    try:
        file_exists = os.path.exists(TRADING_LOG_FILE)
        with open(TRADING_LOG_FILE, mode='a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists or os.path.getsize(TRADING_LOG_FILE) == 0: writer.writeheader() 
            writer.writerow(row_dict)
    except Exception as e: print(f"Error logging event to {TRADING_LOG_FILE}: {e}")

# --- Calculation Functions ---
def calculate_new_avg_price(current_qty: int, current_avg_price: float, buy_qty: int, buy_price: float) -> float:
    if buy_qty <= 0: return current_avg_price
    if current_qty == 0: return buy_price
    else:
        new_total_value = (current_qty * current_avg_price) + (buy_qty * buy_price)
        new_total_qty = current_qty + buy_qty
        if new_total_qty == 0: return 0.0 
        return new_total_value / new_total_qty

# --- Trading Logic Helper Functions ---
def _handle_exit_logic(current_qty: int, avg_price: float, scrip_id: int, scrip_name: str, 
                       exchange: str, exchange_type: str, target_profit_percent: float, 
                       current_total_invested: float) -> tuple[float, int, float]:
    """
    Helper function to handle exit logic based on profit target.
    Returns updated (total_invested, current_qty, avg_price).
    """
    if current_qty <= 0:
        log_trade_event(event="EXIT_CHECK_NO_HOLDINGS", scrip=scrip_name, reason="No holdings to exit.")
        return current_total_invested, current_qty, avg_price

    if avg_price == 0:
        log_trade_event(event="EXIT_ERROR", scrip=scrip_name, reason="Average price is zero, cannot calculate profit.")
        return current_total_invested, current_qty, avg_price

    current_market_price = get_current_price(scrip_id, exchange, exchange_type)
    if current_market_price is None:
        log_trade_event(event="EXIT_ERROR", scrip=scrip_name, reason="Could not fetch current market price for exit check.")
        return current_total_invested, current_qty, avg_price

    profit_percentage = ((current_market_price - avg_price) / avg_price) * 100
    log_trade_event(event="PROFIT_CHECK", scrip=scrip_name, price=current_market_price, 
                    profit_percent=profit_percentage, avg_cost_before=avg_price,
                    reason="Checking exit condition.")

    if profit_percentage >= target_profit_percent:
        log_trade_event(event="EXIT_CONDITION_MET", scrip=scrip_name, action="SELL_INITIATED", 
                        quantity=current_qty, price=current_market_price, 
                        profit_percent=profit_percentage, 
                        reason=f"Profit {profit_percentage:.2f}% >= {target_profit_percent}%.")
        
        simulated_order_response = place_delivery_order(
            scrip_code_id=scrip_id, quantity=current_qty, order_type="SELL", 
            exchange=exchange, exchange_type=exchange_type, price=0 
        )

        if simulated_order_response and simulated_order_response.get("status") == "success":
            simulated_order_id = simulated_order_response.get("OrderID", "N/A")
            log_trade_event(event="SELL_ORDER_SUCCESS", scrip=scrip_name, action="SELL_CONFIRMED", 
                            quantity=current_qty, price=current_market_price, 
                            profit_percent=profit_percentage, order_id=simulated_order_id,
                            avg_cost_before=avg_price)
            
            new_total_invested = 0.0
            new_avg_price = 0.0
            new_qty = 0
            save_position_status(scrip_name, new_qty, new_avg_price, new_total_invested)
            print(f"Simulated SELL successful for {current_qty} of {scrip_name}. Position reset.")
            return new_total_invested, new_qty, new_avg_price
        else:
            log_trade_event(event="SELL_ORDER_FAILED", scrip=scrip_name, action="SELL_FAILED", 
                            quantity=current_qty, reason="Simulated order placement failed or error in response.")
            print(f"Simulated SELL FAILED for {scrip_name}.")
            return current_total_invested, current_qty, avg_price
    else:
        log_trade_event(event="HOLD_POSITION", scrip=scrip_name, price=current_market_price,
                        profit_percent=profit_percentage, avg_cost_before=avg_price,
                        reason=f"Profit {profit_percentage:.2f}% < {target_profit_percent}%. Holding.")
        return current_total_invested, current_qty, avg_price

# --- Main Trading Logic ---
def execute_trading_logic():
    log_trade_event(event="EXECUTE_LOGIC_START", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="Trading logic execution started.")
    
    if not client:
        log_trade_event(event="CLIENT_ERROR", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="5Paisa client not initialized. Skipping logic.")
        print("5Paisa client not initialized. Cannot execute trading logic.")
        return

    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute

    position_data = load_position_status(NIFTYBEES_SCRIP_NAME_CONST)
    current_qty = position_data['quantity']
    avg_price = position_data['average_price']
    total_invested = position_data['total_invested']
    
    log_trade_event(event="POSITION_LOAD", scrip=NIFTYBEES_SCRIP_NAME_CONST, 
                    quantity=current_qty, avg_cost_before=avg_price,
                    reason=f"Loaded: Qty={current_qty}, AvgPrice={avg_price:.2f}, Invested={total_invested:.2f}")

    if current_hour == 9 and current_minute == 30:
        log_trade_event(event="SCHEDULED_CHECK", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="Morning check (9:30 AM) started.")
        
        total_invested, current_qty, avg_price = _handle_exit_logic(
            current_qty, avg_price, 
            NIFTYBEES_SCRIP_ID, NIFTYBEES_SCRIP_NAME_CONST, 
            NIFTYBEES_EXCHANGE, NIFTYBEES_EXCHANGE_TYPE,
            TARGET_PROFIT_PERCENT,
            total_invested 
        )
        # _handle_exit_logic now directly updates and saves position if a sale occurs,
        # and returns the updated values.

        # --- Morning Entry Logic ---
        if current_qty == 0 or total_invested < MAX_TOTAL_INVESTMENT: 
            log_trade_event(event="ENTRY_CHECK_INITIATED", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="Checking entry conditions.")
            
            current_market_price = get_current_price(NIFTYBEES_SCRIP_ID, NIFTYBEES_EXCHANGE, NIFTYBEES_EXCHANGE_TYPE)
            # todays_open = get_todays_open_price(NIFTYBEES_SCRIP_ID, NIFTYBEES_EXCHANGE, NIFTYBEES_EXCHANGE_TYPE) # Not directly used in logic but good to fetch/log
            yesterdays_close = get_yesterdays_close_price(NIFTYBEES_SCRIP_ID, NIFTYBEES_EXCHANGE, NIFTYBEES_EXCHANGE_TYPE)

            if not all([current_market_price, yesterdays_close]): 
                log_trade_event(event="ENTRY_CHECK_FAILED", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="Failed to fetch necessary price data for entry decision.")
            else:
                lower_bound = yesterdays_close * (1 - (PRICE_DROP_MAX_PERCENT / 100.0)) 
                upper_bound = yesterdays_close * (1 - (PRICE_DROP_MIN_PERCENT / 100.0)) 
                
                price_drop_condition_met = (lower_bound <= current_market_price <= upper_bound)
                
                log_trade_event(
                    event="ENTRY_CONDITION_EVAL", 
                    scrip=NIFTYBEES_SCRIP_NAME_CONST,
                    price=current_market_price,
                    reason=f"Drop Condition: YC={yesterdays_close}, CMP={current_market_price}, LowerBound={lower_bound:.2f}, UpperBound={upper_bound:.2f}. Met={price_drop_condition_met}"
                )

                if price_drop_condition_met and total_invested < MAX_TOTAL_INVESTMENT:
                    remaining_investment_capacity = MAX_TOTAL_INVESTMENT - total_invested
                    investment_for_this_trade = min(INVESTMENT_PER_TRADE, remaining_investment_capacity)
                    
                    if investment_for_this_trade < 1: 
                         log_trade_event(event="INVESTMENT_SKIP", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="Investment capacity too low or zero.")
                    else:
                        buy_qty = int(investment_for_this_trade / current_market_price) 
                        
                        if buy_qty > 0:
                            log_trade_event(event="ENTRY_CONDITION_MET", scrip=NIFTYBEES_SCRIP_NAME_CONST, action="BUY_INITIATED", quantity=buy_qty, price=current_market_price, reason=f"Price drop {PRICE_DROP_MIN_PERCENT}-{PRICE_DROP_MAX_PERCENT}% and capital available.")
                            
                            # SIMULATE order placement
                            order_response = place_delivery_order(NIFTYBEES_SCRIP_ID, buy_qty, "BUY", NIFTYBEES_EXCHANGE, NIFTYBEES_EXCHANGE_TYPE, price=0) # Market order for buy
                            simulated_order_id = order_response.get('OrderID', 'N/A') if order_response else 'N/A'
                            
                            if order_response and order_response.get('status') == 'success':
                                log_trade_event(event="BUY_ORDER_SUCCESS", scrip=NIFTYBEES_SCRIP_NAME_CONST, action="BUY_CONFIRMED", quantity=buy_qty, price=current_market_price, order_id=simulated_order_id, avg_cost_before=avg_price)
                                
                                # Update position status
                                # old_avg_price = avg_price # avg_price already holds the value before this buy
                                new_avg_price = calculate_new_avg_price(current_qty, avg_price, buy_qty, current_market_price)
                                current_qty += buy_qty
                                total_invested += (buy_qty * current_market_price) 
                                
                                save_position_status(NIFTYBEES_SCRIP_NAME_CONST, current_qty, new_avg_price, total_invested)
                                log_trade_event(event="POSITION_UPDATE", scrip=NIFTYBEES_SCRIP_NAME_CONST, quantity=current_qty, avg_cost_after=new_avg_price, reason=f"New Pos: Qty={current_qty}, AvgPrice={new_avg_price:.2f}, Invested={total_invested:.2f}")
                                
                                avg_price = new_avg_price # Update local avg_price for current scope
                            else:
                                log_trade_event(event="BUY_ORDER_FAILED", scrip=NIFTYBEES_SCRIP_NAME_CONST, action="BUY_FAILED", quantity=buy_qty, reason=f"Simulated order placement failed. Response: {order_response}")
                        else:
                            log_trade_event(event="INVESTMENT_SKIP", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="Calculated buy quantity is zero or less.")
                elif not price_drop_condition_met:
                    log_trade_event(event="NO_ENTRY", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="Price drop condition not met.")
                elif total_invested >= MAX_TOTAL_INVESTMENT:
                    log_trade_event(event="NO_ENTRY", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="Max total investment reached.")
        else:
            log_trade_event(event="ENTRY_SKIP", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="Not eligible for new entry (already holding max investment or other conditions not met).")


    elif current_hour == 15 and current_minute == 0: 
        log_trade_event(event="SCHEDULED_CHECK", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="Afternoon check (3:00 PM) started.")
        
        total_invested, current_qty, avg_price = _handle_exit_logic( # ensure current_qty, avg_price are updated
            current_qty, avg_price,
            NIFTYBEES_SCRIP_ID, NIFTYBEES_SCRIP_NAME_CONST,
            NIFTYBEES_EXCHANGE, NIFTYBEES_EXCHANGE_TYPE,
            TARGET_PROFIT_PERCENT,
            total_invested
        )
        
    else:
        log_trade_event(event="OFF_SCHEDULE_RUN", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason=f"Run at {now.strftime('%H:%M')} - no scheduled actions.")
    
    log_trade_event(event="EXECUTE_LOGIC_END", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="Trading logic execution finished.")


# --- Main Execution Block ---
if __name__ == "__main__":
    try:
        print("Attempting to load credentials...")
        creds = load_credentials()
        
        print("\n--- Initializing CSV Files (if needed) ---")
        if not os.path.exists(POSITION_STATUS_FILE) or os.path.getsize(POSITION_STATUS_FILE) == 0:
            save_position_status(NIFTYBEES_SCRIP_NAME_CONST, 0, 0.0, 0.0)
            print(f"Initialized {POSITION_STATUS_FILE} for {NIFTYBEES_SCRIP_NAME_CONST}")
        
        if not os.path.exists(TRADING_LOG_FILE) or os.path.getsize(TRADING_LOG_FILE) == 0:
             log_trade_event(event="SYSTEM_INIT", scrip="NA", action="CREATE_LOG", reason="Creating trading_log.csv")
             print(f"Initialized {TRADING_LOG_FILE}")

        initial_pos_for_log = load_position_status(NIFTYBEES_SCRIP_NAME_CONST)
        log_trade_event(event="SCRIPT_START", scrip=NIFTYBEES_SCRIP_NAME_CONST, action="INFO", 
                        reason="Script started, initial position loaded.",
                        quantity=initial_pos_for_log.get('quantity',0),
                        avg_cost_before=initial_pos_for_log.get('average_price', 0.0))
        print(f"Initial position for {NIFTYBEES_SCRIP_NAME_CONST}: {initial_pos_for_log}")


        print("\n--- Testing Average Price Calculation ---")
        avg_price1 = calculate_new_avg_price(0, 0.0, 10, 100.0); print(f"Avg price (0,0,10,100): {avg_price1:.2f}") 
        avg_price2 = calculate_new_avg_price(10, 100.0, 5, 90.0); print(f"Avg price (10,100,5,90): {avg_price2:.2f}") 
        avg_price3 = calculate_new_avg_price(10, 100.0, 0, 90.0); print(f"Avg price (10,100,0,90): {avg_price3:.2f}") 
        avg_price4 = calculate_new_avg_price(0, 0.0, 0, 90.0); print(f"Avg price (0,0,0,90): {avg_price4:.2f}") 

        if creds and initialize_client(creds):
            print("\n--- Client Initialized - Proceeding with Tests & Logic ---")
            
            print("\n--- Executing Trading Logic ---")
            execute_trading_logic()

        else:
            print("Failed to load credentials or initialize 5Paisa client. Trading logic and API functions skipped.")
            log_trade_event(event="CLIENT_INIT_FAIL", scrip=NIFTYBEES_SCRIP_NAME_CONST, reason="Failed to initialize client in main.")

    except (FileNotFoundError, KeyError) as e:
        print(f"Setup or Credential loading error: {e}")
        log_trade_event(event="ERROR_SETUP", scrip="NA", reason=str(e))
    except Exception as e:
        print(f"An unexpected error occurred in main: {e}")
        import traceback
        traceback.print_exc()
        log_trade_event(event="ERROR_UNEXPECTED", scrip="NA", reason=str(e))

    log_trade_event(event="SCRIPT_END", scrip=NIFTYBEES_SCRIP_NAME_CONST, action="INFO", reason="Script execution finished.")
    print("\nScript execution finished.")

# --- Scheduling the Script ---
# This script is designed to be run by a scheduler at specific times on trading days.
#
# Common Scheduling Tools:
# 1. cron (Linux/macOS):
#    - You'll need to edit your crontab (e.g., `crontab -e`).
#    - Example to run at 9:30 AM and 3:00 PM, Monday to Friday:
#      ```cron
#      # Minute Hour DayOfMonth Month DayOfWeek Command
#      30 9  * * 1-5  /usr/bin/python3 /path/to/your/niftybees_bot/niftybees_trader.py
#      00 15 * * 1-5  /usr/bin/python3 /path/to/your/niftybees_bot/niftybees_trader.py
#      ```
#    - Replace `/usr/bin/python3` with the actual path to your Python interpreter if it's different.
#    - Replace `/path/to/your/niftybees_bot/niftybees_trader.py` with the absolute path to this script.
#
# 2. Task Scheduler (Windows):
#    - Search for "Task Scheduler" in the Windows search bar.
#    - Create a new task:
#      - Trigger: Set to run daily at 9:30 AM and another trigger for 3:00 PM. You might need to specify
#                 days of the week (e.g., Monday to Friday).
#      - Action: "Start a program".
#        - Program/script: Path to your Python interpreter (e.g., `C:\Python39\python.exe`).
#        - Add arguments (optional): The path to this script (`C:\path\to\your\niftybees_bot\niftybees_trader.py`).
#        - Start in (optional): The directory containing the script (`C:\path\to\your\niftybees_bot\`). This is important
#                               so that relative paths for `keys.conf` and CSV files work correctly.
#
# Environment and Paths:
# - Ensure that the Python environment used by the scheduler has all necessary libraries installed (e.g., `pip install py5paisa configparser`).
# - The script relies on `keys.conf`, `trading_log.csv`, and `position_status.csv` being in the same directory as the script.
#   When scheduling, ensure the "Start in" or working directory is set to this script's directory.
#
# Logging Output:
# - It's highly recommended to redirect the script's output (stdout and stderr) to a log file when running via a scheduler.
#   This helps in monitoring execution and troubleshooting any issues.
#   - For cron:
#     `30 9 * * 1-5 /usr/bin/python3 /path/to/script.py >> /path/to/logfile.log 2>&1`
#   - For Task Scheduler: You can configure output redirection in the task's settings or use a wrapper batch script.
# - The script itself also generates `trading_log.csv` which contains detailed operational logs.
#
# Important Considerations:
# - Market Holidays: The provided cron example runs Monday to Friday. You might need a more sophisticated
#   scheduling setup or an external mechanism to avoid running the script on market holidays.
# - Time Zones: Ensure your server/machine's time zone is correctly set, especially if using a cloud VM.
# - Script Reliability: Test thoroughly. The script currently uses SIMULATED orders.
#   Before live trading, change `place_delivery_order` to execute real trades and handle API responses robustly.
