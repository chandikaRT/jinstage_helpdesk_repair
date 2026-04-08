from odoo import fields, models


class JinstageRepairDiagnosisCode(models.Model):
    _name = 'jinstage.repair.diagnosis.code'
    _description = 'Repair Diagnosis Code'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
    diagnosis_area_id = fields.Many2one(
        'jinstage.repair.diagnosis.area',
        string='Diagnosis Area',
        ondelete='restrict',
    )

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Diagnosis Code must be unique.'),
    ]
