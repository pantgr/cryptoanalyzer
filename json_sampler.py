#!/usr/bin/env python3
"""
JSON Sampler - Εργαλείο δειγματοληπτικού ελέγχου δεδομένων JSON
Δημιουργήθηκε: 2025-03-01
Χρήστης: pantgr
"""

import json
import os
import argparse
import random
from datetime import datetime
from tabulate import tabulate
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np

class JSONSampler:
    def __init__(self, json_file):
        """Αρχικοποίηση του δειγματολήπτη με το αρχείο JSON."""
        self.json_file = json_file
        self.data = self.load_json()
        self.report_dir = "json_analysis_reports"
        
        # Δημιουργία φακέλου για αναφορές αν δεν υπάρχει
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)
            
    def load_json(self):
        """Φορτώνει το αρχείο JSON."""
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Σφάλμα κατά τη φόρτωση του αρχείου JSON: {e}")
            return None
            
    def get_structure_info(self, data=None, path="", max_depth=5, current_depth=0):
        """Αναλύει τη δομή του JSON αναδρομικά."""
        if data is None:
            data = self.data
            
        if current_depth >= max_depth:
            return {"type": type(data).__name__, "path": path, "too_deep": True}
            
        structure = {}
        
        if isinstance(data, dict):
            structure["type"] = "dict"
            structure["keys"] = list(data.keys())
            structure["key_count"] = len(data)
            structure["children"] = {}
            
            # Δειγματοληψία έως 5 κλειδιών για μεγάλα dictionaries
            sample_keys = list(data.keys())
            if len(sample_keys) > 5:
                sample_keys = random.sample(sample_keys, 5)
                structure["sampled"] = True
                
            for key in sample_keys:
                new_path = f"{path}.{key}" if path else key
                structure["children"][key] = self.get_structure_info(data[key], new_path, max_depth, current_depth + 1)
                
        elif isinstance(data, list):
            structure["type"] = "list"
            structure["length"] = len(data)
            
            # Δειγματοληψία για μεγάλες λίστες
            if structure["length"] > 0:
                structure["element_type"] = type(data[0]).__name__
                
                # Έλεγχος αν όλα τα στοιχεία είναι του ίδιου τύπου
                types = {type(item).__name__ for item in data[:100]}  # Έλεγχος έως 100 στοιχείων
                structure["homogeneous"] = (len(types) == 1)
                
                # Δειγματοληψία έως 3 στοιχεία
                sample_indices = [0]  # Πάντα περιλαμβάνουμε το πρώτο στοιχείο
                if len(data) > 1:
                    sample_indices.append(len(data) - 1)  # Και το τελευταίο
                if len(data) > 10:
                    sample_indices.append(len(data) // 2)  # Και το μεσαίο
                    
                structure["samples"] = {}
                for idx in sample_indices:
                    new_path = f"{path}[{idx}]"
                    structure["samples"][idx] = self.get_structure_info(data[idx], new_path, max_depth, current_depth + 1)
        else:
            structure["type"] = type(data).__name__
            
            # Αν είναι απλός τύπος, προσθέτουμε μια περίληψη της τιμής
            if structure["type"] in ["str", "int", "float", "bool", "NoneType"]:
                if structure["type"] == "str":
                    if len(data) > 50:
                        structure["value_preview"] = f"{data[:50]}..." 
                    else:
                        structure["value_preview"] = data
                else:
                    structure["value_preview"] = str(data)
                    
        return structure
        
    def analyze_coin_data(self, coin_id):
        """Αναλύει λεπτομερώς τα δεδομένα ενός συγκεκριμένου νομίσματος."""
        if not isinstance(self.data, dict) or coin_id not in self.data:
            return f"Το {coin_id} δεν βρέθηκε στα δεδομένα"
            
        coin_data = self.data[coin_id]
        analysis = {
            "id": coin_id,
            "keys_available": list(coin_data.keys()),
            "data_types": {}
        }
        
        # Ανάλυση των κλειδιών και των τύπων τους
        for key, value in coin_data.items():
            value_type = type(value).__name__
            analysis["data_types"][key] = value_type
            
            # Ειδική ανάλυση για λίστες
            if value_type == "list":
                analysis[f"{key}_length"] = len(value)
                if len(value) > 0:
                    # Έλεγχος για το αν έχουμε λίστα από lists (πιθανά ζεύγη ημερομηνίας-τιμής)
                    if isinstance(value[0], list):
                        analysis[f"{key}_structure"] = "nested_list"
                        analysis[f"{key}_element_structure"] = [len(item) for item in value[:5]]
                        analysis[f"{key}_first_elements"] = value[:3]
                    else:
                        analysis[f"{key}_structure"] = "simple_list"
                        analysis[f"{key}_first_elements"] = value[:5]
        
        return analysis
    
    def validate_structure(self):
        """Ελέγχει για προβλήματα στη δομή των δεδομένων."""
        if not isinstance(self.data, dict):
            return "Το αρχείο JSON δεν περιέχει ένα dictionary στη ρίζα"
            
        validation = {
            "total_items": len(self.data),
            "problems": []
        }
        
        # Αν υπάρχει κλειδί "last_updated", το αφαιρούμε προσωρινά από την ανάλυση
        coins = [k for k in self.data.keys() if k != "last_updated"]
        validation["coins"] = len(coins)
        
        # Δειγματοληψία έως 10 νομίσματα για έλεγχο συνέπειας
        sample_coins = coins[:10] if len(coins) > 10 else coins
        
        # Συλλογή όλων των κλειδιών από όλα τα νομίσματα
        all_keys = set()
        key_presence = {}
        
        for coin in sample_coins:
            coin_data = self.data[coin]
            if not isinstance(coin_data, dict):
                validation["problems"].append(f"Το {coin} δεν περιέχει dictionary")
                continue
                
            keys = set(coin_data.keys())
            all_keys.update(keys)
            
            for key in keys:
                if key not in key_presence:
                    key_presence[key] = []
                key_presence[key].append(coin)
        
        # Έλεγχος συνέπειας κλειδιών
        validation["all_possible_keys"] = list(all_keys)
        validation["key_consistency"] = {}
        
        for key in all_keys:
            coins_with_key = len(key_presence.get(key, []))
            percentage = (coins_with_key / len(sample_coins)) * 100
            validation["key_consistency"][key] = {
                "present_count": coins_with_key,
                "present_percentage": percentage,
                "missing_in": [c for c in sample_coins if c not in key_presence.get(key, [])]
            }
            
            if percentage < 100:
                validation["problems"].append(f"Το κλειδί '{key}' λείπει από {100-percentage:.1f}% των νομισμάτων")
                
        return validation
        
    def check_specific_fields(self, fields_to_check):
        """Ελέγχει συγκεκριμένα πεδία σε όλα τα νομίσματα."""
        if not isinstance(self.data, dict):
            return "Το αρχείο JSON δεν περιέχει ένα dictionary στη ρίζα"
            
        coins = [k for k in self.data.keys() if k != "last_updated"]
        
        field_report = {field: {"present": 0, "absent": 0, "coins_missing": []} for field in fields_to_check}
        
        for coin in coins:
            coin_data = self.data.get(coin, {})
            if not isinstance(coin_data, dict):
                continue
                
            for field in fields_to_check:
                if field in coin_data and coin_data[field]:
                    field_report[field]["present"] += 1
                else:
                    field_report[field]["absent"] += 1
                    field_report[field]["coins_missing"].append(coin)
        
        # Υπολογισμός ποσοστών
        for field in fields_to_check:
            total = field_report[field]["present"] + field_report[field]["absent"]
            if total > 0:
                field_report[field]["presence_percentage"] = (field_report[field]["present"] / total) * 100
            else:
                field_report[field]["presence_percentage"] = 0
                
        return field_report
    
    def generate_report(self, coin_id=None):
        """Δημιουργεί πλήρη αναφορά ανάλυσης του JSON."""
        report = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report.append(f"# Αναφορά Ανάλυσης JSON - {timestamp}")
        report.append(f"## Αρχείο: {os.path.basename(self.json_file)}")
        report.append("")
        
        if not self.data:
            report.append("**ΣΦΑΛΜΑ**: Δεν ήταν δυνατή η φόρτωση του αρχείου JSON")
            return "\n".join(report)
            
        # Γενικές πληροφορίες
        report.append("## Γενικές Πληροφορίες")
        
        if isinstance(self.data, dict):
            top_level_keys = list(self.data.keys())
            last_updated = self.data.get("last_updated", "Μη διαθέσιμο")
            if isinstance(last_updated, (int, float)):
                last_updated = datetime.fromtimestamp(last_updated/1000).strftime('%Y-%m-%d %H:%M:%S')
                
            report.append(f"* **Τύπος**: Dictionary")
            report.append(f"* **Πλήθος στοιχείων**: {len(top_level_keys)}")
            report.append(f"* **Last Updated**: {last_updated}")
            report.append("")
            
            # Αφαίρεση του last_updated από τη λίστα νομισμάτων αν υπάρχει
            coins = [k for k in top_level_keys if k != "last_updated"]
            report.append(f"* **Πλήθος νομισμάτων**: {len(coins)}")
            report.append(f"* **Δειγματοληπτικά νομίσματα**: {', '.join(coins[:5])}...")
            report.append("")
        else:
            report.append(f"* **Τύπος**: {type(self.data).__name__}")
            report.append("")
        
        # Έλεγχος εγκυρότητας δομής
        report.append("## Έλεγχος Εγκυρότητας Δομής")
        validation = self.validate_structure()
        if isinstance(validation, str):
            report.append(validation)
        else:
            report.append(f"* **Συνολικά στοιχεία**: {validation['total_items']}")
            report.append(f"* **Νομίσματα**: {validation['coins']}")
            report.append("")
            
            report.append("### Συνέπεια Κλειδιών")
            key_table = []
            for key, stats in validation['key_consistency'].items():
                key_table.append([
                    key, 
                    f"{stats['present_count']}",
                    f"{stats['present_percentage']:.1f}%",
                    ", ".join(stats['missing_in'][:3]) + ("..." if len(stats['missing_in']) > 3 else "")
                ])
            
            report.append("| Κλειδί | Παρόν # | Παρόν % | Λείπει από |")
            report.append("|--------|---------|---------|------------|")
            for row in key_table:
                report.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")
            report.append("")
            
            if validation['problems']:
                report.append("### Προβλήματα")
                for problem in validation['problems']:
                    report.append(f"* {problem}")
                report.append("")
        
        # Αν έχει δοθεί συγκεκριμένο νόμισμα, προσθέτουμε λεπτομερή ανάλυση
        if coin_id:
            report.append(f"## Ανάλυση του {coin_id}")
            coin_analysis = self.analyze_coin_data(coin_id)
            
            if isinstance(coin_analysis, str):
                report.append(coin_analysis)
            else:
                report.append(f"### Διαθέσιμα Κλειδιά")
                for key in coin_analysis["keys_available"]:
                    data_type = coin_analysis["data_types"].get(key, "άγνωστος")
                    report.append(f"* **{key}**: {data_type}")
                    
                    # Προσθήκη επιπλέον πληροφοριών για λίστες
                    if f"{key}_length" in coin_analysis:
                        report.append(f"  * Μήκος: {coin_analysis[f'{key}_length']}")
                    
                    if f"{key}_structure" in coin_analysis:
                        structure = coin_analysis[f"{key}_structure"]
                        report.append(f"  * Δομή: {structure}")
                        
                        if structure == "nested_list":
                            element_structure = coin_analysis.get(f"{key}_element_structure", [])
                            report.append(f"  * Δομή στοιχείων: {element_structure}")
                        
                        first_elements = coin_analysis.get(f"{key}_first_elements", [])
                        if first_elements:
                            preview = str(first_elements)
                            if len(preview) > 100:
                                preview = preview[:100] + "..."
                            report.append(f"  * Δείγματα: {preview}")
                report.append("")
                
                # Έλεγχος για συγκεκριμένα κλειδιά που χρειάζονται για την ανάλυση
                critical_fields = ["prices", "dates", "total_volumes", "id", "current_price"]
                report.append("### Έλεγχος Κρίσιμων Πεδίων")
                
                for field in critical_fields:
                    if field in coin_analysis["keys_available"]:
                        value = "Παρόν"
                        if field in coin_analysis["data_types"]:
                            value += f" ({coin_analysis['data_types'][field]})"
                        report.append(f"* **{field}**: {value}")
                    else:
                        report.append(f"* **{field}**: **ΑΠΟΝ** - ΑΠΑΙΤΕΙΤΑΙ ΓΙΑ ΤΗΝ ΑΝΑΛΥΣΗ!")
                report.append("")
        
        # Έλεγχος συγκεκριμένων πεδίων
        critical_fields = ["prices", "dates", "total_volumes", "id", "current_price"]
        report.append("## Έλεγχος Κρίσιμων Πεδίων σε Όλα τα Νομίσματα")
        
        field_check = self.check_specific_fields(critical_fields)
        if isinstance(field_check, str):
            report.append(field_check)
        else:
            field_table = []
            for field, stats in field_check.items():
                field_table.append([
                    field, 
                    f"{stats['present']}",
                    f"{stats['absence' if 'absence' in stats else 'absent']}",  
                    f"{stats.get('presence_percentage', 0):.1f}%"
                ])
            
            report.append("| Πεδίο | Παρόν | Απόν | Ποσοστό Παρουσίας |")
            report.append("|-------|-------|------|-------------------|")
            for row in field_table:
                report.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")
            report.append("")
            
            # Λεπτομέρειες για απόντα πεδία
            report.append("### Λεπτομέρειες Απόντων Πεδίων")
            for field, stats in field_check.items():
                if stats["absent"] > 0:
                    missing_coins = stats.get("coins_missing", [])
                    preview = ", ".join(missing_coins[:5])
                    if len(missing_coins) > 5:
                        preview += f"... (+{len(missing_coins) - 5} ακόμη)"
                    report.append(f"* **{field}**: Λείπει από {stats['absent']} νομίσματα - {preview}")
            report.append("")
        
        # Συμπεράσματα και προτάσεις
        report.append("## Συμπεράσματα και Προτάσεις")
        
        issues = []
        if "validation" in locals() and isinstance(validation, dict) and validation.get('problems', []):
            issues.extend(validation['problems'])
            
        for field in critical_fields:
            if field in field_check and field_check[field]["absent"] > 0:
                percentage = field_check[field].get("presence_percentage", 0)
                if percentage < 90:  # Αν λείπει από περισσότερο από 10% των νομισμάτων
                    issues.append(f"Το πεδίο '{field}' λείπει από {100-percentage:.1f}% των νομισμάτων")
        
        if issues:
            report.append("### Προβλήματα που Εντοπίστηκαν")
            for issue in issues:
                report.append(f"* {issue}")
                
            report.append("\n### Προτεινόμενες Ενέργειες")
            if any("id" in issue for issue in issues):
                report.append("* Προσθέστε το κλειδί 'id' σε κάθε αντικείμενο κρυπτονομίσματος με τιμή το όνομά του")
                report.append("  ```python")
                report.append("  # Στη μέθοδο get_coin_data():")
                report.append("  coin_data = data[coin_id]")
                report.append("  coin_data['id'] = coin_id  # Προσθήκη του id στα δεδομένα")
                report.append("  ```")
                
            if any("total_volumes" in issue for issue in issues):
                report.append("* Δημιουργήστε συνθετικά δεδομένα όγκου συναλλαγών αν δεν υπάρχουν ή συλλέξτε πραγματικά δεδομένα")
                report.append("  ```python")
                report.append("  # Στη μέθοδο generate_analysis_report():")
                report.append("  if not volumes or len(volumes) != len(prices):")
                report.append("      # Προσομοίωση δεδομένων όγκου")
                report.append("      import random")
                report.append("      volumes = [price * (0.8 + 0.4 * random.random()) for price in prices]")
                report.append("  ```")
        else:
            report.append("Δεν εντοπίστηκαν σημαντικά προβλήματα στη δομή των δεδομένων.")
        
        return "\n".join(report)
        
    def save_report(self, report, coin_id=None):
        """Αποθηκεύει την αναφορά σε αρχείο markdown."""
        filename = f"json_analysis_{os.path.basename(self.json_file).replace('.json', '')}"
        if coin_id:
            filename += f"_{coin_id}"
        filename += f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        filepath = os.path.join(self.report_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
            
        print(f"Η αναφορά αποθηκεύτηκε στο αρχείο: {filepath}")
        return filepath

    def generate_structure_chart(self, coin_id):
        """Δημιουργεί γραφικές αναπαραστάσεις της δομής των δεδομένων."""
        if not isinstance(self.data, dict) or coin_id not in self.data:
            print(f"Το {coin_id} δεν βρέθηκε στα δεδομένα")
            return
            
        coin_data = self.data[coin_id]
        
        # Έλεγχος για τα κρίσιμα πεδία
        critical_fields = ["prices", "dates", "total_volumes"]
        available_fields = [field for field in critical_fields if field in coin_data]
        
        if not available_fields:
            print(f"Δεν βρέθηκαν κρίσιμα πεδία για γραφική απεικόνιση στο {coin_id}")
            return
            
        # Δημιουργία γραφημάτων για κάθε κρίσιμο πεδίο
        for field in available_fields:
            data = coin_data.get(field)
            if not data or not isinstance(data, list) or not data:
                continue
                
            # Ελέγχουμε τον τύπο του πεδίου
            if field == "dates" and isinstance(data[0], (int, float)):
                # Μετατροπή timestamps σε readable dates για το διάγραμμα
                plt.figure(figsize=(10, 6))
                plt.plot(range(len(data)), data)
                plt.title(f"{field.capitalize()} Distribution for {coin_id}")
                plt.xlabel("Index")
                plt.ylabel("Timestamp")
                plt.tight_layout()
                
                # Αποθήκευση γραφήματος
                filename = f"{coin_id}_{field}_distribution.png"
                filepath = os.path.join(self.report_dir, filename)
                plt.savefig(filepath)
                plt.close()
                print(f"Το γράφημα αποθηκεύτηκε στο αρχείο: {filepath}")
                
            elif field in ["prices", "total_volumes"] and all(isinstance(x, (int, float)) for x in data[:100]):
                plt.figure(figsize=(10, 6))
                plt.plot(range(len(data)), data)
                plt.title(f"{field.capitalize()} for {coin_id}")
                plt.xlabel("Index")
                plt.ylabel(field.capitalize())
                plt.grid(True, alpha=0.3)
                plt.tight_layout()
                
                # Αποθήκευση γραφήματος
                filename = f"{coin_id}_{field}.png"
                filepath = os.path.join(self.report_dir, filename)
                plt.savefig(filepath)
                plt.close()
                print(f"Το γράφημα αποθηκεύτηκε στο αρχείο: {filepath}")

def main():
    parser = argparse.ArgumentParser(description='JSON Sampler - Εργαλείο δειγματοληπτικού ελέγχου δεδομένων JSON')
    parser.add_argument('json_file', help='Το αρχείο JSON προς ανάλυση')
    parser.add_argument('-c', '--coin', help='Συγκεκριμένο νόμισμα για ανάλυση')
    parser.add_argument('-g', '--graph', action='store_true', help='Δημιουργία γραφημάτων για το επιλεγμένο νόμισμα')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.json_file):
        print(f"Σφάλμα: Το αρχείο {args.json_file} δεν υπάρχει.")
        return
        
    sampler = JSONSampler(args.json_file)
    
    report = sampler.generate_report(args.coin)
    report_file = sampler.save_report(report, args.coin)
    
    print("\nΒασικά συμπεράσματα από την ανάλυση:")
    if "ΑΠΑΙΤΕΙΤΑΙ ΓΙΑ ΤΗΝ ΑΝΑΛΥΣΗ" in report:
        print("- ΠΡΟΣΟΧΗ: Λείπουν κρίσιμα πεδία για την ανάλυση!")
    if "Προτεινόμενες Ενέργειες" in report:
        print("- Απαιτούνται διορθώσεις στο JSON. Δείτε τις προτεινόμενες ενέργειες στην αναφορά.")
    
    if args.coin and args.graph:
        sampler.generate_structure_chart(args.coin)

if __name__ == "__main__":
    main()