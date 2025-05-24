import configparser
from py5paisa import FivePaisaClient

# IMPORTANT: Replace placeholders below with your actual credentials 
# or use a keys.conf file as shown in the commented section.

# How to read credentials from a keys.conf file:
# config = configparser.ConfigParser()
# config.read('keys.conf')
# cred = config['CREDS']
# email = config['DEFAULT']['email']
# passwd = config['DEFAULT']['passwd']
# dob = config['DEFAULT']['dob']

# Hardcoded placeholder credentials (replace with your actual credentials)
cred = {
    "APP_NAME": "YOUR_APP_NAME",
    "APP_SOURCE": "YOUR_APP_SOURCE",
    "USER_ID": "YOUR_USER_ID",
    "PASSWORD": "YOUR_PASSWORD",
    "USER_KEY": "YOUR_USER_KEY",
    "ENCRYPTION_KEY": "YOUR_ENCRYPTION_KEY"
}
email = "your_email@example.com"
passwd = "your_password"
dob = "YYYYMMDD"  # Replace with your date of birth in YYYYMMDD format

try:
    client = FivePaisaClient(email=email, passwd=passwd, dob=dob, cred=cred)
    # The login happens during client initialization, no explicit client.login() call is needed
    # with recent versions of the library.
    # We can check if login was successful by checking for Jwt_token
    
    if hasattr(client, 'Jwt_token') and client.Jwt_token:
        print("Login Successful!")
        holdings = client.holdings()
        print("\nHoldings:")
        print(holdings)
    else:
        print("Login Failed. Please check your credentials and DOB.")
        if hasattr(client, 'response') and client.response:
            print(f"Response: {client.response.json()}")
        if hasattr(client, 'error_message') and client.error_message:
            print(f"Error Message: {client.error_message}")


except Exception as e:
    print(f"An error occurred: {e}")
    # You might want to log the full traceback here for debugging
    # import traceback
    # print(traceback.format_exc())
