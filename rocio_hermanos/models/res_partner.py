# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Campos para gestionar hermanos
    ref = fields.Char(string="Referencia interna", required=True, tracking=True)
    is_brother = fields.Boolean(string="Hermano", default=False, tracking=True)
    brother_since = fields.Date(string="Fecha de alta", tracking=True)
    brother_end_date = fields.Date(string="Fecha de baja", tracking=True)
    brother_district = fields.Char(string="Distrito", tracking=True)
    brother_birth_date = fields.Date(string="Fecha de nacimiento", tracking=True)
    brother_has_delegated_collection = fields.Boolean(
        string="Cobro delegado en otra dirección",
        help="Indica si el hermano tiene el cobro delegado en otra dirección/partner.",
    )
    brother_advertising = fields.Boolean(
        string="Acepta publicidad",
        help="Indica si el hermano acepta recibir publicidad de la hermandad.",
    )
    brother_method_of_payment = fields.Selection(
        [
            ("Banco", "Banco"),
            ("efectivo", "Recibo"),
            ("otra direccion", "Otra Dirección"),
        ],
        string="Método de pago",
        compute="_compute_brother_method_of_payment",
        store=True,
        tracking=True,
    )
    brother_delegated_partner_id = fields.Many2one(
        "res.partner",
        string="Dirección de cobro delegada",
        help="Si hay cobro delegado, las facturas se emitirán a esta dirección/partner.",
    )
    brother_category = fields.Selection(
        [
            ("ordinario", "Hermano ordinario"),
            ("extraordinario", "Hermano extraordinario"),
            ("honor", "Hermano de honor"),
        ],
        string="Categoría de hermano",
        tracking=True,
    )
    brother_leave_reason = fields.Many2one(
        "res.partner.leave.reason",
        string="Motivo de baja",
        help="Selecciona el motivo por el que el hermano ha dado de baja.",
        tracking=True,
    )

    # Antigüedad: posición del hermano activo ordenado por fecha de alta (el más antiguo = 1)
    brother_seniority = fields.Integer(
        string="Antigüedad",
        default=0,
        help="Número de orden del hermano según su fecha de alta. 1 = el más antiguo. "
        "Se recalcula automáticamente el 1 de febrero de cada año.",
    )

    # Campo calculado para facilitar dominios: True si es hermano y no tiene fecha de baja.
    brother_active = fields.Boolean(
        string="Hermano activo",
        compute="_compute_brother_active",
        store=True,
        help="Indicador calculado: True si es hermano y no tiene fecha de baja.",
    )

    @api.depends("is_brother", "brother_end_date")
    def _compute_brother_active(self):
        for rec in self:
            rec.brother_active = bool(rec.is_brother and not rec.brother_end_date)

    @api.model
    def action_recompute_brother_seniority(self):
        """Recalcula la antigüedad de todos los hermanos activos.
        Los hermanos se ordenan por fecha de alta ascendente (el más antiguo = 1).
        Los hermanos sin fecha de alta quedan con antigüedad 0.
        Esta acción se ejecuta manualmente mediante menú o botón de acción."""
        # Hermanos activos CON fecha de alta, ordenados de más antiguo a más moderno
        active_brothers = self.search(
            [("brother_active", "=", True), ("brother_since", "!=", False)],
            order="brother_since asc",
        )
        for idx, brother in enumerate(active_brothers, start=1):
            brother.brother_seniority = idx

        # Hermanos activos SIN fecha de alta → antigüedad 0
        brothers_no_date = self.search(
            [("brother_active", "=", True), ("brother_since", "=", False)]
        )
        brothers_no_date.write({"brother_seniority": 0})

        # Hermanos de baja → antigüedad 0
        inactive_brothers = self.search([("brother_active", "=", False)])
        inactive_brothers.write({"brother_seniority": 0})

    @api.depends("bank_ids", "bank_ids.mandate_ids", "bank_ids.mandate_ids.state")
    def _compute_brother_method_of_payment(self):
        for rec in self:
            # Si el partner tiene una cuenta bancaria con un mandato válido, el método de pago es "Banco"
            has_bank_and_mandate = False
            if rec.bank_ids:
                for bank in rec.bank_ids:
                    if bank.mandate_ids:
                        valid_mandates = bank.mandate_ids.filtered(
                            lambda m: m.state == "valid"
                        )
                        if valid_mandates:
                            has_bank_and_mandate = True
                            break

            if has_bank_and_mandate:
                rec.brother_method_of_payment = "Banco"
            else:
                # Si no tiene banco y mandato, mantener el valor actual o dejarlo vacío
                # Para evitar sobreescribir valores existentes, solo calculamos si es "Banco"
                if not rec.brother_method_of_payment:
                    rec.brother_method_of_payment = False

    @api.model_create_multi
    def create(self, vals_list):
        # Si se crea un partner desde la vista de hermanos, asegurar que is_brother sea True
        if self.env.context.get("default_is_brother"):
            for vals in vals_list:
                if vals.get("is_brother") is None:
                    vals["is_brother"] = True
        return super(ResPartner, self).create(vals_list)
