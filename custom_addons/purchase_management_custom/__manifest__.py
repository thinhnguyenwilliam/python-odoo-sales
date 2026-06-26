# -*- coding: utf-8 -*-
{
    'name': 'Purchase Management Custom',
    'version': '17.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Quản lý mua hàng nâng cao với approval flow và vendor evaluation',
    'description': """
Purchase Management Custom
==========================
* Approval workflow: Draft → Confirmed → Approved → Done
* Đánh giá nhà cung cấp (Vendor Scorecard): chất lượng, giá, giao hàng
* Cảnh báo mua từ vendor bị blacklist / có lịch sử xấu
* Gửi email thông báo khi duyệt/từ chối
* Phân quyền theo nhóm người dùng
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'purchase',
        'account',
        'mail',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/purchase_security.xml',
        'data/mail_template_data.xml',
        'data/ir_sequence_data.xml',
        'views/purchase_order_views.xml',
        'views/res_partner_views.xml',
        'views/menus.xml',
        'wizards/purchase_reject_wizard_views.xml',
        'reports/purchase_order_report.xml',
        'reports/purchase_order_report_template.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
