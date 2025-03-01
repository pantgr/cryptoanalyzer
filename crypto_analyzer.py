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
        """Επιστρέφει τα δεδομένα για συγκεκριμένο κρυπτονόμισμα με αυτόματη μετατροπή δομής."""
        data = self.load_data()
        if not data or coin_id not in data:
            return None
            
        coin_data = data[coin_id].copy()  # Αντιγραφή για να αποφύγουμε αλλαγές στο αρχικό αντικείμενο
        
        # 1. Προσθήκη του ID στα δεδομένα
        coin_data['id'] = coin_id
        
        # 2. Έλεγχος και μετατροπή δομής τιμών
        if 'prices' in coin_data and isinstance(coin_data['prices'], list) and len(coin_data['prices']) > 0:
            # Έλεγχος αν είναι μορφή [[timestamp, price], ...]
            if isinstance(coin_data['prices'][0], list) and len(coin_data['prices'][0]) >= 2:
                # Εξαγωγή ημερομηνιών και τιμών
                dates = [entry[0] for entry in coin_data['prices']]
                prices_only = [entry[1] for entry in coin_data['prices']]
                
                coin_data['dates'] = dates
                coin_data['prices'] = prices_only
                
                # 3. Προσθήκη τρέχουσας τιμής
                if prices_only:
                    coin_data['current_price'] = prices_only[-1]
                
                # 4. Υπολογισμός ποσοστών μεταβολής
                if len(prices_only) >= 2:
                    coin_data['price_change_percentage_24h'] = ((prices_only[-1] - prices_only[-2]) / prices_only[-2]) * 100
                    
                if len(prices_only) >= 8:
                    coin_data['price_change_percentage_7d'] = ((prices_only[-1] - prices_only[-8]) / prices_only[-8]) * 100
                    
                if len(prices_only) >= 31:
                    coin_data['price_change_percentage_30d'] = ((prices_only[-1] - prices_only[-31]) / prices_only[-31]) * 100
        
        # 5. Μετατροπή του total_volumes σε απλή λίστα τιμών
        if 'total_volumes' in coin_data and isinstance(coin_data['total_volumes'], list) and len(coin_data['total_volumes']) > 0:
            if isinstance(coin_data['total_volumes'][0], list) and len(coin_data['total_volumes'][0]) >= 2:
                coin_data['total_volumes'] = [entry[1] for entry in coin_data['total_volumes']]
        
        # 6. Μετατροπή market_caps αν χρειάζεται
        if 'market_caps' in coin_data and isinstance(coin_data['market_caps'], list) and len(coin_data['market_caps']) > 0:
            if isinstance(coin_data['market_caps'][0], list) and len(coin_data['market_caps'][0]) >= 2:
                coin_data['market_caps'] = [entry[1] for entry in coin_data['market_caps']]
        
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
        
        # Αποφυγή διαίρεσης με το μηδέν
        avg_loss = avg_loss.replace(0, np.finfo(float).eps)
        
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

    def calculate_stochastic(self, prices, window=14):
        """Υπολογίζει τον Στοχαστικό Ταλαντωτή."""
        if not prices or len(prices) < window:
            return None, None
    
        df = pd.DataFrame({'close': prices})
        # Επειδή δεν έχουμε high/low, θα χρησιμοποιήσουμε rolling max/min
        df['low'] = df['close'].rolling(window=window).min()
        df['high'] = df['close'].rolling(window=window).max()
    
        # %K (Fast Stochastic)
        k = 100 * ((df['close'] - df['low']) / (df['high'] - df['low']))
        # %D (Slow Stochastic) - 3-period SMA of %K
        d = k.rolling(window=3).mean()
    
        return k.tolist(), d.tolist()

    def calculate_mfi(self, prices, volumes, period=14):
        """Υπολογίζει τον δείκτη Money Flow Index."""
        if not prices or not volumes or len(prices) != len(volumes) or len(prices) < period+1:
            return None
        
        df = pd.DataFrame({'close': prices, 'volume': volumes})
        df['typical_price'] = df['close']  # Απλοποίηση, ιδανικά: (high + low + close)/3
        df['raw_money_flow'] = df['typical_price'] * df['volume']
    
        df['price_change'] = df['typical_price'].diff()
        df['positive_flow'] = np.where(df['price_change'] > 0, df['raw_money_flow'], 0)
        df['negative_flow'] = np.where(df['price_change'] < 0, df['raw_money_flow'], 0)
    
        df['positive_mf'] = df['positive_flow'].rolling(window=period).sum()
        df['negative_mf'] = df['negative_flow'].rolling(window=period).sum()
    
        # Αποφυγή διαίρεσης με το μηδέν
        df['money_flow_ratio'] = np.where(df['negative_mf'] != 0, df['positive_mf'] / df['negative_mf'], 100)
        df['mfi'] = 100 - (100 / (1 + df['money_flow_ratio']))
    
        return df['mfi'].tolist()

    def calculate_ichimoku(self, prices, conversion_period=9, base_period=26, span_b_period=52, lagging_span_period=26):
        """Υπολογίζει το Ichimoku Cloud."""
        if not prices or len(prices) < span_b_period:
            return None, None, None, None, None

        df = pd.DataFrame({'close': prices})
    
        # Conversion Line (Tenkan-sen)
        high_tenkan = df['close'].rolling(window=conversion_period).max()
        low_tenkan = df['close'].rolling(window=conversion_period).min()
        df['tenkan_sen'] = (high_tenkan + low_tenkan) / 2
    
        # Base Line (Kijun-sen)
        high_kijun = df['close'].rolling(window=base_period).max()
        low_kijun = df['close'].rolling(window=base_period).min()
        df['kijun_sen'] = (high_kijun + low_kijun) / 2
    
        # Leading Span A (Senkou Span A)
        df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(base_period)
    
        # Leading Span B (Senkou Span B)
        high_senkou = df['close'].rolling(window=span_b_period).max()
        low_senkou = df['close'].rolling(window=span_b_period).min()
        df['senkou_span_b'] = ((high_senkou + low_senkou) / 2).shift(base_period)
    
        # Lagging Span (Chikou Span)
        df['chikou_span'] = df['close'].shift(-lagging_span_period)
    
        return (df['tenkan_sen'].tolist(), df['kijun_sen'].tolist(), 
                df['senkou_span_a'].tolist(), df['senkou_span_b'].tolist(), 
                df['chikou_span'].tolist())

    def calculate_fibonacci_levels(self, prices, period=30):
        """Υπολογίζει επίπεδα Fibonacci Retracement για το πιο πρόσφατο διάστημα."""
        if not prices or len(prices) < period:
            return None
    
        # Παίρνουμε την πιο πρόσφατη περίοδο
        recent_prices = prices[-period:]
        max_price = max(recent_prices)
        min_price = min(recent_prices)
        diff = max_price - min_price
    
        # Τυπικά επίπεδα Fibonacci: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
        levels = {
            '0': min_price,
            '23.6': min_price + 0.236 * diff,
            '38.2': min_price + 0.382 * diff,
            '50': min_price + 0.5 * diff,
            '61.8': min_price + 0.618 * diff,
            '78.6': min_price + 0.786 * diff,
            '100': max_price
        }
    
        return levels

    def calculate_parabolic_sar(self, prices, af_start=0.02, af_step=0.02, af_max=0.2):
        """Υπολογίζει τον δείκτη Parabolic SAR."""
        if not prices or len(prices) < 10:  # Χρειάζεται αρκετά δεδομένα
            return None

        # Απλοποιημένος υπολογισμός (προσέγγιση)
        # Σε πραγματική υλοποίηση χρειάζονται high/low τιμές
        sar = [prices[0]]
        trend = 1  # 1 = uptrend, -1 = downtrend
        ep = prices[0]  # extreme point
        af = af_start  # acceleration factor
    
        for i in range(1, len(prices)):
            prev_sar = sar[-1]
        
            # Υπολογισμός νέου SAR
            current_sar = prev_sar + af * (ep - prev_sar)

            # Έλεγχος τάσης και προσαρμογή
            if trend == 1:  # Ανοδική τάση
                if prices[i] < current_sar:
                    # Αλλαγή σε καθοδική τάση
                    trend = -1
                    current_sar = max(prices[max(0, i-5):i+1])
                    ep = min(prices[max(0, i-5):i+1])
                    af = af_start
                else:
                    # Συνέχιση ανοδικής τάσης
                    if prices[i] > ep:
                        ep = prices[i]
                        af = min(af + af_step, af_max)
            else:  # Καθοδική τάση
                if prices[i] > current_sar:
                    # Αλλαγή σε ανοδική τάση
                    trend = 1
                    current_sar = min(prices[max(0, i-5):i+1])
                    ep = max(prices[max(0, i-5):i+1])
                    af = af_start
                else:
                    # Συνέχιση καθοδικής τάσης
                    if prices[i] < ep:
                        ep = prices[i]
                        af = min(af + af_step, af_max)

            sar.append(current_sar)

        return sar
    
    def generate_price_chart(self, coin_id, prices, dates, indicators=None):
        """Δημιουργεί γράφημα τιμών με δείκτες."""
        if not prices or not dates or len(prices) != len(dates):
            return None
            
        plt.figure(figsize=(12, 6))
        
        # Μετατροπή timestamps σε ημερομηνίες
        date_objects = [datetime.fromtimestamp(d/1000) for d in dates]
        
        plt.plot(date_objects, prices, label='Τιμή', color='blue')
        
        # Προσθήκη δεικτών αν υπάρχουν
        if indicators and 'sma' in indicators and indicators['sma']:
            plt.plot(date_objects[-len(indicators['sma']):], indicators['sma'], label='SMA (7)', color='red')
            
        if indicators and 'ema' in indicators and indicators['ema']:
            plt.plot(date_objects[-len(indicators['ema']):], indicators['ema'], label='EMA (14)', color='green')
            
        plt.title(f'Ιστορικό Τιμών {coin_id.capitalize()}')
        plt.xlabel('Ημερομηνία')
        plt.ylabel('Τιμή (USD)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Αποθήκευση γραφήματος
        import io
        import base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
    
        return f"data:image/png;base64,{img_str}"
        
    def generate_indicators_chart(self, coin_id, prices, dates, indicators):
        """Δημιουργεί γράφημα με δείκτες τεχνικής ανάλυσης."""
        if not prices or not dates or len(prices) != len(dates):
            return None
            
        # Δημιουργία γραφήματος RSI
        if 'rsi' in indicators and indicators['rsi']:
            plt.figure(figsize=(12, 4))
            
            # Μετατροπή timestamps σε ημερομηνίες
            date_objects = [datetime.fromtimestamp(d/1000) for d in dates]
            
            plt.plot(date_objects[-len(indicators['rsi']):], indicators['rsi'], label='RSI', color='purple')
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
            import io
            import base64
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            img_str = base64.b64encode(buf.read()).decode('utf-8')
            plt.close()
            return f"data:image/png;base64,{img_str}"
        
        return None
        
    def generate_bollinger_chart(self, coin_id, prices, dates, bollinger_bands):
        """Δημιουργεί γράφημα με ζώνες Bollinger."""
        if not prices or not dates or not bollinger_bands:
            return None
            
        upper, middle, lower = bollinger_bands
        
        if not upper or not middle or not lower:
            return None
            
        plt.figure(figsize=(12, 6))
        
        # Μετατροπή timestamps σε ημερομηνίες
        date_objects = [datetime.fromtimestamp(d/1000) for d in dates]
        
        plt.plot(date_objects[-len(middle):], middle, label='SMA (20)', color='red')
        plt.plot(date_objects[-len(upper):], upper, label='Upper Band', color='green', alpha=0.7)
        plt.plot(date_objects[-len(lower):], lower, label='Lower Band', color='green', alpha=0.7)
        plt.plot(date_objects[-len(middle):], prices[-len(middle):], label='Τιμή', color='blue')
        plt.fill_between(date_objects[-len(upper):], upper, lower, color='green', alpha=0.1)
        plt.title(f'Ζώνες Bollinger {coin_id.capitalize()}')
        plt.xlabel('Ημερομηνία')
        plt.ylabel('Τιμή (USD)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Αποθήκευση γραφήματος
        import io
        import base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        return f"data:image/png;base64,{img_str}"

    def generate_stochastic_chart(self, coin_id, dates, stochastic_k, stochastic_d):
        """Δημιουργεί γράφημα Στοχαστικού Ταλαντωτή."""
        if not dates or not stochastic_k or not stochastic_d:
            return None
        
        plt.figure(figsize=(12, 4))
        
        # Μετατροπή timestamps σε ημερομηνίες
        date_objects = [datetime.fromtimestamp(d/1000) for d in dates]
        
        plt.plot(date_objects[-len(stochastic_k):], stochastic_k, label='%K', color='blue')
        plt.plot(date_objects[-len(stochastic_d):], stochastic_d, label='%D', color='red')
        plt.axhline(y=80, color='r', linestyle='--', alpha=0.3)
        plt.axhline(y=20, color='g', linestyle='--', alpha=0.3)
        plt.title(f'Στοχαστικός Ταλαντωτής {coin_id.capitalize()}')
        plt.xlabel('Ημερομηνία')
        plt.ylabel('Τιμή')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
    
        # Αποθήκευση γραφήματος
        import io
        import base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
    
        return f"data:image/png;base64,{img_str}"

    def generate_mfi_chart(self, coin_id, dates, mfi_values):
        """Δημιουργεί γράφημα Money Flow Index."""
        if not dates or not mfi_values:
            return None
        
        plt.figure(figsize=(12, 4))
        
        # Μετατροπή timestamps σε ημερομηνίες
        date_objects = [datetime.fromtimestamp(d/1000) for d in dates]
        
        plt.plot(date_objects[-len(mfi_values):], mfi_values, label='MFI', color='purple')
        plt.axhline(y=80, color='r', linestyle='--', alpha=0.3)
        plt.axhline(y=20, color='g', linestyle='--', alpha=0.3)
        plt.title(f'Money Flow Index {coin_id.capitalize()}')
        plt.xlabel('Ημερομηνία')
        plt.ylabel('MFI')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
    
        # Αποθήκευση γραφήματος
        import io
        import base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
    
        return f"data:image/png;base64,{img_str}"

    def generate_ichimoku_chart(self, coin_id, prices, dates, ichimoku_data):
        """Δημιουργεί γράφημα Ichimoku Cloud."""
        if not dates or not prices or not ichimoku_data:
            return None

        tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span = ichimoku_data
    
        plt.figure(figsize=(12, 6))
    
        # Μετατροπή timestamps σε ημερομηνίες
        date_objects = [datetime.fromtimestamp(d/1000) for d in dates]
    
        # Προσθέστε την τιμή
        plt.plot(date_objects[-len(prices):], prices, label='Τιμή', color='black')
    
        # Προσθέστε tenkan-sen και kijun-sen
        if tenkan_sen:
            plt.plot(date_objects[-len(tenkan_sen):], tenkan_sen, label='Tenkan-sen', color='red')
    
        if kijun_sen:
            plt.plot(date_objects[-len(kijun_sen):], kijun_sen, label='Kijun-sen', color='blue')
    
        # Προσθέστε το cloud (απλοποιημένο λόγω χρονικής μετατόπισης)
        valid_spans = (len(senkou_span_a) > 26 and len(senkou_span_b) > 26)
        if valid_spans:
            # Χρησιμοποιούμε τα τελευταία σημεία για απλότητα
            span_a = senkou_span_a[-len(dates):]
            span_b = senkou_span_b[-len(dates):]
        
            # Αποτρέποντας σφάλματα για τα NaN
            valid_points = min(len(span_a), len(span_b), len(date_objects))
            
            for i in range(valid_points - 1):
                if pd.notna(span_a[i]) and pd.notna(span_b[i]) and pd.notna(span_a[i+1]) and pd.notna(span_b[i+1]):
                    # Πράσινο όταν Span A > Span B (ανοδικό)
                    if span_a[i] > span_b[i]:
                        plt.fill_between([date_objects[i], date_objects[i+1]], 
                                        [span_a[i], span_a[i+1]], 
                                        [span_b[i], span_b[i+1]], 
                                        color='green', alpha=0.2)
                    # Κόκκινο όταν Span A < Span B (καθοδικό)
                    else:
                        plt.fill_between([date_objects[i], date_objects[i+1]], 
                                        [span_a[i], span_a[i+1]], 
                                        [span_b[i], span_b[i+1]], 
                                        color='red', alpha=0.2)
    
        plt.title(f'Ichimoku Cloud {coin_id.capitalize()}')
        plt.xlabel('Ημερομηνία')
        plt.ylabel('Τιμή (USD)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
    
        # Αποθήκευση γραφήματος
        import io
        import base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
    
        return f"data:image/png;base64,{img_str}"

    def generate_fibonacci_chart(self, coin_id, prices, dates, fib_levels, period=30):
        """Δημιουργεί γράφημα επιπέδων Fibonacci."""
        if not dates or not prices or not fib_levels:
            return None
    
        plt.figure(figsize=(12, 6))
    
        # Πρόσφατα δεδομένα για τα επίπεδα Fibonacci
        recent_dates = dates[-period:] if len(dates) > period else dates
        recent_prices = prices[-period:] if len(prices) > period else prices
    
        # Μετατροπή timestamps σε ημερομηνίες
        date_objects = [datetime.fromtimestamp(d/1000) for d in recent_dates]
    
        # Σχεδιασμός του γραφήματος τιμών
        plt.plot(date_objects, recent_prices, label='Τιμή', color='blue')
    
        # Προσθήκη οριζόντιων γραμμών για κάθε επίπεδο Fibonacci
        colors = {
            '0': 'green', 
            '23.6': 'purple', 
            '38.2': 'blue', 
            '50': 'black', 
            '61.8': 'blue', 
            '78.6': 'purple', 
            '100': 'red'
        }
    
        for level, value in fib_levels.items():
            plt.axhline(y=value, color=colors.get(level, 'gray'), linestyle='--', alpha=0.6)
            plt.text(date_objects[0], value, f' {level}%: ${value:.2f}', fontsize=9)
    
        plt.title(f'Επίπεδα Fibonacci {coin_id.capitalize()}')
        plt.xlabel('Ημερομηνία')
        plt.ylabel('Τιμή (USD)')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
    
        # Αποθήκευση γραφήματος
        import io
        import base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
    
        return f"data:image/png;base64,{img_str}"
        
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
            
    def interpret_stochastic(self, k_values, d_values):
        """Ερμηνεία του Στοχαστικού Ταλαντωτή."""
        if not k_values or not d_values or len(k_values) < 2 or len(d_values) < 2:
            return "Αδυναμία ερμηνείας Στοχαστικού Ταλαντωτή - ανεπαρκή δεδομένα", None
    
        current_k = k_values[-1]
        current_d = d_values[-1]
        prev_k = k_values[-2]
        prev_d = d_values[-2]
    
        # Έλεγχος υπεραγορασμένων/υπερπουλημένων συνθηκών
        if current_k > 80 and current_d > 80:
            state = "Υπεραγορασμένο - πιθανή διόρθωση"
            signal = "bearish"
        elif current_k < 20 and current_d < 20:
            state = "Υπερπουλημένο - πιθανή ανάκαμψη"
            signal = "bullish"
        else:
            state = "Ουδέτερη ζώνη"
            signal = "neutral"
    
        # Έλεγχος διασταύρωσης (crossover)
        if prev_k < prev_d and current_k > current_d:
            state += " - Ανοδική διασταύρωση"
            if signal == "neutral":
                signal = "neutral-bullish"
            else:
                signal = "bullish"
        elif prev_k > prev_d and current_k < current_d:
            state += " - Καθοδική διασταύρωση"
            if signal == "neutral":
                signal = "neutral-bearish"
            else:
                signal = "bearish"
    
        return state, signal
        
    def interpret_mfi(self, mfi_values):
        """Ερμηνεία του Money Flow Index."""
        if not mfi_values or len(mfi_values) < 1:
            return "Αδυναμία ερμηνείας MFI - ανεπαρκή δεδομένα", None
    
        current_mfi = mfi_values[-1]
    
        if current_mfi > 80:
            return "Υπεραγορασμένο - πιθανή διόρθωση", "bearish"
        elif current_mfi < 20:
            return "Υπερπουλημένο - πιθανή ανάκαμψη", "bullish"
        elif current_mfi > 60:
            return "Ελαφρώς υπεραγορασμένο", "neutral-bearish"
        elif current_mfi < 40:
            return "Ελαφρώς υπερπουλημένο", "neutral-bullish"
        else:
            return "Ουδέτερη κατάσταση", "neutral"
            
    def interpret_ichimoku(self, prices, tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span):
        """Ερμηνεία του Ichimoku Cloud."""
        if not prices or not tenkan_sen or not kijun_sen or len(prices) < 26:
            return "Αδυναμία ερμηνείας Ichimoku Cloud - ανεπαρκή δεδομένα", None
    
        current_price = prices[-1]
        current_tenkan = tenkan_sen[-1] if tenkan_sen[-1] is not None else 0
        current_kijun = kijun_sen[-1] if kijun_sen[-1] is not None else 0
    
        # Έλεγχος αν έχουμε αρκετά δεδομένα για τα προαναφερθέντα spans
        cloud_bullish = False
        above_cloud = False
    
        valid_spans = (len(senkou_span_a) > 26 and len(senkou_span_b) > 26)
    
        if valid_spans:
            # Το cloud υπάρχει 26 περιόδους μπροστά
            current_senkou_a = senkou_span_a[-26]
            current_senkou_b = senkou_span_b[-26]
        
            cloud_bullish = current_senkou_a > current_senkou_b
            above_cloud = current_price > max(current_senkou_a, current_senkou_b)
    
        # Κύρια σήματα
        signal = "neutral"
        analysis = ""
    
        # Έλεγχος διασταύρωσης
        if current_tenkan > current_kijun:
            analysis += "Ανοδική διασταύρωση Tenkan-sen και Kijun-sen (σήμα ΑΓΟΡΑΣ). "
            signal = "bullish"
        elif current_tenkan < current_kijun:
            analysis += "Καθοδική διασταύρωση Tenkan-sen και Kijun-sen (σήμα ΠΩΛΗΣΗΣ). "
            signal = "bearish"
    
        # Έλεγχος θέσης τιμής σε σχέση με το cloud
        if valid_spans:
            if above_cloud:
                analysis += "Η τιμή είναι πάνω από το cloud (ΑΝΟΔΙΚΗ τάση). "
                if signal == "neutral":
                    signal = "bullish"
            elif current_price < min(current_senkou_a, current_senkou_b):
                analysis += "Η τιμή είναι κάτω από το cloud (ΚΑΘΟΔΙΚΗ τάση). "
                if signal == "neutral":
                    signal = "bearish"
            else:
                analysis += "Η τιμή είναι μέσα στο cloud (ΑΒΕΒΑΙΟΤΗΤΑ). "
    
            # Χρώμα του cloud
            if cloud_bullish:
                analysis += "Το cloud είναι πράσινο (ανοδικό). "
            else:
                analysis += "Το cloud είναι κόκκινο (καθοδικό). "
    
        # Συνολική αξιολόγηση
        if signal == "bullish":
            return "Ισχυρό ανοδικό σήμα: " + analysis, signal
        elif signal == "bearish":
            return "Ισχυρό καθοδικό σήμα: " + analysis, signal
        else:
            return "Ουδέτερο σήμα: " + analysis, signal

    def interpret_fibonacci(self, price, fib_levels):
        """Ερμηνεία των επιπέδων Fibonacci σε σχέση με την τρέχουσα τιμή."""
        if not price or not fib_levels:
            return "Αδυναμία ερμηνείας επιπέδων Fibonacci - ανεπαρκή δεδομένα", None
    
        # Εύρεση του επιπέδου που είναι πιο κοντά στην τρέχουσα τιμή από κάτω και από πάνω
        below_level = None
        above_level = None
    
        for level, value in sorted(fib_levels.items(), key=lambda x: float(x[1])):
            if value <= price:
                below_level = (level, value)
            else:
                above_level = (level, value)
                break
    
        # Αν η τιμή είναι στο χαμηλότερο επίπεδο
        if below_level and below_level[0] == '0':
            analysis = f"Η τιμή βρίσκεται κοντά στο χαμηλότερο επίπεδο Fibonacci ({below_level[0]}%). "
            analysis += "Πιθανή στήριξη και ανάκαμψη."
            return analysis, "bullish"
    
        # Αν η τιμή είναι στο υψηλότερο επίπεδο
        if not above_level or (above_level and above_level[0] == '100'):
            analysis = "Η τιμή βρίσκεται κοντά στο υψηλότερο επίπεδο Fibonacci (100%). "
            analysis += "Πιθανή αντίσταση και διόρθωση."
            return analysis, "bearish"
    
        # Αν η τιμή είναι μεταξύ επιπέδων
        if below_level and above_level:
            # Υπολογισμός απόστασης από τα επίπεδα (ποσοστό)
            distance_below = price - below_level[1]
            distance_above = above_level[1] - price
        
            if distance_below < distance_above:
                analysis = f"Η τιμή βρίσκεται κοντά στο επίπεδο Fibonacci {below_level[0]}%. "
                analysis += "Πιθανή στήριξη σε αυτό το επίπεδο."
                return analysis, "neutral-bullish"
            else:
                analysis = f"Η τιμή προσεγγίζει το επίπεδο Fibonacci {above_level[0]}%. "
                analysis += "Αυτό το επίπεδο μπορεί να λειτουργήσει ως αντίσταση."
                return analysis, "neutral-bearish"
    
        return "Δεν ήταν δυνατή η ερμηνεία σε σχέση με τα επίπεδα Fibonacci.", "neutral"
        
    def interpret_parabolic_sar(self, prices, sar_values):
        """Ερμηνεία του δείκτη Parabolic SAR."""
        if not prices or not sar_values or len(prices) < 2 or len(sar_values) < 2:
            return "Αδυναμία ερμηνείας Parabolic SAR - ανεπαρκή δεδομένα", None
    
        current_price = prices[-1]
        current_sar = sar_values[-1]
        prev_price = prices[-2]
        prev_sar = sar_values[-2]
    
        # Έλεγχος αλλαγής τάσης
        trend_change = (prev_price > prev_sar and current_price < current_sar) or \
                    (prev_price < prev_sar and current_price > current_sar)
        
        if current_price > current_sar:
            if trend_change:
                return "Αλλαγή σε ανοδική τάση - σήμα αγοράς", "bullish"
            else:
                return "Συνέχιση ανοδικής τάσης", "neutral-bullish"
        else:  # current_price < current_sar
            if trend_change:
                return "Αλλαγή σε καθοδική τάση - σήμα πώλησης", "bearish"
            else:
                return "Συνέχιση καθοδικής τάσης", "neutral-bearish"
                
    def generate_summary(self, coin_data, trend, rsi_analysis, macd_analysis):
        """Δημιουργεί μια συνοπτική ανάλυση."""
        if not coin_data:
            return "Αδυναμία δημιουργίας περίληψης - ελλιπή δεδομένα"
        
        coin_id = coin_data.get('id', 'κρυπτονόμισμα')
        current_price = coin_data.get('current_price', 0)
        
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
        if rsi_analysis and rsi_analysis[1]:  # Το δεύτερο στοιχείο είναι το σήμα
            signals[rsi_analysis[1]] += 1
            
        # Προσθήκη σήματος MACD
        if macd_analysis and macd_analysis[1]:  # Το δεύτερο στοιχείο είναι το σήμα
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
            
            # ===== ΠΡΟΣΘΗΚΗ ΤΩΝ ΝΕΩΝ ΔΕΙΚΤΩΝ =====
            # Υπολογισμός Stochastic Oscillator
            try:
                stochastic_k, stochastic_d = self.calculate_stochastic(prices)
                stochastic_analysis = self.interpret_stochastic(stochastic_k, stochastic_d) if stochastic_k and stochastic_d else ("Δεν υπάρχουν επαρκή δεδομένα", None)
                stochastic_chart = self.generate_stochastic_chart(coin_id, dates, stochastic_k, stochastic_d) if stochastic_k and stochastic_d else None
            except Exception as e:
                print(f"Σφάλμα στον υπολογισμό Stochastic: {e}")
                stochastic_k, stochastic_d, stochastic_analysis, stochastic_chart = None, None, ("Σφάλμα υπολογισμού", None), None

            # Υπολογισμός MFI
            try:
                volumes = coin_data.get('total_volumes', [])
                if not volumes or len(volumes) != len(prices):
                    volumes = [1] * len(prices)  # Fallback σε μονάδες αν δεν υπάρχουν πραγματικά δεδομένα
                
                mfi_values = self.calculate_mfi(prices, volumes)
                mfi_analysis = self.interpret_mfi(mfi_values) if mfi_values else ("Δεν υπάρχουν επαρκή δεδομένα για MFI", None)
                mfi_chart = self.generate_mfi_chart(coin_id, dates, mfi_values) if mfi_values else None
            except Exception as e:
                print(f"Σφάλμα στον υπολογισμό MFI: {e}")
                mfi_values, mfi_analysis, mfi_chart = None, ("Σφάλμα στον υπολογισμό MFI", None), None

            # Υπολογισμός Ichimoku Cloud
            try:
                ichimoku_data = self.calculate_ichimoku(prices)
                if ichimoku_data and None not in ichimoku_data[:2]:  # Βεβαιωθείτε ότι τουλάχιστον τα πρώτα δύο στοιχεία δεν είναι None
                    ichimoku_analysis = self.interpret_ichimoku(prices, *ichimoku_data)
                    ichimoku_chart = self.generate_ichimoku_chart(coin_id, prices, dates, ichimoku_data)
                else:
                    ichimoku_analysis = ("Δεν υπάρχουν επαρκή δεδομένα για Ichimoku Cloud", None)
                    ichimoku_chart = None
            except Exception as e:
                print(f"Σφάλμα στον υπολογισμό Ichimoku: {e}")
                ichimoku_data, ichimoku_analysis, ichimoku_chart = None, ("Σφάλμα στον υπολογισμό Ichimoku Cloud", None), None

            # Υπολογισμός Fibonacci Levels
            try:
                fib_levels = self.calculate_fibonacci_levels(prices)
                fib_analysis = self.interpret_fibonacci(current_price, fib_levels) if fib_levels else ("Δεν υπάρχουν επαρκή δεδομένα", None)
                fib_chart = self.generate_fibonacci_chart(coin_id, prices, dates, fib_levels) if fib_levels else None
            except Exception as e:
                print(f"Σφάλμα στον υπολογισμό Fibonacci: {e}")
                fib_levels, fib_analysis, fib_chart = None, ("Σφάλμα υπολογισμού", None), None
            # Υπολογισμός επιπλέον στατιστικών
            max_price = max(prices[-30:]) if len(prices) >= 30 else max(prices)
            min_price = min(prices[-30:]) if len(prices) >= 30 else min(prices)
            avg_price = sum(prices[-30:]) / len(prices[-30:]) if len(prices) >= 30 else sum(prices) / len(prices)
            
            # Ανάλυση τάσης
            trend = self.calculate_trend(prices)
            
            # Ερμηνεία δεικτών
            rsi_analysis = self.interpret_rsi(rsi_values)
            macd_analysis = self.interpret_macd(macd_line, signal_line)
            
            # Δημιουργία γραφημάτων
            price_chart = self.generate_price_chart(coin_id, prices, dates, {'sma': sma_7, 'ema': ema_14})
            bollinger_chart = self.generate_bollinger_chart(coin_id, prices, dates, bollinger_bands)
            indicators_chart = self.generate_indicators_chart(coin_id, prices, dates, {'rsi': rsi_values})
            
            # Συνολική περίληψη
            summary = self.generate_summary(coin_data, trend, rsi_analysis, macd_analysis)
            
            # Δημιουργία αναφοράς σε μορφή markdown
            # Μετατροπή ημερομηνίας σε αναγνώσιμη μορφή
            if 'last_updated' in coin_data:
                last_updated = coin_data['last_updated'] / 1000  # Αν είναι σε milliseconds
                last_updated_str = datetime.fromtimestamp(last_updated).strftime('%Y-%m-%d %H:%M')
            else:
                last_updated_str = datetime.now().strftime('%Y-%m-%d %H:%M')
                
            # Δημιουργία επικεφαλίδας αναφοράς
            report = f"# Ανάλυση Κρυπτονομίσματος: {coin_id.capitalize()}\n\n"
            report += f"Ημερομηνία ανάλυσης: {last_updated_str}\n\n"
            
            report += f"## Περίληψη\n\n{summary}\n\n"
            
            # Βασικές πληροφορίες
            report += f"## Τρέχουσες Τιμές\n\n"
            report += f"- **Τρέχουσα τιμή**: ${current_price:.2f}\n"
            if 'price_change_percentage_24h' in coin_data:
                report += f"- **Μεταβολή 24h**: {coin_data['price_change_percentage_24h']:.2f}%\n"
            if 'price_change_percentage_7d' in coin_data:
                report += f"- **Μεταβολή 7d**: {coin_data['price_change_percentage_7d']:.2f}%\n"
            if 'price_change_percentage_30d' in coin_data:
                report += f"- **Μεταβολή 30d**: {coin_data['price_change_percentage_30d']:.2f}%\n"
                
            report += f"- **Υψηλό 30 ημερών**: ${max_price:.2f}\n"
            report += f"- **Χαμηλό 30 ημερών**: ${min_price:.2f}\n"
            report += f"- **Μέση τιμή 30 ημερών**: ${avg_price:.2f}\n\n"
            
            # Τεχνική ανάλυση - Τάση
            report += f"## Τεχνική Ανάλυση\n\n"
            report += f"### Τάση\n\n"
            report += f"- **Τάση**: {trend}\n"
            report += f"- **SMA (7)**: ${sma_7[-1]:.2f}\n"
            report += f"- **EMA (14)**: ${ema_14[-1]:.2f}\n\n"
            
            # RSI
            report += f"### RSI (Δείκτης Σχετικής Ισχύος)\n\n"
            if rsi_values and len(rsi_values) > 0:
                report += f"- **RSI (14)**: {rsi_values[-1]:.2f}\n"
                report += f"- **Ερμηνεία RSI**: {rsi_analysis[0]}\n\n"
            
            # MACD
            report += f"### MACD (Moving Average Convergence Divergence)\n\n"
            if macd_line and signal_line and len(macd_line) > 0 and len(signal_line) > 0:
                report += f"- **MACD Line**: {macd_line[-1]:.4f}\n"
                report += f"- **Signal Line**: {signal_line[-1]:.4f}\n"
                report += f"- **Ερμηνεία MACD**: {macd_analysis[0]}\n\n"
            # Bollinger Bands
            report += f"### Bollinger Bands\n\n"
            if bollinger_bands and all(bollinger_bands):
                upper, middle, lower = bollinger_bands
                report += f"- **Άνω ζώνη**: ${upper[-1]:.2f}\n"
                report += f"- **Μέση ζώνη (SMA 20)**: ${middle[-1]:.2f}\n"
                report += f"- **Κάτω ζώνη**: ${lower[-1]:.2f}\n\n"
            
            # Μεταβλητότητα
            report += f"### Μεταβλητότητα\n\n"
            if volatility and len(volatility) > 0:
                avg_volatility = sum(volatility[-30:]) / len(volatility[-30:]) if len(volatility) >= 30 else sum(volatility) / len(volatility)
                report += f"- **Τρέχουσα μεταβλητότητα**: {volatility[-1]:.2f}%\n"
                report += f"- **Μέση μεταβλητότητα (30d)**: {avg_volatility:.2f}%\n\n"
            
            # ===== ΠΡΟΣΘΗΚΗ ΤΩΝ ΝΕΩΝ ΔΕΙΚΤΩΝ ΣΤΗΝ ΑΝΑΦΟΡΑ =====
            # Προσθήκη Stochastic Oscillator στην αναφορά
            report += f"### Στοχαστικός Ταλαντωτής\n\n"
            if stochastic_k and stochastic_d and len(stochastic_k) > 0 and len(stochastic_d) > 0:
                report += f"- **%K (Fast)**: {stochastic_k[-1]:.2f}\n"
                report += f"- **%D (Slow)**: {stochastic_d[-1]:.2f}\n"
                report += f"- **Ερμηνεία**: {stochastic_analysis[0]}\n\n"
            else:
                report += "- Δεν υπάρχουν επαρκή δεδομένα για ανάλυση\n\n"

            # Προσθήκη MFI στην αναφορά
            report += f"### Money Flow Index\n\n"
            if mfi_values and len(mfi_values) > 0:
                report += f"- **MFI (14)**: {mfi_values[-1]:.2f}\n"
                report += f"- **Ερμηνεία**: {mfi_analysis[0]}\n\n"
            else:
                report += "- Δεν υπάρχουν επαρκή δεδομένα για ανάλυση\n\n"

            # Προσθήκη Ichimoku Cloud στην αναφορά
            report += f"### Ichimoku Cloud\n\n"
            if ichimoku_data and all(ichimoku_data[:2]):
                report += f"- **Ερμηνεία**: {ichimoku_analysis[0]}\n\n"
            else:
                report += "- Δεν υπάρχουν επαρκή δεδομένα για ανάλυση\n\n"

            # Προσθήκη Fibonacci Levels στην αναφορά
            report += f"### Επίπεδα Fibonacci\n\n"
            if fib_levels:
                for level, value in fib_levels.items():
                    report += f"- **Επίπεδο {level}%**: ${value:.2f}\n"
                report += f"- **Ερμηνεία**: {fib_analysis[0]}\n\n"
            else:
                report += "- Δεν υπάρχουν επαρκή δεδομένα για ανάλυση\n\n"
            
            # Γραφήματα
            report += f"## Γραφήματα\n\n"
            if price_chart:
                report += f"![Τιμή και Κινητοί Μέσοι]({price_chart})\n\n"
                
            if bollinger_chart:
                report += f"![Bollinger Bands]({bollinger_chart})\n\n"
                
            if indicators_chart:
                report += f"![RSI]({indicators_chart})\n\n"

            # ===== ΠΡΟΣΘΗΚΗ ΓΡΑΦΗΜΑΤΩΝ ΓΙΑ ΤΟΥΣ ΝΕΟΥΣ ΔΕΙΚΤΕΣ =====
            if stochastic_chart:
                report += f"![Στοχαστικός Ταλαντωτής]({stochastic_chart})\n\n"

            if mfi_chart:
                report += f"![Money Flow Index]({mfi_chart})\n\n"

            if ichimoku_chart:
                report += f"![Ichimoku Cloud]({ichimoku_chart})\n\n"

            if fib_chart:
                report += f"![Fibonacci Levels]({fib_chart})\n\n"
                
            # Σημείωση
            report += f"## Σημείωση\n\n"
            report += "Αυτή η ανάλυση είναι μόνο για εκπαιδευτικούς σκοπούς και δεν αποτελεί επενδυτική συμβουλή. "
            report += "Οι επενδύσεις σε κρυπτονομίσματα ενέχουν υψηλό ρίσκο απώλειας κεφαλαίου. "
            report += "Πάντα να διεξάγετε τη δική σας έρευνα και να συμβουλεύεστε επαγγελματίες πριν επενδύσετε.\n\n"
            
            return report
        except Exception as e:
            error_message = f"Σφάλμα κατά την ανάλυση του {coin_id}: {str(e)}"
            print(error_message)
            return error_message