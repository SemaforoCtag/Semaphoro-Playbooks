#!/usr/bin/env python3
"""
Genera Inventario_Equipos_DMZ.xlsx y su versión TXT.
"""

import sys, json, glob, math, re
from datetime import datetime
from pathlib import Path
import pandas as pd
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from tabulate import tabulate

# ───────────────────────── utilidades ──────────────────────────
def parse_size(size_str: str) -> float:
    m = re.match(r"([\d.]+)\s*(GB|MB|TB)", size_str or "")
    if not m:
        return 0.0
    val, unit = float(m[1]), m[2]
    return val / 1024 if unit == "MB" else val * 1024 if unit == "TB" else val

def pick(d: dict, *keys):
    for k in keys:
        if isinstance(k, (list, tuple)):
            for sub in k:
                if sub in d:
                    return d[sub]
        elif k in d:
            return d[k]
    return None

# ──────────── fila para el DataFrame, datos del equipo ────────────
def fila(facts: dict, host_inv: str, datos_json: dict) -> dict:
    ipdata = pick(facts, "ansible_default_ipv4", "default_ipv4") or {}
    ip       = ipdata.get("address") or host_inv
    hostname = pick(facts, "ansible_hostname", "hostname", "fqdn") or host_inv

    distro = pick(facts, "ansible_distribution", "distribution") or ""
    d_ver  = pick(facts, "ansible_distribution_version", "distribution_version") or ""
    so     = f"{distro} {d_ver}".strip()

    kernel = pick(facts, "ansible_kernel", "kernel") or ""
    arch   = pick(facts, "ansible_architecture", "architecture", "machine") or ""

    cpu_lst = pick(facts, "ansible_processor", "processor") or []
    cpu = cpu_lst[2] if len(cpu_lst) > 2 else cpu_lst[-1] if cpu_lst else ""

    mem_total_mb = pick(facts, "ansible_memtotal_mb", "memtotal_mb") or 0
    mem_free_mb  = pick(facts, "ansible_memfree_mb", "memfree_mb",
                        ["ansible_memory_mb", "memory_mb"]) or 0
    if isinstance(mem_free_mb, dict):
        mem_free_mb = mem_free_mb.get("real", {}).get("free", 0)
    mem_total_gb = math.ceil(mem_total_mb / 1024)
    mem_free_gb  = math.ceil(mem_free_mb / 1024)
    mem_used_gb  = mem_total_gb - mem_free_gb

    devs = pick(facts, "ansible_devices", "devices") or {}
    disk_total_gb = sum(parse_size(d.get("size", "0 GB"))
                        for n, d in devs.items() if n.startswith(("sd", "nvme")))
    mounts = pick(facts, "ansible_mounts", "mounts") or []
    bytes_total = bytes_avail = 0
    for m in mounts:
        if not m.get("device", "").startswith(("/dev/sd", "/dev/nvme")):
            continue
        bytes_total += m.get("size_total", 0)
        bytes_avail += m.get("size_available", 0)
    disk_total_mnt_gb = round(bytes_total / 1024**3, 2)
    disk_free_gb      = round(bytes_avail / 1024**3, 2)
    disk_used_gb      = round(disk_total_mnt_gb - disk_free_gb, 2)

    # puertos de bases de datos 
    db_cols = {
        "MySQL (3306)":      "Activo"  if facts.get("mysql")      else "Inactivo",
        "PostgreSQL (5432)": "Activo"  if facts.get("postgresql") else "Inactivo",
        "SQLServer (1433)":  "Activo"  if facts.get("sqlserver")  else "Inactivo",
        "Oracle (1521)":     "Activo"  if facts.get("oracle")     else "Inactivo",
        "MongoDB (27017)":   "Activo"  if facts.get("mongodb")    else "Inactivo",
    }

    tipo = "Virtual" if pick(facts, "ansible_virtualization_role", "virtualization_role") == "guest" else "Física"
    puertos_txt = ", ".join(map(str, facts.get("listening_ports", [])))

    usuarios_brutos = datos_json.get("usuarios", [])
    usuarios_limpios = []
    usuarios_estructurados = []
    grupos_limpios = []

    modo = None
    for linea in usuarios_brutos:
        if "Usuarios del sistema" in linea:
            modo = "usuarios"
            continue
        elif "Grupos del sistema" in linea:
            modo = "grupos"
            continue

        if modo == "usuarios":
            usuarios_limpios.append(linea)
        elif modo == "grupos":
            partes = linea.split(":")
            if len(partes) >= 4:
                nombre_grupo = partes[0]
                miembros = partes[3].split(",") if partes[3] else []
                miembros_limpios = ", ".join(miembros)
                grupos_limpios.append(f"{nombre_grupo}: {miembros_limpios}")
            else:
                grupos_limpios.append(linea)

    for linea in usuarios_limpios:
        match = re.match(r"([\w\-]+)\s+\(UID:\s*(\d+),\s*GID:\s*(\d+),\s*Shell:\s*(.*?)\)", linea)
        if match:
            nombre, uid, gid, shell = match.groups()
            login_habilitado = "Sí" if shell not in ["/usr/sbin/nologin", "/bin/false", "nologin"] else "No"
            usuarios_estructurados.append({
            "Usuario": nombre,
            "UID": uid,
            "GID": gid,
            "Login": login_habilitado
        })
        else:
            usuarios_estructurados.append(linea)

    filas_por_equipo = []
    for usuario in usuarios_estructurados:
        filas_por_equipo.append({
            "FechaHora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "IP": ip,
            "Host": hostname,
            "Usuario": usuario["Usuario"],
            "UID": usuario["UID"],
            "GID": usuario["GID"],
            "Login": usuario["Login"],
            "grupos": grupos_limpios,
            "SO": so,
            "CPU": cpu,
            "RAMTot": mem_total_gb,
            "RAMUsed": mem_used_gb,
            "DSKT": disk_total_gb,
            "Tipo": tipo,
            "Puertos": puertos_txt,
            **db_cols,
            "Kernel": kernel,
            "Arch": arch,
            "RAMFree": mem_free_gb,
            "DSKU": disk_used_gb,
            "DSKF": disk_free_gb,
        })
    return filas_por_equipo


