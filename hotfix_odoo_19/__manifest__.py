{
    'name': 'Hotfix Odoo 19 - Color Scheme Default',
    'version': '1.0',
    'category': 'Technical',
    'summary': 'Hotfix for color_scheme mandatory field in res.users.settings',
    'description': """
        Hotfix Module for Odoo 19
        =========================
        
        This module fixes the issue with missing required value for color_scheme field
        in res.users.settings model by setting a default value of 'dark'.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base'],
    'data': [],
    # 'pre_init_hook': 'pre_init_hook',
    # 'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
