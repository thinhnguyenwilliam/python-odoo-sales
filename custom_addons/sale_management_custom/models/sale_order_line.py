# -*- coding: utf-8 -*-
# Copyright 2024 Your Company <info@yourcompany.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    """
    Kế thừa Sale Order Line - Bổ sung validation và computed fields.
    """
    _inherit = 'sale.order.line'
    _description = 'Sale Order Line Custom'

    # =========================================================================
    # FIELDS
    # =========================================================================

    margin_amount = fields.Monetary(
        string='Biên Lợi Nhuận',
        compute='_compute_margin_amount',
        store=True,
        currency_field='currency_id',
        help='Biên lợi nhuận = Doanh thu - Giá vốn.',
    )
    margin_percent = fields.Float(
        string='% Biên LN',
        compute='_compute_margin_amount',
        store=True,
        digits=(5, 2),
        help='Phần trăm biên lợi nhuận trên doanh thu.',
    )
    delivery_lead_days = fields.Integer(
        string='Lead Time Giao Hàng (ngày)',
        compute='_compute_delivery_lead_days',
        store=True,
    )
    lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        string='Số Lô/Serial',
        help='Số lô hoặc serial number dự kiến giao.',
    )

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================

    @api.constrains('discount')
    def _check_discount_limit(self):
        """Giới hạn chiết khấu tối đa theo quyền."""
        for line in self:
            if not line.discount:
                continue
            # Nhân viên thường: max 10%
            # Manager: max 30%
            max_discount = 30.0 if self.env.user.has_group(
                'sales_team.group_sale_manager'
            ) else 10.0

            if line.discount > max_discount:
                raise ValidationError(
                    _("Chiết khấu tối đa cho phép là %s%%!\n"
                      "Sản phẩm: %s") % (max_discount, line.product_id.name)
                )

    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================

    @api.depends('product_id', 'price_unit', 'product_uom_qty', 'discount',
                 'product_id.standard_price')
    def _compute_margin_amount(self):
        """Tính biên lợi nhuận dòng sản phẩm."""
        for line in self:
            if not line.product_id or not line.product_uom_qty:
                line.margin_amount = 0.0
                line.margin_percent = 0.0
                continue

            revenue = line.price_subtotal
            cost = line.product_id.standard_price * line.product_uom_qty
            margin = revenue - cost
            line.margin_amount = margin
            line.margin_percent = (margin / revenue * 100) if revenue else 0.0

    @api.depends('product_id')
    def _compute_delivery_lead_days(self):
        """Lấy lead time giao hàng từ sản phẩm."""
        for line in self:
            line.delivery_lead_days = (
                line.product_id.sale_delay
                if line.product_id else 0
            )
