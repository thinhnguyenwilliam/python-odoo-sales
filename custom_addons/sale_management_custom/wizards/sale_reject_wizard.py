# -*- coding: utf-8 -*-
# Copyright 2024 Your Company <info@yourcompany.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleRejectWizard(models.TransientModel):
    """
    Wizard nhập lý do từ chối đơn hàng.

    TransientModel: Dữ liệu tự xóa sau session (không lưu vĩnh viễn).
    """
    _name = 'sale.reject.wizard'
    _description = 'Wizard Từ Chối Đơn Hàng'

    order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Đơn Hàng',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    order_name = fields.Char(
        string='Tên Đơn Hàng',
        readonly=True,
    )
    rejection_reason = fields.Text(
        string='Lý Do Từ Chối',
        required=True,
        help='Nêu rõ lý do từ chối để người tạo đơn biết và điều chỉnh.',
    )
    notify_salesman = fields.Boolean(
        string='Thông Báo Cho Nhân Viên',
        default=True,
        help='Gửi email thông báo đến nhân viên kinh doanh phụ trách.',
    )

    def action_confirm_reject(self):
        """Xác nhận từ chối đơn hàng."""
        self.ensure_one()

        if not self.rejection_reason or not self.rejection_reason.strip():
            raise UserError(_('Vui lòng nhập lý do từ chối!'))

        order = self.order_id
        order.write({
            'approval_state': 'rejected',
            'approver_id': self.env.uid,
            'approval_date': fields.Datetime.now(),
            'rejection_reason': self.rejection_reason,
        })

        # Log vào chatter
        order.message_post(
            body=_('<b>❌ Đơn hàng bị từ chối</b><br/>Lý do: %s') % self.rejection_reason,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        # Gửi email cho nhân viên nếu được chọn
        if self.notify_salesman and order.user_id:
            template = self.env.ref(
                'sale_management_custom.email_template_sale_rejected',
                raise_if_not_found=False,
            )
            if template:
                template.with_context(reason=self.rejection_reason).send_mail(
                    order.id, force_send=False
                )

        _logger.info(
            "Sale order %s rejected by %s. Reason: %s",
            order.name, self.env.user.name, self.rejection_reason
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã Từ Chối'),
                'message': _('Đơn hàng %s đã bị từ chối.') % order.name,
                'type': 'warning',
                'sticky': False,
            },
        }
