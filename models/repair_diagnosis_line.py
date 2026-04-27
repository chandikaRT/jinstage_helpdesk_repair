from odoo import fields, models


class RepairDiagnosisLine(models.Model):
    _name = 'jinstage.repair.diagnosis.line'
    _description = 'Repair Diagnosis Line'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    task_id = fields.Many2one('project.task', string='Task', ondelete='cascade', index=True)
    description = fields.Char(string='Description')
    diagnosis_area_id = fields.Many2one('jinstage.repair.diagnosis.area', string='Diagnosis Area')
    diagnosis_code_id = fields.Many2one(
        'jinstage.repair.diagnosis.code', string='Diagnosis Code',
        domain="[('diagnosis_area_id', '=', diagnosis_area_id)]"
    )
    reason_id = fields.Many2one('jinstage.repair.reason', string='Reason')
    sub_reason_id = fields.Many2one(
        'jinstage.repair.sub.reason', string='Sub Reason',
        domain="[('reason_id', '=', reason_id)]"
    )
    resolution_id = fields.Many2one('jinstage.repair.resolution', string='Resolution')
    repair_stage_id = fields.Many2one('helpdesk.stage', string='Repair Stage')
