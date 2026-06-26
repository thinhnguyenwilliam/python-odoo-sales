# -*- coding: utf-8 -*-
# Copyright 2024 Your Company <info@yourcompany.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class ResPartner(models.Model):
    """Mở rộng res.partner — thêm thống kê đơn hàng theo trạng thái duyệt."""
    _inherit = 'res.partner'

    pending_approval_count = fields.Integer(
        string='Chờ Duyệt',
        compute='_compute_approval_stats',
        help='Số đơn hàng đang chờ phê duyệt.',
    )
    approved_order_count = fields.Integer(
        string='Đã Duyệt',
        compute='_compute_approval_stats',
        help='Số đơn hàng đã được phê duyệt.',
    )
    rejected_order_count = fields.Integer(
        string='Bị Từ Chối',
        compute='_compute_approval_stats',
        help='Số đơn hàng bị từ chối.',
    )
    sale_order_ids = fields.One2many(
        comodel_name='sale.order',
        inverse_name='partner_id',
        string='Đơn Hàng',
    )

    @api.depends('sale_order_ids.approval_state')
    def _compute_approval_stats(self):
        """Tính thống kê đơn hàng theo trạng thái duyệt."""
        SaleOrder = self.env['sale.order']
        for partner in self:
            orders = SaleOrder.search([('partner_id', 'child_of', partner.id)])
            partner.pending_approval_count = len(
                orders.filtered(lambda o: o.approval_state == 'pending')
            )
            partner.approved_order_count = len(
                orders.filtered(lambda o: o.approval_state == 'approved')
            )
            partner.rejected_order_count = len(
                orders.filtered(lambda o: o.approval_state == 'rejected')
            )
