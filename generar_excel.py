#!/usr/bin/env python3
"""
Genera Inventario_Equipos_DMZ.xlsx a partir de los JSON recogidos con Ansible.
Incluye:
  • Hardware y SO
  • RAM, discos
  • Puertos de base de datos (MySQL, PostgreSQL, SQL Server, Oracle, MongoDB)
"""

import sys
import json
import glob
import math
import re
from datetime import datetime
from pathlib import Path
from tabulate import tabulate         
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo 
import pandas as pd



# ---------- utilidades ----------
def parse_size(size_str: str) -> float:
    """
    Convierte “100 GB”, “500 MB” o “2 TB” a GiB (float).
    Devuelve 0.0 si la cadena no es reconocible.
    """
    m = re.match(r"([\d.]+)\s*(GB|MB|TB)", size_str or "")
    if not m:
        return 0.0
    val, unit = float(m[1]), m[2]
    return val / 1024 if unit == "MB" else val * 1024 if unit == "TB" else val


def pick(d: dict, *keys):
    """
    Devuelve el primer valor existente en el dict `d`.
    Admite claves sueltas o listas/tuplas de claves alternativas.
    """
    for k in keys:
        if isinstance(k, (list, tuple)):
            for sub in k:
                if sub in d:
                    return d[sub]
        elif k in d:
            return d[k]
    return None


# ---------- cálculo de cada fila ----------
def fila(facts: dict, host_inv: str) -> dict:
    # --- IP & hostname ---
    ip = pick(facts, "ansible_default_ipv4", "default_ipv4") or {}
    ip = ip.get("address") or host_inv
    hostname = pick(facts, "ansible_hostname", "hostname", "fqdn") or host_inv

    # --- SO, kernel, arquitectura ---
    distro = pick(facts, "ansible_distribution", "distribution") or ""
    d_ver = pick(facts, "ansible_distribution_version", "distribution_version") or ""
    so = f"{distro} {d_ver}".strip()

    kernel = pick(facts, "ansible_kernel", "kernel") or ""
    arch = pick(facts, "ansible_architecture", "architecture", "machine") or ""

    # --- CPU ---
    cpu_lst = pick(facts, "ansible_processor", "processor") or []
    cpu = cpu_lst[2] if len(cpu_lst) > 2 else cpu_lst[-1] if cpu_lst else ""

    # ---------- MEMORIA ----------
    mem_total_mb = pick(facts, "ansible_memtotal_mb", "memtotal_mb") or 0
    mem_free_mb = pick(
        facts,
        "ansible_memfree_mb",
        "memfree_mb",
        ["ansible_memory_mb", "memory_mb"],
    ) or 0
    # memory_mb puede ser un dict {real:{total,free}}
    if isinstance(mem_free_mb, dict):
        mem_free_mb = mem_free_mb.get("real", {}).get("free", 0)

    mem_total_gb = math.ceil(mem_total_mb / 1024)
    mem_free_gb = math.ceil(mem_free_mb / 1024)
    mem_used_gb = mem_total_gb - mem_free_gb

    # ---------- DISCO ----------
    # 1. Tamaño físico de los dispositivos
    devs = pick(facts, "ansible_devices", "devices") or {}
    disk_total_gb = sum(
        parse_size(d.get("size", "0 GB"))
        for n, d in devs.items()
        if n.startswith(("sd", "nvme"))
    )

    # 2. Espacio ocupado / libre según mounts
    mounts = pick(facts, "ansible_mounts", "mounts") or []
    bytes_total = bytes_avail = 0
    for m in mounts:
        if not m.get("device", "").startswith(("/dev/sd", "/dev/nvme")):
            continue
        bytes_total += m.get("size_total", 0)
        bytes_avail += m.get("size_available", 0)

    disk_total_mnt_gb = round(bytes_total / 1024**3, 2)
    disk_free_gb = round(bytes_avail / 1024**3, 2)
    disk_used_gb = round(disk_total_mnt_gb - disk_free_gb, 2)

    # ---------- Puertos DB ----------
    
    db_cols = {
        "MySQL (3306)":      "Activo"   if facts.get("mysql",      False) else "Inactivo",
        "PostgreSQL (5432)": "Activo"   if facts.get("postgresql", False) else "Inactivo",
        "SQLServer (1433)":  "Activo"   if facts.get("sqlserver",  False) else "Inactivo",
        "Oracle (1521)":     "Activo"   if facts.get("oracle",     False) else "Inactivo",
        "MongoDB (27017)":    "Activo"   if facts.get("mongodb",    False) else "Inactivo",
    }

    # --- Tipo de máquina ---
    tipo = (
        "Virtual"
        if pick(facts, "ansible_virtualization_role", "virtualization_role") == "guest"
        else "Física"
    )

    puertos_txt = ", ".join(map(str, facts.get("listening_ports", [])))
   

    return {
        "Fecha y Hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "IP": ip,
        "Hostname": hostname,
        "SO": so,
        "Kernel": kernel,
        "Arquitectura": arch,
        "CPU": cpu,
        "RAM Total (GB)": mem_total_gb,
        "RAM Usada (GB)": mem_used_gb,
        "RAM Libre (GB)": mem_free_gb,
        "Disco Total (GB)": disk_total_gb,
        "Disco Usado (GB)": disk_used_gb,
        "Disco Libre (GB)": disk_free_gb,
        "Tipo de maquina": tipo,
        "Puertos en escucha": puertos_txt,
        **db_cols,  # columnas de puertos
    }



# ---------- main ----------
def main():
    if len(sys.argv) < 3:
        sys.exit("Uso: generar_excel.py <salida.xlsx> <glob_json>")

    salida, patron = sys.argv[1], sys.argv[2]
    filas = []

    for path in glob.glob(patron):
        with open(path, "r") as f:
            info = json.load(f)
        facts = info.get("ansible_facts", info)
        filas.append(fila(facts, info.get("inventory_hostname", "desconocido")))

    df = pd.DataFrame(filas).sort_values("IP")

    # ---------- EXCEL ----------
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Inventario DMZ", index=False)

        # --Ajuste de anchos
        hoja = writer.sheets["Inventario DMZ"]
        for i, col in enumerate(df.columns, 1):
            ancho = max(len(str(x)) for x in df[col].astype(str).tolist() + [col]) + 2
            hoja.column_dimensions[get_column_letter(i)].width = ancho

        # --Tabla estructurada para el excel--
         # ----- Crear tabla estructurada -----
        n_filas, n_cols = df.shape
        ultima_col = get_column_letter(n_cols)
        tabla = Table(
            displayName="InventarioDMZ",
            ref=f"A1:{ultima_col}{n_filas+1}"        
        )

        style = TableStyleInfo(
            name="TableStyleMedium9",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        tabla.tableStyleInfo = style
        hoja.add_table(tabla)
   

    # ---------- TXT ----------
    txt_path = Path(salida).with_suffix(".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        tabla = tabulate(df, headers="keys", tablefmt="grid", showindex=False)
        f.write(tabla + "\n")

    print(f"✅ Excel generado con {len(filas)} filas → {salida}")
    print(f"✅ TXT   generado con {len(filas)} filas → {txt_path}")

if __name__ == "__main__":
    main()