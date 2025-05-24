# NiftyBEES Trading Bot

This script implements an automated trading strategy for NiftyBEES ETF based on predefined rules.

**IMPORTANT: This script is for educational purposes and demonstrates how to interact with the 5paisa API. Order placement is currently SIMULATED. Thorough testing is required before considering any live trading.**

## Setup

1.  **Install Libraries**:
    ```bash
    pip install py5paisa configparser
    ```
2.  **Credentials**:
    *   Copy `keys.conf.example` to `keys.conf` (both within the `niftybees_bot` directory).
    *   Edit `keys.conf` and fill in your actual 5paisa API credentials and personal details (Email, Password, DOB).
    *   **IMPORTANT**: Ensure your 5paisa API account has API access enabled.
3.  **Scrip ID**:
    *   Verify the `NIFTYBEES_SCRIP_ID` constant (currently set to 26000 for NSE) in `niftybees_trader.py`. This ID can vary. Use 5paisa API tools or documentation to find the correct `ScripCode` for NiftyBEES in the cash segment (NSE: NIFTYBEES) for your account.

## Running the Script

The script is designed to be run by a scheduler at specific market times (e.g., 9:30 AM and 3:00 PM IST on trading days). See comments in `niftybees_trader.py` for scheduling examples (cron, Task Scheduler).

You can also run it manually for testing:
```bash
cd /path/to/your/niftybees_bot # Navigate to the bot's directory
python niftybees_trader.py
```

## Testing Strategy

**This script involves financial transactions. Test with extreme caution.**

1.  **Understand the Code**: Before running, thoroughly review `niftybees_trader.py` to understand its logic, how it interacts with the API, and how it manages state via `trading_log.csv` and `position_status.csv`.
2.  **Credential Verification**: Double-check your `keys.conf` for accuracy. Incorrect credentials will lead to login failures. The script will log errors related to this.
3.  **Scrip ID Verification**: Ensure `NIFTYBEES_SCRIP_ID` in `niftybees_trader.py` is correct for your 5paisa account and for NiftyBEES (NSE, Cash segment). An incorrect ID will likely cause API errors when fetching market data or attempting (simulated) orders.
4.  **Simulated Mode (Default)**:
    *   The script currently **SIMULATES** order placements. This is controlled within the `place_delivery_order` function in `niftybees_trader.py`. No real orders will be sent to the exchange by default.
    *   Run the script manually or via a scheduler for testing.
    *   **Check `trading_log.csv`**: This is the primary file for observing the bot's behavior. It logs:
        *   Script start/end, credential loading, client initialization.
        *   Scheduled checks (9:30 AM, 3:00 PM).
        *   Position loading from `position_status.csv`.
        *   Exit logic checks: current price fetching, profit calculation, decisions to sell or hold.
        *   Entry logic checks: price fetching (current, yesterday's close), evaluation of price drop conditions, investment capacity checks, decisions to buy or skip.
        *   (Simulated) order placement details: BUY/SELL, quantity, price, and the simulated OrderID.
        *   Updates to position status after simulated trades.
        *   Any errors encountered during API calls or other operations.
    *   **Check `position_status.csv`**: Verify that this file correctly reflects the outcomes of simulated buys and sells.
        *   After a simulated BUY: Quantity should increase, AveragePrice should be recalculated, TotalInvested should increase.
        *   After a simulated SELL (exit): Quantity, AveragePrice, and TotalInvested should reset to 0.
    *   Manually verify calculations logged in `trading_log.csv` (e.g., average price after a buy, profit percentage for a sell) against your own calculations.
5.  **Testing Specific Scenarios**:
    *   **Initial Buy**:
        *   Ensure `position_status.csv` is empty or does not contain an entry for `NIFTYBEES`.
        *   Modify your system time or the script's time check to simulate 9:30 AM on a trading day.
        *   You might need to temporarily adjust `PRICE_DROP_MIN_PERCENT` / `PRICE_DROP_MAX_PERCENT` or mock the `get_current_price` and `get_yesterdays_close_price` functions to return values that meet the entry criteria (e.g., current price is 2% below yesterday's close).
        *   Run the script. Verify `trading_log.csv` shows the entry condition evaluation and a simulated BUY order. Check that `position_status.csv` is updated.
    *   **Averaging Down**:
        *   Start with an existing position in `position_status.csv` (e.g., 10 units at an average price of 200).
        *   Simulate 9:30 AM again. Mock price data so that entry conditions are met for another buy.
        *   Run the script. Verify a new simulated BUY is logged, and `position_status.csv` shows increased quantity and a new, correctly calculated average price.
    *   **Profit Exit**:
        *   Set up `position_status.csv` with a holding (e.g., 20 units at an average price of 190).
        *   Simulate 9:30 AM or 3:00 PM. Mock `get_current_price` to return a price that would trigger the `TARGET_PROFIT_PERCENT` (e.g., if target is 2%, current price should be >= 193.8).
        *   Run the script. Verify `trading_log.csv` shows the profit calculation and a simulated SELL order for the entire quantity. `position_status.csv` should be reset for NIFTYBEES.
    *   **No Action**:
        *   Set up conditions where neither entry nor exit criteria are met (e.g., price drop is too small, or profit is below target).
        *   Run the script at 9:30 AM or 3:00 PM.
        *   Verify logs show messages like "Price drop condition not met" or "Profit ... < target. Holding." and no simulated orders are placed.
6.  **Error Handling**:
    *   **Invalid Credentials**: Temporarily modify `keys.conf` with incorrect data. Run the script. Check for "Login Failed" messages and errors logged in `trading_log.csv`.
    *   **Incorrect Scrip ID**: Change `NIFTYBEES_SCRIP_ID` to an invalid ID. Run the script. Observe API errors when fetching prices, logged in `trading_log.csv` and potentially printed to console.
    *   **API Failures (Advanced)**: To test robustness against API call failures (e.g., network issues, API returning errors), you would ideally modify the API interaction functions (`get_current_price`, etc.) to sometimes return `None` or raise exceptions, then observe how the main logic handles these (it should generally log the error and skip the current action).
7.  **Small Scale Live Testing (Proceed with EXTREME CAUTION and AT YOUR OWN RISK)**:
    *   **ONLY AFTER** you are completely satisfied with simulated testing, fully understand the script's code, and acknowledge all associated risks.
    *   In `niftybees_trader.py`, locate the `place_delivery_order` function.
    *   Carefully comment out the simulation block (the lines that print "SIMULATING order" and return a mock response).
    *   Uncomment the actual `order_response = client.place_order(...)` line.
    *   **Start with the smallest possible `INVESTMENT_PER_TRADE` and a low `MAX_TOTAL_INVESTMENT`**.
    *   Run the script manually at first, not via scheduler.
    *   Monitor its execution very closely. Check your 5paisa account directly for actual orders being placed and their status.
    *   Review `trading_log.csv` immediately after execution.
    *   Be prepared to manually intervene in your 5paisa account (e.g., cancel orders, square off positions) if the script behaves unexpectedly.
8.  **Regular Monitoring**: If you decide to run the script live with a scheduler:
    *   Regularly check `trading_log.csv` for any errors or unexpected behavior.
    *   Monitor your 5paisa account for actual trades and holdings.
    *   Ensure the machine running the script is reliable and its time is synchronized.

**Disclaimer**: Trading in financial markets involves significant risk. This script is provided for educational purposes only and "as-is", without any warranty of any kind. The author(s) or contributors are not responsible for any financial losses or other damages incurred as a result of using this script. Always do your own research and consider consulting with a financial advisor before making any trading decisions.
