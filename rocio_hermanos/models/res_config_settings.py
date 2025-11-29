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
        string='Diario de ventas cuota de hermano',
        domain=[('type', '=', 'sale')],
        config_parameter='rocio_hermanos.brother_fee_journal_id',
    )

    # The config_parameter on fields handles get/set automatically in Odoo 14+,
    # so we don't need to implement get_values/set_values manually unless we
    # need extra behavior.
