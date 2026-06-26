# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    """
    Kế thừa Stock Picking — Bổ sung QC checklist và kiểm soát kho.
    """
    _inherit = 'stock.picking'
    _description = 'Stock Picking Custom'

    # =========================================================================
    # FIELDS
    # =========================================================================

    qc_required = fields.Boolean(
        string='Yêu Cầu Kiểm Tra QC',
        default=False,
        help='Bật để bắt buộc hoàn thành QC checklist trước khi validate.',
    )
    qc_passed = fields.Boolean(
        string='QC Đạt',
        default=False,
        readonly=True,
        copy=False,
        tracking=True,
    )
    qc_inspector_id = fields.Many2one(
        comodel_name='res.users',
        string='Người Kiểm Tra QC',
        readonly=True,
        copy=False,
    )
    qc_date = fields.Datetime(
        string='Ngày Kiểm Tra QC',
        readonly=True,
        copy=False,
    )
    qc_note = fields.Text(
        string='Ghi Chú QC',
        copy=False,
        help='Ghi chú kết quả kiểm tra chất lượng.',
    )

    # QC Checklist items
    qc_check_quantity = fields.Boolean(
        string='✅ Số Lượng Đúng',
        default=False,
    )
    qc_check_packaging = fields.Boolean(
        string='✅ Bao Bì Nguyên Vẹn',
        default=False,
    )
    qc_check_expiry = fields.Boolean(
        string='✅ Hạn Sử Dụng Còn Hạn',
        default=False,
    )
    qc_check_quality = fields.Boolean(
        string='✅ Chất Lượng Đạt',
        default=False,
    )
    qc_check_documents = fields.Boolean(
        string='✅ Chứng Từ Đầy Đủ',
        default=False,
    )

    # Thông tin bổ sung
    priority_custom = fields.Selection(
        selection=[
            ('0', 'Bình Thường'),
            ('1', 'Ưu Tiên'),
            ('2', 'Khẩn Cấp'),
        ],
        string='Mức Ưu Tiên Kho',
        default='0',
        tracking=True,
    )
    note_internal = fields.Text(
        string='Ghi Chú Nội Bộ Kho',
    )
    is_return = fields.Boolean(
        string='Phiếu Trả Hàng',
        compute='_compute_is_return',
        store=True,
    )

    # =========================================================================
    # COMPUTE
    # =========================================================================

    @api.depends('origin')
    def _compute_is_return(self):
        for picking in self:
            picking.is_return = bool(
                picking.origin and 'Return' in picking.origin
            )

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================

    @api.constrains('qc_check_quantity', 'qc_check_packaging',
                    'qc_check_expiry', 'qc_check_quality', 'qc_check_documents')
    def _check_all_qc_done(self):
        """Nếu QC bắt buộc, tất cả checklist phải được tick."""
        pass  # Kiểm tra thực sự ở button_validate

    # =========================================================================
    # OVERRIDE
    # =========================================================================

    def button_validate(self):
        """Override: Kiểm tra QC checklist trước khi validate."""
        for picking in self:
            if picking.qc_required and not picking.qc_passed:
                # Kiểm tra tất cả checklist
                all_checks = [
                    picking.qc_check_quantity,
                    picking.qc_check_packaging,
                    picking.qc_check_quality,
                    picking.qc_check_documents,
                ]
                if not all(all_checks):
                    raise UserError(
                        _('⚠️ Phiếu kho này yêu cầu hoàn thành QC checklist!\n'
                          'Vui lòng kiểm tra đủ tất cả các mục và xác nhận QC Đạt trước khi validate.')
                    )
                # Auto-confirm QC
                picking.write({
                    'qc_passed': True,
                    'qc_inspector_id': self.env.uid,
                    'qc_date': fields.Datetime.now(),
                })
        return super().button_validate()

    # =========================================================================
    # ACTION METHODS
    # =========================================================================

    def action_confirm_qc_passed(self):
        """Xác nhận kiểm tra QC đạt."""
        self.ensure_one()
        checklist = [
            self.qc_check_quantity,
            self.qc_check_packaging,
            self.qc_check_quality,
            self.qc_check_documents,
        ]
        if not all(checklist):
            raise UserError(
                _('Vui lòng tick đầy đủ tất cả mục kiểm tra trước khi xác nhận QC Đạt!')
            )
        self.write({
            'qc_passed': True,
            'qc_inspector_id': self.env.uid,
            'qc_date': fields.Datetime.now(),
        })
        self.message_post(
            body=_('<b>✅ QC PASSED</b> bởi %s lúc %s') % (
                self.env.user.name,
                fields.Datetime.now().strftime('%d/%m/%Y %H:%M')
            ),
            message_type='comment',
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('QC Đạt'),
                'message': _('Phiếu kho %s đã được xác nhận QC đạt!') % self.name,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_reset_qc(self):
        """Reset QC về chưa kiểm tra."""
        self.ensure_one()
        self.write({
            'qc_passed': False,
            'qc_inspector_id': False,
            'qc_date': False,
            'qc_check_quantity': False,
            'qc_check_packaging': False,
            'qc_check_expiry': False,
            'qc_check_quality': False,
            'qc_check_documents': False,
        })

    # =========================================================================
    # CRON
    # =========================================================================

    @api.model
    def _cron_check_low_stock(self):
        """Cron job: Cảnh báo sản phẩm tồn kho dưới mức tối thiểu."""
        products_low = self.env['product.product'].search([
            ('type', '=', 'consu'),
            ('qty_available', '<', 10),  # Ngưỡng tối thiểu mặc định
        ])
        if products_low:
            manager_group = self.env.ref(
                'stock.group_stock_manager', raise_if_not_found=False
            )
            if manager_group:
                managers = manager_group.users.filtered('active')
                if managers:
                    body = _(
                        '<p>⚠️ <b>%d sản phẩm</b> có tồn kho thấp:</p><ul>%s</ul>'
                    ) % (
                        len(products_low),
                        ''.join(
                            '<li><b>%s</b>: còn %.0f %s</li>' % (
                                p.name, p.qty_available, p.uom_id.name
                            )
                            for p in products_low[:20]
                        )
                    )
                    self.env['mail.thread'].sudo().message_notify(
                        partner_ids=managers.mapped('partner_id').ids,
                        subject=_('[Cảnh Báo Kho] %d Sản Phẩm Sắp Hết') % len(products_low),
                        body=body,
                    )
        _logger.info("Cron low stock check: %d products low", len(products_low))
