# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    @api.model_create_multi
    def create(self, vals_list):
        """Asegurar que la cuenta bancaria tenga company_id al crearla"""
        for vals in vals_list:
            if 'company_id' not in vals:
                vals['company_id'] = self.env.company.id
        return super(ResPartnerBank, self).create(vals_list)

