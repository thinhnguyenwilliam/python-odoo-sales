# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestSaleOrderLine(TransactionCase):
    """Test suite cho Sale Order Line — Margin và Discount constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env['res.users'].create({
            'name': 'Line Test Manager',
            'login': 'line_manager@test.com',
            'groups_id': [(4, cls.env.ref('sales_team.group_sale_manager').id)],
        })
        cls.salesman = cls.env['res.users'].create({
            'name': 'Line Test Salesman',
            'login': 'line_salesman@test.com',
            'groups_id': [(4, cls.env.ref('sales_team.group_sale_salesman').id)],
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Line Test Partner'})
        cls.product = cls.env['product.product'].create({
            'name': 'Line Test Product',
            'type': 'service',
            'list_price': 200.0,
            'standard_price': 100.0,
        })

    # =========================================================================
    # TEST: Margin Computation
    # =========================================================================

    def test_01_margin_amount_correct(self):
        """Test: Biên lợi nhuận = doanh thu - giá vốn."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 5,
                'price_unit': 200.0,
            })],
        })
        line = order.order_line[0]
        # Revenue = 200 * 5 = 1000, Cost = 100 * 5 = 500, Margin = 500
        self.assertAlmostEqual(line.margin_amount, 500.0, places=2)

    def test_02_margin_percent_correct(self):
        """Test: % biên lợi nhuận = margin / revenue * 100."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 200.0,
            })],
        })
        line = order.order_line[0]
        # Margin% = (200-100)/200 * 100 = 50%
        self.assertAlmostEqual(line.margin_percent, 50.0, places=1)

    def test_03_margin_zero_when_no_product(self):
        """Test: Margin = 0 khi không có sản phẩm."""
        order = self.env['sale.order'].create({'partner_id': self.partner.id})
        line = self.env['sale.order.line'].new({
            'order_id': order.id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
        })
        line._compute_margin_amount()
        self.assertEqual(line.margin_amount, 0.0)

    # =========================================================================
    # TEST: Discount Limit
    # =========================================================================

    def test_04_salesman_discount_max_10_percent(self):
        """Test: Nhân viên không được CK quá 10%."""
        with self.assertRaises(ValidationError):
            order = self.env['sale.order'].with_user(self.salesman).create({
                'partner_id': self.partner.id,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                    'price_unit': 200.0,
                    'discount': 15.0,  # > 10% → lỗi
                })],
            })
            order.order_line._check_discount_limit()

    def test_05_manager_discount_max_30_percent(self):
        """Test: Manager được CK tối đa 30%."""
        order = self.env['sale.order'].with_user(self.manager).create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 200.0,
                'discount': 25.0,  # OK cho manager
            })],
        })
        # Không raise exception
        order.order_line.with_user(self.manager)._check_discount_limit()
        self.assertEqual(order.order_line.discount, 25.0)

    def test_06_manager_discount_over_30_raises(self):
        """Test: Manager không được CK quá 30%."""
        with self.assertRaises(ValidationError):
            order = self.env['sale.order'].with_user(self.manager).create({
                'partner_id': self.partner.id,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                    'price_unit': 200.0,
                    'discount': 35.0,  # > 30% → lỗi
                })],
            })
            order.order_line.with_user(self.manager)._check_discount_limit()
