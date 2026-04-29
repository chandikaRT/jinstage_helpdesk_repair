"""
Post-install / post-update hook: link the seeded repair stages to every
existing helpdesk team so they appear in the ticket statusbar.

In Odoo 17 helpdesk, helpdesk.stage records are only visible to a team's
tickets when the stage is included in team.stage_ids (Many2many).
Stages with no team_ids are invisible regardless of sequence.
"""

REPAIR_STAGE_XML_IDS = [
    'stage_new',
    'stage_item_received',
    'stage_sent_to_factory',
    'stage_received_at_factory',
    'stage_repair_started',
    'stage_quotation',
    'stage_quotation_sent',
    'stage_so_confirmed',
    'stage_repair_completed',
    'stage_sent_to_centre',
    'stage_received_at_centre',
    'stage_dispatched',
    'stage_handed_over',
]


def _get_repair_stages(env):
    stages = env['helpdesk.stage']
    for xml_id in REPAIR_STAGE_XML_IDS:
        stage = env.ref(
            f'jinstage_helpdesk_repair.{xml_id}',
            raise_if_not_found=False,
        )
        if stage:
            stages |= stage
    return stages


def post_init_hook(env):
    """Assign all repair stages to every existing helpdesk team."""
    stages = _get_repair_stages(env)
    if not stages:
        return
    teams = env['helpdesk.team'].search([])
    for team in teams:
        team.write({'stage_ids': [(4, s.id) for s in stages]})


def post_load_hook():
    pass
