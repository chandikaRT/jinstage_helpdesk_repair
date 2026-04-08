# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestRepairTypeClassification(TransactionCase):
    """Tests for the four repair type classification booleans (related fields from ticket type)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create all four ticket types with correct flag combinations
        cls.type_uw_rug = cls.env['helpdesk.ticket.type'].create({
            'name': 'Test - Under Warranty - RUG',
            'is_rug': True,
            'is_rug_confirmed': True,
        })
        cls.type_uw_external = cls.env['helpdesk.ticket.type'].create({
            'name': 'Test - Under Warranty - External not RUG',
            'is_rug': True,
            'is_rug_confirmed': False,
        })
        cls.type_nuw_serial = cls.env['helpdesk.ticket.type'].create({
            'name': 'Test - Not UW With Serial',
            'is_with_serial_no': True,
        })
        cls.type_nuw_no_serial = cls.env['helpdesk.ticket.type'].create({
            'name': 'Test - Not UW Without Serial',
            'is_without_serial_no': True,
        })
        cls.partner = cls.env.ref('base.res_partner_1')
        cls.team = cls.env['helpdesk.team'].search([], limit=1)

    def _make_ticket(self, ticket_type=None, name='Test Ticket'):
        vals = {'name': name, 'partner_id': self.partner.id}
        if self.team:
            vals['team_id'] = self.team.id
        if ticket_type:
            vals['ticket_type_id'] = ticket_type.id
        return self.env['helpdesk.ticket'].create(vals)

    def test_under_warranty_rug_flags(self):
        ticket = self._make_ticket(self.type_uw_rug)
        self.assertTrue(ticket.rug_repair)
        self.assertTrue(ticket.rug_confirmed)
        self.assertFalse(ticket.normal_repair_with_serial_no)
        self.assertFalse(ticket.normal_repair_without_serial_no)

    def test_external_not_rug_flags(self):
        ticket = self._make_ticket(self.type_uw_external)
        self.assertTrue(ticket.rug_repair)
        self.assertFalse(ticket.rug_confirmed)
        self.assertFalse(ticket.normal_repair_with_serial_no)
        self.assertFalse(ticket.normal_repair_without_serial_no)

    def test_normal_serial_type_flags(self):
        ticket = self._make_ticket(self.type_nuw_serial)
        self.assertFalse(ticket.rug_repair)
        self.assertFalse(ticket.rug_confirmed)
        self.assertTrue(ticket.normal_repair_with_serial_no)
        self.assertFalse(ticket.normal_repair_without_serial_no)

    def test_normal_no_serial_type_flags(self):
        ticket = self._make_ticket(self.type_nuw_no_serial)
        self.assertFalse(ticket.rug_repair)
        self.assertFalse(ticket.rug_confirmed)
        self.assertFalse(ticket.normal_repair_with_serial_no)
        self.assertTrue(ticket.normal_repair_without_serial_no)

    def test_type_change_recomputes(self):
        """Changing ticket type triggers recompute of all four related booleans."""
        ticket = self._make_ticket(self.type_uw_rug)
        self.assertTrue(ticket.rug_repair)
        self.assertTrue(ticket.rug_confirmed)
        # Change to serial type
        ticket.write({'ticket_type_id': self.type_nuw_serial.id})
        ticket.invalidate_recordset()
        self.assertFalse(ticket.rug_repair)
        self.assertFalse(ticket.rug_confirmed)
        self.assertTrue(ticket.normal_repair_with_serial_no)


class TestRepairCancelReopen(TransactionCase):
    """Tests for cancel and reopen audit trail."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env.ref('base.res_partner_1')
        cls.team = cls.env['helpdesk.team'].search([], limit=1)

    def _make_ticket(self, name='Test Cancel Ticket'):
        vals = {'name': name, 'partner_id': self.partner.id}
        if self.team:
            vals['team_id'] = self.team.id
        return self.env['helpdesk.ticket'].create(vals)

    def test_cancel_sets_audit_fields(self):
        ticket = self._make_ticket()
        self.assertFalse(ticket.cancelled)
        ticket.action_cancel_ticket()
        self.assertTrue(ticket.cancelled)
        self.assertEqual(ticket.cancelled_by, self.env.user)
        self.assertIsNotNone(ticket.cancelled_date)
        # cancelled_stage_id may be False if no stage set yet — just verify field written
        self.assertEqual(ticket.cancelled_stage_id, ticket.stage_id)

    def test_cancel_twice_raises_error(self):
        ticket = self._make_ticket()
        ticket.action_cancel_ticket()
        with self.assertRaises(UserError):
            ticket.action_cancel_ticket()

    def test_reopen_clears_cancelled(self):
        ticket = self._make_ticket()
        ticket.action_cancel_ticket()
        self.assertTrue(ticket.cancelled)
        ticket.action_reopen_ticket()
        self.assertFalse(ticket.cancelled)
        self.assertEqual(ticket.reopened_by, self.env.user)
        self.assertIsNotNone(ticket.reopened_date)

    def test_reopen_non_cancelled_raises_error(self):
        ticket = self._make_ticket()
        self.assertFalse(ticket.cancelled)
        with self.assertRaises(UserError):
            ticket.action_reopen_ticket()


