#!/usr/bin/env python3
import sys, json, glob,math, pandas as pd, re
from datetime import datetime

# ---------- utilidades ----------
def parse_size(s):
    """Convierte '100 GB' / '500 MB' / '2 TB' → GiB flotantes"""
    m = re.match(r"([\d.]+)\s*(GB|MB|TB)", s or "")
    if not m:
        return 0.0
    val, unit = float(m[1]), m[2]
    return val/1024 if unit == "MB" else val*1024 if unit == "TB" else val

def pick(d, *keys):
    """Devuelve la primera clave presente en dict `d`"""
    for k in keys:
        if k in d:
            return d[k]

# ---------- cálculo de cada fila ----------
def fila(facts, host_inv):
    # --- IP & hostname ---
    ip = pick(facts, "ansible_default_ipv4", "default_ipv4") or {}
    ip = ip.get("address") or host_inv
    hostname = pick(facts, "ansible_hostname", "hostname", "fqdn") or host_inv

    # --- SO, kernel, arquitectura ---
    distro = pick(facts, "ansible_distribution", "distribution") or ""
    d_ver  = pick(facts, "ansible_distribution_version",
                  "distribution_version") or ""
    so = f"{distro} {d_ver}".strip()

    kernel = pick(facts, "ansible_kernel", "kernel") or ""
    arch   = pick(facts, "ansible_architecture", "architecture", "machine") or ""

    # --- CPU ---
    cpu_lst = pick(facts, "ansible_processor", "processor") or []
    cpu = cpu_lst[2] if len(cpu_lst) > 2 else (cpu_lst[-1] if cpu_lst else "")

    # ---------- MEMORIA ----------
    mem_total_mb = pick(facts, "ansible_memtotal_mb", "memtotal_mb") or 0
    mem_free_mb  = pick(facts, "ansible_memfree_mb",
                        "memfree_mb",
                        ["ansible_memory_mb","memory_mb"]) or 0
    # si memory_mb es un dict {real:{total,free}} …
    if isinstance(mem_free_mb, dict):
        mem_free_mb = mem_free_mb.get("real", {}).get("free", 0)

    mem_total_gb = math.ceil(mem_total_mb / 1024)
    mem_free_gb  = math.ceil(mem_free_mb  / 1024)
    mem_used_gb  =  mem_total_gb - mem_free_gb

    # ---------- DISCO ----------
    # 1. Tamaño físico de los dispositivos (igual que antes)
    devs = pick(facts, "ansible_devices", "devices") or {}
    disk_total_gb = sum(
        parse_size(d.get("size", "0 GB"))
        for n, d in devs.items() if n.startswith(("sd", "nvme"))
    )

    # 2. Espacio ocupado / libre según mounts
    mounts = pick(facts, "ansible_mounts", "mounts") or []
    bytes_total = bytes_avail = 0
    for m in mounts:
        if not m.get("device","").startswith(("/dev/sd","/dev/nvme")):
            continue
        bytes_total  += m.get("size_total", 0)
        bytes_avail  += m.get("size_available", 0)
    disk_total_mnt_gb = round(bytes_total  / 1024**3, 2)
    disk_free_gb      = round(bytes_avail  / 1024**3, 2)
    disk_used_gb      = round(disk_total_mnt_gb - disk_free_gb, 2)

    # --- Tipo de máquina ---
    tipo = "Virtual" if pick(facts, "ansible_virtualization_role",
                                      "virtualization_role") == "guest" else "Física"

    return {
        "Fecha y Hora"     : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "IP"               : ip,
        "Hostname"         : hostname,
        "SO"               : so,
        "Kernel"           : kernel,
        "Arquitectura"     : arch,
        "CPU"              : cpu,
        "RAM Total (GB)"   : mem_total_gb,
        "RAM Usada (GB)"   : mem_used_gb,
        "RAM Libre (GB)"   : mem_free_gb,
        "Disco Total (GB)" : disk_total_gb,         # físico
        "Disco Usado (GB)" : disk_used_gb,          # según mounts
        "Disco Libre (GB)" : disk_free_gb,
        "Tipo de maquina"  : tipo,
    }

# ---------- main ----------
def main():
    if len(sys.argv) < 3:
        sys.exit("Uso: generar_excel.py <salida.xlsx> <glob_json>")
    salida, patron = sys.argv[1], sys.argv[2]
    filas = []
    for p in glob.glob(patron):
        with open(p) as f:
            info  = json.load(f)
        facts = info.get("ansible_facts", info)
        filas.append(fila(facts, info.get("inventory_hostname", "desconocido")))

    pd.DataFrame(filas).sort_values("IP").to_excel(salida, index=False)
    print(f"✅ Excel generado con {len(filas)} filas → {salida}")

if __name__ == "__main__":
    main()
