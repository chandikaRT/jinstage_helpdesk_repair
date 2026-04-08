from odoo import fields, models


class JinstageRepairDiagnosisArea(models.Model):
    _name = 'jinstage.repair.diagnosis.area'
    _description = 'Repair Diagnosis Area'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Diagnosis Area code must be unique.'),
    ]
