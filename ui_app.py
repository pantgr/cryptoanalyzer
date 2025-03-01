#!/usr/bin/env python3
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import threading
import subprocess
from datetime import datetime
from crypto_analyzer import CryptoAnalyzer
from data_collector import CryptoDataCollector

class CryptoAnalysisApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Crypto Analyzer - Αλγοριθμική Ανάλυση Κρυπτονομισμάτων")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        self.analyzer = CryptoAnalyzer()
        self.collector = CryptoDataCollector()
        
        # Δημιουργία του GUI
        self.create_widgets()
        
        # Ενημέρωση της λίστας με τα διαθέσιμα κρυπτονομίσματα
        self.update_coin_list()
        
    def create_widgets(self):
        """Δημιουργία όλων των στοιχείων του UI"""
        # Δημιουργία πλαισίου
        main_frame = ttk.Frame(self.root, padding="10 10 10 10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Μήνυμα καλωσορίσματος
        welcome_lbl = ttk.Label(
            main_frame, 
            text="Καλωσήρθατε στο Crypto Analyzer",
            font=('Helvetica', 16, 'bold')
        )
        welcome_lbl.pack(pady=10)
        
        # Ημερομηνία τελευταίας ενημέρωσης
        self.last_update_lbl = ttk.Label(
            main_frame,
            text="Τελευταία ενημέρωση δεδομένων: Δεν έχει γίνει ενημέρωση"
        )
        self.last_update_lbl.pack(pady=5)
        self.check_last_update()
        
        # Επιλογή κρυπτονομίσματος
        coin_frame = ttk.LabelFrame(main_frame, text="Επιλογή Κρυπτονομίσματος")
        coin_frame.pack(fill=tk.X, pady=10, padx=5)
        
        self.coin_var = tk.StringVar(value="bitcoin")
        
        coin_lbl = ttk.Label(coin_frame, text="Επιλέξτε κρυπτονόμισμα:")
        coin_lbl.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        
        self.coin_combo = ttk.Combobox(
            coin_frame, 
            textvariable=self.coin_var,
            state="readonly",
            width=30
        )
        self.coin_combo.grid(row=0, column=1, padx=5, pady=5)
        
        # Πλαίσιο ενεργειών
        action_frame = ttk.LabelFrame(main_frame, text="Ενέργειες")
        action_frame.pack(fill=tk.X, pady=10, padx=5)
        
        update_btn = ttk.Button(
            action_frame, 
            text="Ενημέρωση Δεδομένων",
            command=self.update_data
        )
        update_btn.grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)
        
        analyze_btn = ttk.Button(
            action_frame,
            text="Ανάλυση Κρυπτονομίσματος",
            command=self.analyze_crypto
        )
        analyze_btn.grid(row=0, column=1, padx=5, pady=10)
        
        view_report_btn = ttk.Button(
            action_frame,
            text="Προβολή Τελευταίας Ανάλυσης",
            command=self.view_last_report
        )
        view_report_btn.grid(row=0, column=2, padx=5, pady=10)
        
        # Πρόοδος και κατάσταση
        self.status_var = tk.StringVar(value="Έτοιμο")
        status_lbl = ttk.Label(main_frame, textvariable=self.status_var)
        status_lbl.pack(pady=5, anchor=tk.W)
        
        self.progress = ttk.Progressbar(
            main_frame,
            orient=tk.HORIZONTAL,
            mode='indeterminate',
            length=580
        )
        self.progress.pack(fill=tk.X, pady=5)
        
        # Περιοχή πληροφοριών
        info_frame = ttk.LabelFrame(main_frame, text="Πληροφορίες")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)
        
        self.info_text = tk.Text(info_frame, height=10, width=70, wrap=tk.WORD)
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.info_text.insert(tk.END, """Καλωσήρθατε στο Crypto Analyzer!

Αυτή η εφαρμογή προσφέρει αλγοριθμική ανάλυση κρυπτονομισμάτων χρησιμοποιώντας:
• Τεχνικούς δείκτες (SMA, EMA, RSI, MACD, Bollinger Bands)
• Στατιστική ανάλυση τιμών
• Συγκριτική απόδοση με άλλα κρυπτονομίσματα

Βήματα χρήσης:
1. Πατήστε 'Ενημέρωση Δεδομένων' για να λάβετε τις τελευταίες τιμές
2. Επιλέξτε ένα κρυπτονόμισμα από τη λίστα
3. Πατήστε 'Ανάλυση Κρυπτονομίσματος' για να δημιουργηθεί η αναφορά

Η αναφορά θα αποθηκευτεί στο φάκελο 'reports' και τα γραφήματα στο φάκελο 'analysis_charts'.
""")
        self.info_text.config(state=tk.DISABLED)
        
    def check_last_update(self):
        """Έλεγχος πότε έγινε η τελευταία ενημέρωση δεδομένων"""
        data = self.analyzer.load_data()
        if data and 'last_updated' in data:
            last_updated = data['last_updated']
            self.last_update_lbl.config(text=f"Τελευταία ενημέρωση δεδομένων: {last_updated}")
        else:
            self.last_update_lbl.config(text="Δεν υπάρχουν δεδομένα. Παρακαλώ κάντε ενημέρωση.")
    
    def update_coin_list(self):
        """Ενημέρωση της λίστας με τα διαθέσιμα κρυπτονομίσματα"""
        coins = self.analyzer.get_available_coins()
        if coins:
            coin_names = [f"{name} ({symbol})" for name, symbol in coins]
            self.coin_combo['values'] = coin_names
            self.coin_var.set(coin_names[0])  # Επιλογή του πρώτου κρυπτονομίσματος
        else:
            self.coin_combo['values'] = ["Δεν υπάρχουν διαθέσιμα δεδομένα"]
            self.coin_var.set("Δεν υπάρχουν διαθέσιμα δεδομένα")
    
    def update_data(self):
        """Ενημέρωση των δεδομένων κρυπτονομισμάτων"""
        def run_update():
            self.status_var.set("Ενημέρωση δεδομένων...")
            self.progress.start()
            
            success = self.collector.update_all_data(10)  # Top 10 κρυπτονομίσματα
            
            self.progress.stop()
            if success:
                self.status_var.set("Η ενημέρωση ολοκληρώθηκε επιτυχώς!")
                self.check_last_update()
                self.update_coin_list()
            else:
                self.status_var.set("Σφάλμα κατά την ενημέρωση δεδομένων.")
                messagebox.showerror("Σφάλμα", "Δεν ήταν δυνατή η ενημέρωση των δεδομένων.")
        
        # Εκτέλεση της ενημέρωσης σε ξεχωριστό νήμα
        thread = threading.Thread(target=run_update)
        thread.daemon = True
        thread.start()
    
    def analyze_crypto(self):
        """Ανάλυση του επιλεγμένου κρυπτονομίσματος"""
        def run_analysis():
            selected = self.coin_var.get().split(" ")[0]  # Παίρνουμε το όνομα χωρίς το σύμβολο
            
            self.status_var.set(f"Ανάλυση {selected}...")
            self.progress.start()
            
            report = self.analyzer.generate_analysis_report(selected)
            
            self.progress.stop()
            
            if "Σφάλμα" not in report:
                # Αποθήκευση αναφοράς
                report_filename = f"{selected}_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
                report_path = os.path.join(self.analyzer.reports_dir, report_filename)
                
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report)
                
                self.status_var.set(f"Η ανάλυση του {selected} ολοκληρώθηκε επιτυχώς!")
                
                # Άνοιγμα της αναφοράς στον προεπιλεγμένο browser ή editor
                self.last_report_path = report_path
                messagebox.showinfo("Επιτυχία", f"Η ανάλυση ολοκληρώθηκε!\nΑποθηκεύτηκε στο: {report_path}")
                self.open_file(report_path)
            else:
                self.status_var.set(f"Σφάλμα κατά την ανάλυση του {selected}.")
                messagebox.showerror("Σφάλμα Ανάλυσης", report)
        
        # Εκτέλεση της ανάλυσης σε ξεχωριστό νήμα
        thread = threading.Thread(target=run_analysis)
        thread.daemon = True
        thread.start()
    
    def view_last_report(self):
        """Άνοιγμα της τελευταίας αναφοράς"""
        if hasattr(self, 'last_report_path') and os.path.exists(self.last_report_path):
            self.open_file(self.last_report_path)
        else:
            # Εύρεση της πιο πρόσφατης αναφοράς στο φάκελο reports
            reports_dir = self.analyzer.reports_dir
            if os.path.exists(reports_dir):
                files = [os.path.join(reports_dir, f) for f in os.listdir(reports_dir) 
                        if f.endswith('.md')]
                if files:
                    latest_file = max(files, key=os.path.getctime)
                    self.last_report_path = latest_file
                    self.open_file(latest_file)
                    return
            
            messagebox.showinfo("Πληροφορία", "Δεν υπάρχει διαθέσιμη αναφορά ανάλυσης.")
    
    def open_file(self, filepath):
        """Άνοιγμα ενός αρχείου με την προεπιλεγμένη εφαρμογή"""
        try:
            if sys.platform.startswith('darwin'):  # macOS
                subprocess.call(('open', filepath))
            elif sys.platform.startswith('win32'):  # Windows
                os.startfile(filepath)
            else:  # Linux
                subprocess.call(('xdg-open', filepath))
        except Exception as e:
            messagebox.showerror("Σφάλμα", f"Δεν ήταν δυνατό το άνοιγμα του αρχείου: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CryptoAnalysisApp(root)
    root.mainloop()