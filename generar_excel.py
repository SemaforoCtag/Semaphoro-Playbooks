#!/usr/bin/env python3
import sys
import json
import glob
import pandas as pd
from datetime import datetime
import re

def parse_disk_size(size_str):
    """
    Convierte una cadena como '100.1 GB' o '500 MB' a GB como número flotante.
    """
    if not size_str:
        return 0.0
    match = re.match(r"([\d\.]+)\s*(GB|MB|TB)", size_str)
    if not match:
        return 0.0
    size, unit = match.groups()
    size = float(size)
    if unit == 'MB':
        return size / 1024
    elif unit == 'TB':
        return size * 1024
    return size  # GB

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
            facts = info

            # Sumar los tamaños de todos los discos (sd* o nvme*)
            total_disk_gb = 0.0
            for device, data in facts.get('ansible_devices', {}).items():
                if device.startswith('sd') or device.startswith('nvme'):
                    total_disk_gb += parse_disk_size(data.get('size', '0 GB'))

            datos.append({
                'Fecha y Hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'IP': info.get('inventory_hostname', 'desconocido'),
                'Hostname': facts.get('ansible_hostname', ''),
                'SO': f"{facts.get('ansible_distribution', '')} {facts.get('ansible_distribution_version', '')}",
                'Kernel': facts.get('ansible_kernel', ''),
                'Arquitectura': facts.get('ansible_architecture', ''),
                'CPU': facts.get('ansible_processor', [''])[2] if len(facts.get('ansible_processor', [])) > 2 else '',
                'RAM (GB)': round(facts.get('ansible_memtotal_mb', 0) / 1024, 2),
                'Disco (GB)': round(total_disk_gb, 2),
                'Tipo de maquina': facts.get('ansible_virtualization_type') if facts.get('ansible_virtualization_role') == 'guest' else 'Físico'
            })

    df = pd.DataFrame(datos)
    df = df.sort_values(by="IP")
    df.to_excel(salida_excel, index=False)

if __name__ == "__main__":
    main()
