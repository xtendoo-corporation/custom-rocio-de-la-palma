# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RocioHermanoInvoiceWizard(models.TransientModel):
    _name = 'rocio.hermano.invoice.wizard'
    _description = 'Asistente para generar facturas de cuota a hermanos'

    invoice_date = fields.Date(string='Fecha de factura', default=fields.Date.context_today)
    product_id = fields.Many2one('product.product', string='Producto a facturar')
    journal_id = fields.Many2one('account.journal', string='Diario de ventas', domain=[('type', '=', 'sale')])

    @api.model
    def default_get(self, fields_list):
        res = super(RocioHermanoInvoiceWizard, self).default_get(fields_list)
        params = self.env['ir.config_parameter'].sudo()
        product_id = params.get_param('rocio_hermanos.brother_fee_product_id')
        journal_id = params.get_param('rocio_hermanos.brother_fee_journal_id')
        if product_id:
            res['product_id'] = int(product_id)
        if journal_id:
            res['journal_id'] = int(journal_id)
        return res

    def action_generate_invoices(self):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_('Debe configurar el producto de cuota en Ajustes o seleccionarlo aquí.'))
        # Buscar hermanos activos
        partners = self.env['res.partner'].search([('is_brother', '=', True), ('active', '=', True)])
        if not partners:
            raise UserError(_('No se han encontrado hermanos activos para facturar.'))

        Move = self.env['account.move']
        MoveLine = self.env['account.move.line']
        created_moves = []
        for partner in partners:
            # Determinar partner al que facturar
            partner_invoice = partner
            if partner.brother_has_delegated_collection and partner.brother_delegated_partner_id:
                partner_invoice = partner.brother_delegated_partner_id
            # Buscar journal
            journal = self.journal_id or self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
            if not journal:
                raise UserError(_('No hay diario de ventas configurado para crear las facturas.'))
            # Crear factura en borrador
            move_vals = {
                'partner_id': partner_invoice.id,
                'move_type': 'out_invoice',
                'invoice_date': self.invoice_date,
                'journal_id': journal.id,
                'invoice_origin': 'Cuota de hermano',
                'invoice_line_ids': [(0, 0, {
                    'product_id': self.product_id.id,
                    'name': self.product_id.display_name,
                    'quantity': 1.0,
                    'price_unit': self.product_id.list_price,
                    'tax_ids': [(6, 0, self.product_id.taxes_id.ids)],
                })],
            }
            move = Move.create(move_vals)
            created_moves.append(move.id)
        # Devolver acción para ver las facturas creadas
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        # Filtrar por las facturas creadas
        action.update({
            'domain': [('id', 'in', created_moves)],
            'context': {'default_move_type': 'out_invoice'},
        })
        return action

