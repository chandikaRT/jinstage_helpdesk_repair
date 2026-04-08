from odoo import fields, models


class JinstageRepairResolution(models.Model):
    _name = 'jinstage.repair.resolution'
    _description = 'Repair Resolution'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Resolution code must be unique.'),
    ]
