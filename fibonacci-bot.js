
// Απαιτούμενες βιβλιοθήκες
const fs = require('fs');
const path = require('path');
const winston = require('winston');
const axios = require('axios'); // Προσθήκη axios για HTTP αιτήματα

// Ρύθμιση καταγραφής συμβάντων (logging)
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.printf(info => `${info.timestamp} ${info.level}: ${info.message}`)
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'fibonacci_live_trading.log' })
  ]
});

// Ρυθμίσεις
const CONFIG = {
  // Βασικές παράμετροι
  tradingPair: 'SOLBTC',           // Το ζεύγος συναλλαγής (πχ. SOLBTC, ETHBTC)
  btcUsdPair: 'BTCUSDT',           // Το ζεύγος BTC/USDT για αναφορά
  initialBalance: 1.0,             // Αρχικό υπόλοιπο (σε BTC)
  tradeAmount: 0.1,                // Ποσοστό του διαθέσιμου υπολοίπου ανά συναλλαγή (10%)
  
  // Παράμετροι API
  apiBaseUrl: 'https://api.binance.com',
  candlestickEndpoint: '/api/v3/klines',
  tickerEndpoint: '/api/v3/ticker/price',
  interval: '1m',                  // Διάστημα κεριών (1m, 5m, 15m, 1h κτλ.)
  limit: 100,                      // Αριθμός κεριών που θα ληφθούν
  
  // Παράμετροι στρατηγικής
  shortPeriod: 9,                  // Περίοδος για βραχυπρόθεσμο EMA
  longPeriod: 21,                  // Περίοδος για μακροπρόθεσμο EMA
  rsiPeriod: 14,                   // Περίοδος για RSI
  rsiOverbought: 70,               // Επίπεδο υπεραγοράς για RSI
  rsiOversold: 30,                 // Επίπεδο υπερπώλησης για RSI
  
  // Παράμετροι Fibonacci
  fibWindowSize: 20,               // Μέγεθος παραθύρου για τον εντοπισμό κορυφών και κοιλάδων
  fibEntryLevel: 0.618,            // Επίπεδο εισόδου Fibonacci (61.8%)
  fibTakeProfitLevel: 0.0,         // Επίπεδο take profit (0% - επιστροφή στο υψηλό)
  fibStopLossLevel: 1.0,           // Επίπεδο stop loss (100% - χαμηλό)
  
  // Παράμετροι προστασίας
  stopLossPercentage: 0.03,        // Ποσοστό stop-loss (3%)
  takeProfitPercentage: 0.05,      // Ποσοστό take-profit (5%)
  
  // Παράμετροι παρακολούθησης
  updateInterval: 5000,           // Χρόνος μεταξύ ενημερώσεων τιμών (15 δευτερόλεπτα)
};

// Βοηθητικές παράμετροι
const isBTCPair = CONFIG.tradingPair.endsWith('BTC');
const currency = isBTCPair ? 'BTC' : 'USDT';
const asset = CONFIG.tradingPair.replace(/BTC$|USDT$/, '');

// Μεταβλητές κατάστασης
let candleData = [];
let isInPosition = false;
let entryPrice = 0;
let stopLossPrice = 0;
let takeProfitPrice = 0;
let currentBtcUsdPrice = 0;

// Μεταβλητές Fibonacci
let fibonacciLevels = null;
let trendDirection = null; // 'up' ή 'down'
let swingHigh = 0;
let swingLow = 0;

// Μεταβλητές λογιστικής
let simulationBalance = CONFIG.initialBalance;
let simulationHoldings = 0;
let simulationTrades = [];
let simulationStartTime = null;
let simulationProfitLoss = 0;
let simulationElapsedTime = 0; // Σε λεπτά

// ====== Συναρτήσεις API για λήψη δεδομένων =======

// Λήψη τιμής BTC/USD
async function fetchBtcUsdPrice() {
  try {
    const response = await axios.get(`${CONFIG.apiBaseUrl}${CONFIG.tickerEndpoint}`, {
      params: {
        symbol: CONFIG.btcUsdPair
      }
    });
    
    if (response.data && response.data.price) {
      currentBtcUsdPrice = parseFloat(response.data.price);
      logger.info(`Τιμή BTC/USD: ${formatPrice(currentBtcUsdPrice)} USD`);
      return currentBtcUsdPrice;
    } else {
      logger.error('Δεν ήταν δυνατή η λήψη τιμής BTC/USD');
      return null;
    }
  } catch (error) {
    logger.error(`Σφάλμα κατά τη λήψη τιμής BTC/USD: ${error.message}`);
    return null;
  }
}

// Λήψη τρέχουσας τιμής για το επιλεγμένο ζεύγος
async function fetchCurrentPrice() {
  try {
    const response = await axios.get(`${CONFIG.apiBaseUrl}${CONFIG.tickerEndpoint}`, {
      params: {
        symbol: CONFIG.tradingPair
      }
    });
    
    if (response.data && response.data.price) {
      return parseFloat(response.data.price);
    } else {
      logger.error('Δεν ήταν δυνατή η λήψη τρέχουσας τιμής');
      return null;
    }
  } catch (error) {
    logger.error(`Σφάλμα κατά τη λήψη τρέχουσας τιμής: ${error.message}`);
    return null;
  }
}

// Λήψη ιστορικών δεδομένων κεριών
async function fetchCandlestickData() {
  try {
    const response = await axios.get(`${CONFIG.apiBaseUrl}${CONFIG.candlestickEndpoint}`, {
      params: {
        symbol: CONFIG.tradingPair,
        interval: CONFIG.interval,
        limit: CONFIG.limit
      }
    });
    
    if (response.data && Array.isArray(response.data)) {
      // Μετατροπή δεδομένων από το Binance API στη μορφή που χρησιμοποιεί το bot
      const candles = response.data.map(candle => ({
        time: candle[0], // Χρόνος ανοίγματος
        open: parseFloat(candle[1]),
        high: parseFloat(candle[2]),
        low: parseFloat(candle[3]),
        close: parseFloat(candle[4]),
        volume: parseFloat(candle[5])
      }));
      
      logger.info(`Ελήφθησαν ${candles.length} κεριά από το API`);
      return candles;
    } else {
      logger.error('Δεν ήταν δυνατή η λήψη δεδομένων κεριών');
      return [];
    }
  } catch (error) {
    logger.error(`Σφάλμα κατά τη λήψη δεδομένων κεριών: ${error.message}`);
    return [];
  }
}

// ====== Συναρτήσεις Fibonacci =======

