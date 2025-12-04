# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RocioHermanoInvoiceWizard(models.TransientModel):
    _name = 'rocio.hermano.invoice.wizard'
    _description = 'Generar facturas de cuotas para hermanos'

    invoice_date = fields.Date(string='Fecha de factura', default=fields.Date.context_today)
    product_id = fields.Many2one('product.product', string='Producto a facturar')
    journal_id = fields.Many2one('account.journal', string='Diario de ventas', domain=[('type', '=', 'sale')])

    @api.model
    def default_get(self, fields_list):
        res = super(RocioHermanoInvoiceWizard, self).default_get(fields_list)
        IrConfig = self.env['ir.config_parameter'].sudo()
        product_id = IrConfig.get_param('rocio_hermanos.brother_fee_product_id')
        journal_id = IrConfig.get_param('rocio_hermanos.brother_fee_journal_id')
        if product_id:
            try:
                res['product_id'] = int(product_id)
            except Exception:
                res['product_id'] = False
        if journal_id:
            try:
                res['journal_id'] = int(journal_id)
            except Exception:
                res['journal_id'] = False
        return res

    def action_generate_invoices(self):
        # Validaciones
        if not self.product_id:
            raise UserError(_('Debe configurar el producto de cuota en Ajustes del módulo'))

        # Diario por defecto si no se pasa
        journal = self.journal_id or self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
        if not journal:
            raise UserError(_('No se ha encontrado ningún diario de ventas. Configure uno en Ajustes o seleccione uno en el asistente.'))

        partners = self.env['res.partner'].search([('brother_active', '=', True)])
        if not partners:
            raise UserError(_('No se han encontrado hermanos activos para facturar.'))

        created_invoices = self.env['account.move']
        for partner in partners:
            # partner_id SIEMPRE es el hermano, nunca el delegado
            invoice_partner_id = partner.id
            partner_shipping_id = False
            if partner.brother_has_delegated_collection and partner.brother_delegated_partner_id:
                partner_shipping_id = partner.brother_delegated_partner_id.id

            line_vals = {
                'product_id': self.product_id.id,
                'name': self.product_id.display_name,
                'quantity': 1.0,
                'price_unit': self.product_id.list_price,
            }

            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': invoice_partner_id,  # SIEMPRE el hermano
                'invoice_date': self.invoice_date,
                'journal_id': journal.id,
                'invoice_line_ids': [(0, 0, line_vals)],
                'invoice_origin': 'Cuota de hermano',
            }
            if partner_shipping_id:
                invoice_vals['partner_shipping_id'] = partner_shipping_id  # Dirección de entrega: delegado

            invoice = self.env['account.move'].create(invoice_vals)
            created_invoices += invoice

        # Acción para mostrar las facturas creadas
        action = self.env.ref('account.action_move_out_invoice_type')
        result = action.read()[0]
        result['domain'] = [('id', 'in', created_invoices.ids)]
        return result
