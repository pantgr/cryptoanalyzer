import os
import json
from crypto_analyzer import CryptoAnalyzer

# Έλεγχος διαδρομής
print(f"Current directory: {os.getcwd()}")
print(f"Data directory should be: {os.path.join(os.getcwd(), 'data')}")

# Έλεγχος αν υπάρχει το αρχείο
data_file = os.path.join(os.getcwd(), 'data', 'crypto_historical_data.json')
print(f"Data file exists: {os.path.exists(data_file)}")
print(f"Data file size: {os.path.getsize(data_file) if os.path.exists(data_file) else 'N/A'}")

# Προσπάθεια φόρτωσης δεδομένων
try:
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    print(f"Data loaded successfully!")
    print(f"Available coins: {list(data.keys())}")
    
    # Προσπάθεια χρήσης του CryptoAnalyzer
    analyzer = CryptoAnalyzer()
    coins = analyzer.get_available_coins()
    print(f"CryptoAnalyzer found coins: {coins}")
    
    for coin_id, symbol in coins:
        print(f"Testing {coin_id}...")
        coin_data = analyzer.get_coin_data(coin_id)
        if coin_data:
            print(f"  - Found data for {coin_id}")
            print(f"  - Has prices: {len(coin_data.get('prices', []))}")
            print(f"  - Has dates: {len(coin_data.get('dates', []))}")
        else:
            print(f"  - NO DATA for {coin_id}")
    
except Exception as e:
    print(f"Error loading data: {str(e)}")