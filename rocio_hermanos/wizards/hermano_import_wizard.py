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
        if pd.isna(state_name) or not country_id:
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
        if pd.isna(name):
            return False
        partner = self.env["res.partner"].search([("name", "=", name)], limit=1)
        return partner.id if partner else False

    def _get_leave_reason_id(self, name):
        """Busca un motivo de baja por nombre o lo crea"""
        if not name:
            return False
        name_str = str(name).strip()
        if not name_str:
            return False
        reason = self.env["res.partner.leave.reason"].search(
            [("name", "=", name_str)], limit=1
        )
        if not reason:
            reason = self.env["res.partner.leave.reason"].create({"name": name_str})
        return reason.id

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

                contact_name = row_data.get("name")
                if not contact_name:
                    error_count += 1
                    log_lines.append(_("Fila %s: No se especificó un nombre") % row_idx)
                    continue

                # Obtener país primero
                country_id = self._get_country_id(row_data.get("País"))

                vals = {
                    "name": contact_name,
                    "street": row_data.get("Street"),
                    "zip": self._to_str(row_data.get("C.P.")),
                    "city": row_data.get("Ciudad"),
                    "phone": self._to_str(row_data.get("TELEFONO")),
                    "email": self._to_str(row_data.get("EMAIL")),
                    "is_brother": True,
                    "brother_district": self._to_str(row_data.get("DIST")),
                    "brother_birth_date": self._to_date(
                        row_data.get("brother_birth_date")
                    ),
                    "brother_since": self._to_date(row_data.get("F ALTA")),
                    "brother_end_date": self._to_date(row_data.get("F BAJA")),
                    "brother_leave_reason_id": self._get_leave_reason_id(
                        row_data.get("Motivo")
                    ),
                    "brother_advertising": self._to_bool(row_data.get("PUBLI")),
                    "brother_method_of_payment": self._map_payment(
                        row_data.get("F DE PAGO")
                    ),
                    "brother_delegated_partner_id": self._get_partner_id_by_name(
                        row_data.get("DIRECCION DE COBRO")
                    ),
                    "country_id": country_id,
                    "state_id": self._get_state_id(
                        country_id, row_data.get("State_id")
                    ),
                }

                # Buscar si el contacto ya existe por nombre
                existing_partner = self.env["res.partner"].search(
                    [("name", "=", contact_name)], limit=1
                )

                if existing_partner:
                    # ACTUALIZAR contacto existente
                    existing_partner.write(vals)
                    partner_id = existing_partner.id
                    updated_count += 1
                    log_lines.append(_("Actualizado: %s") % contact_name)
                else:
                    # CREAR nuevo contacto
                    partner = self.env["res.partner"].create(vals)
                    partner_id = partner.id
                    created_count += 1
                    log_lines.append(_("Creado: %s") % contact_name)

                # Crear o actualizar cuenta bancaria si existe en el Excel
                if "Banco" in row_data and row_data.get("Banco"):
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
