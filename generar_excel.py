#!/usr/bin/env python3
import sys
import json
import glob
import pandas as pd
from datetime import datetime

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
            total_disco_gb = 0

            for dev, props in dispositivos.items():
                if dev.startswith("sd") or dev.startswith("nvme"):
                    size_str = props.get("size", "0 GB")
                    try:
                        size_val = float(size_str.split()[0])
                        total_disco_gb += size_val
                    except:
                        continue

            datos.append({
                'Fecha y Hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'IP': info.get('inventory_hostname', 'desconocido'),
                'Hostname': facts.get('ansible_hostname', ''),
                'SO': f"{facts.get('ansible_distribution', '')} {facts.get('ansible_distribution_version', '')}",
                'Kernel': facts.get('ansible_kernel', ''),
                'Arquitectura': facts.get('ansible_architecture', ''),
                'CPU': facts.get('ansible_processor', [''])[2] if len(facts.get('ansible_processor', [])) > 2 else '',
                'RAM (GB)': round(facts.get('ansible_memtotal_mb', 0) / 1024, 2),
                'Disco (GB)': round(total_disco_gb, 2),
                'Tipo de maquina': facts.get('ansible_virtualization_type') if facts.get('ansible_virtualization_role') == 'guest' else 'Físico'
            })

    df = pd.DataFrame(datos)
    df = df.sort_values(by="IP")
    df.to_excel(salida_excel, index=False)

if __name__ == "__main__":
    main()
