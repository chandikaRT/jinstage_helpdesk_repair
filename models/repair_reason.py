from odoo import fields, models


class JinstageRepairReason(models.Model):
    _name = 'jinstage.repair.reason'
    _description = 'Repair Reason'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Repair Reason code must be unique.'),
    ]
