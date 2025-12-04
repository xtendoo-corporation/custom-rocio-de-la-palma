# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_shipping_id = fields.Many2one('res.partner', string='Dirección de entrega')

