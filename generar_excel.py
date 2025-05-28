#!/usr/bin/env python3
import sys
import json
import glob
import pandas as pd

def main():
    if len(sys.argv) < 3:
        print("Uso: generar_excel.py <ruta_salida.xlsx> <jsons...>")
        sys.exit(1)

    salida_excel = sys.argv[1]
    json_glob = sys.argv[2]

    datos = []

    for json_path in glob.glob(json_glob):
        with open(json_path, 'r') as f:
            info = json.load(f)
            datos.append({
                'IP': info.get('inventory_hostname', 'desconocido'),
                'Hostname': info.get('ansible_hostname'),
                'SO': f"{info.get('ansible_distribution')} {info.get('ansible_distribution_version')}",
                'Kernel': info.get('ansible_kernel'),
                'Arquitectura': info.get('ansible_architecture'),
                'CPU': info.get('ansible_processor', [''])[2] if len(info.get('ansible_processor', [])) > 2 else '',
                'RAM (GB)': round(info.get('ansible_memtotal_mb', 0) / 1024, 2),
                'Virtual': info.get('ansible_virtualization_type') if info.get('ansible_virtualization_role') == 'guest' else 'Físico'
            })

    df = pd.DataFrame(datos)
    df = df.sort_values(by="IP")
    df.to_excel(salida_excel, index=False)

if __name__ == "__main__":
    main()
