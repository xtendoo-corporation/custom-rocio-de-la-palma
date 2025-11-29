# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Campos para gestionar hermanos
    is_brother = fields.Boolean(string='Hermano', default=False)
    brother_since = fields.Date(string='Fecha alta como hermano')
    brother_end_date = fields.Date(string='Fecha baja como hermano')
    brother_district = fields.Char(string='Distrito')
    brother_has_delegated_collection = fields.Boolean(
        string='Cobro delegado en otra dirección',
    )
    brother_delegated_partner_id = fields.Many2one(
        'res.partner',
        string='Dirección de cobro delegada',
        help='Si hay cobro delegado, las facturas se emitirán a esta dirección/partner.',
    )
    brother_category = fields.Selection(
        [
            ('ordinario', 'Hermano ordinario'),
            ('extraordinario', 'Hermano extraordinario'),
            ('honor', 'Hermano de honor'),
        ],
        string='Categoría de hermano',
    )

    # Campo calculado para facilitar dominios: True si es hermano y no tiene fecha de baja.
    brother_active = fields.Boolean(
        string='Hermano activo',
        compute='_compute_brother_active',
        store=True,
        help='Indicador calculado: True si es hermano y no tiene fecha de baja.',
    )

    @api.depends('is_brother', 'brother_end_date')
    def _compute_brother_active(self):
        for rec in self:
            rec.brother_active = bool(rec.is_brother and not rec.brother_end_date)

    @api.model
    def create(self, vals):
        # Si se crea un partner desde la vista de hermanos, asegurar que is_brother sea True
        if vals.get('is_brother') is None and self.env.context.get('default_is_brother'):
            vals['is_brother'] = True
        return super(ResPartner, self).create(vals)
