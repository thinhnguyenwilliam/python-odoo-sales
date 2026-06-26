# -*- coding: utf-8 -*-
# Copyright 2024 Your Company <info@yourcompany.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

APPROVAL_STATES = [
    ('pending', 'Chờ Duyệt'),
    ('approved', 'Đã Duyệt'),
    ('rejected', 'Từ Chối'),
]


class SaleOrder(models.Model):
    """
    Kế thừa Sale Order - Bổ sung approval workflow cho doanh nghiệp.

    Quy trình duyệt:
        Draft → (Confirm) → Sale (Chờ Duyệt) → Approved / Rejected
    """
    _inherit = 'sale.order'
    _description = 'Sale Order Custom'

    # =========================================================================
    # FIELDS
    # =========================================================================

    # --- Mã nội bộ ---
    internal_code = fields.Char(
        string='Mã Nội Bộ',
        copy=False,
        readonly=True,
        index=True,
        help='Mã đơn hàng nội bộ, tự động sinh khi xác nhận.',
    )

    # --- Approval ---
    approval_state = fields.Selection(
        selection=APPROVAL_STATES,
        string='Trạng Thái Duyệt',
        default='pending',
        required=True,
        tracking=True,
        copy=False,
        help='Trạng thái duyệt đơn hàng của phòng kinh doanh.',
    )
    approver_id = fields.Many2one(
        comodel_name='res.users',
        string='Người Duyệt',
        readonly=True,
        copy=False,
        tracking=True,
        domain="[('share', '=', False)]",
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

    # --- Thông tin bổ sung ---
    priority_level = fields.Selection(
        selection=[
            ('normal', 'Bình Thường'),
            ('high', 'Cao'),
            ('urgent', 'Khẩn Cấp'),
        ],
        string='Mức Độ Ưu Tiên',
        default='normal',
        required=True,
        tracking=True,
    )
    department_id = fields.Many2one(
        comodel_name='hr.department',
        string='Phòng Ban',
        tracking=True,
        help='Phòng ban phụ trách đơn hàng này.',
    )
    note_internal = fields.Text(
        string='Ghi Chú Nội Bộ',
        help='Ghi chú nội bộ, không hiển thị trên báo cáo.',
    )

    # --- Computed Fields ---
    total_discount_amount = fields.Monetary(
        string='Tổng Chiết Khấu',
        compute='_compute_discount_totals',
        store=True,
        currency_field='currency_id',
        help='Tổng giá trị chiết khấu của tất cả dòng sản phẩm.',
    )
    total_weight = fields.Float(
        string='Tổng Trọng Lượng (kg)',
        compute='_compute_total_weight',
        store=True,
        digits=(16, 3),
    )
    is_overdue = fields.Boolean(
        string='Quá Hạn',
        compute='_compute_is_overdue',
        store=True,
        help='True nếu đơn hàng chưa hoàn thành và đã quá ngày giao dự kiến.',
    )

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================

    @api.constrains('internal_code', 'company_id')
    def _check_unique_internal_code(self):
        """Đảm bảo mã nội bộ unique trong cùng công ty."""
        for record in self:
            if not record.internal_code:
                continue
            domain = [
                ('internal_code', '=', record.internal_code),
                ('company_id', '=', record.company_id.id),
                ('id', '!=', record.id),
            ]
            if self.search_count(domain):
                raise ValidationError(
                    _("Mã nội bộ '%s' đã tồn tại trong công ty '%s'!")
                    % (record.internal_code, record.company_id.name)
                )

    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================

    @api.depends('order_line.discount', 'order_line.price_unit', 'order_line.product_uom_qty')
    def _compute_discount_totals(self):
        """Tính tổng giá trị chiết khấu."""
        for order in self:
            order.total_discount_amount = sum(
                line.price_unit * line.product_uom_qty * (line.discount or 0.0) / 100
                for line in order.order_line
            )

    @api.depends('order_line.product_id', 'order_line.product_uom_qty')
    def _compute_total_weight(self):
        """Tính tổng trọng lượng đơn hàng."""
        for order in self:
            order.total_weight = sum(
                line.product_id.weight * line.product_uom_qty
                for line in order.order_line
                if line.product_id
            )

    @api.depends('commitment_date', 'state')
    def _compute_is_overdue(self):
        """Xác định đơn hàng có bị quá hạn không."""
        today = fields.Date.today()
        for order in self:
            order.is_overdue = bool(
                order.commitment_date
                and order.state in ('sale', 'done')
                and fields.Date.to_date(order.commitment_date) < today
            )

    # =========================================================================
    # ONCHANGE METHODS
    # =========================================================================

    @api.onchange('partner_id')
    def _onchange_partner_id_set_priority(self):
        """Tự động set priority theo hạng khách hàng."""
        if self.partner_id:
            # Khách VIP (category đặc biệt) → urgent
            vip_category = self.env.ref(
                'base.res_partner_category_0', raise_if_not_found=False
            )
            if vip_category and vip_category in self.partner_id.category_id:
                self.priority_level = 'urgent'

    # =========================================================================
    # CRUD OVERRIDE
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        _logger.info(
            "Created %d sale order(s): %s",
            len(records),
            ', '.join(records.mapped('name'))
        )
        return records

    def action_confirm(self):
        """Override: Sinh mã nội bộ khi xác nhận đơn hàng."""
        for order in self:
            if not order.internal_code:
                order.internal_code = self.env['ir.sequence'].next_by_code(
                    'sale.order.internal'
                ) or _('New')
        return super().action_confirm()

    def unlink(self):
        """Override: Không cho xóa đơn đã duyệt."""
        if any(order.approval_state == 'approved' for order in self):
            raise UserError(
                _('Không thể xóa đơn hàng đã được phê duyệt!\n'
                  'Vui lòng liên hệ quản lý để hủy đơn.')
            )
        return super().unlink()

    # =========================================================================
    # ACTION METHODS
    # =========================================================================

    def action_submit_approval(self):
        """Gửi đơn hàng để phê duyệt."""
        self.ensure_one()
        if self.state != 'sale':
            raise UserError(_('Chỉ có thể gửi duyệt đơn hàng đã xác nhận!'))
        if not self.order_line:
            raise UserError(_('Đơn hàng phải có ít nhất 1 sản phẩm!'))

        self.write({'approval_state': 'pending'})
        self._notify_approvers()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã Gửi Duyệt'),
                'message': _('Đơn hàng %s đã gửi đến quản lý phê duyệt.') % self.name,
                'type': 'info',
                'sticky': False,
            },
        }

    def action_approve(self):
        """Phê duyệt đơn hàng."""
        self.ensure_one()
        self._check_approval_rights()

        self.write({
            'approval_state': 'approved',
            'approver_id': self.env.uid,
            'approval_date': fields.Datetime.now(),
            'rejection_reason': False,
        })

        self._send_approval_email()
        _logger.info("Sale order %s approved by user %s", self.name, self.env.user.name)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Phê Duyệt Thành Công'),
                'message': _('Đơn hàng %s đã được phê duyệt!') % self.name,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_reject(self):
        """Mở wizard từ chối đơn hàng."""
        self.ensure_one()
        self._check_approval_rights()
        return {
            'name': _('Lý Do Từ Chối'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_order_name': self.name,
            },
        }

    def action_reset_to_pending(self):
        """Reset về trạng thái chờ duyệt."""
        self.ensure_one()
        self.write({
            'approval_state': 'pending',
            'approver_id': False,
            'approval_date': False,
            'rejection_reason': False,
        })

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _check_approval_rights(self):
        """Kiểm tra quyền phê duyệt đơn hàng."""
        self.ensure_one()
        if not self.env.user.has_group('sales_team.group_sale_manager'):
            raise UserError(
                _('Chỉ Quản Lý Kinh Doanh mới có quyền phê duyệt đơn hàng!\n'
                  'Vui lòng liên hệ: %s') % self.env.user.company_id.name
            )

    def _notify_approvers(self):
        """Gửi thông báo đến các quản lý có quyền duyệt."""
        self.ensure_one()
        manager_group = self.env.ref('sales_team.group_sale_manager', raise_if_not_found=False)
        if not manager_group:
            return

        managers = manager_group.users.filtered(
            lambda u: u.company_id == self.company_id and u.active
        )
        if managers:
            self.message_notify(
                partner_ids=managers.mapped('partner_id').ids,
                subject=_('Đơn Hàng Chờ Phê Duyệt: %s') % self.name,
                body=_(
                    '<p>Đơn hàng <b>%s</b> của khách hàng <b>%s</b> '
                    'cần phê duyệt.</p>'
                    '<p>Tổng tiền: <b>%s %s</b></p>'
                ) % (
                    self.name,
                    self.partner_id.name,
                    '{:,.0f}'.format(self.amount_total),
                    self.currency_id.symbol,
                ),
            )

    def _send_approval_email(self):
        """Gửi email thông báo phê duyệt đến khách hàng."""
        self.ensure_one()
        template = self.env.ref(
            'sale_management_custom.email_template_sale_approved',
            raise_if_not_found=False,
        )
        if template:
            # force_send=False: đẩy vào queue, không block request
            template.send_mail(self.id, force_send=False)

    # =========================================================================
    # CRON METHODS
    # =========================================================================

    @api.model
    def _cron_check_overdue_orders(self):
        """Cron job: Cập nhật cờ is_overdue và gửi thông báo đơn quá hạn."""
        overdue_orders = self.search([
            ('state', 'in', ('sale', 'done')),
            ('commitment_date', '!=', False),
            ('commitment_date', '<', fields.Datetime.now()),
        ])
        if overdue_orders:
            # Trigger recompute
            overdue_orders._compute_is_overdue()
            # Thông báo cho manager
            manager_group = self.env.ref(
                'sales_team.group_sale_manager', raise_if_not_found=False
            )
            if manager_group:
                managers = manager_group.users.filtered('active')
                if managers:
                    body = _(
                        '<p>Có <b>%d</b> đơn hàng đã quá hạn giao:</p><ul>%s</ul>'
                    ) % (
                        len(overdue_orders),
                        ''.join(
                            '<li><b>%s</b> — %s (%s)</li>' % (
                                o.name, o.partner_id.name,
                                o.commitment_date.strftime('%d/%m/%Y')
                            )
                            for o in overdue_orders[:10]
                        )
                    )
                    self.env['mail.thread'].sudo().message_notify(
                        partner_ids=managers.mapped('partner_id').ids,
                        subject=_('[Cảnh Báo] %d Đơn Hàng Quá Hạn') % len(overdue_orders),
                        body=body,
                    )
        _logger.info("Cron overdue check: %d orders overdue", len(overdue_orders))

    @api.model
    def _cron_remind_pending_orders(self):
        """Cron job: Nhắc Manager duyệt các đơn đã chờ > 2 ngày."""
        deadline = fields.Datetime.subtract(fields.Datetime.now(), days=2)
        pending_orders = self.search([
            ('approval_state', '=', 'pending'),
            ('state', '=', 'sale'),
            ('write_date', '<', deadline),
        ])
        if not pending_orders:
            return

        manager_group = self.env.ref(
            'sales_team.group_sale_manager', raise_if_not_found=False
        )
        if not manager_group:
            return

        managers = manager_group.users.filtered(
            lambda u: u.active and u.company_id in pending_orders.mapped('company_id')
        )
        if managers:
            body = _(
                '<p>Có <b>%d</b> đơn hàng đang chờ duyệt quá <b>2 ngày</b>:</p><ul>%s</ul>'
            ) % (
                len(pending_orders),
                ''.join(
                    '<li><b>%s</b> — %s — %s %s</li>' % (
                        o.name, o.partner_id.name,
                        '{:,.0f}'.format(o.amount_total), o.currency_id.symbol
                    )
                    for o in pending_orders[:10]
                )
            )
            self.env['mail.thread'].sudo().message_notify(
                partner_ids=managers.mapped('partner_id').ids,
                subject=_('[Nhắc Nhở] %d Đơn Hàng Chờ Duyệt') % len(pending_orders),
                body=body,
            )
        _logger.info("Cron pending reminder: %d orders reminded", len(pending_orders))

