# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo import fields
from odoo.exceptions import UserError
from datetime import date


class TestRocioHermanosInvoiceGeneration(TransactionCase):

    def setUp(self):
        super(TestRocioHermanosInvoiceGeneration, self).setUp()
        # Crear producto de cuota
        Product = self.env['product.product']
        self.product = Product.create({
            'name': 'Cuota de Hermano Test',
            'type': 'service',
            'list_price': 15.0,
            'sale_ok': True,
        })
        # Crear diario de ventas
        Journal = self.env['account.journal']
        self.journal = Journal.search([('type', '=', 'sale')], limit=1)
        if not self.journal:
            # Crear un diario mínimo para el test
            self.journal = Journal.create({
                'name': 'Ventas Test',
                'code': 'VT',
                'type': 'sale',
            })
        # Crear algunos partners marcados como hermanos
        Partner = self.env['res.partner']
        self.partner1 = Partner.create({'name': 'Hermano Uno', 'is_brother': True, 'active': True})
        self.partner2 = Partner.create({'name': 'Hermano Dos', 'is_brother': True, 'active': True, 'brother_has_delegated_collection': True})
        # partner delegado
        self.delegated = Partner.create({'name': 'Delegado', 'is_brother': False})
        self.partner2.brother_delegated_partner_id = self.delegated

    def test_generate_invoices_wizard(self):
        # Ejecutar wizard
        Wizard = self.env['rocio.hermano.invoice.wizard']
        wiz = Wizard.create({'product_id': self.product.id, 'journal_id': self.journal.id, 'invoice_date': fields.Date.context_today(self)})
        action = wiz.action_generate_invoices()
        # Comprobar que la acción devuelve el domain con las facturas
        self.assertIn('domain', action)
        domain = action['domain']
        # Obtener las facturas creadas
        account_move = self.env['account.move'].search(domain)
        self.assertEqual(len(account_move), 2)
        # Comprobar partner correctos
        partners = account_move.mapped('partner_id')
        self.assertIn(self.partner1, partners)
        # partner2 se factura al delegado
        self.assertIn(self.delegated, partners)
        # Comprobar líneas y precio
        for move in account_move:
            self.assertEqual(len(move.invoice_line_ids), 1)
            line = move.invoice_line_ids[0]
            self.assertEqual(line.product_id, self.product)
            self.assertAlmostEqual(line.price_unit, 15.0)

    def test_generate_invoices_excludes_baja(self):
        # Crear dos hermanos: uno activo y uno con fecha de baja
        active = self.env['res.partner'].create({'name': 'Hermano Activo', 'is_brother': True})
        baja = self.env['res.partner'].create({'name': 'Hermano Baja', 'is_brother': True, 'brother_end_date': date.today()})

        wizard = self.env['rocio.hermano.invoice.wizard'].create({
            'invoice_date': date.today(),
            'product_id': self.product.id,
            'journal_id': self.journal.id,
        })

        # Ejecutar generador
        action = wizard.action_generate_invoices()

        # Comprobar que solo se creó la factura para el activo
        invoices = self.env['account.move'].search([('invoice_origin', '=', 'Cuota de hermano')])
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices.partner_id.id, active.id)

    def test_generate_invoices_delegated(self):
        # Crear un partner delegado
        delegado = self.env['res.partner'].create({'name': 'Delegado'})
        hermano = self.env['res.partner'].create({'name': 'Hermano Delegado', 'is_brother': True, 'brother_has_delegated_collection': True, 'brother_delegated_partner_id': delegado.id})

        wizard = self.env['rocio.hermano.invoice.wizard'].create({
            'invoice_date': date.today(),
            'product_id': self.product.id,
            'journal_id': self.journal.id,
        })

        wizard.action_generate_invoices()
        invoices = self.env['account.move'].search([('invoice_origin', '=', 'Cuota de hermano')])
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices.partner_id.id, delegado.id)

    def test_missing_product_raises(self):
        # Borrar param
        self.env['ir.config_parameter'].sudo().set_param('rocio_hermanos.brother_fee_product_id', '')
        wizard = self.env['rocio.hermano.invoice.wizard'].create({'invoice_date': date.today()})
        with self.assertRaises(UserError):
            wizard.action_generate_invoices()
