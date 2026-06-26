# -*- coding: utf-8 -*-
{
    'name': 'Stock Management Custom',
    'version': '17.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Quản lý kho nâng cao với QC checklist và cảnh báo tồn kho',
    'description': """
Stock Management Custom
=======================
* QC checklist khi nhập/xuất kho
* Bắt buộc nhập số lô/serial cho hàng quan trọng
* Cảnh báo tồn kho dưới mức tối thiểu
* Phân loại phiếu kho theo mức độ ưu tiên
* Báo cáo tồn kho theo lô/serial
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'stock',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/stock_picking_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
