# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestRabWorkflow(TransactionCase):
    """Test cases for RAB Management workflow/status"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test customer
        cls.customer = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'contact_type': 'customer',
        })
        
        # Create test vendor
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Test Vendor',
            'contact_type': 'vendor',
        })
        
        # Create test product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'consu',
            'list_price': 100.0,
        })

    def _create_rab_with_lines(self):
        """Helper to create RAB with complete lines and vendor"""
        rab = self.env['rab.management'].create({
            'customer_id': self.customer.id,
        })
        
        # Add line
        line = self.env['rab.management.line'].create({
            'rab_id': rab.id,
            'product_id': self.product.id,
            'quantity': 1.0,
        })
        
        # Add vendor and finalize
        vendor_comp = self.env['rab.vendor.comparison'].create({
            'rab_line_id': line.id,
            'vendor_id': self.vendor.id,
            'price': 80.0,
        })
        vendor_comp.action_set_negotiation()
        vendor_comp.action_set_final()
        
        return rab

    def test_01_initial_state_is_draft(self):
        """Test RAB starts in draft state"""
        rab = self.env['rab.management'].create({
            'customer_id': self.customer.id,
        })
        self.assertEqual(rab.state, 'draft', "Initial state should be draft")

    def test_02_cannot_confirm_without_lines(self):
        """Test cannot confirm RAB without lines"""
        rab = self.env['rab.management'].create({
            'customer_id': self.customer.id,
        })
        
        with self.assertRaises(UserError) as cm:
            rab.action_confirm()
        self.assertIn('tanpa detail', str(cm.exception))

    def test_03_cannot_confirm_without_vendor(self):
        """Test cannot confirm RAB without vendor selection"""
        rab = self.env['rab.management'].create({
            'customer_id': self.customer.id,
        })
        
        # Add line but no vendor
        self.env['rab.management.line'].create({
            'rab_id': rab.id,
            'product_id': self.product.id,
            'quantity': 1.0,
        })
        
        with self.assertRaises(UserError) as cm:
            rab.action_confirm()
        self.assertIn('vendor terpilih', str(cm.exception))

    def test_04_confirm_success(self):
        """Test successful confirmation"""
        rab = self._create_rab_with_lines()
        
        rab.action_confirm()
        self.assertEqual(rab.state, 'confirmed', "State should be confirmed")

    def test_05_cannot_delete_confirmed_rab(self):
        """Test cannot delete RAB that is not in draft"""
        rab = self._create_rab_with_lines()
        
        rab.action_confirm()
        
        with self.assertRaises(UserError) as cm:
            rab.unlink()
        self.assertIn('tidak boleh dihapus', str(cm.exception))

    def test_06_can_delete_draft_rab(self):
        """Test can delete RAB in draft state"""
        rab = self.env['rab.management'].create({
            'customer_id': self.customer.id,
        })
        
        # Should not raise error
        rab.unlink()

    def test_07_workflow_draft_to_confirmed(self):
        """Test complete workflow: draft -> confirmed"""
        rab = self._create_rab_with_lines()
        
        # Draft
        self.assertEqual(rab.state, 'draft')
        
        # Confirm
        rab.action_confirm()
        self.assertEqual(rab.state, 'confirmed')

    def test_08_state_options(self):
        """Test only draft and confirmed states are available"""
        rab = self.env['rab.management'].create({
            'customer_id': self.customer.id,
        })
        
        state_field = rab._fields['state']
        states = dict(state_field.selection)
        
        self.assertIn('draft', states)
        self.assertIn('confirmed', states)
        # Removed states should not be present
        self.assertNotIn('to_approve', states)
        self.assertNotIn('revision', states)
        self.assertNotIn('approved', states)

    def test_09_state_tracking(self):
        """Test state field has tracking enabled"""
        rab = self.env['rab.management'].create({
            'customer_id': self.customer.id,
        })
        
        state_field = rab._fields['state']
        self.assertTrue(state_field.tracking, "State field should have tracking enabled")