class TestRUGWorkflow(TransactionCase):
    """Tests for RUG approval workflow — distinguishing Under Warranty RUG from External not RUG."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.type_uw_rug = cls.env['helpdesk.ticket.type'].create({
            'name': 'Test UW RUG',
            'is_rug': True,
            'is_rug_confirmed': True,
        })
        cls.type_uw_external = cls.env['helpdesk.ticket.type'].create({
            'name': 'Test UW External',
            'is_rug': True,
            'is_rug_confirmed': False,
        })
        cls.partner = cls.env.ref('base.res_partner_1')
        cls.team = cls.env['helpdesk.team'].search([], limit=1)
        # Create a repair location for transfer tests
        cls.repair_location = cls.env['stock.location'].search(
            [('usage', '=', 'internal')], limit=1
        )

    def _make_rug_ticket(self):
        vals = {
            'name': 'Test RUG Ticket',
            'partner_id': self.partner.id,
            'ticket_type_id': self.type_uw_rug.id,
        }
        if self.team:
            vals['team_id'] = self.team.id
        return self.env['helpdesk.ticket'].create(vals)

    def _make_external_ticket(self):
        vals = {
            'name': 'Test External Ticket',
            'partner_id': self.partner.id,
            'ticket_type_id': self.type_uw_external.id,
        }
        if self.team:
            vals['team_id'] = self.team.id
        return self.env['helpdesk.ticket'].create(vals)

    def test_send_rug_request(self):
        ticket = self._make_rug_ticket()
        self.assertTrue(ticket.rug_confirmed)
        ticket.action_send_rug_request()
        self.assertTrue(ticket.rug_request_sent)
        self.assertEqual(ticket.rug_approval_status, 'pending')

    def test_send_rug_request_blocked_for_external(self):
        """External not RUG ticket (rug_confirmed=False) must NOT be able to send RUG request."""
        ticket = self._make_external_ticket()
        self.assertFalse(ticket.rug_confirmed)
        with self.assertRaises(UserError):
            ticket.action_send_rug_request()

    def test_send_rug_request_twice_raises_error(self):
        ticket = self._make_rug_ticket()
        ticket.action_send_rug_request()
        with self.assertRaises(UserError):
            ticket.action_send_rug_request()

    def test_approve_rug(self):
        """Approval sets rug_approved=True. rug_confirmed comes from type, NOT set by approval."""
        ticket = self._make_rug_ticket()
        ticket.action_send_rug_request()
        ticket.action_approve_rug()
        self.assertTrue(ticket.rug_approved)
        self.assertEqual(ticket.rug_approval_status, 'approved')
        # rug_confirmed is from ticket type (related field), not set during approval
        self.assertTrue(ticket.rug_confirmed)

    def test_reject_rug(self):
        ticket = self._make_rug_ticket()
        ticket.action_send_rug_request()
        ticket.action_reject_rug()
        self.assertFalse(ticket.rug_approved)
        self.assertEqual(ticket.rug_approval_status, 'rejected')

    def test_factory_blocked_without_approval(self):
        """Under Warranty - RUG: factory blocked until rug_approved=True."""
        ticket = self._make_rug_ticket()
        ticket.write({
            'send_to_centre': True,
            'receive_at_centre': True,
            'repair_location': self.repair_location.id,
        })
        # Create a dummy picking so picking_count > 0
        picking_type = self.env['stock.picking.type'].search(
            [('code', '=', 'incoming')], limit=1
        )
        if picking_type:
            self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': self.env.ref('stock.stock_location_customers').id,
                'location_dest_id': self.repair_location.id,
                'helpdesk_ticket_id': ticket.id,
            })
        with self.assertRaises(UserError):
            ticket.action_send_to_factory()

    def test_factory_allowed_after_approval(self):
        """Under Warranty - RUG: factory allowed once rug_approved=True."""
        ticket = self._make_rug_ticket()
        ticket.write({
            'send_to_centre': True,
            'receive_at_centre': True,
        })
        ticket.action_send_rug_request()
        ticket.action_approve_rug()
        # Should NOT raise UserError
        ticket.action_send_to_factory()
        self.assertTrue(ticket.send_to_factory)

    def test_external_not_rug_factory_no_approval_needed(self):
        """External not RUG: can reach factory without any approval step."""
        ticket = self._make_external_ticket()
        self.assertFalse(ticket.rug_confirmed)
        ticket.write({
            'send_to_centre': True,
            'receive_at_centre': True,
        })
        # Must NOT raise UserError — rug_confirmed=False means no approval gate
        ticket.action_send_to_factory()
        self.assertTrue(ticket.send_to_factory)


class TestSerialNumber(TransactionCase):
    """Tests for serial number creation and management."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.type_serial = cls.env['helpdesk.ticket.type'].create({
            'name': 'Test Serial Type',
            'is_with_serial_no': True,
        })
        cls.type_no_serial = cls.env['helpdesk.ticket.type'].create({
            'name': 'Test No Serial Type',
            'is_without_serial_no': True,
        })
        cls.partner = cls.env.ref('base.res_partner_1')
        cls.team = cls.env['helpdesk.team'].search([], limit=1)

    def _make_serial_ticket(self):
        vals = {
            'name': 'REP/2026/00001',
            'partner_id': self.partner.id,
            'ticket_type_id': self.type_serial.id,
        }
        if self.team:
            vals['team_id'] = self.team.id
        return self.env['helpdesk.ticket'].create(vals)

    def _make_no_serial_ticket(self):
        vals = {
            'name': 'REP/2026/00002',
            'partner_id': self.partner.id,
            'ticket_type_id': self.type_no_serial.id,
        }
        if self.team:
            vals['team_id'] = self.team.id
        return self.env['helpdesk.ticket'].create(vals)

    def test_create_serial(self):
        ticket = self._make_serial_ticket()
        self.assertFalse(ticket.repair_serial_created)
        ticket.action_create_serial_number()
        self.assertTrue(ticket.repair_serial_created)
        self.assertTrue(ticket.sn_updated)
        self.assertTrue(ticket.repair_serial_no)
        # Verify stock.lot was created
        lot = self.env['stock.lot'].browse(ticket.repair_serial_no.id)
        self.assertTrue(lot.exists())

    def test_create_serial_twice_raises_error(self):
        ticket = self._make_serial_ticket()
        ticket.action_create_serial_number()
        with self.assertRaises(UserError):
            ticket.action_create_serial_number()

    def test_create_serial_blocked_for_no_serial_type(self):
        ticket = self._make_no_serial_ticket()
        self.assertTrue(ticket.normal_repair_without_serial_no)
        with self.assertRaises(UserError):
            ticket.action_create_serial_number()


class TestStageDate(TransactionCase):
    """Tests for stage change timestamp."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env.ref('base.res_partner_1')
        cls.team = cls.env['helpdesk.team'].search([], limit=1)
        cls.stage1 = cls.env['helpdesk.stage'].search([], limit=1)
        cls.stage2 = cls.env['helpdesk.stage'].search([('id', '!=', cls.stage1.id)], limit=1)

    def test_stage_change_updates_stage_date(self):
        vals = {'name': 'Test Stage Date', 'partner_id': self.partner.id}
        if self.team:
            vals['team_id'] = self.team.id
        ticket = self.env['helpdesk.ticket'].create(vals)
        if self.stage1 and self.stage2:
            ticket.write({'stage_id': self.stage1.id})
            first_date = ticket.stage_date
            self.assertIsNotNone(first_date)
            ticket.write({'stage_id': self.stage2.id})
            self.assertNotEqual(ticket.stage_date, first_date)
