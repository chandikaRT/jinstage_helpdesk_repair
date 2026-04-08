# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestRepairWorkflowA_RUG(TransactionCase):
    """Full lifecycle test for Under Warranty - RUG repair."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.type_uw_rug = cls.env['helpdesk.ticket.type'].create({
            'name': 'Integration Test - UW RUG',
            'is_rug': True,
            'is_rug_confirmed': True,
        })
        cls.partner = cls.env.ref('base.res_partner_1')
        cls.team = cls.env['helpdesk.team'].search([], limit=1)
        cls.repair_location = cls.env['stock.location'].search(
            [('usage', '=', 'internal')], limit=1
        )
        cls.picking_type = cls.env['stock.picking.type'].search(
            [('code', '=', 'incoming')], limit=1
        )

    def _create_picking_for_ticket(self, ticket):
        """Helper to create a stock picking linked to the ticket."""
        if self.picking_type and self.repair_location:
            return self.env['stock.picking'].create({
                'picking_type_id': self.picking_type.id,
                'location_id': self.env.ref('stock.stock_location_customers').id,
                'location_dest_id': self.repair_location.id,
                'origin': ticket.name,
                'helpdesk_ticket_id': ticket.id,
            })

    def test_full_rug_workflow(self):
        """Simulate the complete Under Warranty - RUG lifecycle."""
        # Step 1: Create ticket
        vals = {
            'name': 'Integration RUG Test',
            'partner_id': self.partner.id,
            'ticket_type_id': self.type_uw_rug.id,
            'repair_location': self.repair_location.id if self.repair_location else False,
        }
        if self.team:
            vals['team_id'] = self.team.id
        ticket = self.env['helpdesk.ticket'].create(vals)

        # Verify classification
        self.assertTrue(ticket.rug_repair)
        self.assertTrue(ticket.rug_confirmed)

        # Step 2: Create repair route (simulate by creating picking directly)
        self._create_picking_for_ticket(ticket)
        ticket.invalidate_recordset()
        self.assertGreater(ticket.picking_count, 0)

        # Step 3 & 4: Centre movement
        ticket.action_send_to_centre()
        self.assertTrue(ticket.send_to_centre)
        self.assertEqual(ticket.s_shipped_by, self.env.user)

        ticket.action_receive_at_centre()
        self.assertTrue(ticket.receive_at_centre)
        self.assertEqual(ticket.s_received_by, self.env.user)

        # Step 5: RUG approval request
        ticket.action_send_rug_request()
        self.assertTrue(ticket.rug_request_sent)
        self.assertEqual(ticket.rug_approval_status, 'pending')

        # Step 6: Approve
        ticket.action_approve_rug()
        self.assertTrue(ticket.rug_approved)
        self.assertEqual(ticket.rug_approval_status, 'approved')

        # Step 7 & 8: Factory movement (should succeed after approval)
        ticket.action_send_to_factory()
        self.assertTrue(ticket.send_to_factory)

        ticket.action_receive_at_factory()
        self.assertTrue(ticket.receive_at_factory)
        self.assertEqual(ticket.f_received_by, self.env.user)

        # Final state verification
        self.assertTrue(ticket.rug_approved)
        self.assertTrue(ticket.rug_confirmed)  # from type, not from approval
        self.assertTrue(ticket.receive_at_factory)


class TestRepairWorkflowA2_ExternalNotRUG(TransactionCase):
    """Full lifecycle test for Under Warranty - External not RUG (no approval required)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.type_uw_external = cls.env['helpdesk.ticket.type'].create({
            'name': 'Integration Test - UW External',
            'is_rug': True,
            'is_rug_confirmed': False,
        })
        cls.partner = cls.env.ref('base.res_partner_1')
        cls.team = cls.env['helpdesk.team'].search([], limit=1)
        cls.repair_location = cls.env['stock.location'].search(
            [('usage', '=', 'internal')], limit=1
        )
        cls.picking_type = cls.env['stock.picking.type'].search(
            [('code', '=', 'incoming')], limit=1
        )

    def test_full_external_not_rug_workflow(self):
        """External not RUG reaches factory without any approval step."""
        vals = {
            'name': 'Integration External RUG Test',
            'partner_id': self.partner.id,
            'ticket_type_id': self.type_uw_external.id,
        }
        if self.team:
            vals['team_id'] = self.team.id
        ticket = self.env['helpdesk.ticket'].create(vals)

        # Verify External not RUG classification
        self.assertTrue(ticket.rug_repair)
        self.assertFalse(ticket.rug_confirmed)

        # Create picking
        if self.picking_type and self.repair_location:
            self.env['stock.picking'].create({
                'picking_type_id': self.picking_type.id,
                'location_id': self.env.ref('stock.stock_location_customers').id,
                'location_dest_id': self.repair_location.id,
                'helpdesk_ticket_id': ticket.id,
            })

        # Centre movement
        ticket.action_send_to_centre()
        ticket.action_receive_at_centre()

        # Factory — direct, NO approval step required
        ticket.action_send_to_factory()  # Must NOT raise UserError
        self.assertTrue(ticket.send_to_factory)

        ticket.action_receive_at_factory()
        self.assertTrue(ticket.receive_at_factory)

        # Final state: rug_approved was never called, but workflow completed
        self.assertFalse(ticket.rug_approved)
        self.assertFalse(ticket.rug_confirmed)
        self.assertTrue(ticket.receive_at_factory)