// Εύρεση κορυφών και κοιλάδων (swing high/low)
function findSwingPoints() {
  if (candleData.length < CONFIG.fibWindowSize) {
    return false; // Ανεπαρκή δεδομένα
  }
  
  const recentCandles = candleData.slice(-CONFIG.fibWindowSize);
  
  // Εύρεση του υψηλότερου υψηλού και του χαμηλότερου χαμηλού
  let highest = -Infinity;
  let highestIndex = -1;
  let lowest = Infinity;
  let lowestIndex = -1;
  
  for (let i = 0; i < recentCandles.length; i++) {
    if (recentCandles[i].high > highest) {
      highest = recentCandles[i].high;
      highestIndex = i;
    }
    if (recentCandles[i].low < lowest) {
      lowest = recentCandles[i].low;
      lowestIndex = i;
    }
  }
  
  // Καθορισμός κατεύθυνσης τάσης
  if (highestIndex > lowestIndex) {
    // Ανοδική τάση (το υψηλό εμφανίστηκε μετά το χαμηλό)
    trendDirection = 'up';
    swingHigh = highest;
    swingLow = lowest;
  } else {
    // Καθοδική τάση (το χαμηλό εμφανίστηκε μετά το υψηλό)
    trendDirection = 'down';
    swingHigh = highest;
    swingLow = lowest;
  }
  
  // Υπολογισμός επιπέδων Fibonacci
  fibonacciLevels = calculateFibonacciLevels(swingHigh, swingLow);
  
  logger.info(`Νέα επίπεδα Fibonacci - Τάση: ${trendDirection}, Υψηλό: ${formatPrice(swingHigh)}, Χαμηλό: ${formatPrice(swingLow)}`);
  
  return true;
}

// Υπολογισμός επιπέδων Fibonacci
function calculateFibonacciLevels(highPrice, lowPrice) {
  const diff = highPrice - lowPrice;
  
  return {
    level0: highPrice,                     // 0% retracement (100% της κίνησης)
    level236: highPrice - 0.236 * diff,    // 23.6% retracement
    level382: highPrice - 0.382 * diff,    // 38.2% retracement
    level50: highPrice - 0.5 * diff,       // 50% retracement
    level618: highPrice - 0.618 * diff,    // 61.8% retracement
    level786: highPrice - 0.786 * diff,    // 78.6% retracement
    level100: lowPrice,                    // 100% retracement
    // Επίπεδα επέκτασης (προς τα κάτω)
    level1618: lowPrice - 0.618 * diff,    // 161.8% extension
    level2618: lowPrice - 1.618 * diff,    // 261.8% extension
    // Επίπεδα επέκτασης (προς τα πάνω)
    levelup1618: highPrice + 0.618 * diff, // 161.8% extension up
    levelup2618: highPrice + 1.618 * diff  // 261.8% extension up
  };
}

// Έλεγχος αν η τιμή βρίσκεται κοντά σε επίπεδο Fibonacci
function isNearFibonacciLevel(price, level, threshold = 0.005) {
  if (!fibonacciLevels) return false;
  
  const fibLevel = fibonacciLevels[`level${level * 1000}`] || 
                  (level === 0 ? fibonacciLevels.level0 : 
                   level === 0.236 ? fibonacciLevels.level236 : 
                   level === 0.382 ? fibonacciLevels.level382 : 
                   level === 0.5 ? fibonacciLevels.level50 : 
                   level === 0.618 ? fibonacciLevels.level618 : 
                   level === 0.786 ? fibonacciLevels.level786 : 
                   level === 1 ? fibonacciLevels.level100 : null);
  
  if (!fibLevel) return false;
  
  // Ελέγχουμε αν η τιμή είναι κοντά στο επίπεδο Fibonacci (±threshold%)
  const upperBound = fibLevel * (1 + threshold);
  const lowerBound = fibLevel * (1 - threshold);
  
  return price >= lowerBound && price <= upperBound;
}

// ====== Βοηθητικές συναρτήσεις =======

// Μορφοποίηση τιμής με τα κατάλληλα δεκαδικά ψηφία
function formatPrice(price) {
  return isBTCPair ? price.toFixed(8) : price.toFixed(2);
}

// Υπολογισμός αξίας σε USD
function calculateUsdValue(btcAmount) {
  return btcAmount * currentBtcUsdPrice;
}

// Μορφοποίηση αξίας σε USD
function formatUsdValue(btcAmount) {
  return calculateUsdValue(btcAmount).toFixed(2);
}

// Υπολογισμός EMA (Exponential Moving Average)
function calculateEMA(prices, period) {
  if (prices.length < period) {
    return prices[prices.length - 1];
  }
  
  const k = 2 / (period + 1);
  let ema = prices[0];
  
  for (let i = 1; i < prices.length; i++) {
    ema = prices[i] * k + ema * (1 - k);
  }
  
  return ema;
}

// Υπολογισμός RSI (Relative Strength Index)
function calculateRSI(prices, period) {
  if (prices.length <= period) {
    return 50; // Ουδέτερη τιμή αν δεν έχουμε αρκετά δεδομένα
  }
  
  let gains = 0;
  let losses = 0;
  
  for (let i = prices.length - period; i < prices.length; i++) {
    const change = prices[i] - prices[i - 1];
    if (change >= 0) {
      gains += change;
    } else {
      losses -= change;
    }
  }
  
  // Μέσος όρος gain/loss
  const avgGain = gains / period;
  const avgLoss = losses / period;
  
  // Υπολογισμός RSI
  if (avgLoss === 0) {
    return 100;
  }
  
  const rs = avgGain / avgLoss;
  return 100 - (100 / (1 + rs));
}

// Εύρεση του κοντινότερου επιπέδου Fibonacci
function findClosestFibonacciLevel(price) {
  if (!fibonacciLevels) return null;
  
  const levels = {
    0: fibonacciLevels.level0,
    23.6: fibonacciLevels.level236,
    38.2: fibonacciLevels.level382,
    50: fibonacciLevels.level50,
    61.8: fibonacciLevels.level618,
    78.6: fibonacciLevels.level786,
    100: fibonacciLevels.level100,
    161.8: fibonacciLevels.level1618,
    261.8: fibonacciLevels.level2618
  };
  
  let closestLevel = null;
  let minDistance = Infinity;
  
  for (const [level, value] of Object.entries(levels)) {
    const distance = Math.abs(price - value);
    if (distance < minDistance) {
      minDistance = distance;
      closestLevel = level;
    }
  }
  
  return closestLevel;
}

// ====== Κύριες συναρτήσεις συναλλαγών =======

