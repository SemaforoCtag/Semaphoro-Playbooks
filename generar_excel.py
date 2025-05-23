#!/usr/bin/env python3

import sys
import json
import glob
import os
import pandas as pd

def extraer_datos(fichero_json):
    with open(fichero_json, 'r') as f:
        data = json.load(f)

    hostname = data.get("ansible_hostname", "Desconocido")
    os_info = f"{data.get('ansible_distribution', '')} {data.get('ansible_distribution_version', '')}"
    kernel = data.get("ansible_kernel", "")
    arquitectura = data.get("ansible_architecture", "")
    cpu = data.get("ansible_processor", [""])[-1]
    nucleos = data.get("ansible_processor_cores", 0)
    logicos = data.get("ansible_processor_count", 0)
    ram = round(int(data.get("ansible_memtotal_mb", 0)) / 1024, 2)
    tipo_maquina = "Desconocido"

    if data.get("ansible_virtualization_role") == "guest":
        tipo_maquina = f"Máquina Virtual ({data.get('ansible_virtualization_type', '')})"
    elif data.get("ansible_virtualization_role") == "host":
        tipo_maquina = f"Host de Virtualización ({data.get('ansible_virtualization_type', '')})"
    else:
        tipo_maquina = "Equipo físico"

    discos = []
    for device, info in data.get("ansible_devices", {}).items():
        if device.startswith('sd') or device.startswith('nvme'):
            discos.append(f"{device}: {info.get('size', 'desconocido')}")
    disco_duro = "; ".join(discos)

    return {
        "Hostname": hostname,
        "Sistema Operativo": os_info,
        "Kernel": kernel,
        "Arquitectura": arquitectura,
        "CPU": cpu,
        "Núcleos Físicos": nucleos,
        "Núcleos Lógicos": logicos,
        "RAM (GB)": ram,
        "Tipo de Máquina": tipo_maquina,
        "Disco(s)": disco_duro
    }

def main():
    if len(sys.argv) < 3:
        print("Uso: generar_excel.py <ruta_salida_excel.xlsx> <ficheros_json>")
        sys.exit(1)

    salida_excel = sys.argv[1]
    patrones_json = sys.argv[2:]

    datos = []
    for patron in patrones_json:
        for fichero in glob.glob(patron):
            datos.append(extraer_datos(fichero))

    df = pd.DataFrame(datos)
    df.to_excel(salida_excel, index=False)

if __name__ == "__main__":
    main()
