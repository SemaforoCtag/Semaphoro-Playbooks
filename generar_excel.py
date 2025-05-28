#!/usr/bin/env python3
import sys, json, glob, pandas as pd, re
from datetime import datetime

def parse_disk_size(s):
    m = re.match(r"([\d.]+)\s*(GB|MB|TB)", s or "")
    if not m:
        return 0.0
    size, unit = float(m[1]), m[2]
    return size/1024 if unit == "MB" else size*1024 if unit == "TB" else size

def get(facts, *keys):
    """Devuelve la primera clave existente o None."""
    for k in keys:
        if k in facts:
            return facts[k]

def fila_excel(facts, host_inv):
    ip_dict = get(facts, "ansible_default_ipv4", "default_ipv4") or {}
    ip = ip_dict.get("address") or host_inv

    # Nombre de host: prueba varios campos
    hostname = get(facts, "ansible_hostname", "hostname", "fqdn", "nodename") or host_inv

    # SO + versión
    distro      = get(facts, "ansible_distribution", "distribution") or ""
    distro_ver  = get(facts, "ansible_distribution_version", "distribution_version",
                      "distribution_major_version") or ""
    so = f"{distro} {distro_ver}".strip()

    # Kernel, arquitectura, CPU
    kernel = get(facts, "ansible_kernel", "kernel") or ""
    arch   = get(facts, "ansible_architecture", "architecture", "machine") or ""
    cpu_l  = get(facts, "ansible_processor", "processor") or []
    cpu    = cpu_l[2] if len(cpu_l) > 2 else (cpu_l[-1] if cpu_l else "")

    # RAM
    ram_mb = get(facts, "ansible_memtotal_mb", "memtotal_mb") or 0
    ram_gb = round(ram_mb / 1024, 2)

    # Discos
    devs = get(facts, "ansible_devices", "devices") or {}
    total_disk = sum(
        parse_disk_size(d.get("size", "0 GB"))
        for name, d in devs.items()
        if name.startswith(("sd", "nvme"))
    )
    total_disk = round(total_disk, 2)

    # Tipo de máquina
    virt_role = get(facts, "ansible_virtualization_role", "virtualization_role")
    tipo = "Virtual" if virt_role == "guest" else "Física"

    return {
        "Fecha y Hora" : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "IP"           : ip,
        "Hostname"     : hostname,
        "SO"           : so,
        "Kernel"       : kernel,
        "Arquitectura" : arch,
        "CPU"          : cpu,
        "RAM (GB)"     : ram_gb,
        "Disco (GB)"   : total_disk,
        "Tipo de maquina": tipo,
    }

def main():
    if len(sys.argv) < 3:
        sys.exit("Uso: generar_excel.py <salida.xlsx> <glob_json>")

    salida, patron = sys.argv[1], sys.argv[2]
    filas = []
    for path in glob.glob(patron):
        with open(path) as f:
            info  = json.load(f)
        facts = info.get("ansible_facts", info)   # por si algún host usa el formato viejo
        filas.append(fila_excel(facts, info.get("inventory_hostname", "desconocido")))

    pd.DataFrame(filas).sort_values("IP").to_excel(salida, index=False)
    print(f"✅ Excel generado con {len(filas)} filas → {salida}")

if __name__ == "__main__":
    main()