// Εκτέλεση της στρατηγικής συναλλαγών
async function runTradingStrategy() {
  try {
    // Έλεγχος ότι έχουμε αρκετά δεδομένα
    if (candleData.length < CONFIG.longPeriod) {
      logger.warn('Ανεπαρκή δεδομένα για ανάλυση');
      return;
    }
    
    // Λήψη της τρέχουσας τιμής
    const currentPrice = await fetchCurrentPrice();
    if (!currentPrice) return;
    
    // Λήψη τιμής BTC/USD αν χρειάζεται
    if (isBTCPair && !currentBtcUsdPrice) {
      await fetchBtcUsdPrice();
    }
    
    // Ενημέρωση του τελευταίου κεριού με την τρέχουσα τιμή
    const lastCandle = candleData[candleData.length - 1];
    if (currentPrice > lastCandle.high) lastCandle.high = currentPrice;
    if (currentPrice < lastCandle.low) lastCandle.low = currentPrice;
    lastCandle.close = currentPrice;
    
    // Υπολογισμός τεχνικών δεικτών
    const closePrices = candleData.map(candle => candle.close);
    
    // Υπολογισμός EMA
    const shortEMA = calculateEMA(closePrices.slice(-CONFIG.shortPeriod), CONFIG.shortPeriod);
    const longEMA = calculateEMA(closePrices.slice(-CONFIG.longPeriod), CONFIG.longPeriod);
    
    // Υπολογισμός RSI
    const rsiValue = calculateRSI(closePrices, CONFIG.rsiPeriod);
    
    // Εύρεση/Ενημέρωση επιπέδων Fibonacci κάθε 10 νέα κεριά
    if (candleData.length % 10 === 0 || !fibonacciLevels) {
      findSwingPoints();
    }
    
    logger.info(`Τιμή: ${formatPrice(currentPrice)} ${currency} (${isBTCPair ? formatUsdValue(currentPrice) + ' USD' : ''}), Βραχ. EMA: ${formatPrice(shortEMA)}, Μακρ. EMA: ${formatPrice(longEMA)}, RSI: ${rsiValue.toFixed(2)}`);
    
    // Εκτύπωση επιπέδων Fibonacci αν υπάρχουν
    if (fibonacciLevels) {
      // Βρείτε το πιο κοντινό επίπεδο Fibonacci
      const closestLevel = findClosestFibonacciLevel(currentPrice);
      const closestPercentage = closestLevel;
      
      logger.info(`Fibonacci: Πιο κοντινό επίπεδο ${closestPercentage}%`);
    }
    
    // Λογική συναλλαγών ενισχυμένη με Fibonacci
    if (!isInPosition) {
      // ΣΤΡΑΤΗΓΙΚΗ ΑΓΟΡΑΣ
      
      // Συνθήκη 1: Παραδοσιακό EMA crossover + RSI oversold
      const condition1 = shortEMA > longEMA && rsiValue < CONFIG.rsiOversold;
      
      // Συνθήκη 2: Fibonacci retracement + RSI
      let condition2 = false;
      
      if (fibonacciLevels) {
        // Σε ανοδική τάση, αγοράζουμε στο επίπεδο retracement 61.8%
        if (trendDirection === 'up' && isNearFibonacciLevel(currentPrice, CONFIG.fibEntryLevel)) {
          condition2 = rsiValue < 50; // Ο RSI να δείχνει ότι δεν είναι υπεραγορασμένο
        }
        // Σε καθοδική τάση, αγοράζουμε με αντιστροφή στο 78.6% retracement
        else if (trendDirection === 'down' && isNearFibonacciLevel(currentPrice, 0.786) && rsiValue > 50) {
          condition2 = true;
        }
      }
      
      // Εκτέλεση αγοράς εάν ισχύει μία από τις δύο συνθήκες
      if (condition1 || condition2) {
        await executeBuy(currentPrice);
      }
    } else {
      // ΣΤΡΑΤΗΓΙΚΗ ΠΩΛΗΣΗΣ
      
      // Συνθήκη 1: Παραδοσιακό EMA crossover + RSI overbought
      const condition1 = shortEMA < longEMA && rsiValue > CONFIG.rsiOverbought;
      
      // Συνθήκη 2: Fibonacci take-profit
      let condition2 = false;
      
      if (fibonacciLevels && trendDirection === 'up') {
        // Σε ανοδική τάση, πουλάμε στην τιμή-στόχο (π.χ. 0% retracement = επιστροφή στο υψηλό)
        if (currentPrice >= fibonacciLevels.level0) {
          condition2 = true;
        }
        // Ή πουλάμε επίσης σε επίπεδο επέκτασης Fibonacci (161.8%)
        else if (currentPrice >= fibonacciLevels.levelup1618) {
          condition2 = rsiValue > 70; // Με επιπλέον επιβεβαίωση από RSI
        }
      }
      
      // Εκτέλεση πώλησης εάν ισχύει μία από τις δύο συνθήκες
      if (condition1 || condition2) {
        await executeSell(currentPrice);
      }
      
      // Έλεγχος stop-loss/take-profit
      await checkStopLossTakeProfit(currentPrice);
    }
    
  } catch (error) {
    logger.error(`Σφάλμα κατά την εκτέλεση στρατηγικής: ${error.message}`);
  }
}

// Έλεγχος stop-loss και take-profit
async function checkStopLossTakeProfit(currentPrice) {
  if (!isInPosition) return;
  
  // Έλεγχος stop-loss
  if (currentPrice <= stopLossPrice) {
    logger.info(`🛑 STOP-LOSS ΕΝΕΡΓΟΠΟΙΗΘΗΚΕ @ ${formatPrice(currentPrice)}`);
    await executeSell(currentPrice);
    return;
  }
  
  // Έλεγχος take-profit
  if (currentPrice >= takeProfitPrice) {
    logger.info(`🎯 TAKE-PROFIT ΕΝΕΡΓΟΠΟΙΗΘΗΚΕ @ ${formatPrice(currentPrice)}`);
    await executeSell(currentPrice);
    return;
  }
  
  // Έλεγχος Fibonacci stop-loss (για επιπλέον προστασία)
  if (fibonacciLevels && trendDirection === 'up') {
    if (currentPrice <= fibonacciLevels.level100) {
      logger.info(`📊 FIBONACCI STOP-LOSS ΕΝΕΡΓΟΠΟΙΗΘΗΚΕ @ ${formatPrice(currentPrice)} (100% retracement)`);
      await executeSell(currentPrice);
    }
  }
}

