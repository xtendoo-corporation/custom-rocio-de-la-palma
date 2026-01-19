import base64
import openpyxl
from io import BytesIO
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RocioHermanoImportWizard(models.TransientModel):
    _name = "rocio.hermano.import.wizard"
    _description = "Importar hermanos desde Excel"

    file = fields.Binary(
        string="Archivo Excel",
        required=True,
        help="Archivo Excel con los datos de los hermanos",
    )
    filename = fields.Char(string="Nombre del archivo")

    # Contadores de resultados
    created_count = fields.Integer(string="Creados", readonly=True)
    updated_count = fields.Integer(string="Actualizados", readonly=True)
    error_count = fields.Integer(string="Errores", readonly=True)
    log_message = fields.Text(string="Log de importación", readonly=True)

    def _to_date(self, value):
        """Convierte un valor a fecha"""
        try:
            if value is None or value is False:
                return False
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d")

            # Si es un string, intentar parsear
            if isinstance(value, str):
                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
                    except ValueError:
                        continue
            return False
        except Exception:
            return False

    def _to_str(self, value):
        """Convierte un valor a cadena"""
        if value is None or value is False:
            return ""
        return str(value).strip()

    def _to_bool(self, value):
        """Convierte un valor a booleano"""
        if not value:
            return False
        return str(value).strip().upper() in ("VERDADERO", "TRUE", "1", "S", "SI")

    def _get_country_id(self, name):
        """Busca un país por nombre"""
        if not name:
            return False
        name_str = str(name).strip()
        if not name_str:
            return False

        country = self.env["res.country"].search([("name", "=", name_str)], limit=1)
        if country:
            return country.id

        # Intenta búsqueda por código
        country = self.env["res.country"].search(
            [("code", "=", name_str.upper())], limit=1
        )
        return country.id if country else False

    def _get_state_id(self, country_id, state_name):
        """Busca un estado por nombre y país"""
        if not state_name or state_name is None or not country_id:
            return False
        state_name_str = str(state_name).strip()
        if not state_name_str:
            return False

        if "(" in state_name_str:
            state_name_str = state_name_str.split("(")[0].strip()

        state = self.env["res.country.state"].search(
            [("name", "=", state_name_str), ("country_id", "=", country_id)], limit=1
        )
        return state.id if state else False

    def _get_partner_id_by_name(self, name):
        """Busca un contacto por nombre"""
        if not name or name is None:
            return False
        partner = self.env["res.partner"].search([("name", "=", name)], limit=1)
        return partner.id if partner else False

    def _autocomplete_spanish_address(self, zip_code, country_id):
        """Autocompleta dirección española basándose en código postal usando l10n_es_toponyms"""
        if not zip_code or not country_id:
            return {}

        # Verificar que es España
        spain = self.env["res.country"].browse(country_id)
        if not spain or spain.code != "ES":
            return {}

        zip_str = str(zip_code).strip()
        if not zip_str or len(zip_str) != 5 or not zip_str.isdigit():
            return {}

        print(f"Intentando autocompletado español para CP: {zip_str}")

        try:
            # Método 1: Intentar usar directamente l10n_es_toponyms
            if 'res.better.zip' in self.env:
                better_zip = self.env['res.better.zip'].search([
                    ('name', '=', zip_str),
                    ('country_id', '=', country_id)
                ], limit=1)

                if better_zip:
                    result = {
                        'city': better_zip.city,
                        'state_id': better_zip.state_id.id if better_zip.state_id else False,
                    }
                    print(f"Encontrado en better_zip: {result}")
                    return result

            # Método 2: Crear partner temporal y usar onchange
            temp_partner = self.env["res.partner"].new({
                'zip': zip_str,
                'country_id': country_id
            })

            # Intentar diferentes métodos de onchange según la versión del módulo
            methods_to_try = ['_onchange_zip', 'onchange_zip', '_onchange_zip_id']

            for method_name in methods_to_try:
                if hasattr(temp_partner, method_name):
                    print(f"Ejecutando {method_name}")
                    try:
                        method = getattr(temp_partner, method_name)
                        method()

                        if temp_partner.city:
                            result = {
                                'city': temp_partner.city,
                                'state_id': temp_partner.state_id.id if temp_partner.state_id else False,
                            }
                            print(f"Autocompletado con {method_name}: {result}")
                            return result
                    except Exception as e:
                        print(f"Error en {method_name}: {e}")
                        continue

            # Método 3: Buscar directamente en res.country.state por código postal
            # Los códigos postales españoles tienen patrones por provincia
            province_codes = {
                '01': 'Álava', '02': 'Albacete', '03': 'Alicante', '04': 'Almería',
                '05': 'Ávila', '06': 'Badajoz', '07': 'Baleares', '08': 'Barcelona',
                '09': 'Burgos', '10': 'Cáceres', '11': 'Cádiz', '12': 'Castellón',
                '13': 'Ciudad Real', '14': 'Córdoba', '15': 'A Coruña', '16': 'Cuenca',
                '17': 'Girona', '18': 'Granada', '19': 'Guadalajara', '20': 'Gipuzkoa',
                '21': 'Huelva', '22': 'Huesca', '23': 'Jaén', '24': 'León',
                '25': 'Lleida', '26': 'La Rioja', '27': 'Lugo', '28': 'Madrid',
                '29': 'Málaga', '30': 'Murcia', '31': 'Navarra', '32': 'Ourense',
                '33': 'Asturias', '34': 'Palencia', '35': 'Las Palmas', '36': 'Pontevedra',
                '37': 'Salamanca', '38': 'Santa Cruz de Tenerife', '39': 'Cantabria',
                '40': 'Segovia', '41': 'Sevilla', '42': 'Soria', '43': 'Tarragona',
                '44': 'Teruel', '45': 'Toledo', '46': 'Valencia', '47': 'Valladolid',
                '48': 'Bizkaia', '49': 'Zamora', '50': 'Zaragoza', '51': 'Ceuta', '52': 'Melilla'
            }

            province_code = zip_str[:2]
            if province_code in province_codes:
                province_name = province_codes[province_code]
                state = self.env['res.country.state'].search([
                    ('name', 'ilike', province_name),
                    ('country_id', '=', country_id)
                ], limit=1)

                if state:
                    result = {'state_id': state.id}
                    print(f"Autocompletado por código provincial: {province_name} -> {result}")
                    return result

        except Exception as e:
            print(f"Error en autocompletado español: {e}")

        return {}


    def _create_or_update_bank_account(self, partner_id, acc_number):
        """Crea o actualiza la cuenta bancaria del contacto"""
        if not acc_number:
            return False

        acc_number_str = str(acc_number).strip()
        if not acc_number_str:
            return False

        # Buscar si ya existe una cuenta bancaria con ese número para este partner
        existing_bank = self.env["res.partner.bank"].search(
            [("acc_number", "=", acc_number_str), ("partner_id", "=", partner_id)],
            limit=1,
        )

        if existing_bank:
            return existing_bank.id
        else:
            # Si no existe, crear nueva cuenta bancaria
            bank = self.env["res.partner.bank"].create(
                {"acc_number": acc_number_str, "partner_id": partner_id}
            )
            return bank.id

    def _map_payment(self, value):
        """Mapea el método de pago"""
        if value == "Banco":
            return "Banco"
        if value == "Recibo":
            return "efectivo"
        return False

    def action_import(self):
        """Importa los hermanos desde el archivo Excel"""
        self.ensure_one()

        if not self.file:
            raise UserError(_("Debe cargar un archivo Excel"))

        try:
            # Decodificar el archivo
            file_content = base64.b64decode(self.file)
            wb = openpyxl.load_workbook(BytesIO(file_content), data_only=True)
            sheet = wb.active
        except Exception as e:
            raise UserError(_("Error al leer el archivo Excel: %s") % str(e))

        # Obtener encabezados
        headers = {cell.value: i for i, cell in enumerate(sheet[1]) if cell.value}
        print(f"=== ENCABEZADOS ENCONTRADOS ===")
        print(f"Headers: {list(headers.keys())}")
        print(f"Total columnas: {len(headers)}")

        # Validar que el archivo tenga las columnas necesarias
        required_columns = ["name"]
        missing_columns = [col for col in required_columns if col not in headers]
        if missing_columns:
            raise UserError(
                _("El archivo Excel no tiene las columnas necesarias: %s")
                % ", ".join(missing_columns)
            )

        created_count = 0
        updated_count = 0
        error_count = 0
        log_lines = []

        for row_idx, row in enumerate(
            sheet.iter_rows(min_row=2, values_only=True), start=2
        ):
            try:
                # Mapear fila a diccionario usando encabezados
                row_data = {h: row[i] for h, i in headers.items() if i < len(row)}

                print(f"\n=== FILA {row_idx} ===")
                print(f"Datos completos de la fila:")
                for key, value in row_data.items():
                    print(f"  {key}: '{value}' (tipo: {type(value)})")

                contact_name = row_data.get("name")
                if not contact_name:
                    error_count += 1
                    log_lines.append(_("Fila %s: No se especificó un nombre") % row_idx)
                    continue

                # Obtener país primero
                country_id = self._get_country_id(row_data.get("País"))
                print(f"País obtenido: {row_data.get('País')} -> ID: {country_id}")
                print(f"Ciudad obtenida: '{row_data.get('Ciudad')}'")
                print(f"Street obtenida: '{row_data.get('Street')}'")

                # Buscar código postal en diferentes formatos posibles
                zip_code = (row_data.get("C.P."))
                zip_code = self._to_str(zip_code)
                print(f"Código Postal encontrado: '{zip_code}'")

                # Intentar autocompletar dirección española si no hay ciudad pero sí código postal
                city = row_data.get("Ciudad")
                state_id = self._get_state_id(country_id, row_data.get("State_id"))

                print(f"Antes autocompletado: Ciudad='{city}', CP='{zip_code}', Estado={state_id}")

                # Si hay código postal, intentar autocompletar
                if zip_code:
                    # Si no tenemos país, intentar determinarlo por el código postal
                    if not country_id and len(zip_code) == 5 and zip_code.isdigit():
                        # Asumir España para códigos postales de 5 dígitos
                        spain = self.env["res.country"].search([("code", "=", "ES")], limit=1)
                        if spain:
                            country_id = spain.id
                            print(f"País determinado por CP: España")

                    if country_id:
                        spain = self.env["res.country"].browse(country_id)
                        if spain and spain.code == "ES":
                            print(f"Es España, intentando autocompletar con CP: {zip_code}")
                            autocomplete_data = self._autocomplete_spanish_address(zip_code, country_id)
                            if autocomplete_data:
                                # Solo usar ciudad si no la tenemos
                                if not city or str(city).strip() == '':
                                    city = autocomplete_data.get('city', city)
                                # Solo usar estado si no lo tenemos
                                if not state_id:
                                    state_id = autocomplete_data.get('state_id', state_id)
                                # IMPORTANTE: No cambiar el país si ya teníamos uno
                                # country_id ya está establecido correctamente
                                print(f"Después autocompletado: Ciudad='{city}', Estado={state_id}")
                            else:
                                print("No se pudo autocompletar")
                        else:
                            print(f"No es España (código: {spain.code if spain else 'None'})")
                    else:
                        print("Sin país determinado para autocompletar")

                # Validar consistencia entre país y código postal
                if country_id and zip_code:
                    country = self.env["res.country"].browse(country_id)
                    if country.code == "ES" and len(zip_code) == 5 and zip_code.isdigit():
                        print(f"✓ Consistencia España-CP: {zip_code} es válido para España")
                    elif country.code != "ES" and len(zip_code) == 5 and zip_code.isdigit():
                        print(f"⚠ Posible inconsistencia: CP {zip_code} parece español pero país es {country.name}")
                        # Opción: cambiar país a España si el CP es claramente español
                        if zip_code.startswith(('0', '1', '2', '3', '4', '5')):
                            spain = self.env["res.country"].search([("code", "=", "ES")], limit=1)
                            if spain:
                                print(f"Cambiando país a España por CP {zip_code}")
                                country_id = spain.id

                vals = {
                    "name": contact_name,
                    "street": row_data.get("Street"),
                    "zip": zip_code,
                    "city": city,
                    "phone": self._to_str(row_data.get("TELEFONO")),
                    "email": self._to_str(row_data.get("EMAIL")),
                    "is_brother": True,
                    "brother_district": self._to_str(row_data.get("DIST")),
                    "brother_birth_date": self._to_date(
                        row_data.get("brother_birth_date")
                    ),
                    "brother_since": self._to_date(row_data.get("F ALTA")),
                    "brother_end_date": self._to_date(row_data.get("F BAJA")),
                    "brother_advertising": self._to_bool(row_data.get("PUBLI")),
                    "brother_method_of_payment": self._map_payment(
                        row_data.get("F DE PAGO")
                    ),
                    "brother_delegated_partner_id": self._get_partner_id_by_name(
                        row_data.get("DIRECCION DE COBRO")
                    ),
                    "country_id": country_id,
                    "state_id": state_id,
                }

                print(f"Valores finales para crear/actualizar contacto:")
                for key, value in vals.items():
                    print(f"  {key}: '{value}'")

                # Buscar si el contacto ya existe por nombre
                existing_partner = self.env["res.partner"].search(
                    [("name", "=", contact_name)], limit=1
                )

                if existing_partner:
                    # ACTUALIZAR contacto existente
                    print(f"ACTUALIZANDO contacto existente: {contact_name}")
                    try:
                        existing_partner.write(vals)
                        partner_id = existing_partner.id
                        updated_count += 1
                        log_lines.append(_("Actualizado: %s") % contact_name)
                    except Exception as e:
                        error_msg = str(e)
                        if "difiere del de la ubicación" in error_msg and zip_code:
                            # Error de inconsistencia país-código postal, intentar corregir
                            print(f"Error de inconsistencia país-CP, intentando corregir...")
                            spain = self.env["res.country"].search([("code", "=", "ES")], limit=1)
                            if spain:
                                vals["country_id"] = spain.id
                                print(f"Corregido país a España para {contact_name}")
                                existing_partner.write(vals)
                                partner_id = existing_partner.id
                                updated_count += 1
                                log_lines.append(_("Actualizado (país corregido): %s") % contact_name)
                            else:
                                raise e
                        else:
                            raise e
                else:
                    # CREAR nuevo contacto
                    print(f"CREANDO nuevo contacto: {contact_name}")
                    try:
                        partner = self.env["res.partner"].create(vals)
                        partner_id = partner.id
                        created_count += 1
                        log_lines.append(_("Creado: %s") % contact_name)
                    except Exception as e:
                        error_msg = str(e)
                        if "difiere del de la ubicación" in error_msg and zip_code:
                            # Error de inconsistencia país-código postal, intentar corregir
                            print(f"Error de inconsistencia país-CP, intentando corregir...")
                            spain = self.env["res.country"].search([("code", "=", "ES")], limit=1)
                            if spain:
                                vals["country_id"] = spain.id
                                print(f"Corregido país a España para {contact_name}")
                                partner = self.env["res.partner"].create(vals)
                                partner_id = partner.id
                                created_count += 1
                                log_lines.append(_("Creado (país corregido): %s") % contact_name)
                            else:
                                raise e
                        else:
                            raise e

                # Crear o actualizar cuenta bancaria si existe en el Excel
                if "Banco" in row_data and row_data.get("Banco"):
                    print(f"Procesando cuenta bancaria: {row_data.get('Banco')}")
                    self._create_or_update_bank_account(
                        partner_id, row_data.get("Banco")
                    )
                    log_lines.append(
                        _("  → Cuenta bancaria asignada: %s") % row_data.get("Banco")
                    )

            except Exception as e:
                error_count += 1
                log_lines.append(_("Fila %s - Error: %s") % (row_idx, str(e)))

        # Actualizar contadores y log
        self.write(
            {
                "created_count": created_count,
                "updated_count": updated_count,
                "error_count": error_count,
                "log_message": "\n".join(log_lines),
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Resultado de la importación"),
            "res_model": "rocio.hermano.import.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
