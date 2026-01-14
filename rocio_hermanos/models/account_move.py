from odoo import api, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def action_invoices_filtered_by_config_journal(self):
        """Devuelve facturas de cuotas filtradas por el diario configurado."""
        journal_id = self.env['ir.config_parameter'].sudo().get_param(
            'rocio_hermanos.brother_fee_journal_id'
        )

        # Convertir a entero y validar que el diario existe
        try:
            journal_id = int(journal_id)
            if not self.env['account.journal'].sudo().browse(journal_id).exists():
                journal_id = False
        except (ValueError, TypeError):
            journal_id = False

        # Construir el domain
        domain = [('move_type', 'in', ['out_invoice', 'out_refund'])]
        if journal_id:
            domain.append(('journal_id', '=', journal_id))
        else:
            domain = [('id', 'in', [])]  # Lista vacía si no hay diario configurado

        # Construir el contexto como lo hace el menú de facturas de Odoo
        context = {
            'default_move_type': 'out_invoice',
            'move_type': 'out_invoice',
            'journal_type': 'sale',
            'search_default_posted': 1,
        }

        if journal_id:
            context['default_journal_id'] = journal_id
            context['search_default_journal_id'] = journal_id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturas de cuotas'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'context': context,
        }

