# -*- coding: utf-8 -*-
from odoo import api, models


class AccountPaymentMode(models.Model):
    _inherit = "account.payment.mode"

    @api.model
    def _create_sepa_direct_debit_mode_if_not_exists(self):
        """Crea el modo de pago SEPA Direct Debit si no existe"""
        # Buscar si ya existe el registro con el external ID
        mode = self.env.ref(
            'rocio_hermanos.account_payment_mode_sepa_direct_debit',
            raise_if_not_found=False
        )

        if mode:
            return mode

        # Si no existe, buscarlo por criterios
        payment_method = self.env.ref(
            'account_banking_sepa_direct_debit.sepa_direct_debit',
            raise_if_not_found=False
        )

        if not payment_method:
            return False

        # Buscar si existe un modo con estos criterios
        existing_mode = self.search([
            ('payment_method_id', '=', payment_method.id),
            ('payment_type', '=', 'inbound'),
            ('bank_account_link', '=', 'variable'),
        ], limit=1)

        if existing_mode:
            # Crear el external ID si no existe
            self.env['ir.model.data'].create({
                'module': 'rocio_hermanos',
                'name': 'account_payment_mode_sepa_direct_debit',
                'model': 'account.payment.mode',
                'res_id': existing_mode.id,
                'noupdate': True,
            })
            return existing_mode

        # Si no existe, crearlo
        new_mode = self.create({
            'name': 'Domiciliación bancaria',
            'company_id': self.env.company.id,
            'payment_method_id': payment_method.id,
            'payment_type': 'inbound',
            'bank_account_link': 'variable',
        })

        # Crear el external ID
        self.env['ir.model.data'].create({
            'module': 'rocio_hermanos',
            'name': 'account_payment_mode_sepa_direct_debit',
            'model': 'account.payment.mode',
            'res_id': new_mode.id,
            'noupdate': True,
        })

        return new_mode

