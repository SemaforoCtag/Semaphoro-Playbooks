#!/usr/bin/env python3
import sys, json, glob, pandas as pd, re
from datetime import datetime

def parse_disk_size(size_str):
    if not size_str:
        return 0.0
    m = re.match(r"([\d\.]+)\s*(GB|MB|TB)", size_str)
    if not m:
        return 0.0
    size, unit = m.groups()
    size = float(size)
    return size / 1024 if unit == "MB" else size * 1024 if unit == "TB" else size

def main():
    if len(sys.argv) < 3:
        print("Uso: generar_excel.py <salida.xlsx> <json_glob>")
        sys.exit(1)

    salida_excel, json_glob = sys.argv[1:3]
    filas = []

    for json_path in glob.glob(json_glob):
        print("Leyendo:", json_path)
        with open(json_path, 'r') as f:
            try:
                info = json.load(f)
            except Exception as e:
                print("Json invalido:", e)
            facts = info.get('ansible_facts', info)         # ← clave del arreglo

        total_disk = sum(
            parse_disk_size(dev.get('size', '0 GB'))
            for dev_name, dev in facts.get('ansible_devices', {}).items()
            if dev_name.startswith(('sd', 'nvme'))
        )

        filas.append({
            'Fecha y Hora' : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'IP'           : info.get('inventory_hostname', 'desconocido'),
            'Hostname'     : facts.get('ansible_hostname', ''),
            'SO'           : f"{facts.get('ansible_distribution','')} {facts.get('ansible_distribution_version','')}",
            'Kernel'       : facts.get('ansible_kernel', ''),
            'Arquitectura' : facts.get('ansible_architecture', ''),
            'CPU'          : (facts.get('ansible_processor') or ['',''])[2] if len(facts.get('ansible_processor',[]))>2 else '',
            'RAM (GB)'     : round(facts.get('ansible_memtotal_mb',0)/1024,2),
            'Disco (GB)'   : round(total_disk,2),
            'Tipo de maquina': 'Virtual' if facts.get('ansible_virtualization_role')=='guest' else 'Física'
        })

    if not filas:
        print("⚠️  No se cargó ningún host. Revisa la ruta o el patrón de JSON.")
        sys.exit(1)

    pd.DataFrame(filas).sort_values('IP').to_excel(salida_excel, index=False)
    print(f"✅ Excel generado con {len(filas)} filas → {salida_excel}")

if __name__ == '__main__':
    main()
