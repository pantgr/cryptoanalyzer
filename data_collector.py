#!/usr/bin/env python3
import os
import json
import requests
import time
from datetime import datetime, timedelta

class CryptoDataCollector:
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.data_dir = "data"
        self.ensure_data_directory()
        self.historical_data_file = os.path.join(self.data_dir, "crypto_historical_data.json")
        
    def ensure_data_directory(self):
        """Βεβαιώνεται ότι υπάρχει ο φάκελος data"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            print(f"Δημιουργήθηκε ο φάκελος: {self.data_dir}")
            
    def get_coin_list(self, limit=10):
        """Λήψη λίστας με τα κορυφαία κρυπτονομίσματα"""
        try:
            url = f"{self.base_url}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': limit,
                'page': 1
            }
            response = requests.get(url, params=params)
            data = response.json()
            return [(coin['id'], coin['symbol']) for coin in data]
        except Exception as e:
            print(f"Σφάλμα κατά τη λήψη λίστας κρυπτονομισμάτων: {e}")
            return []
            
    def collect_historical_data(self, coin_id, days=90):
        """Συλλογή ιστορικών δεδομένων για ένα κρυπτονόμισμα"""
        try:
            url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days,
                'interval': 'daily'
            }
            print(f"Λήψη δεδομένων για {coin_id} ({days} ημέρες)...")
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # Rate limit hit
                print(f"Όριο API - περιμένουμε για 60 δευτερόλεπτα...")
                time.sleep(60)
                return self.collect_historical_data(coin_id, days)
            else:
                print(f"Σφάλμα API: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Σφάλμα κατά τη λήψη δεδομένων για {coin_id}: {e}")
            return None
            
    def update_all_data(self, limit=10):
        """Ενημέρωση δεδομένων μόνο για τα νέα ή τα δεδομένα που λείπουν"""
        coin_list = self.get_coin_list(limit)
        if not coin_list:
            print("Δεν βρέθηκαν κρυπτονομίσματα για ανάλυση.")
            return False
            
        # Διάβασμα υπάρχοντων δεδομένων (αν υπάρχουν)
        all_data = {}
        if os.path.exists(self.historical_data_file):
            try:
                with open(self.historical_data_file, 'r') as f:
                    all_data = json.load(f)
            except Exception as e:
                print(f"Σφάλμα ανάγνωσης υπάρχοντων δεδομένων: {e}")
        
        last_update = None
        if 'last_updated' in all_data:
            try:
                last_update = datetime.strptime(all_data['last_updated'], "%Y-%m-%d %H:%M:%S")
                # Κρατάμε μόνο την ημερομηνία, αγνοούμε την ώρα
                last_update = last_update.date()
            except:
                last_update = None
        
        # Ενημέρωση δεδομένων για κάθε κρυπτονόμισμα
        for coin_id, symbol in coin_list:
            if coin_id in all_data:
                # Το κρυπτονόμισμα υπάρχει ήδη, ενημερώνουμε μόνο τα νέα δεδομένα
                if 'prices' in all_data[coin_id] and all_data[coin_id]['prices']:
                    # Βρίσκουμε την τελευταία ημερομηνία που έχουμε δεδομένα
                    last_timestamp = all_data[coin_id]['prices'][-1][0]
                    last_date = datetime.fromtimestamp(last_timestamp/1000).date()
                    
                    today = datetime.now().date()
                    days_difference = (today - last_date).days
                    
                    if days_difference <= 1:
                        print(f"Τα δεδομένα για το {coin_id} είναι ήδη ενημερωμένα.")
                        continue
                    
                    # Ανακτούμε μόνο τα νέα δεδομένα (προσθέτουμε 1 για επικάλυψη)
                    days_to_fetch = days_difference + 1
                    print(f"Λήψη νέων δεδομένων {days_to_fetch} ημερών για {coin_id}...")
                    new_data = self.collect_historical_data(coin_id, days=days_to_fetch)
                    
                    if new_data:
                        # Συγχωνεύουμε τα παλιά με τα νέα δεδομένα
                        # Αγνοούμε την πρώτη τιμή των νέων δεδομένων (επικάλυψη)
                        if len(new_data['prices']) > 1:
                            # Ημερομηνία επικάλυψης για έλεγχο
                            overlap_date = datetime.fromtimestamp(new_data['prices'][0][0]/1000).date()
                            
                            all_data[coin_id]['prices'].extend(new_data['prices'][1:])
                            all_data[coin_id]['market_caps'].extend(new_data['market_caps'][1:])
                            all_data[coin_id]['total_volumes'].extend(new_data['total_volumes'][1:])
                            print(f"Προστέθηκαν {len(new_data['prices'])-1} νέες τιμές για {coin_id}")
                else:
                    # Λείπουν τα δεδομένα prices, ανάκτηση ολόκληρου ιστορικού
                    print(f"Ανάκτηση πλήρους ιστορικού για {coin_id}...")
                    hist_data = self.collect_historical_data(coin_id)
                    if hist_data:
                        hist_data['symbol'] = symbol
                        all_data[coin_id] = hist_data
            else:
                # Νέο κρυπτονόμισμα, ανάκτηση όλων των δεδομένων
                print(f"Νέο κρυπτονόμισμα {coin_id}, ανάκτηση πλήρους ιστορικού...")
                hist_data = self.collect_historical_data(coin_id)
                if hist_data:
                    hist_data['symbol'] = symbol
                    all_data[coin_id] = hist_data
                    
            # Μικρή καθυστέρηση για αποφυγή rate limiting
            time.sleep(1)  
        
        # Προσθήκη χρονικής σήμανσης τελευταίας ενημέρωσης
        all_data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Αποθήκευση δεδομένων
        try:
            with open(self.historical_data_file, 'w') as f:
                json.dump(all_data, f)
            print(f"Δεδομένα αποθηκεύτηκαν στο: {self.historical_data_file}")
            return True
        except Exception as e:
            print(f"Σφάλμα αποθήκευσης δεδομένων: {e}")
            return False

if __name__ == "__main__":
    collector = CryptoDataCollector()
    success = collector.update_all_data(10)
    if success:
        print("Επιτυχής ενημέρωση δεδομένων!")
    else:
        print("Η ενημέρωση δεδομένων απέτυχε.")