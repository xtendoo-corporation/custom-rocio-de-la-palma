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
        """Convierte un valor a fecha. Formatos soportados: MM/DD/YY, DD/MM/YYYY, YYYY-MM-DD"""
        try:
            if value is None or value is False:
                return False

            # Si ya es datetime
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d")

            # Convertir a string y limpiar
            value_str = str(value).strip()
            if not value_str or value_str.upper() in ("NONE", "NULL", "N/A"):
                return False

            # Quitar la parte de hora si existe (todo después del espacio)
            if " " in value_str:
                value_str = value_str.split(" ")[0]

            # Intentar parsear con diferentes formatos
            # Orden de prioridad: primero formato Excel MM/DD/YY, luego otros formatos
            formats_to_try = [
                "%m/%d/%y",    # MM/DD/YY (formato Excel de 2 dígitos) - ej: 02/11/83
                "%m/%d/%Y",    # MM/DD/YYYY (formato Excel de 4 dígitos)
                "%d/%m/%Y",    # DD/MM/YYYY (formato español tradicional)
                "%Y-%m-%d",    # YYYY-MM-DD (formato ISO)
                "%d-%m-%Y",    # DD-MM-YYYY (formato español con guiones)
            ]

            for fmt in formats_to_try:
                try:
                    parsed_date = datetime.strptime(value_str, fmt)

                    # Ajustar años de 2 dígitos si es necesario
                    # Python interpreta 00-68 como 2000-2068 y 69-99 como 1969-1999
                    # Para fechas de nacimiento, ajustar si el año está muy en el futuro
                    if fmt == "%m/%d/%y" and parsed_date.year > datetime.now().year + 10:
                        # Si la fecha está más de 10 años en el futuro, probablemente
                        # debería ser del siglo pasado (ej: 55 -> 1955 no 2055)
                        parsed_date = parsed_date.replace(year=parsed_date.year - 100)

                    return parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    continue

            return False
        except Exception:
            return False

    def _to_str(self, value):
        """Convierte un valor a cadena"""
        if value is None or value is False:
            return ""
        value_str = str(value).strip()
        # Filtrar "None" como string
        if value_str.upper() in ("NONE", "NULL", "N/A"):
            return ""
        return value_str

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
                    try:
                        method = getattr(temp_partner, method_name)
                        method()

                        if temp_partner.city:
                            result = {
                                'city': temp_partner.city,
                                'state_id': temp_partner.state_id.id if temp_partner.state_id else False,
                            }
                            return result
                    except Exception:
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
                    return result

        except Exception:
            pass

        return {}


    def _create_or_update_bank_account(self, partner_id, acc_number):
        """Crea o actualiza la cuenta bancaria del contacto y crea mandato SEPA"""
        if not acc_number:
            return False

        acc_number_str = str(acc_number).strip()
        if not acc_number_str:
            return False

        company = self.env.company

        # Buscar si ya existe una cuenta bancaria con ese número para este partner
        existing_bank = self.env["res.partner.bank"].search(
            [("acc_number", "=", acc_number_str), ("partner_id", "=", partner_id)],
            limit=1,
        )

        bank_id = False
        bank_record = False
        if existing_bank:
            bank_id = existing_bank.id
            bank_record = existing_bank
        else:
            # Si no existe, crear nueva cuenta bancaria con company_id
            bank_record = self.env["res.partner.bank"].create({
                "acc_number": acc_number_str,
                "partner_id": partner_id,
                "company_id": company.id,
            })
            bank_id = bank_record.id

        # Si se obtuvo una cuenta bancaria válida, crear mandato SEPA y asignar modo de pago
        if bank_id and bank_record:
            # Usar el método seguro que crea el modo de pago si no existe
            sepa_payment_mode = self.env['account.payment.mode']._create_sepa_direct_debit_mode_if_not_exists()

            if sepa_payment_mode:
                partner = self.env["res.partner"].browse(partner_id)
                partner.write({"customer_payment_mode_id": sepa_payment_mode.id})

            # Crear mandato SEPA si no existe uno válido para esta cuenta bancaria
            existing_mandate = self.env["account.banking.mandate"].search([
                ("partner_bank_id", "=", bank_id),
                ("state", "=", "valid"),
                ("company_id", "=", company.id),
            ], limit=1)

            if not existing_mandate:
                # Crear mandato SEPA válido automáticamente
                self.env["account.banking.mandate"].create({
                    "format": "sepa",
                    "type": "recurrent",
                    "recurrent_sequence_type": "first",
                    "signature_date": fields.Date.today(),
                    "partner_bank_id": bank_id,
                    "company_id": company.id,
                    "state": "valid",
                    "scheme": "CORE",  # Esquema SEPA CORE para particulares
                })

        return bank_id

    def _get_or_create_manual_payment_mode(self):
        """Obtiene o crea un modo de pago manual (Recibo) para clientes"""
        company = self.env.company

        # Buscar modo de pago manual existente
        manual_mode = self.env["account.payment.mode"].search([
            ("name", "ilike", "Recibo"),
            ("company_id", "=", company.id),
            ("payment_type", "=", "inbound"),
        ], limit=1)

        if not manual_mode:
            # Buscar también por "Manual" o "Efectivo"
            manual_mode = self.env["account.payment.mode"].search([
                "|", "|",
                ("name", "ilike", "Manual"),
                ("name", "ilike", "Efectivo"),
                ("name", "ilike", "Cash"),
                ("company_id", "=", company.id),
                ("payment_type", "=", "inbound"),
            ], limit=1)

        if not manual_mode:
            # Si no existe, intentar crear uno
            try:
                # Buscar método de pago manual
                manual_method = self.env["account.payment.method"].search([
                    ("code", "=", "manual"),
                    ("payment_type", "=", "inbound"),
                ], limit=1)

                if manual_method:
                    # Buscar un diario de banco o efectivo
                    journal = self.env["account.journal"].search([
                        ("type", "in", ["bank", "cash"]),
                        ("company_id", "=", company.id),
                    ], limit=1)

                    if journal:
                        manual_mode = self.env["account.payment.mode"].create({
                            "name": "Recibo",
                            "company_id": company.id,
                            "bank_account_link": "fixed",
                            "fixed_journal_id": journal.id,
                            "payment_method_id": manual_method.id,
                            "payment_type": "inbound",
                        })
            except Exception:
                pass

        return manual_mode

    def _map_language(self, value):
        """Mapea el idioma según el valor del campo lang"""
        if not value:
            return "es_ES"  # Español por defecto

        value_str = str(value).strip().lower()

        # Si contiene "españa" o "spanish" o "español", usar español
        if any(word in value_str for word in ["españa", "spanish", "español", "espana", "es"]):
            return "es_ES"  # Español de España

        # En cualquier otro caso, inglés
        return "en_US"

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

                # Validar que REGISTRO (ref) está presente - es obligatorio
                ref_value = self._to_str(row_data.get("REGISTRO"))
                if not ref_value:
                    error_count += 1
                    log_lines.append(_("Fila %s: Campo REGISTRO (referencia) obligatorio y vacío") % row_idx)
                    continue

                contact_name = row_data.get("name")
                if not contact_name:
                    error_count += 1
                    log_lines.append(_("Fila %s: No se especificó un nombre") % row_idx)
                    continue

                # Obtener país primero
                country_id = self._get_country_id(row_data.get("País"))

                # Buscar código postal en diferentes formatos posibles
                zip_code = row_data.get("zip_code") or row_data.get("C.P.") or row_data.get("C POSTAL")
                zip_code = self._to_str(zip_code)

                # Obtener ciudad del Excel
                city = self._to_str(row_data.get("city") or row_data.get("Ciudad"))

                # Obtener provincia/estado del Excel (buscar por nombre)
                state_name = self._to_str(row_data.get("state_id") or row_data.get("State_id") or row_data.get("PROVINCIA"))

                state_id = False
                if state_name:
                    # Primero buscar con país si lo tenemos
                    if country_id:
                        state_id = self._get_state_id(country_id, state_name)

                    # Si no encontramos el estado, buscar sin país
                    if not state_id:
                        state = self.env["res.country.state"].search([
                            ("name", "ilike", state_name.strip())
                        ], limit=1)
                        if state:
                            state_id = state.id
                            # Si encontramos estado, usar su país
                            if not country_id:
                                country_id = state.country_id.id

                # Si hay código postal, intentar autocompletar
                if zip_code:
                    # Si no tenemos país, intentar determinarlo por el código postal
                    if not country_id and len(zip_code) == 5 and zip_code.isdigit():
                        # Asumir España para códigos postales de 5 dígitos
                        spain = self.env["res.country"].search([("code", "=", "ES")], limit=1)
                        if spain:
                            country_id = spain.id

                    if country_id:
                        spain = self.env["res.country"].browse(country_id)
                        if spain and spain.code == "ES":
                            autocomplete_data = self._autocomplete_spanish_address(zip_code, country_id)
                            if autocomplete_data:
                                # Solo usar ciudad si no la tenemos
                                if not city or str(city).strip() == '':
                                    city = autocomplete_data.get('city', city)
                                # Solo usar estado si no lo tenemos
                                if not state_id:
                                    state_id = autocomplete_data.get('state_id', state_id)
                        else:
                            pass

                # Debug de fechas
                birth_date_raw = row_data.get("brother_birth_date") or row_data.get("NACIMIENTO")
                birth_date_parsed = self._to_date(birth_date_raw)

                since_date_raw = row_data.get("F ALTA")
                since_date_parsed = self._to_date(since_date_raw)

                vals = {
                    "ref": ref_value,
                    "name": contact_name,
                    "street": self._to_str(row_data.get("Street") or row_data.get("DIRECCION")),
                    "zip": zip_code,
                    "city": city,
                    "phone": self._to_str(row_data.get("TELEFONO")),
                    "email": self._to_str(row_data.get("EMAIL")),
                    "lang": self._map_language(row_data.get("lang")),
                    "is_brother": True,
                    "brother_district": self._to_str(row_data.get("DIST")),
                    "brother_birth_date": birth_date_parsed,
                    "brother_since": since_date_parsed,
                    "brother_end_date": self._to_date(row_data.get("F BAJA")),
                    "brother_advertising": self._to_bool(row_data.get("PUBLI")),
                    "brother_delegated_partner_id": self._get_partner_id_by_name(
                        row_data.get("DIRECCION DE COBRO")
                    ),
                    "country_id": country_id,
                    "state_id": state_id,
                }



                # Buscar si el contacto ya existe
                # IMPORTANTE: Usamos UN SOLO método de búsqueda, no ambos
                # Si hay ref → buscar SOLO por ref
                # Si no hay ref → buscar SOLO por nombre
                existing_partner = False
                search_method = None

                if ref_value:
                    # Búsqueda exclusiva por referencia
                    existing_partner = self.env["res.partner"].search(
                        [("ref", "=", ref_value)], limit=1
                    )
                    search_method = "ref"
                else:
                    # Búsqueda exclusiva por nombre (solo si no hay ref)
                    existing_partner = self.env["res.partner"].search(
                        [("name", "=", contact_name)], limit=1
                    )
                    search_method = "name"

                if existing_partner:
                    # ACTUALIZAR contacto existente
                    try:
                        existing_partner.write(vals)
                        partner_id = existing_partner.id
                        updated_count += 1
                        log_lines.append(_("Actualizado (por %s): %s") % (search_method, contact_name))
                    except Exception as e:
                        error_msg = str(e)
                        if "difiere del de la ubicación" in error_msg and zip_code:
                            # Error de inconsistencia país-código postal, intentar corregir
                            spain = self.env["res.country"].search([("code", "=", "ES")], limit=1)
                            if spain:
                                vals["country_id"] = spain.id
                                existing_partner.write(vals)
                                partner_id = existing_partner.id
                                updated_count += 1
                                log_lines.append(_("Actualizado (por %s, país corregido): %s") % (search_method, contact_name))
                            else:
                                raise e
                        else:
                            raise e
                else:
                    # CREAR nuevo contacto
                    try:
                        partner = self.env["res.partner"].create(vals)
                        partner_id = partner.id
                        created_count += 1
                        log_lines.append(_("Creado: %s") % contact_name)
                    except Exception as e:
                        error_msg = str(e)
                        if "difiere del de la ubicación" in error_msg and zip_code:
                            # Error de inconsistencia país-código postal, intentar corregir
                            spain = self.env["res.country"].search([("code", "=", "ES")], limit=1)
                            if spain:
                                vals["country_id"] = spain.id
                                partner = self.env["res.partner"].create(vals)
                                partner_id = partner.id
                                created_count += 1
                                log_lines.append(_("Creado (país corregido): %s") % contact_name)
                            else:
                                raise e
                        else:
                            raise e

                # Determinar método de pago basándose en si hay cuenta bancaria
                # Si columna "Banco" tiene datos → Domiciliación bancaria (SEPA)
                # Si columna "Banco" está vacía → Recibo (pago manual)
                banco_value = self._to_str(row_data.get("Banco"))
                partner = self.env["res.partner"].browse(partner_id)

                if banco_value:
                    # BANCO: Crear cuenta bancaria + mandato SEPA + asignar modo de pago SEPA
                    self._create_or_update_bank_account(partner_id, banco_value)
                    log_lines.append(
                        _("  → Cuenta bancaria asignada: %s") % banco_value
                    )
                    log_lines.append(_("  → Modo de pago: Domiciliación SEPA"))
                else:
                    # RECIBO: Sin cuenta bancaria, buscar o crear modo de pago manual
                    manual_payment_mode = self._get_or_create_manual_payment_mode()
                    if manual_payment_mode:
                        partner.write({"customer_payment_mode_id": manual_payment_mode.id})
                    log_lines.append(_("  → Modo de pago: Recibo"))

                # Print final con el nombre registrado
                partner = self.env["res.partner"].browse(partner_id)
                print(f"✓ Registrado: {partner.name}")

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
