from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # --- Repair images taken during the repair process ---
    repair_image_01 = fields.Binary(string='Repair Image 01', attachment=True)
    repair_image_02 = fields.Binary(string='Repair Image 02', attachment=True)

    # --- Warranty documents (accessible on task for technician) ---
    warranty_card = fields.Binary(string='Warranty Card', attachment=True)
    related_information = fields.Binary(string='Related Information', attachment=True)

    # --- Repair diagnosis lines ---
    repair_diagnosis_ids = fields.One2many(
        'jinstage.repair.diagnosis.line', 'task_id', string='Repair Diagnosis'
    )

    # --- Repair status fields ---
    material_availability = fields.Selection([
        ('available', 'Available'),
        ('partial', 'Partially Available'),
        ('unavailable', 'Unavailable'),
        ('ordered', 'Ordered'),
    ], string='Material Availability', compute='_compute_repair_fields', store=False)

    quotation_type = fields.Char(
        string='Quotation Type', compute='_compute_repair_fields', store=False
    )

    @api.depends('helpdesk_ticket_id')
    def _compute_repair_fields(self):
        has_sale_order = 'sale_order_id' in self.env['project.task']._fields
        for task in self:
            ticket = task.helpdesk_ticket_id
            task.material_availability = ticket.material_availability if ticket else False
            so = task.sale_order_id if has_sale_order else False
            if so and hasattr(so, 'quotation_type') and so.quotation_type:
                task.quotation_type = dict(
                    so._fields['quotation_type'].selection
                ).get(so.quotation_type, '')
            else:
                task.quotation_type = ''

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def action_repair_tested_ok(self):
        """Mark the linked helpdesk ticket as Tested OK."""
        self.ensure_one()
        ticket = self.helpdesk_ticket_id
        if not ticket:
            raise UserError(_('No helpdesk ticket linked to this task.'))
        ticket.action_tested_ok()

    def action_view_repair_diagnosis_validation(self):
        """Open the repair diagnosis lines for this task."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Repair Diagnosis'),
            'res_model': 'jinstage.repair.diagnosis.line',
            'view_mode': 'tree,form',
            'domain': [('task_id', '=', self.id)],
            'context': {'default_task_id': self.id},
        }

    def action_view_repair_image_validation(self):
        """Open this task form focused on the Repair Image tab."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Repair Images'),
            'res_model': 'project.task',
            'res_id': self.id,
            'view_mode': 'form',
        }
