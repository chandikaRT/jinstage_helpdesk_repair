from odoo import fields, models


class JinstageRepairReasonCustomer(models.Model):
    _name = 'jinstage.repair.reason.customer'
    _description = 'Repair Customer Reason'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Customer Reason code must be unique.'),
    ]
