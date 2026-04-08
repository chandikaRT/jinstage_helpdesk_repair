from odoo import fields, models


class JinstageRepairSubReason(models.Model):
    _name = 'jinstage.repair.sub.reason'
    _description = 'Repair Sub Reason'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
    reason_id = fields.Many2one(
        'jinstage.repair.reason',
        string='Reason',
        ondelete='restrict',
    )

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Sub Reason code must be unique.'),
    ]
