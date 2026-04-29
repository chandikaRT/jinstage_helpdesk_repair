from odoo import api, models

REPAIR_STAGE_XML_IDS = [
    'jinstage_helpdesk_repair.stage_new',
    'jinstage_helpdesk_repair.stage_item_received',
    'jinstage_helpdesk_repair.stage_sent_to_factory',
    'jinstage_helpdesk_repair.stage_received_at_factory',
    'jinstage_helpdesk_repair.stage_repair_started',
    'jinstage_helpdesk_repair.stage_quotation',
    'jinstage_helpdesk_repair.stage_quotation_sent',
    'jinstage_helpdesk_repair.stage_so_confirmed',
    'jinstage_helpdesk_repair.stage_repair_completed',
    'jinstage_helpdesk_repair.stage_sent_to_centre',
    'jinstage_helpdesk_repair.stage_received_at_centre',
    'jinstage_helpdesk_repair.stage_dispatched',
    'jinstage_helpdesk_repair.stage_handed_over',
]


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    @api.model_create_multi
    def create(self, vals_list):
        teams = super().create(vals_list)
        self._add_repair_stages_to_teams(teams)
        return teams

    def _add_repair_stages_to_teams(self, teams):
        """Link all repair stages to the given teams."""
        stages = self._get_repair_stages()
        if stages:
            for team in teams:
                team.write({'stage_ids': [(4, s.id) for s in stages]})

    @api.model
    def _get_repair_stages(self):
        """Return all repair stage records."""
        stages = self.env['helpdesk.stage']
        for xml_id in REPAIR_STAGE_XML_IDS:
            stage = self.env.ref(xml_id, raise_if_not_found=False)
            if stage:
                stages |= stage
        return stages

    @api.model
    def _link_repair_stages_to_all_teams(self):
        """Link all repair stages to every existing team. Called on install and update."""
        stages = self._get_repair_stages()
        if not stages:
            return
        teams = self.search([])
        for team in teams:
            team.write({'stage_ids': [(4, s.id) for s in stages]})