// Εκτέλεση αγοράς
async function executeBuy(price) {
  try {
    // Έλεγχος αν έχουμε ήδη ανοιχτή θέση αγοράς
    if (isInPosition) {
      logger.info("Υπάρχει ήδη ανοιχτή θέση αγοράς");
      return;
    }
    
    // Υπολογισμός ποσότητας προς αγορά
    const amount = simulationBalance * CONFIG.tradeAmount / price;
    
    // Καταγραφή της αγοράς
    logger.info(`🔵 ΑΓΟΡΑ: ${amount.toFixed(5)} ${asset} @ ${formatPrice(price)} ${currency} (${isBTCPair ? formatUsdValue(price) + ' USD' : ''})`);
    
    // Προσθέστε τις πληροφορίες Fibonacci αν υπάρχουν
    if (fibonacciLevels) {
      const closestLevel = findClosestFibonacciLevel(price);
      logger.info(`📐 Σήμα Fibonacci: Αγορά κοντά στο επίπεδο ${closestLevel}%`);
    }
    
    const tradeCost = amount * price;
    const fee = tradeCost * 0.001; // Χρέωση 0.1%
    
    logger.info(`💰 Κόστος συναλλαγής: ${formatPrice(tradeCost)} ${currency} (${isBTCPair ? formatUsdValue(tradeCost) + ' USD' : ''}) + ${formatPrice(fee)} ${currency} χρέωση`);
    
    // Ενημέρωση εικονικού υπολοίπου και χαρτοφυλακίου
    simulationBalance -= (tradeCost + fee);
    simulationHoldings += amount;
    
    // Καταγραφή της συναλλαγής στο ιστορικό
    simulationTrades.push({
      type: 'BUY',
      price: price,
      amount: amount,
      cost: tradeCost,
      fee: fee,
      timestamp: Date.now(),
      balance: simulationBalance,
      btcUsdPrice: currentBtcUsdPrice,
      usdValue: isBTCPair ? calculateUsdValue(tradeCost) : tradeCost,
      fibonacciLevel: fibonacciLevels ? findClosestFibonacciLevel(price) : null
    });
    
    logger.info(`🏦 Νέο υπόλοιπο: ${formatPrice(simulationBalance)} ${currency} (${isBTCPair ? formatUsdValue(simulationBalance) + ' USD' : ''}), Κατοχή: ${simulationHoldings.toFixed(5)} ${asset}`);
    
    // Ενημέρωση κατάστασης θέσης
    isInPosition = true;
    entryPrice = price;
    
    // Ορισμός stop-loss και take-profit βάσει είτε ποσοστών είτε επιπέδων Fibonacci
    if (fibonacciLevels && trendDirection === 'up') {
      // Σε ανοδική τάση, χρησιμοποιούμε επίπεδα Fibonacci για stop-loss και take-profit
      stopLossPrice = fibonacciLevels.level100; // 100% retracement (στο χαμηλό)
      takeProfitPrice = fibonacciLevels.level0;  // 0% retracement (στο υψηλό)
    } else {
      // Χρήση των παραδοσιακών ποσοστών
      stopLossPrice = price * (1 - CONFIG.stopLossPercentage);
      takeProfitPrice = price * (1 + CONFIG.takeProfitPercentage);
    }
    
    logger.info(`🛑 Stop-Loss: ${formatPrice(stopLossPrice)}, 🎯 Take-Profit: ${formatPrice(takeProfitPrice)}`);
    
  } catch (error) {
    logger.error(`Σφάλμα κατά την αγορά: ${error.message}`);
  }
}

// Λήψη ιστορικών δεδομένων κεριών
async function fetchCandlestickData() {
  try {
    const response = await axios.get(`${CONFIG.apiBaseUrl}${CONFIG.candlestickEndpoint}`, {
      params: {
        symbol: CONFIG.tradingPair,
        interval: CONFIG.interval,
        limit: CONFIG.limit
      }
    });
    
    if (response.data && Array.isArray(response.data)) {
      // Μετατροπή δεδομένων από το Binance API στη μορφή που χρησιμοποιεί το bot
      const candles = response.data.map(candle => ({
        time: candle[0], // Χρόνος ανοίγματος
        open: parseFloat(candle[1]),
        high: parseFloat(candle[2]),
        low: parseFloat(candle[3]),
        close: parseFloat(candle[4]),
        volume: parseFloat(candle[5])
      }));
      
      logger.info(`Ελήφθησαν ${candles.length} κεριά από το API`);
      return candles;
    } else {
      logger.error('Δεν ήταν δυνατή η λήψη δεδομένων κεριών');
      return [];
    }
  } catch (error) {
    logger.error(`Σφάλμα κατά τη λήψη δεδομένων κεριών: ${error.message}`);
    return [];
  }
}

// ====== Συναρτήσεις Fibonacci =======

// Εύρεση κορυφών και κοιλάδων (swing high/low)
function findSwingPoints() {
  if (candleData.length < CONFIG.fibWindowSize) {
    return false; // Ανεπαρκή δεδομένα
  }
  
  const recentCandles = candleData.slice(-CONFIG.fibWindowSize);
  
  // Εύρεση του υψηλότερου υψηλού και του χαμηλότερου χαμηλού
  let highest = -Infinity;
  let highestIndex = -1;
  let lowest = Infinity;
  let lowestIndex = -1;
  
  for (let i = 0; i < recentCandles.length; i++) {
    if (recentCandles[i].high > highest) {
      highest = recentCandles[i].high;
      highestIndex = i;
    }
    if (recentCandles[i].low < lowest) {
      lowest = recentCandles[i].low;
      lowestIndex = i;
    }
  }
  
  // Καθορισμός κατεύθυνσης τάσης
  if (highestIndex > lowestIndex) {
    // Ανοδική τάση (το υψηλό εμφανίστηκε μετά το χαμηλό)
    trendDirection = 'up';
    swingHigh = highest;
    swingLow = lowest;
  } else {
    // Καθοδική τάση (το χαμηλό εμφανίστηκε μετά το υψηλό)
    trendDirection = 'down';
    swingHigh = highest;
    swingLow = lowest;
  }
  
  // Υπολογισμός επιπέδων Fibonacci
  fibonacciLevels = calculateFibonacciLevels(swingHigh, swingLow);
  
  logger.info(`Νέα επίπεδα Fibonacci - Τάση: ${trendDirection}, Υψηλό: ${formatPrice(swingHigh)}, Χαμηλό: ${formatPrice(swingLow)}`);
  
  return true;
}

// Υπολογισμός επιπέδων Fibonacci
function calculateFibonacciLevels(highPrice, lowPrice) {
  const diff = highPrice - lowPrice;
  
  return {
    level0: highPrice,                     // 0% retracement (100% της κίνησης)
    level236: highPrice - 0.236 * diff,    // 23.6% retracement
    level382: highPrice - 0.382 * diff,    // 38.2% retracement
    level50: highPrice - 0.5 * diff,       // 50% retracement
    level618: highPrice - 0.618 * diff,    // 61.8% retracement
    level786: highPrice - 0.786 * diff,    // 78.6% retracement
    level100: lowPrice,                    // 100% retracement
    // Επίπεδα επέκτασης (προς τα κάτω)
    level1618: lowPrice - 0.618 * diff,    // 161.8% extension
    level2618: lowPrice - 1.618 * diff,    // 261.8% extension
    // Επίπεδα επέκτασης (προς τα πάνω)
    levelup1618: highPrice + 0.618 * diff, // 161.8% extension up
    levelup2618: highPrice + 1.618 * diff  // 261.8% extension up
  };
}

// Έλεγχος αν η τιμή βρίσκεται κοντά σε επίπεδο Fibonacci
function isNearFibonacciLevel(price, level, threshold = 0.005) {
  if (!fibonacciLevels) return false;
  
  const fibLevel = fibonacciLevels[`level${level * 1000}`] || 
                  (level === 0 ? fibonacciLevels.level0 : 
                   level === 0.236 ? fibonacciLevels.level236 : 
                   level === 0.382 ? fibonacciLevels.level382 : 
                   level === 0.5 ? fibonacciLevels.level50 : 
                   level === 0.618 ? fibonacciLevels.level618 : 
                   level === 0.786 ? fibonacciLevels.level786 : 
                   level === 1 ? fibonacciLevels.level100 : null);
  
  if (!fibLevel) return false;
  
  // Ελέγχουμε αν η τιμή είναι κοντά στο επίπεδο Fibonacci (±threshold%)
  const upperBound = fibLevel * (1 + threshold);
  const lowerBound = fibLevel * (1 - threshold);
  
  return price >= lowerBound && price <= upperBound;
}

// ====== Βοηθητικές συναρτήσεις =======

// Μορφοποίηση τιμής με τα κατάλληλα δεκαδικά ψηφία
function formatPrice(price) {
  return isBTCPair ? price.toFixed(8) : price.toFixed(2);
}

