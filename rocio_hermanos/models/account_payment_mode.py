# -*- coding: utf-8 -*-
from odoo import api, models


class AccountPaymentMode(models.Model):
    _inherit = "account.payment.mode"

    @api.model
    def _create_sepa_direct_debit_mode_if_not_exists(self):
        """Obtiene o crea el modo de pago SEPA Direct Debit para clientes (inbound)"""
        import logging
        _logger = logging.getLogger(__name__)

        # 1. Buscar por método de pago con código sepa_direct_debit o sepa.sdd
        sepa_mode = self.search([
            ('payment_method_id.code', 'in', ['sepa_direct_debit', 'sepa.sdd']),
            ('payment_type', '=', 'inbound'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

        if sepa_mode:
            _logger.info(f"Modo de pago SEPA encontrado: {sepa_mode.name} (ID: {sepa_mode.id})")
            return sepa_mode

        # 2. Si no existe, buscar el método de pago SEPA Direct Debit
        payment_method = self.env['account.payment.method'].search([
            ('code', 'in', ['sepa_direct_debit', 'sepa.sdd']),
            ('payment_type', '=', 'inbound'),
        ], limit=1)

        if not payment_method:
            _logger.error("Método de pago SEPA Direct Debit no encontrado. ¿Está instalado account_banking_sepa_direct_debit?")
            return False

        # 3. Buscar un diario bancario
        bank_journal = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

        if not bank_journal:
            _logger.error("No hay diario bancario disponible para crear modo de pago SEPA")
            return False

        # 4. Crear el modo de pago SEPA
        try:
            sepa_mode = self.create({
                'name': 'Adeudo directo SEPA de clientes',
                'company_id': self.env.company.id,
                'payment_method_id': payment_method.id,
                'payment_type': 'inbound',
                'bank_account_link': 'variable',
                'fixed_journal_id': bank_journal.id,
            })
            _logger.info(f"Modo de pago SEPA creado: {sepa_mode.name} (ID: {sepa_mode.id})")
            return sepa_mode
        except Exception as e:
            _logger.error(f"Error al crear modo de pago SEPA: {str(e)}")
            return False

