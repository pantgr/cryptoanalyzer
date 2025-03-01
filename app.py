#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
import os
import json
from datetime import datetime
import threading
import time
from crypto_analyzer import CryptoAnalyzer
from data_collector import CryptoDataCollector

app = Flask(__name__)
analyzer = CryptoAnalyzer()
collector = CryptoDataCollector()

# Προσθήκη του τρέχοντος χρόνου σε όλα τα templates
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# Μεταβλητές κατάστασης
update_status = {
    "running": False,
    "message": "",
    "progress": 0
}

analysis_status = {
    "running": False,
    "message": "",
    "progress": 0,
    "crypto": ""
}

@app.route('/')
def index():
    # Έλεγχος τελευταίας ενημέρωσης
    last_update = "Δεν έχει γίνει ακόμα"
    data = analyzer.load_data()
    if data and 'last_updated' in data:
        last_update = data['last_updated']
    
    return render_template('index.html', last_update=last_update)

@app.route('/coins')
def coins():
    coins = analyzer.get_available_coins()
    return render_template('coins.html', coins=coins)

@app.route('/analyze', methods=['GET', 'POST'])
def analyze():
    if request.method == 'POST':
        crypto = request.form.get('crypto')
        if crypto:
            # Έναρξη ανάλυσης σε ξεχωριστό νήμα
            threading.Thread(target=run_analysis, args=(crypto,)).start()
            return redirect(url_for('analysis_progress', crypto=crypto))
    
    # Αν είναι GET ή δεν έχει επιλεγεί κρυπτονόμισμα
    coins = analyzer.get_available_coins()
    return render_template('analyze_form.html', coins=coins)

@app.route('/update_data')
def update_data():
    # Αν δεν τρέχει ήδη ενημέρωση
    if not update_status["running"]:
        threading.Thread(target=run_update).start()
    return render_template('update_progress.html')

@app.route('/analysis_progress/<crypto>')
def analysis_progress(crypto):
    return render_template('analysis_progress.html', crypto=crypto)

@app.route('/reports')
def reports():
    reports_dir = analyzer.reports_dir
    report_files = []
    
    if os.path.exists(reports_dir):
        for file in os.listdir(reports_dir):
            if file.endswith('.md'):
                file_path = os.path.join(reports_dir, file)
                mod_time = os.path.getmtime(file_path)
                mod_date = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
                
                # Προσδιορισμός ονόματος κρυπτονομίσματος από το όνομα αρχείου
                parts = file.split('_')
                crypto_name = parts[0].capitalize()
                
                report_files.append({
                    'filename': file,
                    'crypto': crypto_name,
                    'date': mod_date
                })
                
    # Ταξινόμηση με βάση την ημερομηνία, νεότερα πρώτα
    report_files.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template('reports.html', reports=report_files)

@app.route('/report/<filename>')
def view_report(filename):
    report_path = os.path.join(analyzer.reports_dir, filename)
    
    if os.path.exists(report_path):
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return render_template('report_view.html', 
                              content=content, 
                              filename=filename,
                              download_link=url_for('download_report', filename=filename))
    else:
        return "Η αναφορά δεν βρέθηκε", 404

@app.route('/download/report/<filename>')
def download_report(filename):
    return send_from_directory(analyzer.reports_dir, filename, as_attachment=True)

@app.route('/charts/<filename>')
def view_chart(filename):
    return send_from_directory(analyzer.charts_dir, filename)

@app.route('/api/update_status')
def get_update_status():
    return jsonify(update_status)

@app.route('/api/analysis_status')
def get_analysis_status():
    return jsonify(analysis_status)

def run_update():
    """Εκτελεί την ενημέρωση δεδομένων σε ξεχωριστό νήμα"""
    global update_status
    
    update_status = {
        "running": True,
        "message": "Ξεκίνησε η ενημέρωση δεδομένων...",
        "progress": 10
    }
    
    try:
        update_status["message"] = "Λήψη δεδομένων από το CoinGecko API..."
        update_status["progress"] = 30
        
        success = collector.update_all_data(10)  # Top 10 κρυπτονομίσματα
        
        if success:
            update_status["message"] = "Η ενημέρωση ολοκληρώθηκε επιτυχώς!"
            update_status["progress"] = 100
        else:
            update_status["message"] = "Σφάλμα κατά την ενημέρωση δεδομένων."
            update_status["progress"] = 0
    except Exception as e:
        update_status["message"] = f"Σφάλμα: {str(e)}"
        update_status["progress"] = 0
    finally:
        # Περιμένουμε λίγο πριν τερματίσουμε την κατάσταση
        time.sleep(2)
        update_status["running"] = False

def run_analysis(crypto):
    """Εκτελεί την ανάλυση σε ξεχωριστό νήμα"""
    global analysis_status
    
    analysis_status = {
        "running": True,
        "message": f"Ξεκίνησε η ανάλυση του {crypto}...",
        "progress": 10,
        "crypto": crypto
    }
    
    try:
        analysis_status["message"] = "Υπολογισμός τεχνικών δεικτών..."
        analysis_status["progress"] = 30
        
        report = analyzer.generate_analysis_report(crypto)
        
        if "Σφάλμα" not in report:
            analysis_status["message"] = f"Η ανάλυση του {crypto} ολοκληρώθηκε επιτυχώς!"
            analysis_status["progress"] = 100
            
            # Αποθήκευση αναφοράς
            report_filename = f"{crypto}_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
            report_path = os.path.join(analyzer.reports_dir, report_filename)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
                
            # Προσθήκη του ονόματος αρχείου στην κατάσταση
            analysis_status["report_file"] = report_filename
        else:
            analysis_status["message"] = f"Σφάλμα κατά την ανάλυση του {crypto}."
            analysis_status["progress"] = 0
    except Exception as e:
        analysis_status["message"] = f"Σφάλμα: {str(e)}"
        analysis_status["progress"] = 0
    finally:
        # Περιμένουμε λίγο πριν τερματίσουμε την κατάσταση
        time.sleep(2)
        analysis_status["running"] = False

if __name__ == '__main__':
    # Βεβαιωνόμαστε ότι υπάρχουν οι απαραίτητοι φάκελοι
    for directory in [analyzer.data_dir, analyzer.reports_dir, analyzer.charts_dir]:
        if not os.path.exists(directory):
            os.makedirs(directory)
    
    # Εκκίνηση του server
    app.run(host='0.0.0.0', port=5000, debug=True)