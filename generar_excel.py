#!/usr/bin/env python3
import sys, json, glob, pandas as pd, re
from datetime import datetime

def parse_disk_size(size_str: str) -> float:
    if not size_str:
        return 0.0
    m = re.match(r"([\d.]+)\s*(GB|MB|TB)", size_str)
    if not m:
        return 0.0
    size, unit = m.groups()
    size = float(size)
    return size / 1024 if unit == "MB" else size * 1024 if unit == "TB" else size

def main() -> None:
    if len(sys.argv) < 3:
        sys.exit("Uso: generar_excel.py <salida.xlsx> <glob_json>")

    salida_excel, json_glob = sys.argv[1], sys.argv[2]
    datos = []

    for json_path in glob.glob(json_glob):
        with open(json_path, "r") as f:
            info = json.load(f)

        # admitimos tanto estructura plana como anidada en ansible_facts
        facts = info.get("ansible_facts", info)

        # tamaño total de discos (sd* / nvme*)
        total_disk_gb = sum(
            parse_disk_size(d.get("size", "0 GB"))
            for dev, d in facts.get("ansible_devices", {}).items()
            if dev.startswith(("sd", "nvme"))
        )

        ip_addr = (
            facts.get("ansible_default_ipv4", {}).get("address")
            or info.get("inventory_hostname", "desconocido")
        )

        datos.append(
            {
                "Fecha y Hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "IP": ip_addr,
                "Hostname": facts.get("ansible_hostname", ""),
                "SO": f'{facts.get("ansible_distribution","")} {facts.get("ansible_distribution_version","")}',
                "Kernel": facts.get("ansible_kernel", ""),
                "Arquitectura": facts.get("ansible_architecture", ""),
                "CPU": facts.get("ansible_processor", ["", "", ""])[2]
                if len(facts.get("ansible_processor", [])) > 2
                else "",
                "RAM (GB)": round(facts.get("ansible_memtotal_mb", 0) / 1024, 2),
                "Disco (GB)": round(total_disk_gb, 2),
                "Tipo de maquina": "Virtual"
                if facts.get("ansible_virtualization_role") == "guest"
                else "Física",
            }
        )

    pd.DataFrame(datos).sort_values("IP").to_excel(salida_excel, index=False)
    print(f"✅ Excel generado con {len(datos)} filas → {salida_excel}")

if __name__ == "__main__":
    main()