// Υπολογισμός αξίας σε USD
function calculateUsdValue(btcAmount) {
  return btcAmount * currentBtcUsdPrice;
}

// Μορφοποίηση αξίας σε USD
function formatUsdValue(btcAmount) {
  return calculateUsdValue(btcAmount).toFixed(2);
}

// Υπολογισμός EMA (Exponential Moving Average)
function calculateEMA(prices, period) {
  if (prices.length < period) {
    return prices[prices.length - 1];
  }
  
  const k = 2 / (period + 1);
  let ema = prices[0];
  
  for (let i = 1; i < prices.length; i++) {
    ema = prices[i] * k + ema * (1 - k);
  }
  
  return ema;
}

// Υπολογισμός RSI (Relative Strength Index)
function calculateRSI(prices, period) {
  if (prices.length <= period) {
    return 50; // Ουδέτερη τιμή αν δεν έχουμε αρκετά δεδομένα
  }
  
  let gains = 0;
  let losses = 0;
  
  for (let i = prices.length - period; i < prices.length; i++) {
    const change = prices[i] - prices[i - 1];
    if (change >= 0) {
      gains += change;
    } else {
      losses -= change;
    }
  }
  
  // Μέσος όρος gain/loss
  const avgGain = gains / period;
  const avgLoss = losses / period;
  
  // Υπολογισμός RSI
  if (avgLoss === 0) {
    return 100;
  }
  
  const rs = avgGain / avgLoss;
  return 100 - (100 / (1 + rs));
}

// Εύρεση του κοντινότερου επιπέδου Fibonacci
function findClosestFibonacciLevel(price) {
  if (!fibonacciLevels) return null;
  
  const levels = {
    0: fibonacciLevels.level0,
    23.6: fibonacciLevels.level236,
    38.2: fibonacciLevels.level382,
    50: fibonacciLevels.level50,
    61.8: fibonacciLevels.level618,
    78.6: fibonacciLevels.level786,
    100: fibonacciLevels.level100,
    161.8: fibonacciLevels.level1618,
    261.8: fibonacciLevels.level2618
  };
  
  let closestLevel = null;
  let minDistance = Infinity;
  
  for (const [level, value] of Object.entries(levels)) {
    const distance = Math.abs(price - value);
    if (distance < minDistance) {
      minDistance = distance;
      closestLevel = level;
    }
  }
  
  return closestLevel;
}

// ====== Κύριες συναρτήσεις συναλλαγών =======

// Εκτέλεση της στρατηγικής συναλλαγών
async function runTradingStrategy() {
  try {
    // Έλεγχος ότι έχουμε αρκετά δεδομένα
    if (candleData.length < CONFIG.longPeriod) {
      logger.warn('Ανεπαρκή δεδομένα για ανάλυση');
      return;
    }
    
    // Λήψη της τρέχουσας τιμής
    const currentPrice = await fetchCurrentPrice();
    if (!currentPrice) return;
    
    // Λήψη τιμής BTC/USD αν χρειάζεται
    if (isBTCPair && !currentBtcUsdPrice) {
      await fetchBtcUsdPrice();
    }
    
    // Ενημέρωση του τελευταίου κεριού με την τρέχουσα τιμή
    const lastCandle = candleData[candleData.length - 1];
    if (currentPrice > lastCandle.high) lastCandle.high = currentPrice;
    if (currentPrice < lastCandle.low) lastCandle.low = currentPrice;
    lastCandle.close = currentPrice;
    
    // Υπολογισμός τεχνικών δεικτών
    const closePrices = candleData.map(candle => candle.close);
    
    // Υπολογισμός EMA
    const shortEMA = calculateEMA(closePrices.slice(-CONFIG.shortPeriod), CONFIG.shortPeriod);
    const longEMA = calculateEMA(closePrices.slice(-CONFIG.longPeriod), CONFIG.longPeriod);
    
    // Υπολογισμός RSI
    const rsiValue = calculateRSI(closePrices, CONFIG.rsiPeriod);
    
    // Εύρεση/Ενημέρωση επιπέδων Fibonacci κάθε 10 νέα κεριά
    if (candleData.length % 10 === 0 || !fibonacciLevels) {
      findSwingPoints();
    }
    
    logger.info(`Τιμή: ${formatPrice(currentPrice)} ${currency} (${isBTCPair ? formatUsdValue(currentPrice) + ' USD' : ''}), Βραχ. EMA: ${formatPrice(shortEMA)}, Μακρ. EMA: ${formatPrice(longEMA)}, RSI: ${rsiValue.toFixed(2)}`);
    
    // Εκτύπωση επιπέδων Fibonacci αν υπάρχουν
    if (fibonacciLevels) {
      // Βρείτε το πιο κοντινό επίπεδο Fibonacci
      const closestLevel = findClosestFibonacciLevel(currentPrice);
      const closestPercentage = closestLevel;
      
      logger.info(`Fibonacci: Πιο κοντινό επίπεδο ${closestPercentage}%`);
    }
    
    // Λογική συναλλαγών ενισχυμένη με Fibonacci
    if (!isInPosition) {
      // ΣΤΡΑΤΗΓΙΚΗ ΑΓΟΡΑΣ
      
      // Συνθήκη 1: Παραδοσιακό EMA crossover + RSI oversold
      const condition1 = shortEMA > longEMA && rsiValue < CONFIG.rsiOversold;
      
      // Συνθήκη 2: Fibonacci retracement + RSI
      let condition2 = false;
      
      if (fibonacciLevels) {
        // Σε ανοδική τάση, αγοράζουμε στο επίπεδο retracement 61.8%
        if (trendDirection === 'up' && isNearFibonacciLevel(currentPrice, CONFIG.fibEntryLevel)) {
          condition2 = rsiValue < 50; // Ο RSI να δείχνει ότι δεν είναι υπεραγορασμένο
        }
        // Σε καθοδική τάση, αγοράζουμε με αντιστροφή στο 78.6% retracement
        else if (trendDirection === 'down' && isNearFibonacciLevel(currentPrice, 0.786) && rsiValue > 50) {
          condition2 = true;
        }
      }
      
      // Εκτέλεση αγοράς εάν ισχύει μία από τις δύο συνθήκες
      if (condition1 || condition2) {
        await executeBuy(currentPrice);
      }
    } else {
      // ΣΤΡΑΤΗΓΙΚΗ ΠΩΛΗΣΗΣ
      
      // Συνθήκη 1: Παραδοσιακό EMA crossover + RSI overbought
      const condition1 = shortEMA < longEMA && rsiValue > CONFIG.rsiOverbought;
      
      // Συνθήκη 2: Fibonacci take-profit
      let condition2 = false;
      
      if (fibonacciLevels && trendDirection === 'up') {
        // Σε ανοδική τάση, πουλάμε στην τιμή-στόχο (π.χ. 0% retracement = επιστροφή στο υψηλό)
        if (currentPrice >= fibonacciLevels.level0) {
          condition2 = true;
        }
        // Ή πουλάμε επίσης σε επίπεδο επέκτασης Fibonacci (161.8%)
        else if (currentPrice >= fibonacciLevels.levelup1618) {
          condition2 = rsiValue > 70; // Με επιπλέον επιβεβαίωση από RSI
        }
      }
      
      // Εκτέλεση πώλησης εάν ισχύει μία από τις δύο συνθήκες
      if (condition1 || condition2) {
        await executeSell(currentPrice);
      }
      
      // Έλεγχος stop-loss/take-profit
      await checkStopLossTakeProfit(currentPrice);
    }
    
  } catch (error) {
    logger.error(`Σφάλμα κατά την εκτέλεση στρατηγικής: ${error.message}`);
  }
}

