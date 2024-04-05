# -*- coding: utf-8 -*-
{
    'name': "Softina Custom Changes",

    'summary': """
    inherit stock.picking and stock.move.line , add description BL field 
        """,

    'description': """
        Add new related field (product descrition BL) to stock.picking and stock.move.line
    """,

    'author': "Softina",
    'website': "http://www.softina.com",
    'license': "LGPL-3",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'stock', 'sale', 'sale_subscription'],

    # always loaded
    'data': [
        'views/stock_picking_inherit.xml',
    ],
    # only loaded in demonstration mode
}
