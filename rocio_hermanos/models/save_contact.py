import pandas as pd
import xmlrpc.client
from datetime import datetime

from urllib3.util.util import to_str

# -----------------------------
# CONFIGURACIÓN ODOO
# -----------------------------#cambiar a las credenciales correspondientes
url = "http://localhost:18069"
db = "devel2"
username = "admin"
password = "admin"#preguntar porque lo mejor es un Api-key en produccion

# -----------------------------
# CONEXIÓN
# -----------------------------
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# -----------------------------
# FUNCIONES AUXILIARES
# -----------------------------
def to_date(value):
    try:
        if pd.isna(value):
            return False
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")

        date = pd.to_datetime(value, dayfirst=True, errors="coerce")

        if pd.isna(date) or date.year < 1900:
            return False

        return date.strftime("%Y-%m-%d")

    except Exception:
        return False

def to_str(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def to_bool(value):
    return str(value).strip().upper() == "VERDADERO"

def get_country_id(name):
    if pd.isna(name):
        return False
    name_str = str(name).strip()
    if not name_str:
        return False
    ids = models.execute_kw(
        db, uid, password,
        "res.country", "search",
        [[("name", "=", name_str)]],
        {"limit": 1}
    )
    if ids:
        return ids[0]
    # Intenta búsqueda por código
    ids = models.execute_kw(
        db, uid, password,
        "res.country", "search",
        [[("code", "=", name_str.upper())]],
        {"limit": 1}
    )
    return ids[0] if ids else False

def get_state_id(country_id, state_name):
    if pd.isna(state_name) or not country_id:
        return False
    state_name_str = str(state_name).strip()
    if not state_name_str:
        return False

    if "(" in state_name_str:
        state_name_str = state_name_str.split("(")[0].strip()
    ids = models.execute_kw(
        db, uid, password,
        "res.country.state", "search",
        [[("name", "=", state_name_str), ("country_id", "=", country_id)]],
        {"limit": 1}
    )
    return ids[0] if ids else False

def get_partner_id_by_name(name):
    if pd.isna(name):
        return False
    ids = models.execute_kw(
        db, uid, password,
        "res.partner", "search",
        [[("name", "=", name)]],
        {"limit": 1}
    )
    return ids[0] if ids else False

def search_partner_by_name(name):
    """Busca un contacto por nombre y devuelve su ID si existe"""
    if pd.isna(name):
        return False
    ids = models.execute_kw(
        db, uid, password,
        "res.partner", "search",
        [[("name", "=", name)]],
        {"limit": 1}
    )
    return ids[0] if ids else False

def create_or_update_bank_account(partner_id, acc_number):
    """Crea o actualiza la cuenta bancaria del contacto"""
    if pd.isna(acc_number) or not acc_number:
        return False

    acc_number_str = str(acc_number).strip()
    if not acc_number_str:
        return False

    # Buscar si ya existe una cuenta bancaria con ese número para este partner
    existing_bank = models.execute_kw(
        db, uid, password,
        "res.partner.bank", "search",
        [[("acc_number", "=", acc_number_str), ("partner_id", "=", partner_id)]],
        {"limit": 1}
    )

    if existing_bank:
        # Si ya existe, actualizar
        models.execute_kw(
            db, uid, password,
            "res.partner.bank", "write",
            [existing_bank, {"acc_number": acc_number_str}]
        )
        return existing_bank[0]
    else:
        # Si no existe, crear nueva cuenta bancaria
        bank_id = models.execute_kw(
            db, uid, password,
            "res.partner.bank", "create",
            [{"acc_number": acc_number_str, "partner_id": partner_id}]
        )
        return bank_id

def map_payment(value):
    if value == "Banco":
        return "Banco"
    if value == "Recibo":
        return "efectivo"
    return False

# -----------------------------
# LEER EXCEL
# -----------------------------
df = pd.read_excel("HermanosLimpioPrueba.xlsx")

# -----------------------------
# IMPORTACIÓN (CREAR O ACTUALIZAR)
# -----------------------------
created_count = 0
updated_count = 0

for _, row in df.iterrows():
    contact_name = row["name"]

    # Obtener país primero
    country_id = get_country_id(row["País"])

    vals = {
        "name": contact_name,
        "street": row["Street"],
        "zip": to_str(row["C.P."]),
        "city": row["Ciudad"],
        "phone": to_str(row["TELEFONO"]),
        "email": to_str(row["EMAIL"]),

        "is_brother": True,
        "brother_district": to_str(row["DIST"]),
        "brother_birth_date": to_date(row["brother_birth_date"]),
        "brother_since": to_date(row["F ALTA"]),
        "brother_end_date": to_date(row["F BAJA"]),
        "brother_leave_reason": row["Motivo"],
        "brother_advertising": to_bool(row["PUBLI"]),
        "brother_method_of_payment": map_payment(row["F DE PAGO"]),
        "brother_delegated_partner_id": get_partner_id_by_name(row["DIRECCION DE COBRO"]),

        "country_id": country_id,
        "state_id": get_state_id(country_id, row["State_id"]),
    }

    # Buscar si el contacto ya existe por nombre
    existing_partner_id = search_partner_by_name(contact_name)

    if existing_partner_id:
        # ACTUALIZAR contacto existente
        models.execute_kw(
            db, uid, password,
            "res.partner", "write",
            [[existing_partner_id], vals]
        )
        partner_id = existing_partner_id
        updated_count += 1
        print(f"Actualizado: {contact_name}")
    else:
        # CREAR nuevo contacto
        partner_id = models.execute_kw(
            db, uid, password,
            "res.partner", "create",
            [vals]
        )
        created_count += 1
        print(f"Creado: {contact_name}")

    # Crear o actualizar cuenta bancaria si existe en el Excel
    if "Banco" in row and not pd.isna(row["Banco"]):
        create_or_update_bank_account(partner_id, row["Banco"])
        print(f"Cuenta bancaria asignada: {row['Banco']}")

print(f"\nImportación completada")
print(f"Creados: {created_count}")
print(f"Actualizados: {updated_count}")
