# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    brother_fee_product_id = fields.Many2one(
        'product.product',
        string='Producto cuota de hermano',
        config_parameter='rocio_hermanos.brother_fee_product_id',
    )

    brother_fee_journal_id = fields.Many2one(
        'account.journal',
        string='Diario de ventas cuota',
        domain=[('type', '=', 'sale')],
        config_parameter='rocio_hermanos.brother_fee_journal_id',
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        product_id = params.get_param('rocio_hermanos.brother_fee_product_id')
        journal_id = params.get_param('rocio_hermanos.brother_fee_journal_id')
        if product_id:
            res.update({'brother_fee_product_id': int(product_id)})
        if journal_id:
            res.update({'brother_fee_journal_id': int(journal_id)})
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        params = self.env['ir.config_parameter'].sudo()
        if self.brother_fee_product_id:
            params.set_param('rocio_hermanos.brother_fee_product_id', str(self.brother_fee_product_id.id))
        if self.brother_fee_journal_id:
            params.set_param('rocio_hermanos.brother_fee_journal_id', str(self.brother_fee_journal_id.id))

