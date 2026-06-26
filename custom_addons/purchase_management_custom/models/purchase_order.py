# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

PURCHASE_APPROVAL_STATES = [
    ('pending', 'Chờ Duyệt'),
    ('approved', 'Đã Duyệt'),
    ('rejected', 'Từ Chối'),
]


class PurchaseOrder(models.Model):
    """
    Kế thừa Purchase Order — Bổ sung approval workflow và vendor evaluation.

    Quy trình:
        Draft → (Confirm) → Purchase (Chờ Duyệt) → Approved / Rejected
    """
    _inherit = 'purchase.order'
    _description = 'Purchase Order Custom'

    # =========================================================================
    # FIELDS
    # =========================================================================

    internal_code = fields.Char(
        string='Mã Nội Bộ',
        copy=False,
        readonly=True,
        index=True,
        help='Mã đơn mua nội bộ, tự động sinh khi xác nhận.',
    )
    approval_state = fields.Selection(
        selection=PURCHASE_APPROVAL_STATES,
        string='Trạng Thái Duyệt',
        default='pending',
        required=True,
        tracking=True,
        copy=False,
    )
    approver_id = fields.Many2one(
        comodel_name='res.users',
        string='Người Duyệt',
        readonly=True,
        copy=False,
        tracking=True,
        ondelete='restrict',
    )
    approval_date = fields.Datetime(
        string='Ngày Duyệt',
        readonly=True,
        copy=False,
        tracking=True,
    )
    rejection_reason = fields.Text(
        string='Lý Do Từ Chối',
        readonly=True,
        copy=False,
        tracking=True,
    )
    vendor_score = fields.Float(
        string='Điểm NCC',
        related='partner_id.vendor_score',
        readonly=True,
        help='Điểm đánh giá nhà cung cấp (0–5).',
    )
    is_blacklisted_vendor = fields.Boolean(
        string='NCC Blacklist',
        related='partner_id.is_blacklisted_vendor',
        readonly=True,
    )
    urgency = fields.Selection(
        selection=[
            ('normal', 'Bình Thường'),
            ('urgent', 'Khẩn Cấp'),
        ],
        string='Mức Khẩn Cấp',
        default='normal',
        required=True,
        tracking=True,
    )
    total_discount_amount = fields.Monetary(
        string='Tổng Chiết Khấu',
        compute='_compute_discount_totals',
        store=True,
        currency_field='currency_id',
    )

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================

    @api.constrains('partner_id')
    def _check_blacklisted_vendor(self):
        """Cảnh báo nếu mua từ vendor bị blacklist."""
        for order in self:
            if order.partner_id.is_blacklisted_vendor:
                raise ValidationError(
                    _('⚠️ Nhà cung cấp "%s" đang bị BLACKLIST!\n'
                      'Vui lòng liên hệ Trưởng phòng Mua hàng để được phê duyệt đặc biệt.')
                    % order.partner_id.name
                )

    # =========================================================================
    # COMPUTE
    # =========================================================================

    @api.depends('order_line.price_unit', 'order_line.product_qty')
    def _compute_discount_totals(self):
        for order in self:
            order.total_discount_amount = sum(
                line.price_unit * line.product_qty * (getattr(line, 'discount', 0.0) or 0.0) / 100
                for line in order.order_line
            )

    # =========================================================================
    # CRUD OVERRIDE
    # =========================================================================

    def button_confirm(self):
        """Override: Sinh mã nội bộ khi xác nhận."""
        for order in self:
            if not order.internal_code:
                order.internal_code = self.env['ir.sequence'].next_by_code(
                    'purchase.order.internal'
                ) or _('New')
        return super().button_confirm()

    def unlink(self):
        """Override: Không cho xóa đơn đã duyệt."""
        if any(o.approval_state == 'approved' for o in self):
            raise UserError(_('Không thể xóa đơn mua hàng đã được phê duyệt!'))
        return super().unlink()

    # =========================================================================
    # ACTION METHODS
    # =========================================================================

    def action_approve(self):
        """Phê duyệt đơn mua."""
        self.ensure_one()
        self._check_approval_rights()
        self.write({
            'approval_state': 'approved',
            'approver_id': self.env.uid,
            'approval_date': fields.Datetime.now(),
            'rejection_reason': False,
        })
        self._send_approval_email()
        _logger.info("PO %s approved by %s", self.name, self.env.user.name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Phê Duyệt Thành Công'),
                'message': _('Đơn mua %s đã được phê duyệt!') % self.name,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_reject(self):
        """Mở wizard từ chối."""
        self.ensure_one()
        self._check_approval_rights()
        return {
            'name': _('Lý Do Từ Chối'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_order_name': self.name,
            },
        }

    def action_reset_to_pending(self):
        """Reset về chờ duyệt."""
        self.ensure_one()
        self.write({
            'approval_state': 'pending',
            'approver_id': False,
            'approval_date': False,
            'rejection_reason': False,
        })

    # =========================================================================
    # PRIVATE
    # =========================================================================

    def _check_approval_rights(self):
        if not self.env.user.has_group('purchase.group_purchase_manager'):
            raise UserError(_('Chỉ Quản Lý Mua Hàng mới có quyền phê duyệt!'))

    def _send_approval_email(self):
        template = self.env.ref(
            'purchase_management_custom.email_template_purchase_approved',
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=False)

    # =========================================================================
    # VENDOR EVALUATION
    # =========================================================================

    def action_evaluate_vendor(self):
        """Mở wizard đánh giá nhà cung cấp sau khi nhận hàng xong."""
        self.ensure_one()
        if self.state not in ('purchase', 'done'):
            raise UserError(_('Chỉ có thể đánh giá NCC sau khi đơn hàng được xác nhận!'))
        return {
            'name': _('Đánh Giá Nhà Cung Cấp'),
            'type': 'ir.actions.act_window',
            'res_model': 'vendor.evaluation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
        }