// Έλεγχος stop-loss και take-profit
async function checkStopLossTakeProfit(currentPrice) {
  if (!isInPosition) return;
  
  // Έλεγχος stop-loss
  if (currentPrice <= stopLossPrice) {
    logger.info(`🛑 STOP-LOSS ΕΝΕΡΓΟΠΟΙΗΘΗΚΕ @ ${formatPrice(currentPrice)}`);
    await executeSell(currentPrice);
    return;
  }
  
  // Έλεγχος take-profit
  if (currentPrice >= takeProfitPrice) {
    logger.info(`🎯 TAKE-PROFIT ΕΝΕΡΓΟΠΟΙΗΘΗΚΕ @ ${formatPrice(currentPrice)}`);
    await executeSell(currentPrice);
    return;
  }
  
  // Έλεγχος Fibonacci stop-loss (για επιπλέον προστασία)
  if (fibonacciLevels && trendDirection === 'up') {
    if (currentPrice <= fibonacciLevels.level100) {
      logger.info(`📊 FIBONACCI STOP-LOSS ΕΝΕΡΓΟΠΟΙΗΘΗΚΕ @ ${formatPrice(currentPrice)} (100% retracement)`);
      await executeSell(currentPrice);
    }
  }
}

// Εκτέλεση αγοράς
async function executeBuy(price) {
  try {
    // Έλεγχος αν έχουμε ήδη ανοιχτή θέση αγοράς
    if (isInPosition) {
      logger.info("Υπάρχει ήδη ανοιχτή θέση αγοράς");
      return;
    }
    
    // Υπολογισμός ποσότητας προς αγορά
    const amount = simulationBalance * CONFIG.tradeAmount / price;
    
    // Καταγραφή της αγοράς
    logger.info(`🔵 ΑΓΟΡΑ: ${amount.toFixed(5)} ${asset} @ ${formatPrice(price)} ${currency} (${isBTCPair ? formatUsdValue(price) + ' USD' : ''})`);
    
    // Προσθέστε τις πληροφορίες Fibonacci αν υπάρχουν
    if (fibonacciLevels) {
      const closestLevel = findClosestFibonacciLevel(price);
      logger.info(`📐 Σήμα Fibonacci: Αγορά κοντά στο επίπεδο ${closestLevel}%`);
    }
    
    const tradeCost = amount * price;
    const fee = tradeCost * 0.001; // Χρέωση 0.1%
    
    logger.info(`💰 Κόστος συναλλαγής: ${formatPrice(tradeCost)} ${currency} (${isBTCPair ? formatUsdValue(tradeCost) + ' USD' : ''}) + ${formatPrice(fee)} ${currency} χρέωση`);
    
    // Ενημέρωση εικονικού υπολοίπου και χαρτοφυλακίου
    simulationBalance -= (tradeCost + fee);
    simulationHoldings += amount;
    
    // Καταγραφή της συναλλαγής στο ιστορικό
    simulationTrades.push({
      type: 'BUY',
      price: price,
      amount: amount,
      cost: tradeCost,
      fee: fee,
      timestamp: Date.now(),
      balance: simulationBalance,
      btcUsdPrice: currentBtcUsdPrice,
      usdValue: isBTCPair ? calculateUsdValue(tradeCost) : tradeCost,
      fibonacciLevel: fibonacciLevels ? findClosestFibonacciLevel(price) : null
    });
    
    logger.info(`🏦 Νέο υπόλοιπο: ${formatPrice(simulationBalance)} ${currency} (${isBTCPair ? formatUsdValue(simulationBalance) + ' USD' : ''}), Κατοχή: ${simulationHoldings.toFixed(5)} ${asset}`);
    
    // Ενημέρωση κατάστασης θέσης
    isInPosition = true;
    entryPrice = price;
    
    // Ορισμός stop-loss και take-profit βάσει είτε ποσοστών είτε επιπέδων Fibonacci
    if (fibonacciLevels && trendDirection === 'up') {
      // Σε ανοδική τάση, χρησιμοποιούμε επίπεδα Fibonacci για stop-loss και take-profit
      stopLossPrice = fibonacciLevels.level100; // 100% retracement (στο χαμηλό)
      takeProfitPrice = fibonacciLevels.level0;  // 0% retracement (στο υψηλό)
    } else {
      // Χρήση των παραδοσιακών ποσοστών
      stopLossPrice = price * (1 - CONFIG.stopLossPercentage);
      takeProfitPrice = price * (1 + CONFIG.takeProfitPercentage);
    }
    
    logger.info(`🛑 Stop-Loss: ${formatPrice(stopLossPrice)}, 🎯 Take-Profit: ${formatPrice(takeProfitPrice)}`);
    
  } catch (error) {
    logger.error(`Σφάλμα κατά την αγορά: ${error.message}`);
  }
}

// Εκτέλεση πώλησης
async function executeSell(price) {
  try {
    // Έλεγχος αν υπάρχει ανοιχτή θέση
    if (!isInPosition) {
      logger.info("Δεν υπάρχει ανοιχτή θέση αγοράς για πώληση");
      return;
    }
    
    // ΠΡΟΣΟΜΟΙΩΣΗ: Υπολογισμός κέρδους/ζημίας
    const profitLoss = ((price - entryPrice) / entryPrice) * 100;
    const profitLossAmount = simulationHoldings * (price - entryPrice);
    
    logger.info(`🔴 ΠΩΛΗΣΗ: ${simulationHoldings.toFixed(5)} ${asset} @ ${formatPrice(price)} ${currency} (${isBTCPair ? formatUsdValue(price) + ' USD' : ''})`);
    
    // Προσθέστε τις πληροφορίες Fibonacci αν υπάρχουν
    if (fibonacciLevels) {
      const closestLevel = findClosestFibonacciLevel(price);
      logger.info(`📐 Σήμα Fibonacci: Πώληση κοντά στο επίπεδο ${closestLevel}%`);
    }
    
    logger.info(`📊 Κέρδος/Ζημία: ${profitLoss.toFixed(2)}% (${formatPrice(profitLossAmount)} ${currency} ${isBTCPair ? '/ ' + formatUsdValue(profitLossAmount) + ' USD' : ''})`);
    
    // Ενημέρωση εικονικού υπολοίπου και χαρτοφυλακίου
    const tradeValue = simulationHoldings * price;
    const fee = tradeValue * 0.001; // Χρέωση 0.1%
    simulationBalance += (tradeValue - fee);
    
    // Καταγραφή της συναλλαγής στο ιστορικό
    simulationTrades.push({
      type: 'SELL',
      price: price,
      amount: simulationHoldings,
      value: tradeValue,
      fee: fee,
      profitLoss: profitLoss,
      profitLossAmount: profitLossAmount,
      timestamp: Date.now(),
      balance: simulationBalance,
      btcUsdPrice: currentBtcUsdPrice,
      usdValue: isBTCPair ? calculateUsdValue(tradeValue) : tradeValue,
      fibonacciLevel: fibonacciLevels ? findClosestFibonacciLevel(price) : null
    });
    
    // Ενημέρωση συνολικού κέρδους/ζημίας
    simulationProfitLoss = ((simulationBalance / CONFIG.initialBalance) - 1) * 100;
    
    logger.info(`🏦 Νέο υπόλοιπο: ${formatPrice(simulationBalance)} ${currency} (${isBTCPair ? formatUsdValue(simulationBalance) + ' USD' : ''}) (${simulationProfitLoss > 0 ? '+' : ''}${simulationProfitLoss.toFixed(2)}%)`);
    
    // Μηδενισμός των κατοχών
    simulationHoldings = 0;
    
    // Επαναφορά κατάστασης
    isInPosition = false;
    entryPrice = 0;
    stopLossPrice = 0;
    takeProfitPrice = 0;
    
  } catch (error) {
    logger.error(`Σφάλμα κατά την πώληση: ${error.message}`);
  }
}

