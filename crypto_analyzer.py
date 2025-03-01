import os
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
from tabulate import tabulate

class CryptoAnalyzer:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.base_dir, 'data')
        self.reports_dir = os.path.join(self.base_dir, 'reports')
        self.charts_dir = os.path.join(self.base_dir, 'analysis_charts')
        
        # Δημιουργία απαραίτητων φακέλων αν δεν υπάρχουν
        for directory in [self.data_dir, self.reports_dir, self.charts_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
    def load_data(self):
        """Φορτώνει τα δεδομένα από το αρχείο JSON."""
        try:
            data_file = os.path.join(self.data_dir, 'crypto_historical_data.json')
            if not os.path.exists(data_file):
                print(f"Σφάλμα φόρτωσης δεδομένων: Το αρχείο {data_file} δεν υπάρχει")
                return None
                
            with open(data_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Σφάλμα φόρτωσης δεδομένων: {e}")
            return None
            
    def get_available_coins(self):
        """Επιστρέφει λίστα με τα διαθέσιμα κρυπτονομίσματα."""
        data = self.load_data()
        if not data:
            return []
            
        coins = []
        # Παραλείπουμε το "last_updated"
        for coin_id, coin_data in data.items():
            if coin_id != "last_updated" and isinstance(coin_data, dict) and 'symbol' in coin_data:
                coins.append((coin_id, coin_data['symbol']))
        return coins
        
    def get_coin_data(self, coin_id):
        """Επιστρέφει τα δεδομένα για συγκεκριμένο κρυπτονόμισμα."""
        data = self.load_data()
        if not data or coin_id not in data:
            return None
            
        coin_data = data[coin_id]
        # Έλεγχος για τιμές και ημερομηνίες
        if 'prices' in coin_data and isinstance(coin_data['prices'], list) and len(coin_data['prices']) > 0:
            # Αν δεν υπάρχει ήδη το κλειδί dates, το δημιουργούμε από τα timestamps των τιμών
            if 'dates' not in coin_data:
                dates = [price[0] for price in coin_data['prices']]
                coin_data['dates'] = dates
                # Εξαγωγή μόνο των τιμών (δεύτερο στοιχείο κάθε εγγραφής)
                prices_only = [price[1] for price in coin_data['prices']]
                coin_data['prices'] = prices_only
                
            # Προσθέτουμε την τρέχουσα τιμή
            if not 'current_price' in coin_data and len(coin_data['prices']) > 0:
                coin_data['current_price'] = coin_data['prices'][-1]
            
            # Υπολογισμός ποσοστών μεταβολής
            prices = coin_data['prices']
            if len(prices) >= 2:  # Χρειαζόμαστε τουλάχιστον 2 τιμές για μεταβολή 24h
                coin_data['price_change_percentage_24h'] = ((prices[-1] - prices[-2]) / prices[-2]) * 100
                
            if len(prices) >= 8:  # Περίπου 7 ημέρες (εξαρτάται από το διάστημα των δεδομένων)
                coin_data['price_change_percentage_7d'] = ((prices[-1] - prices[-8]) / prices[-8]) * 100
                
            if len(prices) >= 31:  # Περίπου 30 ημέρες
                coin_data['price_change_percentage_30d'] = ((prices[-1] - prices[-31]) / prices[-31]) * 100
        
        return coin_data
    def calculate_simple_moving_average(self, prices, window=7):
        """Υπολογίζει τον απλό κινητό μέσο όρο."""
        if not prices or len(prices) < window:
            return None
        return pd.Series(prices).rolling(window=window).mean().tolist()
        
    def calculate_exponential_moving_average(self, prices, window=14):
        """Υπολογίζει τον εκθετικό κινητό μέσο όρο."""
        if not prices or len(prices) < window:
            return None
        return pd.Series(prices).ewm(span=window, adjust=False).mean().tolist()
        
    def calculate_rsi(self, prices, window=14):
        """Υπολογίζει τον δείκτη σχετικής ισχύος (RSI)."""
        if not prices or len(prices) < window+1:
            return None
            
        # Μετατροπή σε pandas Series για εύκολους υπολογισμούς
        prices_series = pd.Series(prices)
        
        # Υπολογισμός των διαφορών τιμών (deltas)
        deltas = prices_series.diff().dropna()
        
        # Διαχωρισμός θετικών και αρνητικών μεταβολών
        gain = deltas.where(deltas > 0, 0)
        loss = -deltas.where(deltas < 0, 0)
        
        # Υπολογισμός του average gain και average loss
        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()
        
        # Υπολογισμός του relative strength και RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.tolist()
        
    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Υπολογίζει τον δείκτη MACD."""
        if not prices or len(prices) < slow + signal:
            return None, None, None
            
        prices_series = pd.Series(prices)
        
        # Υπολογισμός EMAs
        ema_fast = prices_series.ewm(span=fast, adjust=False).mean()
        ema_slow = prices_series.ewm(span=slow, adjust=False).mean()
        
        # Υπολογισμός MACD line και signal line
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        
        # Υπολογισμός histogram
        histogram = macd_line - signal_line
        
        return macd_line.tolist(), signal_line.tolist(), histogram.tolist()
        
    def calculate_bollinger_bands(self, prices, window=20, num_std=2):
        """Υπολογίζει τις ζώνες Bollinger."""
        if not prices or len(prices) < window:
            return None, None, None
            
        prices_series = pd.Series(prices)
        
        # Υπολογισμός κεντρικής γραμμής (SMA)
        middle_band = prices_series.rolling(window=window).mean()
        
        # Υπολογισμός τυπικής απόκλισης
        std = prices_series.rolling(window=window).std()
        
        # Υπολογισμός άνω και κάτω ζωνών
        upper_band = middle_band + (std * num_std)
        lower_band = middle_band - (std * num_std)
        
        return upper_band.tolist(), middle_band.tolist(), lower_band.tolist()
        
    def calculate_volatility(self, prices, window=14):
        """Υπολογίζει τη μεταβλητότητα (volatility)."""
        if not prices or len(prices) < window:
            return None
            
        prices_series = pd.Series(prices)
        volatility = prices_series.pct_change().rolling(window=window).std() * 100
        
        return volatility.tolist()
    def generate_price_chart(self, coin_id, prices, dates, indicators=None):
        """Δημιουργεί γράφημα τιμών με δείκτες."""
        if not prices or not dates or len(prices) != len(dates):
            return None
            
        plt.figure(figsize=(12, 6))
        plt.plot(dates, prices, label='Τιμή', color='blue')
        
        # Προσθήκη δεικτών αν υπάρχουν
        if indicators and 'sma' in indicators and indicators['sma']:
            plt.plot(dates[-len(indicators['sma']):], indicators['sma'], label='SMA (7)', color='red')
            
        if indicators and 'ema' in indicators and indicators['ema']:
            plt.plot(dates[-len(indicators['ema']):], indicators['ema'], label='EMA (14)', color='green')
            
        plt.title(f'Ιστορικό Τιμών {coin_id.capitalize()}')
        plt.xlabel('Ημερομηνία')
        plt.ylabel('Τιμή (USD)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Αποθήκευση γραφήματος
        chart_filename = f"{coin_id}_price_chart.png"
        chart_path = os.path.join(self.charts_dir, chart_filename)
        plt.savefig(chart_path)
        plt.show()
        plt.close()
        
        return chart_filename
        
    def generate_indicators_chart(self, coin_id, prices, dates, indicators):
        """Δημιουργεί γράφημα με δείκτες τεχνικής ανάλυσης."""
        if not prices or not dates or len(prices) != len(dates):
            return None
            
        # Δημιουργία γραφήματος RSI
        if 'rsi' in indicators and indicators['rsi']:
            plt.figure(figsize=(12, 4))
            plt.plot(dates[-len(indicators['rsi']):], indicators['rsi'], label='RSI', color='purple')
            plt.axhline(y=70, color='r', linestyle='-', alpha=0.3)
            plt.axhline(y=30, color='g', linestyle='-', alpha=0.3)
            plt.title(f'Δείκτης RSI {coin_id.capitalize()}')
            plt.xlabel('Ημερομηνία')
            plt.ylabel('RSI')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Αποθήκευση γραφήματος RSI
            rsi_chart_filename = f"{coin_id}_rsi_chart.png"
            rsi_chart_path = os.path.join(self.charts_dir, rsi_chart_filename)
            plt.savefig(rsi_chart_path)
            plt.show()
            plt.close()
            
            return rsi_chart_filename
        
        return None
        
    def generate_bollinger_chart(self, coin_id, prices, dates, bollinger_bands):
        """Δημιουργεί γράφημα με ζώνες Bollinger."""
        if not prices or not dates or not bollinger_bands:
            return None
            
        upper, middle, lower = bollinger_bands
        
        if not upper or not middle or not lower:
            return None
            
        plt.figure(figsize=(12, 6))
        plt.plot(dates[-len(middle):], middle, label='SMA (20)', color='red')
        plt.plot(dates[-len(upper):], upper, label='Upper Band', color='green', alpha=0.7)
        plt.plot(dates[-len(lower):], lower, label='Lower Band', color='green', alpha=0.7)
        plt.plot(dates[-len(middle):], prices[-len(middle):], label='Τιμή', color='blue')
        plt.fill_between(dates[-len(upper):], upper, lower, color='green', alpha=0.1)
        plt.title(f'Ζώνες Bollinger {coin_id.capitalize()}')
        plt.xlabel('Ημερομηνία')
        plt.ylabel('Τιμή (USD)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Αποθήκευση γραφήματος
        bb_chart_filename = f"{coin_id}_bollinger_chart.png"
        bb_chart_path = os.path.join(self.charts_dir, bb_chart_filename)
        plt.savefig(bb_chart_path)
        plt.show()
        plt.close()
        
        return bb_chart_filename
    def calculate_trend(self, prices, short_window=7, long_window=30):
        """Ανάλυση τάσης με βάση τους κινητούς μέσους όρους."""
        if not prices or len(prices) < long_window:
            return "Αδυναμία υπολογισμού τάσης - ανεπαρκή δεδομένα"
            
        short_sma = self.calculate_simple_moving_average(prices, short_window)
        long_sma = self.calculate_simple_moving_average(prices, long_window)
        
        if not short_sma or not long_sma:
            return "Αδυναμία υπολογισμού τάσης - σφάλμα στον υπολογισμό"
            
        current_short = short_sma[-1]
        current_long = long_sma[-1]
        
        if current_short > current_long * 1.05:
            return "Ισχυρή ανοδική τάση"
        elif current_short > current_long:
            return "Ήπια ανοδική τάση"
        elif current_short < current_long * 0.95:
            return "Ισχυρή καθοδική τάση"
        elif current_short < current_long:
            return "Ήπια καθοδική τάση"
        else:
            return "Ουδέτερη τάση - πλευρική κίνηση"
            
    def interpret_rsi(self, rsi_values):
        """Ερμηνεία του δείκτη RSI."""
        if not rsi_values:
            return "Αδυναμία ερμηνείας RSI - ανεπαρκή δεδομένα", None
            
        current_rsi = rsi_values[-1]
        
        if current_rsi > 70:
            return "Υπεραγορασμένο - πιθανή διόρθωση", "bearish"
        elif current_rsi < 30:
            return "Υπερπουλημένο - πιθανή ανάκαμψη", "bullish"
        elif current_rsi > 60:
            return "Ελαφρώς υπεραγορασμένο", "neutral-bearish"
        elif current_rsi < 40:
            return "Ελαφρώς υπερπουλημένο", "neutral-bullish"
        else:
            return "Ουδέτερη κατάσταση", "neutral"
            
    def interpret_macd(self, macd_line, signal_line):
        """Ερμηνεία του δείκτη MACD."""
        if not macd_line or not signal_line:
            return "Αδυναμία ερμηνείας MACD - ανεπαρκή δεδομένα", None
            
        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        
        if current_macd > current_signal and current_macd > 0:
            return "Ισχυρό ανοδικό σήμα", "bullish"
        elif current_macd > current_signal:
            return "Ανοδικό σήμα", "neutral-bullish"
        elif current_macd < current_signal and current_macd < 0:
            return "Ισχυρό καθοδικό σήμα", "bearish"
        else:
            return "Καθοδικό σήμα", "neutral-bearish"
    def generate_summary(self, coin_data, trend, rsi_analysis, macd_analysis):
        """Δημιουργεί μια συνοπτική ανάλυση."""
        if not coin_data or 'current_price' not in coin_data or 'id' not in coin_data:
            return "Αδυναμία δημιουργίας περίληψης - ελλιπή δεδομένα"
            
        coin_id = coin_data['id']
        current_price = coin_data['current_price']
        
        # Αξιολόγηση συνολικής εικόνας
        signals = {
            "bullish": 0,
            "neutral-bullish": 0,
            "neutral": 0,
            "neutral-bearish": 0,
            "bearish": 0
        }
        
        # Προσθήκη σημάτων από τους δείκτες
        if "Ισχυρή ανοδική" in trend or "Ήπια ανοδική" in trend:
            signals["bullish"] += 1
        elif "Ισχυρή καθοδική" in trend or "Ήπια καθοδική" in trend:
            signals["bearish"] += 1
        else:
            signals["neutral"] += 1
            
        # Προσθήκη σήματος RSI
        if rsi_analysis[1]:  # Το δεύτερο στοιχείο είναι το σήμα
            signals[rsi_analysis[1]] += 1
            
        # Προσθήκη σήματος MACD
        if macd_analysis[1]:  # Το δεύτερο στοιχείο είναι το σήμα
            signals[macd_analysis[1]] += 1
            
        # Εύρεση του πιο συχνού σήματος
        max_signal = max(signals, key=signals.get)
        
        # Δημιουργία περίληψης
        summary = f"Συνολική εικόνα για το {coin_id.capitalize()}:\n\n"
        
        if max_signal == "bullish" or signals["bullish"] > 1:
            summary += "Η τεχνική ανάλυση δείχνει θετικές προοπτικές για το κρυπτονόμισμα. "
            summary += "Οι περισσότεροι δείκτες υποδεικνύουν ανοδική τάση. "
            summary += "Ωστόσο, η αγορά κρυπτονομισμάτων είναι εξαιρετικά ευμετάβλητη και "
            summary += "οι επενδυτές θα πρέπει να είναι προσεκτικοί."
        elif max_signal == "bearish" or signals["bearish"] > 1:
            summary += "Η τεχνική ανάλυση δείχνει αρνητικές ενδείξεις για το κρυπτονόμισμα. "
            summary += "Οι περισσότεροι δείκτες υποδεικνύουν καθοδική τάση. "
            summary += "Συστήνεται προσοχή και επαγρύπνηση για τυχόν διορθώσεις στην τιμή."
        else:
            summary += "Η τεχνική ανάλυση δείχνει μικτά σήματα για το κρυπτονόμισμα. "
            summary += "Οι δείκτες δεν δίνουν σαφή κατεύθυνση και η αγορά φαίνεται να "
            summary += "βρίσκεται σε φάση αναμονής. Προτείνεται παρακολούθηση των δεδομένων "
            summary += "και προσεκτικές κινήσεις."
            
        return summary
            
    def generate_analysis_report(self, coin_id):
        """Δημιουργεί αναλυτική αναφορά για το επιλεγμένο κρυπτονόμισμα."""
        try:
            coin_data = self.get_coin_data(coin_id)
            if not coin_data:
                return f"Σφάλμα: Δεν βρέθηκαν δεδομένα για το {coin_id}."
            
            # Έλεγχος αν υπάρχουν τα απαραίτητα δεδομένα
            if 'prices' not in coin_data or 'dates' not in coin_data:
                return f"Σφάλμα: Ελλιπή δεδομένα για το {coin_id}."
            
            # Εξαγωγή των δεδομένων
            prices = coin_data.get('prices', [])
            dates = coin_data.get('dates', [])
            current_price = coin_data.get('current_price', 0)
            
            # Έλεγχος αν τα arrays είναι κενά
            if not prices or not dates:
                return f"Σφάλμα: Κενά δεδομένα για το {coin_id}."
                
            # Έλεγχος αν τα δεδομένα είναι αρκετά για ανάλυση
            if len(prices) < 30:
                return f"Σφάλμα: Ανεπαρκή δεδομένα για το {coin_id}. Χρειάζονται τουλάχιστον 30 τιμές."
            # Υπολογισμός δεικτών
            sma_7 = self.calculate_simple_moving_average(prices, 7)
            ema_14 = self.calculate_exponential_moving_average(prices, 14)
            rsi_values = self.calculate_rsi(prices, 14)
            macd_line, signal_line, histogram = self.calculate_macd(prices)
            bollinger_bands = self.calculate_bollinger_bands(prices)
            volatility = self.calculate_volatility(prices)
            
            # Υπολογισμός τάσης και ερμηνείες
            trend_analysis = self.calculate_trend(prices)
            rsi_analysis = self.interpret_rsi(rsi_values)
            macd_analysis = self.interpret_macd(macd_line, signal_line)
            
            # Δημιουργία γραφημάτων
            indicators = {
                'sma': sma_7,
                'ema': ema_14,
                'rsi': rsi_values
            }
            
            price_chart = self.generate_price_chart(coin_id, prices, dates, indicators)
            indicators_chart = self.generate_indicators_chart(coin_id, prices, dates, indicators)
            bollinger_chart = self.generate_bollinger_chart(coin_id, prices, dates, bollinger_bands)
            
            # Δημιουργία περίληψης
            coin_data['id'] = coin_id
            summary = self.generate_summary(coin_data, trend_analysis, rsi_analysis, macd_analysis)
            
            # Υπολογισμός μεταβολής τιμής
            price_change_24h = coin_data.get('price_change_percentage_24h', 0)
            price_change_7d = coin_data.get('price_change_percentage_7d', 0)
            price_change_30d = coin_data.get('price_change_percentage_30d', 0)
            
            # Στατιστικά
            highest_price_30d = max(prices[-30:]) if len(prices) >= 30 else max(prices)
            lowest_price_30d = min(prices[-30:]) if len(prices) >= 30 else min(prices)
            avg_price_30d = sum(prices[-30:]) / len(prices[-30:]) if len(prices) >= 30 else sum(prices) / len(prices)
            
            # Δημιουργία αναφοράς σε Markdown
            from datetime import datetime
            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            # Αρχικοποίηση αναφοράς
            report = f"# Αναφορά Τεχνικής Ανάλυσης για {coin_id.capitalize()}\n\n"
            report += f"## Ημερομηνία ανάλυσης: {now}\n\n"
            # Προσθήκη συνδέσμων προς τα γραφήματα
            report += "## Γραφήματα\n\n"
            if price_chart:
                chart_path = os.path.abspath(os.path.join(self.charts_dir, price_chart))
                report += f"- [**Γράφημα Τιμής**](file://{chart_path})\n"
    
            if bollinger_chart:
                chart_path = os.path.abspath(os.path.join(self.charts_dir, bollinger_chart))
                report += f"- [**Γράφημα Bollinger Bands**](file://{chart_path})\n"
    
            if indicators_chart:
                chart_path = os.path.abspath(os.path.join(self.charts_dir, indicators_chart))
                report += f"- [**Γράφημα RSI**](file://{chart_path})\n"
    
            report += "\n"
           
            # Βασικά στοιχεία
            report += "## Βασικά Στοιχεία\n\n"
            report += f"- **Τρέχουσα τιμή**: ${current_price:.2f}\n"
            report += f"- **Μεταβολή 24h**: {price_change_24h:.2f}%\n"
            report += f"- **Μεταβολή 7d**: {price_change_7d:.2f}%\n"
            report += f"- **Μεταβολή 30d**: {price_change_30d:.2f}%\n\n"
            
            # Στατιστικά 30 ημερών
            report += "## Στατιστικά 30 ημερών\n\n"
            report += f"- **Υψηλότερη τιμή**: ${highest_price_30d:.2f}\n"
            report += f"- **Χαμηλότερη τιμή**: ${lowest_price_30d:.2f}\n"
            report += f"- **Μέση τιμή**: ${avg_price_30d:.2f}\n\n"
            
            # Τεχνικοί δείκτες
            report += "## Τεχνικοί Δείκτες\n\n"
            
            report += f"### Τάση\n\n"
            report += f"- **Κατεύθυνση τάσης**: {trend_analysis}\n\n"
            
            report += f"### Κινητοί Μέσοι Όροι\n\n"
            if sma_7 and len(sma_7) > 0:
                report += f"- **SMA (7)**: ${sma_7[-1]:.2f}\n"
            if ema_14 and len(ema_14) > 0:
                report += f"- **EMA (14)**: ${ema_14[-1]:.2f}\n\n"
            
            report += f"### RSI\n\n"
            if rsi_values and len(rsi_values) > 0:
                report += f"- **Τιμή RSI (14)**: {rsi_values[-1]:.2f}\n"
                report += f"- **Ερμηνεία**: {rsi_analysis[0]}\n\n"
            
            report += f"### MACD\n\n"
            if macd_line and signal_line and len(macd_line) > 0 and len(signal_line) > 0:
                report += f"- **MACD Line**: {macd_line[-1]:.6f}\n"
                report += f"- **Signal Line**: {signal_line[-1]:.6f}\n"
                report += f"- **Ερμηνεία**: {macd_analysis[0]}\n\n"
            
            report += f"### Bollinger Bands\n\n"
            if all(bollinger_bands) and all(band is not None for band in bollinger_bands):
                upper, middle, lower = bollinger_bands
                current_upper = upper[-1]
                current_middle = middle[-1]
                current_lower = lower[-1]
                
                report += f"- **Upper Band**: ${current_upper:.2f}\n"
                report += f"- **Middle Band (SMA 20)**: ${current_middle:.2f}\n"
                report += f"- **Lower Band**: ${current_lower:.2f}\n\n"
                
                # Απόσταση τιμής από τις ζώνες
                band_width = current_upper - current_lower
                if band_width > 0:
                    position = (current_price - current_lower) / band_width
                    report += f"- **Σχετική θέση**: {position*100:.2f}% (0% = Lower Band, 100% = Upper Band)\n\n"

            # Μεταβλητότητα
            if volatility:
                report += f"### Μεταβλητότητα\n\n"
                report += f"- **Τρέχουσα μεταβλητότητα (14d)**: {volatility[-1]:.2f}%\n"
                
                avg_volatility = sum(volatility[-30:]) / len(volatility[-30:]) if len(volatility) >= 30 else sum(volatility) / len(volatility)
                report += f"- **Μέση μεταβλητότητα (30d)**: {avg_volatility:.2f}%\n\n"
            
            # Περίληψη και συμπεράσματα
            report += "## Συνοπτική Ανάλυση\n\n"
            report += summary
            report += "\n\n"
            
            # Σημείωση αποποίησης ευθύνης
            report += "---\n\n"
            report += "*Σημείωση: Η παραπάνω ανάλυση παρέχεται μόνο για εκπαιδευτικούς σκοπούς και δεν αποτελεί χρηματοοικονομική συμβουλή.*\n\n"
            report += "*Οι επενδύσεις σε κρυπτονομίσματα ενέχουν υψηλό ρίσκο και οι παρελθοντικές αποδόσεις δεν εγγυώνται μελλοντικά αποτελέσματα.*"
            
            return report
            
        except Exception as e:
            return f"Σφάλμα: {str(e)}"