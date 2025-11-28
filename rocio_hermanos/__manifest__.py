# -*- coding: utf-8 -*-
{
    'name': 'Rocío - Gestión de Hermanos',
    'version': '18.0.1.0.0',
    'summary': 'Gestión de miembros (hermanos) y generación de cuotas',
    'category': 'Uncategorized',
    'author': 'Autogenerado',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'account',
        'sale',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/product_data.xml',
        'data/default_config.xml',
        'views/res_partner_view.xml',
        'views/res_config_settings_view.xml',
        'wizards/hermano_invoice_wizard_view.xml',
        'views/menus_actions.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
}
