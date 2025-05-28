#!/usr/bin/env python3
import sys
import json
import glob
import pandas as pd
from datetime import datetime

def obtener_tamano_discos(dispositivos):
    total_gb = 0
    for nombre, info in dispositivos.items():
        if nombre.startswith(('sd', 'nvme')):
            try:
                size_str = info.get('size', '0')
                if size_str.endswith(' GB'):
                    total_gb += float(size_str.replace(' GB', ''))
                elif size_str.endswith(' MB'):
                    total_gb += float(size_str.replace(' MB', '')) / 1024
            except:
                continue
    return round(total_gb, 2)

def main():
    if len(sys.argv) < 3:
        print("Uso: generar_excel.py <ruta_salida.xlsx> <jsons_glob>")
        sys.exit(1)

    salida_excel = sys.argv[1]
    json_glob = sys.argv[2]

    datos = []

    for json_path in glob.glob(json_glob):
        with open(json_path, 'r') as f:
            info = json.load(f)
            facts = info.get('ansible_facts', {})
            dispositivos = facts.get('ansible_devices', {})

            datos.append({
                'Fecha y Hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'IP': info.get('inventory_hostname', 'desconocido'),
                'Hostname': facts.get('ansible_hostname', ''),
                'SO': f"{facts.get('ansible_distribution', '')} {facts.get('ansible_distribution_version', '')}",
                'Kernel': facts.get('ansible_kernel', ''),
                'Arquitectura': facts.get('ansible_architecture', ''),
                'CPU': facts.get('ansible_processor', [''])[2] if len(facts.get('ansible_processor', [])) > 2 else '',
                'RAM (GB)': round(facts.get('ansible_memtotal_mb', 0) / 1024, 2),
                'Disco (GB)': obtener_tamano_discos(dispositivos),
                'Tipo de máquina': facts.get('ansible_virtualization_type') if facts.get('ansible_virtualization_role') == 'guest' else 'Físico'
            })

    df = pd.DataFrame(datos)
    df = df.sort_values(by="IP")
    df.to_excel(salida_excel, index=False)

if __name__ == "__main__":
    main()