# ─────────────────────────── main ────────────────────────────
def main():
    if len(sys.argv) < 3:
        sys.exit("Uso: generar_excel.py <salida.xlsx> <glob_json>")

    salida, patron = sys.argv[1], sys.argv[2]
    filas = []

    for path in glob.glob(patron):
        with open(path, "r") as f:
            info = json.load(f)
        facts = info.get("ansible_facts", info)
        filas.extend(fila(facts, info.get("inventory_hostname", "desconocido"), info))

    df = pd.DataFrame(filas).sort_values("IP")

    # ---------- EXCEL ----------
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Inventario DMZ", index=False)
        hoja = writer.sheets["Inventario DMZ"]
        for i, col in enumerate(df.columns, 1):
            ancho = max(len(str(x)) for x in df[col].astype(str).tolist() + [col]) + 2
            hoja.column_dimensions[get_column_letter(i)].width = ancho
        n_filas, n_cols = df.shape
        ultima_col = get_column_letter(n_cols)
        tabla = Table(displayName="InventarioDMZ", ref=f"A1:{ultima_col}{n_filas+1}")
        tabla.tableStyleInfo = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
        hoja.add_table(tabla)

    # ---------- TXT ----------
    txt_path = Path(salida).with_suffix(".txt")
    cols_txt = ["FechaHora", "IP", "Host", "SO", "CPU", "RAMTot", "Puertos",
                "MySQL (3306)", "PostgreSQL (5432)", "SQLServer (1433)"]
    df_txt = df[cols_txt].copy()

    def resume_puertos(p):
        lst = [x.strip() for x in p.split(",")] if p else []
        return ", ".join(lst[:5]) + (f", +{len(lst)-5}" if len(lst) > 5 else "")
    df_txt["Puertos"] = df_txt["Puertos"].apply(resume_puertos)

    tabla_ascii = tabulate(df_txt, headers="keys", tablefmt="pretty", showindex=False)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(tabla_ascii + "\n")

    print(f"✅ Excel generado → {salida}")
    print(f"✅ TXT   generado → {txt_path}")

if __name__ == "__main__":
    main()
