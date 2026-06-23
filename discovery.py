"""Descoberta automatica de impressoras Bambu na rede local (SSDP).

As impressoras Bambu se anunciam periodicamente via SSDP no UDP 2021
(multicast 239.255.255.250). Aqui ouvimos esses anuncios (e mandamos um
M-SEARCH para acelerar) e extraimos IP, numero de serie, modelo e nome.

O codigo de acesso NAO vem por aqui - ele e' secreto e so aparece na tela
da impressora (Modo LAN).
"""
import socket
import struct
import time

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 2021
M_SEARCH = (
    "M-SEARCH * HTTP/1.1\r\n"
    f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
    'MAN: "ssdp:discover"\r\n'
    "MX: 1\r\n"
    "ST: urn:bambulab-com:device:3dprinter:1\r\n"
    "\r\n"
).encode()


def _parse(text, src_ip):
    """Extrai os dados de um anuncio SSDP da Bambu; None se nao for Bambu."""
    if "bambulab" not in text.lower():
        return None
    headers = {}
    for line in text.split("\r\n"):
        chave, sep, valor = line.partition(":")
        if sep:
            headers[chave.strip().lower()] = valor.strip()
    serial = headers.get("usn", "")
    if not serial:
        return None
    return {
        "ip": headers.get("location", src_ip) or src_ip,
        "serial": serial,
        "model": headers.get("devmodel.bambu.com", ""),
        "name": headers.get("devname.bambu.com", ""),
    }


def discover(timeout=6):
    """Procura impressoras Bambu na rede por ate `timeout` segundos.

    Retorna lista de dicts: {ip, serial, model, name}. Lista vazia se nada achar.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind(("", SSDP_PORT))
    except OSError:
        try:
            sock.bind(("", 0))
        except OSError:
            sock.close()
            return []
    try:
        mreq = struct.pack("=4sl", socket.inet_aton(SSDP_ADDR), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    except OSError:
        pass
    try:
        sock.sendto(M_SEARCH, (SSDP_ADDR, SSDP_PORT))
    except OSError:
        pass

    sock.settimeout(1.0)
    encontradas = {}
    fim = time.time() + timeout
    while time.time() < fim:
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        info = _parse(data.decode("utf-8", "ignore"), addr[0])
        if info:
            encontradas[info["serial"]] = info
    sock.close()
    return list(encontradas.values())
