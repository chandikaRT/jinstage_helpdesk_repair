from odoo import fields, models


class HelpdeskStage(models.Model):
    _inherit = 'helpdesk.stage'

    company_id = fields.Many2one(
        'res.company', string='Company', tracking=True,
        help='Leave empty for stages visible to all companies.'
    )