// Εκτύπωση αναφοράς προσομοίωσης
function printSimulationReport() {
  if (simulationTrades.length === 0) return;
  
  const totalTrades = simulationTrades.length;
  const buyTrades = simulationTrades.filter(t => t.type === 'BUY').length;
  const sellTrades = simulationTrades.filter(t => t.type === 'SELL').length;
  
  // Υπολογισμός κερδοφόρων συναλλαγών
  const profitableTrades = simulationTrades
    .filter(t => t.type === 'SELL' && t.profitLoss > 0)
    .length;
  
  const winRate = sellTrades > 0 ? (profitableTrades / sellTrades) * 100 : 0;
  
  // Υπολογισμός μέσου κέρδους/ζημίας ανά συναλλαγή
  const avgProfitLoss = simulationTrades
    .filter(t => t.type === 'SELL')
    .reduce((sum, trade) => sum + trade.profitLoss, 0) / (sellTrades || 1);
  
  // Τρέχουσα τιμή του περιουσιακού στοιχείου
  const currentPrice = candleData.length > 0 ? candleData[candleData.length - 1].close : 0;
  
  // Υπολογισμός τρέχουσας αξίας χαρτοφυλακίου (υπόλοιπο + αξία κατοχών)
  const holdingsValue = simulationHoldings * currentPrice;
  const totalPortfolioValue = simulationBalance + holdingsValue;
  const totalReturn = ((totalPortfolioValue / CONFIG.initialBalance) - 1) * 100;
  
  // Υπολογισμός διάρκειας λειτουργίας
  const currentTime = Date.now();
  const runningTime = simulationStartTime ? (currentTime - simulationStartTime) / (1000 * 60 * 60) : 0; // σε ώρες
  
  // Εκτύπωση αναφοράς
  logger.info('\n==================================================');
  logger.info(`📊 ΑΝΑΦΟΡΑ ΣΥΝΑΛΛΑΓΩΝ (${new Date().toISOString()})`);
  logger.info('==================================================');
  logger.info(`⏱️  Διάρκεια λειτουργίας: ${runningTime.toFixed(1)} ώρες`);
  logger.info(`💱 Συνολικές συναλλαγές: ${totalTrades} (${buyTrades} αγορές, ${sellTrades} πωλήσεις)`);
  logger.info(`✅ Ποσοστό επιτυχίας: ${winRate.toFixed(2)}%`);
  logger.info(`📈 Μέσο κέρδος/ζημία ανά συναλλαγή: ${avgProfitLoss.toFixed(2)}%`);
  logger.info(`💰 Αρχικό υπόλοιπο: ${formatPrice(CONFIG.initialBalance)} ${currency} (${isBTCPair ? formatUsdValue(CONFIG.initialBalance) + ' USD*' : ''})`);
  logger.info(`💰 Τρέχον υπόλοιπο: ${formatPrice(simulationBalance)} ${currency} (${isBTCPair ? formatUsdValue(simulationBalance) + ' USD' : ''})`);
  
  if (simulationHoldings > 0) {
    logger.info(`🏦 Τρέχουσα κατοχή: ${simulationHoldings.toFixed(5)} ${asset} (${formatPrice(holdingsValue)} ${currency} / ${isBTCPair ? formatUsdValue(holdingsValue) + ' USD' : ''})`);
    logger.info(`📊 Συνολική αξία χαρτοφυλακίου: ${formatPrice(totalPortfolioValue)} ${currency} (${isBTCPair ? formatUsdValue(totalPortfolioValue) + ' USD' : ''})`);
  }
  
  logger.info(`📊 Συνολική απόδοση: ${totalReturn > 0 ? '+' : ''}${totalReturn.toFixed(2)}%`);
  
  if (fibonacciLevels) {
    logger.info('\n--- Τρέχοντα Επίπεδα Fibonacci ---');
    logger.info(`Τάση: ${trendDirection}`);
    logger.info(`0.0%: ${formatPrice(fibonacciLevels.level0)}`);
    logger.info(`23.6%: ${formatPrice(fibonacciLevels.level236)}`);
    logger.info(`38.2%: ${formatPrice(fibonacciLevels.level382)}`);
    logger.info(`50.0%: ${formatPrice(fibonacciLevels.level50)}`);
    logger.info(`61.8%: ${formatPrice(fibonacciLevels.level618)}`);
    logger.info(`78.6%: ${formatPrice(fibonacciLevels.level786)}`);
    logger.info(`100.0%: ${formatPrice(fibonacciLevels.level100)}`);
  }
  
  if (isBTCPair) {
    logger.info('\n* Αξίες USD υπολογίζονται με τρέχουσα ισοτιμία BTC/USD');
  }
  
  logger.info('==================================================\n');
}

