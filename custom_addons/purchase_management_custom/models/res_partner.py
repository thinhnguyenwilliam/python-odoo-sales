# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResPartnerVendor(models.Model):
    """Mở rộng res.partner — Vendor Scorecard & Blacklist."""
    _inherit = 'res.partner'

    # ── Vendor Evaluation ───────────────────────────────────────
    vendor_score = fields.Float(
        string='Điểm NCC',
        default=3.0,
        digits=(3, 1),
        help='Điểm đánh giá nhà cung cấp từ 0 đến 5.',
    )
    vendor_score_quality = fields.Float(
        string='Chất Lượng Hàng',
        default=3.0,
        digits=(3, 1),
    )
    vendor_score_delivery = fields.Float(
        string='Giao Hàng Đúng Hạn',
        default=3.0,
        digits=(3, 1),
    )
    vendor_score_price = fields.Float(
        string='Giá Cả Cạnh Tranh',
        default=3.0,
        digits=(3, 1),
    )
    vendor_score_service = fields.Float(
        string='Dịch Vụ',
        default=3.0,
        digits=(3, 1),
    )
    vendor_evaluation_count = fields.Integer(
        string='Số Lần Đánh Giá',
        default=0,
    )
    last_evaluation_date = fields.Date(
        string='Lần Đánh Giá Cuối',
        readonly=True,
    )
    is_blacklisted_vendor = fields.Boolean(
        string='Blacklist NCC',
        default=False,
        tracking=True,
        help='Nhà cung cấp bị blacklist sẽ không thể đặt hàng.',
    )
    blacklist_reason = fields.Text(
        string='Lý Do Blacklist',
        tracking=True,
    )
    vendor_grade = fields.Selection(
        selection=[
            ('A', '⭐⭐⭐ Xuất Sắc (4.5–5.0)'),
            ('B', '⭐⭐ Tốt (3.5–4.4)'),
            ('C', '⭐ Trung Bình (2.5–3.4)'),
            ('D', '⚠️ Yếu (< 2.5)'),
        ],
        string='Hạng NCC',
        compute='_compute_vendor_grade',
        store=True,
    )

    # ── Purchase Stats ───────────────────────────────────────────
    purchase_order_count_custom = fields.Integer(
        string='Số Đơn Mua',
        compute='_compute_purchase_stats',
    )
    pending_purchase_count = fields.Integer(
        string='⏳ Chờ Duyệt',
        compute='_compute_purchase_stats',
    )

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================

    @api.constrains('vendor_score', 'vendor_score_quality',
                    'vendor_score_delivery', 'vendor_score_price', 'vendor_score_service')
    def _check_score_range(self):
        """Điểm phải từ 0 đến 5."""
        fields_to_check = ['vendor_score', 'vendor_score_quality',
                           'vendor_score_delivery', 'vendor_score_price', 'vendor_score_service']
        for partner in self:
            for f in fields_to_check:
                val = getattr(partner, f)
                if not (0.0 <= val <= 5.0):
                    raise ValidationError(_('Điểm đánh giá phải từ 0 đến 5!'))

    # =========================================================================
    # COMPUTE
    # =========================================================================

    @api.depends('vendor_score')
    def _compute_vendor_grade(self):
        for partner in self:
            score = partner.vendor_score
            if score >= 4.5:
                partner.vendor_grade = 'A'
            elif score >= 3.5:
                partner.vendor_grade = 'B'
            elif score >= 2.5:
                partner.vendor_grade = 'C'
            else:
                partner.vendor_grade = 'D'

    @api.depends('purchase_order_ids.approval_state')
    def _compute_purchase_stats(self):
        PO = self.env['purchase.order']
        for partner in self:
            orders = PO.search([('partner_id', 'child_of', partner.id)])
            partner.purchase_order_count_custom = len(orders)
            partner.pending_purchase_count = len(
                orders.filtered(lambda o: o.approval_state == 'pending')
            )

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def action_blacklist_vendor(self):
        """Toggle blacklist."""
        self.ensure_one()
        self.is_blacklisted_vendor = not self.is_blacklisted_vendor
        status = 'BLACKLISTED' if self.is_blacklisted_vendor else 'UNBANNED'
        _logger.warning("Vendor %s %s by %s", self.name, status, self.env.user.name)

    def update_vendor_score(self, quality, delivery, price, service):
        """Cập nhật điểm NCC dựa trên đánh giá mới (trung bình có trọng số)."""
        self.ensure_one()
        # Trọng số: Chất lượng 40%, Giao hàng 30%, Giá 20%, Dịch vụ 10%
        new_score = (quality * 0.4 + delivery * 0.3 + price * 0.2 + service * 0.1)
        n = self.vendor_evaluation_count
        # Tính trung bình lũy kế
        avg_score = (self.vendor_score * n + new_score) / (n + 1)

        self.write({
            'vendor_score': round(avg_score, 1),
            'vendor_score_quality': round((self.vendor_score_quality * n + quality) / (n + 1), 1),
            'vendor_score_delivery': round((self.vendor_score_delivery * n + delivery) / (n + 1), 1),
            'vendor_score_price': round((self.vendor_score_price * n + price) / (n + 1), 1),
            'vendor_score_service': round((self.vendor_score_service * n + service) / (n + 1), 1),
            'vendor_evaluation_count': n + 1,
            'last_evaluation_date': fields.Date.today(),
        })
        _logger.info("Vendor %s score updated to %.1f", self.name, avg_score)