class TestRepairWorkflowC_Serial(TransactionCase):
    """Full lifecycle test for Not Under Warranty With Serial Number."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.type_serial = cls.env['helpdesk.ticket.type'].create({
            'name': 'Integration Test - Serial',
            'is_with_serial_no': True,
        })
        cls.partner = cls.env.ref('base.res_partner_1')
        cls.team = cls.env['helpdesk.team'].search([], limit=1)

    def test_full_serial_workflow(self):
        vals = {
            'name': 'REP/TEST/00001',
            'partner_id': self.partner.id,
            'ticket_type_id': self.type_serial.id,
        }
        if self.team:
            vals['team_id'] = self.team.id
        ticket = self.env['helpdesk.ticket'].create(vals)

        self.assertTrue(ticket.normal_repair_with_serial_no)
        self.assertFalse(ticket.rug_repair)

        # Create serial number
        ticket.action_create_serial_number()
        self.assertTrue(ticket.repair_serial_created)
        self.assertTrue(ticket.sn_updated)
        self.assertTrue(ticket.repair_serial_no)

        lot = self.env['stock.lot'].browse(ticket.repair_serial_no.id)
        self.assertTrue(lot.exists())
        self.assertEqual(lot.name, ticket.name)


class TestRepairWorkflowD_NoSerial(TransactionCase):
    """Full lifecycle test for Not Under Warranty Without Serial Number."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.type_no_serial = cls.env['helpdesk.ticket.type'].create({
            'name': 'Integration Test - No Serial',
            'is_without_serial_no': True,
        })
        cls.partner = cls.env.ref('base.res_partner_1')
        cls.team = cls.env['helpdesk.team'].search([], limit=1)

    def test_no_serial_workflow(self):
        vals = {
            'name': 'REP/TEST/00002',
            'partner_id': self.partner.id,
            'ticket_type_id': self.type_no_serial.id,
        }
        if self.team:
            vals['team_id'] = self.team.id
        ticket = self.env['helpdesk.ticket'].create(vals)

        self.assertTrue(ticket.normal_repair_without_serial_no)
        self.assertFalse(ticket.normal_repair_with_serial_no)
        self.assertFalse(ticket.rug_repair)

        # Serial creation must be blocked
        with self.assertRaises(UserError):
            ticket.action_create_serial_number()


class TestMultiCompanyStage(TransactionCase):
    """Tests for multi-company stage scoping via company_id."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.ref('base.main_company')
        cls.team = cls.env['helpdesk.team'].search([], limit=1)

    def test_stage_company_field_set(self):
        """Stage can have a company_id set."""
        stage = self.env['helpdesk.stage'].create({
            'name': 'Test Stage Company A',
            'company_id': self.company_a.id,
        })
        self.assertEqual(stage.company_id, self.company_a)

    def test_stage_no_company_global(self):
        """Stage without company_id is global (visible to all companies)."""
        stage = self.env['helpdesk.stage'].create({
            'name': 'Test Global Stage',
        })
        self.assertFalse(stage.company_id)
