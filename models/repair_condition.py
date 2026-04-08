from odoo import fields, models


class JinstageRepairCondition(models.Model):
    _name = 'jinstage.repair.condition'
    _description = 'Repair Condition'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Condition code must be unique.'),
    ]
