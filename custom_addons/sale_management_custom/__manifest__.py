# -*- coding: utf-8 -*-
# Copyright 2024 Your Company <info@yourcompany.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
{
    'name': 'Sale Management Custom',
    'version': '17.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Quản lý bán hàng nâng cao với approval flow',
    'description': """
Sale Management Custom
======================
Module mở rộng nghiệp vụ bán hàng:

* Approval workflow: Draft → Confirmed → Approved → Done
* Tự động sinh mã đơn hàng nội bộ
* Gửi email thông báo khi duyệt/từ chối
* Báo cáo doanh số theo nhóm khách hàng
* Phân quyền theo nhóm người dùng
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'account',
        'mail',
        'hr',
        'stock',
    ],
    'data': [
        # Security - phải load đầu tiên
        'security/ir.model.access.csv',
        'security/sale_security.xml',
        # Data mặc định
        'data/ir_sequence_data.xml',
        'data/mail_template_data.xml',
        # Views
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'views/menus.xml',
        # Wizards
        'wizards/sale_reject_wizard_views.xml',
        # Reports
        'reports/sale_order_report.xml',
        'reports/sale_order_report_template.xml',
        # Scheduled Actions
        'data/ir_cron_data.xml',
    ],
    'demo': [
        'demo/sale_demo.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
