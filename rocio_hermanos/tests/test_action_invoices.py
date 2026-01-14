from odoo.tests.common import TransactionCase


class TestInvoicesAction(TransactionCase):
    def test_action_invoices_filtered_by_config_journal(self):
        # Crear un diario de prueba
        journal = self.env['account.journal'].create({
            'name': 'Journal Test Rocio',
            'type': 'sale',
            'company_id': self.env.company.id,
        })
        # Configurar el parámetro con la id del diario
        self.env['ir.config_parameter'].sudo().set_param('rocio_hermanos.brother_fee_journal_id', str(journal.id))

        action = self.env['account.move'].action_invoices_filtered_by_config_journal()
        # Comprobaciones básicas
        self.assertIsInstance(action, dict)
        self.assertIn('domain', action)
        self.assertIn('context', action)
        self.assertIn(('journal_id', '=', journal.id), action['domain'])
        self.assertIn(('move_type', 'in', ['out_invoice', 'out_refund']), action['domain'])
        # Verificar que el contexto incluye el journal_id
        self.assertEqual(action['context'].get('default_journal_id'), journal.id)
        self.assertEqual(action['context'].get('default_move_type'), 'out_invoice')

