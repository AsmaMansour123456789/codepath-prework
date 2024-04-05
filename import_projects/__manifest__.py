# -*- coding: utf-8 -*-
{
    'name': 'import_invoices',
    'version': '1.0',
    'category': 'Account',
    'author': '',
    'website': '',
    'license': 'LGPL-3',
    'summary': 'Import datas to account.move from excel file',
    'depends': ['base', 'project', 'product', 'helpdesk_timesheet'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'wizard/import_projects.xml',
        'wizard/import_tasks.xml',
        'wizard/import_tickets.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
