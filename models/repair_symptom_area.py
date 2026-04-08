from odoo import fields, models


class JinstageRepairSymptomArea(models.Model):
    _name = 'jinstage.repair.symptom.area'
    _description = 'Repair Symptom Area'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Symptom Area code must be unique.'),
    ]