// Εκτύπωση κατάστασης
function printStatus() {
  const currentPrice = candleData.length > 0 ? candleData[candleData.length - 1].close : 0;
  
  logger.info('\n--------------------------------------------------');
  logger.info(`📊 ΚΑΤΑΣΤΑΣΗ (Τιμή ${CONFIG.tradingPair}: ${formatPrice(currentPrice)} ${currency} ${isBTCPair ? '/ ' + formatUsdValue(currentPrice) + ' USD' : ''})`);
  
  if (isInPosition) {
    const unrealizedPL = ((currentPrice - entryPrice) / entryPrice) * 100;
    const unrealizedPLAmount = simulationHoldings * (currentPrice - entryPrice);
    
    logger.info(`🔹 Ανοιχτή θέση: ${simulationHoldings.toFixed(5)} ${asset} @ ${formatPrice(entryPrice)}`);
    logger.info(`📈 Μη πραγματοποιημένο κέρδος/ζημία: ${unrealizedPL > 0 ? '+' : ''}${unrealizedPL.toFixed(2)}% (${unrealizedPL > 0 ? '+' : ''}${formatPrice(unrealizedPLAmount)} ${currency})`);
    logger.info(`🛑 Stop-Loss: ${formatPrice(stopLossPrice)}, 🎯 Take-Profit: ${formatPrice(takeProfitPrice)}`);
  } else {
    logger.info('🔹 Καμία ανοιχτή θέση');
  }
  
  logger.info(`🏦 Διαθέσιμο υπόλοιπο: ${formatPrice(simulationBalance)} ${currency} ${isBTCPair ? '(' + formatUsdValue(simulationBalance) + ' USD)' : ''}`);
  logger.info(`💰 Συνολική απόδοση: ${simulationProfitLoss > 0 ? '+' : ''}${simulationProfitLoss.toFixed(2)}%`);
  
  if (fibonacciLevels) {
    logger.info('\n--- Επίπεδα Fibonacci ---');
    const levels = [0, 23.6, 38.2, 50, 61.8, 78.6, 100];
    const closestLevel = findClosestFibonacciLevel(currentPrice);
    
    for (const level of levels) {
      const fibLevel = level === 0 ? fibonacciLevels.level0 : 
                      level === 23.6 ? fibonacciLevels.level236 : 
                      level === 38.2 ? fibonacciLevels.level382 : 
                      level === 50 ? fibonacciLevels.level50 : 
                      level === 61.8 ? fibonacciLevels.level618 : 
                      level === 78.6 ? fibonacciLevels.level786 : 
                      level === 100 ? fibonacciLevels.level100 : null;
      
      const marker = (level.toString() === closestLevel) ? '▶ ' : '  ';
      logger.info(`${marker}${level}%: ${formatPrice(fibLevel)}`);
    }
  }
  
  logger.info('--------------------------------------------------\n');
}

// ====== Κύρια λειτουργία =======

// Αρχικοποίηση του bot
async function initialize() {
  try {
    // Αρχικοποίηση χρόνου
    simulationStartTime = Date.now();
    
    // Εκκίνηση μηνύματα
    logger.info('=== Εκκίνηση Fibonacci Bot με live δεδομένα ===');
    logger.info(`Χρόνος εκκίνησης: ${new Date().toISOString()}`);
    logger.info(`Χρήστης: ${process.env.USER || 'pantgr'}`);
    logger.info(`Ζεύγος συναλλαγής: ${CONFIG.tradingPair}`);
    logger.info(`Αρχικό υπόλοιπο: ${formatPrice(CONFIG.initialBalance)} ${currency}`);
    logger.info('Φόρτωση ιστορικών δεδομένων...');
    
    // Λήψη ιστορικών δεδομένων
    candleData = await fetchCandlestickData();
    
    if (candleData.length === 0) {
      throw new Error('Αδυναμία φόρτωσης ιστορικών δεδομένων. Το bot δεν μπορεί να ξεκινήσει.');
    }
    
    // Λήψη τιμής BTC/USD αν χρειάζεται
    if (isBTCPair) {
      await fetchBtcUsdPrice();
    }
    
    logger.info(`Φορτώθηκαν ${candleData.length} κεριά για το ${CONFIG.tradingPair}`);
    logger.info(`Τρέχουσα τιμή: ${formatPrice(candleData[candleData.length - 1].close)} ${currency}`);
    
    // Αρχική εύρεση επιπέδων Fibonacci
    findSwingPoints();
    
    // Εκκίνηση παρακολούθησης
    startMonitoring();
  } catch (error) {
    logger.error(`Σφάλμα κατά την αρχικοποίηση: ${error.message}`);
    process.exit(1);
  }
}

// Έναρξη παρακολούθησης
function startMonitoring() {
  logger.info('Η παρακολούθηση της αγοράς ξεκίνησε!');
  logger.info(`Διάστημα ενημέρωσης: ${CONFIG.updateInterval / 1000} δευτερόλεπτα`);
  
  // Άμεση εκτέλεση μιας φοράς
  runTradingStrategy();
  printStatus();
  
  // Ρύθμιση περιοδικής ενημέρωσης τιμών
  const updateInterval = setInterval(async () => {
    try {
      // Ενημέρωση χρόνου προσομοίωσης (για μέτρηση διάρκειας)
      simulationElapsedTime += CONFIG.updateInterval / 60000;
      
      // Λήψη νέων δεδομένων κεριών
      const latestCandleTime = candleData[candleData.length - 1].time;
      const currentTime = Date.now();
      
      // Αν έχει περάσει αρκετός χρόνος για νέο κερί (βάσει του διαστήματος)
      const intervalMs = getIntervalInMilliseconds(CONFIG.interval);
      if (currentTime - latestCandleTime >= intervalMs) {
        // Λήψη νέων δεδομένων
        const newCandles = await fetchCandlestickData();
        if (newCandles.length > 0) {
          // Αφαιρούμε τα παλαιότερα κεριά ώστε να διατηρήσουμε σταθερό μέγεθος
          candleData = newCandles;
          logger.info(`Ενημέρωση δεδομένων: ${newCandles.length} νέα κεριά`);
        }
      }
      
      // Εκτέλεση της στρατηγικής συναλλαγών
      await runTradingStrategy();
      
      // Ενημέρωση τιμής BTC/USD αν χρειάζεται
      if (isBTCPair) {
        await fetchBtcUsdPrice();
      }
      
    } catch (error) {
      logger.error(`Σφάλμα κατά την παρακολούθηση: ${error.message}`);
    }
  }, CONFIG.updateInterval);
  
  // Ρύθμιση περιοδικής εκτύπωσης κατάστασης (κάθε 15 λεπτά)
  setInterval(() => {
    printStatus();
  }, 15 * 60 * 1000);
  
  // Ρύθμιση περιοδικής εκτύπωσης αναφοράς (κάθε 1 ώρα)
  setInterval(() => {
    printSimulationReport();
  }, 60 * 60 * 1000);
  
  // Χειρισμός τερματισμού
  process.on('SIGINT', () => {
    clearInterval(updateInterval);
    logger.info('\n=== Το bot τερματίστηκε ===');
    printSimulationReport();
    setTimeout(() => process.exit(0), 1000); // Δίνουμε χρόνο για την καταγραφή των τελευταίων μηνυμάτων
  });
}

// Μετατροπή διαστήματος κεριών σε milliseconds
function getIntervalInMilliseconds(interval) {
  const unit = interval.slice(-1);
  const value = parseInt(interval.slice(0, -1));
  
  switch (unit) {
    case 'm': return value * 60 * 1000;        // λεπτά
    case 'h': return value * 60 * 60 * 1000;    // ώρες
    case 'd': return value * 24 * 60 * 60 * 1000; // ημέρες
    case 'w': return value * 7 * 24 * 60 * 60 * 1000; // εβδομάδες
    default: return 60 * 1000; // προεπιλογή 1 λεπτό
  }
}

// Έναρξη του bot
initialize().catch(error => {
  logger.error(`Κρίσιμο σφάλμα: ${error.message}`);
  process.exit(1);
});