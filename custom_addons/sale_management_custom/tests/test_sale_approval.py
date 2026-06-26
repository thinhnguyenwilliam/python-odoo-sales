# -*- coding: utf-8 -*-
# Copyright 2024 Your Company <info@yourcompany.com>
# License LGPL-3.0 or later

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields


class TestSaleApproval(TransactionCase):
    """
    Test suite cho Sale Approval Workflow.

    Chạy: docker compose exec odoo odoo -d test_db \
          --test-enable --stop-after-init -i sale_management_custom
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Tạo users
        cls.manager = cls.env['res.users'].create({
            'name': 'Test Manager',
            'login': 'test_manager@test.com',
            'email': 'test_manager@test.com',
            'groups_id': [(4, cls.env.ref('sales_team.group_sale_manager').id)],
        })
        cls.salesman = cls.env['res.users'].create({
            'name': 'Test Salesman',
            'login': 'test_salesman@test.com',
            'email': 'test_salesman@test.com',
            'groups_id': [(4, cls.env.ref('sales_team.group_sale_salesman').id)],
        })

        # Tạo partner
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'customer_rank': 1,
        })

        # Tạo product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'service',
            'list_price': 100.0,
            'standard_price': 60.0,
        })

    def _create_sale_order(self, user=None):
        """Helper: Tạo sale order đã confirm."""
        user = user or self.salesman
        order = self.env['sale.order'].with_user(user).create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 5,
                'price_unit': 100.0,
            })],
        })
        order.with_user(user).action_confirm()
        return order

    # =========================================================================
    # TEST: Internal Code Generation
    # =========================================================================

    def test_01_internal_code_generated_on_confirm(self):
        """Test: Mã nội bộ tự sinh khi xác nhận đơn hàng."""
        order = self._create_sale_order()
        self.assertTrue(order.internal_code, "Mã nội bộ phải được tạo sau khi confirm")
        self.assertIn('SO-', order.internal_code, "Mã phải có prefix SO-")

    def test_02_internal_code_unique(self):
        """Test: Mã nội bộ phải unique trong cùng công ty."""
        order1 = self._create_sale_order()
        order2 = self._create_sale_order()
        self.assertNotEqual(
            order1.internal_code,
            order2.internal_code,
            "Hai đơn hàng không được có cùng mã nội bộ"
        )

    # =========================================================================
    # TEST: Approval Workflow
    # =========================================================================

    def test_03_initial_approval_state_is_pending(self):
        """Test: Đơn mới confirm phải ở trạng thái pending."""
        order = self._create_sale_order()
        self.assertEqual(order.approval_state, 'pending')

    def test_04_approve_requires_manager_group(self):
        """Test: Nhân viên thường không thể phê duyệt."""
        order = self._create_sale_order()
        with self.assertRaises(UserError, msg="Nhân viên không được phép duyệt"):
            order.with_user(self.salesman).action_approve()

    def test_05_manager_can_approve(self):
        """Test: Manager có thể phê duyệt thành công."""
        order = self._create_sale_order()
        order.with_user(self.manager).action_approve()
        self.assertEqual(order.approval_state, 'approved')
        self.assertEqual(order.approver_id, self.manager)
        self.assertIsNotNone(order.approval_date)

    def test_06_approved_order_clears_rejection_reason(self):
        """Test: Khi duyệt, lý do từ chối bị xóa."""
        order = self._create_sale_order()
        order.write({'rejection_reason': 'Test reason'})
        order.with_user(self.manager).action_approve()
        self.assertFalse(order.rejection_reason)

    def test_07_reject_requires_manager_group(self):
        """Test: Nhân viên không thể từ chối."""
        order = self._create_sale_order()
        with self.assertRaises(UserError):
            order.with_user(self.salesman).action_reject()

    def test_08_reset_to_pending(self):
        """Test: Reset về pending xóa thông tin approver."""
        order = self._create_sale_order()
        order.with_user(self.manager).action_approve()
        order.with_user(self.manager).action_reset_to_pending()
        self.assertEqual(order.approval_state, 'pending')
        self.assertFalse(order.approver_id)
        self.assertFalse(order.approval_date)

    # =========================================================================
    # TEST: Delete Protection
    # =========================================================================

    def test_09_cannot_delete_approved_order(self):
        """Test: Không thể xóa đơn đã duyệt."""
        order = self._create_sale_order()
        order.with_user(self.manager).action_approve()
        with self.assertRaises(UserError, msg="Phải raise lỗi khi xóa đơn đã duyệt"):
            order.with_user(self.manager).unlink()

    def test_10_can_delete_pending_order(self):
        """Test: Có thể xóa đơn đang pending (chưa duyệt)."""
        order = self._create_sale_order()
        # Reset to draft first
        order.action_cancel()
        order.action_draft()
        order_id = order.id
        order.unlink()
        self.assertFalse(
            self.env['sale.order'].browse(order_id).exists(),
            "Đơn pending bị hủy phải xóa được"
        )

    # =========================================================================
    # TEST: Computed Fields
    # =========================================================================

    def test_11_discount_total_computed(self):
        """Test: Tổng chiết khấu tính đúng."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 10,
                'price_unit': 100.0,
                'discount': 10.0,  # 10%
            })],
        })
        # Discount = 100 * 10 * 10% = 100
        self.assertAlmostEqual(order.total_discount_amount, 100.0, places=2)

    def test_12_total_weight_computed(self):
        """Test: Tổng trọng lượng tính đúng."""
        self.product.weight = 2.5
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 4,
            })],
        })
        # Weight = 2.5 * 4 = 10
        self.assertAlmostEqual(order.total_weight, 10.0, places=3)

    def test_13_is_overdue_false_for_future_date(self):
        """Test: Đơn có commitment_date tương lai không bị overdue."""
        order = self._create_sale_order()
        order.commitment_date = fields.Datetime.add(fields.Datetime.now(), days=10)
        order._compute_is_overdue()
        self.assertFalse(order.is_overdue)

    def test_14_priority_level_default_normal(self):
        """Test: Mức ưu tiên mặc định là normal."""
        order = self.env['sale.order'].create({'partner_id': self.partner.id})
        self.assertEqual(order.priority_level, 'normal')
