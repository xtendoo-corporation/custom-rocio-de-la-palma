# -*- coding: utf-8 -*-
{
    'name': 'Rocío - Gestión de hermanos',
    'version': '18.0.1.0.0',
    'summary': 'Gestión de hermanos y generación de cuotas',
    'category': 'Tools',
    'author': 'Auto-generated',
    'depends': ['base', 'contacts', 'account', 'sale', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_view.xml',
        'views/res_config_settings_view.xml',
        'wizards/hermano_invoice_wizard_view.xml',
        'views/menus_actions.xml',
        'data/product_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
